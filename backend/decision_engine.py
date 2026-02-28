"""
Decision Engine — Separate module from Risk Engine (architecture maturity)
Implements:
  - Threshold-based classification
  - Exit-point interception logic
  - Step-up verification triggers
"""

from typing import Dict, Optional
from datetime import datetime


class DecisionEngine:
    """
    Translates risk scores into operational decisions.
    Intentionally decoupled from scoring for clean architecture.
    """

    # Decision thresholds
    ALLOW_THRESHOLD = 40
    MONITOR_THRESHOLD = 70
    STEPUP_THRESHOLD = 85

    # Exit-point channels that trigger re-evaluation
    EXIT_POINT_CHANNELS = {"ATM", "EXTERNAL_TRANSFER", "CRYPTO"}

    def classify(self, risk_result: Dict, current_tx: Dict) -> Dict:
        """
        Primary decision classification.
        Returns decision dict with action, rationale, and metadata.
        """
        score = risk_result["risk_score"]
        cashout = risk_result.get("cashout_detected", False)
        channel = current_tx.get("channel", "")
        amount = current_tx.get("amount", 0)
        is_exit_point = channel in self.EXIT_POINT_CHANNELS

        # Base decision
        if score < self.ALLOW_THRESHOLD:
            action = "ALLOW"
            severity = "INFO"
            message = "Transaction within normal parameters. Proceeding."
            sla_ms = 120

        elif score < self.MONITOR_THRESHOLD:
            action = "MONITOR"
            severity = "WARNING"
            message = "Elevated risk detected. Transaction allowed with enhanced monitoring."
            sla_ms = 250

        elif score < self.STEPUP_THRESHOLD:
            action = "STEP_UP_VERIFICATION"
            severity = "HIGH"
            message = "High risk. Requesting additional authentication before processing."
            sla_ms = 500

        else:
            action = "INTERCEPT"
            severity = "CRITICAL"
            message = "Critical risk score. Transaction blocked pending review."
            sla_ms = 50

        # Exit-point override logic (STEP 7)
        exit_override = None
        if is_exit_point and score >= 60:
            exit_override = self._exit_point_intercept(score, cashout, amount, channel)
            if exit_override["escalated"]:
                action = exit_override["action"]
                severity = "CRITICAL"
                message = exit_override["message"]

        decision = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "transaction_id": current_tx.get("transaction_id", ""),
            "account_id": risk_result.get("account_id", ""),
            "risk_score": score,
            "risk_level": risk_result["risk_level"],
            "action": action,
            "severity": severity,
            "message": message,
            "reasons": risk_result.get("reasons", []),
            "is_exit_point": is_exit_point,
            "exit_override": exit_override,
            "sla_target_ms": sla_ms,
            "requires_analyst_review": action in ("INTERCEPT", "STEP_UP_VERIFICATION"),
        }

        return decision

    def _exit_point_intercept(self, score: float, cashout: bool, 
                               amount: float, channel: str) -> Dict:
        """
        Exit-point interception re-evaluation.
        ATM withdrawals and external transfers are irreversible — apply stricter logic.
        """
        escalated = False
        action = "MONITOR"
        message = ""

        if cashout and score >= 65:
            # High risk + cashout = intercept immediately
            action = "INTERCEPT"
            escalated = True
            message = (
                f"EXIT-POINT INTERCEPT: ATM withdrawal of ₹{amount:,.0f} blocked. "
                "Funds cannot be recovered once dispensed. Flagging for immediate review."
            )
        elif score >= 70 and amount > 50000:
            # High value exit without confirmed cashout
            action = "DELAY_WITHDRAWAL"
            escalated = True
            message = (
                f"EXIT-POINT DELAY: High-value {channel} transaction paused. "
                "Step-up verification required before funds released."
            )
        elif score >= 55:
            # Medium-high at exit point
            action = "STEP_UP_VERIFICATION"
            escalated = True
            message = "Exit-point detected with elevated risk. OTP/biometric verification required."

        return {
            "escalated": escalated,
            "action": action,
            "message": message,
            "channel": channel,
            "amount": amount,
            "irreversibility_flag": True
        }


class NeighborScrutinyEngine:
    """
    Risk Propagation — Phase 6
    Applies temporary scrutiny boost to accounts near flagged entities.
    """
    
    def __init__(self, base_boost: float = 8.0, decay_minutes: int = 60):
        self.scrutiny_map: Dict[str, Dict] = {}  # account → {boost, expires_at}
        self.base_boost = base_boost
        self.decay_minutes = decay_minutes

    def apply_scrutiny(self, flagged_account: str, neighbors: list, 
                        flag_reason: str = "") -> Dict:
        """Mark neighbor accounts for heightened scrutiny."""
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(minutes=self.decay_minutes)
        
        for acc in neighbors:
            existing_boost = self.scrutiny_map.get(acc, {}).get("boost", 0)
            self.scrutiny_map[acc] = {
                "boost": min(25.0, existing_boost + self.base_boost),
                "expires_at": expires_at,
                "reason": f"Neighbor of flagged account {flagged_account}: {flag_reason}",
                "flagged_at": datetime.utcnow().isoformat()
            }
        
        return {"applied_to": neighbors, "boost": self.base_boost, "expires_at": expires_at.isoformat()}

    def get_scrutiny_boost(self, account: str) -> float:
        """Get current scrutiny boost for an account (0 if none or expired)."""
        entry = self.scrutiny_map.get(account)
        if not entry:
            return 0.0
        if datetime.utcnow() > entry["expires_at"]:
            del self.scrutiny_map[account]
            return 0.0
        return entry["boost"]

    def get_scrutiny_reason(self, account: str) -> Optional[str]:
        entry = self.scrutiny_map.get(account)
        if entry and datetime.utcnow() <= entry["expires_at"]:
            return entry.get("reason")
        return None


class AnalystFeedbackSystem:
    """
    Closed-loop feedback — Phase 5
    Analyst confirmations adapt feature weights in the risk engine.
    """
    
    def __init__(self, adaptive_weights, scrutiny_engine: NeighborScrutinyEngine):
        self.weights = adaptive_weights
        self.scrutiny = scrutiny_engine
        self.feedback_log = []

    def confirm_fraud(self, transaction_id: str, account_id: str,
                      contributing_features: list, neighbors: list,
                      analyst_note: str = "") -> Dict:
        """Analyst confirms a fraud case → increase weights, apply neighbor scrutiny."""
        new_weights = self.weights.adjust(contributing_features, "confirmed_fraud", analyst_note)
        scrutiny_result = self.scrutiny.apply_scrutiny(account_id, neighbors, "confirmed_fraud")

        entry = {
            "action": "CONFIRM_FRAUD",
            "transaction_id": transaction_id,
            "account_id": account_id,
            "features_reinforced": contributing_features,
            "new_weights": new_weights,
            "neighbors_flagged": len(neighbors),
            "analyst_note": analyst_note,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.feedback_log.append(entry)
        return entry

    def mark_false_positive(self, transaction_id: str, account_id: str,
                             contributing_features: list, analyst_note: str = "") -> Dict:
        """Analyst marks false positive → reduce weights for those features."""
        new_weights = self.weights.adjust(contributing_features, "false_positive", analyst_note)

        entry = {
            "action": "FALSE_POSITIVE",
            "transaction_id": transaction_id,
            "account_id": account_id,
            "features_reduced": contributing_features,
            "new_weights": new_weights,
            "analyst_note": analyst_note,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.feedback_log.append(entry)
        return entry


if __name__ == "__main__":
    engine = DecisionEngine()
    
    # Test: critical ATM cashout
    risk = {
        "risk_score": 91,
        "risk_level": "CRITICAL",
        "cashout_detected": True,
        "account_id": "MULE_C",
        "reasons": ["ATM cashout detected", "3-hop chain"]
    }
    tx = {"transaction_id": "TXN_TEST", "channel": "ATM", "amount": 85000}
    decision = engine.classify(risk, tx)
    print(f"Decision: {decision['action']}")
    print(f"Message: {decision['message']}")
    print("✓ Decision Engine OK")

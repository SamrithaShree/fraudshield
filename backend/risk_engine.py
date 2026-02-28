"""
Risk Scoring Engine
Converts graph journey features into explainable risk scores.
Weighted sum of normalized feature scores → 0-100 risk score.
"""

from typing import Dict, List, Tuple
from datetime import datetime


class AdaptiveWeights:
    """Manages adaptive feature weights that update via analyst feedback."""
    
    def __init__(self):
        self.weights = {
            "velocity_score": 0.25,
            "hop_score": 0.30,
            "channel_switch_score": 0.15,
            "new_account_penalty": 0.15,
            "cross_border_penalty": 0.10,
            "amount_concentration_score": 0.05,
        }
        self._learning_rate = 0.05
        self.adjustment_log = []

    def adjust(self, contributing_features: List[str], direction: str, analyst_note: str = ""):
        """
        direction: 'confirmed_fraud' → increase weights
                   'false_positive'  → decrease weights
        """
        delta = self._learning_rate if direction == "confirmed_fraud" else -self._learning_rate
        
        for feature in contributing_features:
            if feature in self.weights:
                self.weights[feature] = max(0.01, min(0.5, self.weights[feature] + delta))

        # Normalize so weights sum to 1
        total = sum(self.weights.values())
        self.weights = {k: round(v / total, 4) for k, v in self.weights.items()}

        self.adjustment_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "direction": direction,
            "features": contributing_features,
            "delta": delta,
            "note": analyst_note,
            "weights_after": dict(self.weights)
        })
        return self.weights


class RiskScoringEngine:
    def __init__(self, weights: AdaptiveWeights = None):
        self.weights = weights or AdaptiveWeights()
        self.HIGH_RISK_COUNTRIES = {"AE", "NG", "PK", "IR", "KP", "RU"}
        self.TRUSTED_COUNTRIES = {"IN", "US", "GB", "AU", "SG", "JP"}

    def score_transaction(
        self,
        account_id: str,
        account_age: int,
        country_code: str,
        account_type: str,
        journey_paths: List[Dict],
        window_transactions: List[Dict],
        current_tx: Dict,
        scrutiny_boost: float = 0.0
    ) -> Dict:
        """
        Compute risk score for a transaction/account combo.
        Returns: { risk_score, reasons, feature_scores }
        """
        
        # ── 1. Velocity Score ──────────────────────────────────────
        tx_count = len(window_transactions)
        if tx_count <= 2:
            velocity_raw = 0.0
        elif tx_count <= 5:
            velocity_raw = 0.3
        elif tx_count <= 10:
            velocity_raw = 0.6
        else:
            velocity_raw = 1.0
        
        # Amount velocity
        total_amount_in_window = sum(t["amount"] for t in window_transactions)
        if total_amount_in_window > 100000:
            velocity_raw = min(1.0, velocity_raw + 0.3)

        # ── 2. Hop Score ───────────────────────────────────────────
        max_hops = max((p["hop_count"] for p in journey_paths), default=0)
        time_compressed = any(
            p["total_time_minutes"] < 20 and p["hop_count"] >= 2 
            for p in journey_paths
        )
        
        if max_hops == 0:
            hop_raw = 0.0
        elif max_hops == 1:
            hop_raw = 0.2
        elif max_hops == 2:
            hop_raw = 0.55
        else:
            hop_raw = 0.9
        
        if time_compressed:
            hop_raw = min(1.0, hop_raw + 0.2)

        # ── 3. Channel Switch Score ────────────────────────────────
        max_switches = max((p["channel_switch_count"] for p in journey_paths), default=0)
        cashout_detected = any(p["cashout_flag"] for p in journey_paths)
        
        channel_raw = min(1.0, max_switches * 0.35)
        if cashout_detected:
            channel_raw = min(1.0, channel_raw + 0.4)

        # ── 4. New Account Penalty ─────────────────────────────────
        if account_age < 7:
            new_acc_raw = 1.0
        elif account_age < 30:
            new_acc_raw = 0.85
        elif account_age < 90:
            new_acc_raw = 0.4
        else:
            new_acc_raw = 0.0

        # ── 5. Cross-Border Penalty ────────────────────────────────
        if country_code in self.HIGH_RISK_COUNTRIES:
            cross_raw = 1.0
        elif country_code not in self.TRUSTED_COUNTRIES:
            cross_raw = 0.5
        else:
            cross_raw = 0.0

        # Also check if path crosses borders
        path_countries = set()
        for tx in window_transactions:
            path_countries.add(tx.get("country_code", "IN"))
        if len(path_countries) > 1:
            cross_raw = min(1.0, cross_raw + 0.3)

        # ── 6. Amount Concentration Score ─────────────────────────
        amounts_in_window = [t["amount"] for t in window_transactions]
        if len(amounts_in_window) >= 2:
            max_a = max(amounts_in_window)
            total_a = sum(amounts_in_window)
            concentration = max_a / total_a if total_a > 0 else 0
            amount_conc_raw = concentration * 0.5
        else:
            amount_conc_raw = 0.0

        # ── Weighted Sum ───────────────────────────────────────────
        w = self.weights.weights
        feature_scores = {
            "velocity_score": round(velocity_raw, 3),
            "hop_score": round(hop_raw, 3),
            "channel_switch_score": round(channel_raw, 3),
            "new_account_penalty": round(new_acc_raw, 3),
            "cross_border_penalty": round(cross_raw, 3),
            "amount_concentration_score": round(amount_conc_raw, 3),
        }

        raw_risk = sum(feature_scores[k] * w[k] for k in feature_scores)
        risk_score = min(100, round(raw_risk * 100 + scrutiny_boost, 1))

        # ── Reasons ────────────────────────────────────────────────
        reasons = self._build_reasons(
            feature_scores, max_hops, max_switches, cashout_detected,
            account_age, country_code, tx_count, total_amount_in_window,
            time_compressed, scrutiny_boost
        )

        # Contributing features (for feedback)
        contributing = [k for k, v in feature_scores.items() if v > 0.3]

        return {
            "account_id": account_id,
            "risk_score": risk_score,
            "risk_level": self._classify_level(risk_score),
            "feature_scores": feature_scores,
            "weights_used": dict(w),
            "reasons": reasons,
            "contributing_features": contributing,
            "journey_paths": journey_paths[:3],  # top 3 paths
            "cashout_detected": cashout_detected,
            "window_tx_count": tx_count,
        }

    def _classify_level(self, score: float) -> str:
        if score < 40:
            return "LOW"
        elif score < 70:
            return "MEDIUM"
        elif score < 85:
            return "HIGH"
        else:
            return "CRITICAL"

    def _build_reasons(self, features, max_hops, max_switches, cashout,
                       account_age, country, tx_count, total_amount,
                       time_compressed, scrutiny_boost) -> List[str]:
        reasons = []
        
        if features["velocity_score"] > 0.5:
            reasons.append(f"High transaction velocity: {tx_count} txns / ₹{total_amount:,.0f} in 30-min window")
        if features["hop_score"] > 0.5:
            reasons.append(f"Multi-hop money movement detected ({max_hops} hops)")
        if time_compressed:
            reasons.append("Time-compressed layering: rapid sequential transfers")
        if features["channel_switch_score"] > 0.4:
            reasons.append(f"Channel switching detected ({max_switches} switches) — layering pattern")
        if cashout:
            reasons.append("ATM cashout detected at terminal hop — exit-point risk")
        if features["new_account_penalty"] > 0.5:
            reasons.append(f"Short-lived account: {account_age} days old")
        if features["cross_border_penalty"] > 0.4:
            reasons.append(f"Cross-border risk: source country {country}")
        if scrutiny_boost > 0:
            reasons.append(f"Neighbor scrutiny boost applied (+{scrutiny_boost:.1f} pts): associated with flagged account")
        
        if not reasons:
            reasons.append("Transaction within normal behavioral parameters")

        return reasons


if __name__ == "__main__":
    weights = AdaptiveWeights()
    engine = RiskScoringEngine(weights)
    
    # Test: mule-like scenario
    result = engine.score_transaction(
        account_id="MULE_TEST",
        account_age=8,
        country_code="IN",
        account_type="personal",
        journey_paths=[{
            "hop_count": 3, "total_time_minutes": 13, "channel_switch_count": 2,
            "cashout_flag": True, "unique_senders": 2,
            "amount_sequence": [95000, 92000, 89000],
            "entry_amount": 95000, "exit_amount": 89000,
            "path": ["FRAUD", "MULE_A", "MULE_B", "ATM"]
        }],
        window_transactions=[
            {"amount": 92000, "channel": "Wallet", "country_code": "IN"},
            {"amount": 89000, "channel": "ATM", "country_code": "IN"},
        ],
        current_tx={"amount": 89000, "channel": "ATM"}
    )
    print(f"Risk Score: {result['risk_score']} ({result['risk_level']})")
    print("Reasons:", result["reasons"])
    print("✓ Risk Scoring Engine OK")

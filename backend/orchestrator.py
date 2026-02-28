"""
FraudShield Orchestrator
Main entry point — ties all phases together into a single operational pipeline.

Transaction Event → Temporal Graph Update → Local Subgraph Extraction
→ Feature Computation → Risk Scoring → Decision Engine → Action
→ Analyst Feedback → Adaptive Weight Update
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from backend.graph_engine import TemporalGraphEngine
from backend.risk_engine import RiskScoringEngine, AdaptiveWeights
from backend.decision_engine import DecisionEngine, NeighborScrutinyEngine, AnalystFeedbackSystem


class FraudShieldSystem:
    def __init__(self):
        # Phase 2: Graph Engine
        self.graph_engine = TemporalGraphEngine(window_minutes=30, max_depth=3)
        
        # Phase 3: Risk Engine with adaptive weights
        self.adaptive_weights = AdaptiveWeights()
        self.risk_engine = RiskScoringEngine(self.adaptive_weights)
        
        # Phase 4: Decision Engine
        self.decision_engine = DecisionEngine()
        
        # Phase 6: Neighbor Scrutiny
        self.scrutiny_engine = NeighborScrutinyEngine(base_boost=8.0, decay_minutes=60)
        
        # Phase 5: Feedback System
        self.feedback_system = AnalystFeedbackSystem(self.adaptive_weights, self.scrutiny_engine)
        
        # Audit log
        self.audit_log: List[Dict] = []
        self.account_metadata: Dict[str, Dict] = {}

    def load_dataset(self, filepath: str) -> None:
        """Load synthetic dataset and populate graph."""
        with open(filepath) as f:
            data = json.load(f)
        
        # Store account metadata
        self.account_metadata = data.get("accounts", {})
        
        # Load transactions into graph
        for tx in data["transactions"]:
            self.graph_engine.add_transaction(tx)
        
        print(f"Loaded {len(data['transactions'])} transactions, {len(self.account_metadata)} accounts")
        return data.get("scenario_accounts", {})

    def process_transaction(self, tx: Dict, verbose: bool = False) -> Dict:
        """
        Full pipeline execution for a single transaction.
        Returns complete analysis result.
        """
        account_id = tx["source"]
        reference_time = datetime.fromisoformat(tx["timestamp"].replace("Z", ""))

        # PHASE 2: Update graph
        self.graph_engine.add_transaction(tx)

        # PHASE 2: Extract local subgraph + window transactions
        window_txns = self.graph_engine.get_window_transactions(account_id, reference_time)
        
        # PHASE 2: BFS journey paths (≤3 hops)
        journey_paths = self.graph_engine.bfs_journey_paths(account_id, reference_time)

        # Account metadata
        meta = self.account_metadata.get(account_id, {})
        account_age = meta.get("account_age", tx.get("account_age", 365))
        country_code = meta.get("country_code", tx.get("country_code", "IN"))
        account_type = meta.get("account_type", tx.get("account_type", "personal"))

        # Neighbor scrutiny boost (Phase 6)
        scrutiny_boost = self.scrutiny_engine.get_scrutiny_boost(account_id)
        scrutiny_reason = self.scrutiny_engine.get_scrutiny_reason(account_id)

        # PHASE 3: Risk scoring
        risk_result = self.risk_engine.score_transaction(
            account_id=account_id,
            account_age=account_age,
            country_code=country_code,
            account_type=account_type,
            journey_paths=journey_paths,
            window_transactions=window_txns,
            current_tx=tx,
            scrutiny_boost=scrutiny_boost
        )

        if scrutiny_reason:
            risk_result["reasons"].insert(0, f"⚠ SCRUTINY ACTIVE: {scrutiny_reason}")

        # PHASE 4: Decision
        decision = self.decision_engine.classify(risk_result, tx)

        # PHASE 6: If high risk, propagate to neighbors
        if risk_result["risk_score"] >= 70:
            neighbors = self.graph_engine.get_neighbor_accounts(account_id, hops=1)
            if neighbors:
                self.scrutiny_engine.apply_scrutiny(
                    account_id, neighbors,
                    f"risk_score={risk_result['risk_score']}"
                )

        # Audit
        audit_entry = {
            "processed_at": datetime.utcnow().isoformat(),
            "transaction_id": tx.get("transaction_id"),
            "account_id": account_id,
            "risk_score": risk_result["risk_score"],
            "action": decision["action"],
        }
        self.audit_log.append(audit_entry)

        if verbose:
            self._print_result(tx, risk_result, decision)

        return {
            "transaction": tx,
            "risk_result": risk_result,
            "decision": decision,
            "journey_paths": journey_paths,
            "window_tx_count": len(window_txns),
        }

    def analyst_confirm_fraud(self, transaction_id: str, account_id: str,
                               contributing_features: List[str], note: str = "") -> Dict:
        """Analyst confirms fraud — adapts weights, flags neighbors."""
        neighbors = self.graph_engine.get_neighbor_accounts(account_id, hops=1)
        return self.feedback_system.confirm_fraud(
            transaction_id, account_id, contributing_features, neighbors, note
        )

    def analyst_false_positive(self, transaction_id: str, account_id: str,
                                contributing_features: List[str], note: str = "") -> Dict:
        """Analyst marks false positive — reduces those feature weights."""
        return self.feedback_system.mark_false_positive(
            transaction_id, account_id, contributing_features, note
        )

    def get_account_summary(self, account_id: str) -> Dict:
        """Get account risk summary."""
        meta = self.account_metadata.get(account_id, {})
        neighbors = self.graph_engine.get_neighbor_accounts(account_id, 1)
        scrutiny = self.scrutiny_engine.get_scrutiny_boost(account_id)
        
        # Get recent audit entries
        recent = [e for e in self.audit_log if e["account_id"] == account_id][-5:]
        
        return {
            "account_id": account_id,
            "metadata": meta,
            "neighbors_1hop": neighbors,
            "scrutiny_boost_active": scrutiny > 0,
            "scrutiny_boost_value": scrutiny,
            "recent_decisions": recent,
        }

    def _print_result(self, tx: Dict, risk: Dict, decision: Dict) -> None:
        print("\n" + "="*60)
        print(f"TRANSACTION: {tx.get('transaction_id', 'N/A')}")
        print(f"  {tx['source']} → {tx['destination']}")
        print(f"  ₹{tx['amount']:,.0f} via {tx['channel']}")
        print(f"\nRISK SCORE: {risk['risk_score']} / 100 [{risk['risk_level']}]")
        print(f"DECISION:   {decision['action']} ({decision['severity']})")
        print(f"MESSAGE:    {decision['message']}")
        print("\nREASONS:")
        for r in risk["reasons"]:
            print(f"  • {r}")
        if risk.get("journey_paths"):
            print(f"\nJOURNEY PATHS DETECTED: {len(risk['journey_paths'])}")
            for p in risk["journey_paths"][:2]:
                print(f"  {' → '.join(p['path'])} | {p['hop_count']} hops | {p['total_time_minutes']:.1f} min | Cashout: {p['cashout_flag']}")
        print("="*60)


def run_demo():
    """Run the 3-scenario demo."""
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    
    from backend.data_generator import generate_dataset
    import tempfile, json
    
    # Generate and save dataset
    data = generate_dataset()
    tmpfile = "/tmp/fraud_demo_data.json"
    with open(tmpfile, "w") as f:
        json.dump(data, f)

    system = FraudShieldSystem()
    scenarios = system.load_dataset(tmpfile)

    print("\n" + "🔵"*30)
    print("  FRAUDSHIELD DEMO — 3 SCENARIOS")
    print("🔵"*30)

    # ── Scenario 1: Normal Salary User ─────────────────────────────
    print("\n\n📗 SCENARIO 1: Normal Salary User")
    normal_acc = scenarios["normal_sample"]
    normal_tx = {
        "transaction_id": "TXN_DEMO_S1",
        "source": normal_acc,
        "destination": "UTIL_ELECTRIC",
        "amount": 2500,
        "timestamp": "2024-01-15T14:00:00Z",
        "channel": "UPI",
        "account_type": "personal",
        "account_age": 1200,
        "country_code": "IN"
    }
    system.process_transaction(normal_tx, verbose=True)

    # ── Scenario 2: Business User ──────────────────────────────────
    print("\n\n📘 SCENARIO 2: Business User — Medium Activity")
    biz_tx = {
        "transaction_id": "TXN_DEMO_S2",
        "source": "BIZ_DEMO",
        "destination": "VENDOR_ALPHA",
        "amount": 75000,
        "timestamp": "2024-01-15T11:30:00Z",
        "channel": "NEFT",
        "account_type": "business",
        "account_age": 450,
        "country_code": "IN"
    }
    system.process_transaction(biz_tx, verbose=True)

    # ── Scenario 3: Mule Attack ────────────────────────────────────
    print("\n\n🔴 SCENARIO 3: MULE CHAIN ATTACK INJECTION")
    fraud_src = scenarios["fraud_source"]
    mule_a = scenarios["mule_a"]
    mule_b = scenarios["mule_b"]
    mule_c = scenarios["mule_c"]
    atm_node = scenarios["atm_node"]

    attack_time_base = "2024-01-15T16:00:00"

    txns = [
        {"transaction_id": "TXN_ATK_1", "source": fraud_src, "destination": mule_a,
         "amount": 95000, "timestamp": f"{attack_time_base}:00Z", "channel": "UPI",
         "account_type": "personal", "account_age": 12, "country_code": "AE"},
        {"transaction_id": "TXN_ATK_2", "source": mule_a, "destination": mule_b,
         "amount": 92000, "timestamp": f"{attack_time_base.replace(':00:00', ':04:00')}:00Z", "channel": "Wallet",
         "account_type": "personal", "account_age": 8, "country_code": "IN"},
        {"transaction_id": "TXN_ATK_3", "source": mule_b, "destination": mule_c,
         "amount": 89000, "timestamp": f"{attack_time_base.replace(':00:00', ':09:00')}:00Z", "channel": "UPI",
         "account_type": "personal", "account_age": 15, "country_code": "IN"},
        {"transaction_id": "TXN_ATK_4", "source": mule_c, "destination": atm_node,
         "amount": 85000, "timestamp": f"{attack_time_base.replace(':00:00', ':13:00')}:00Z", "channel": "ATM",
         "account_type": "personal", "account_age": 6, "country_code": "IN"},
    ]

    for t in txns:
        system.process_transaction(t, verbose=True)

    # Analyst feedback
    print("\n\n💬 ANALYST FEEDBACK: Confirming fraud on mule chain")
    result = system.analyst_confirm_fraud(
        "TXN_ATK_4", mule_c,
        ["hop_score", "channel_switch_score", "new_account_penalty"],
        note="Confirmed 3-hop mule chain with ATM exit"
    )
    print(f"Weights updated. New hop_score weight: {result['new_weights']['hop_score']:.4f}")
    print(f"Neighbor accounts flagged for scrutiny: {result['neighbors_flagged']}")

    print("\n\n✅ DEMO COMPLETE")


if __name__ == "__main__":
    run_demo()

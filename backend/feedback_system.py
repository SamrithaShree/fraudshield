"""
PHASE 5 - Closed Loop Feedback System (STEP 8)
Analyst confirms fraud or marks false positive.
System adapts weights slightly. No ML required.
"""
from typing import Dict, List, Optional
from datetime import datetime
import json


FEATURE_MAP = {
    "velocity": "velocity",
    "hop": "hop",
    "channel_switch": "channel_switch",
    "new_account": "new_account",
    "cross_border": "cross_border",
}


class FeedbackRecord:
    def __init__(self, txn_id: str, decision: str, risk_score: float,
                 component_scores: Dict[str, float], analyst_verdict: str,
                 notes: str = ""):
        self.txn_id = txn_id
        self.decision = decision
        self.risk_score = risk_score
        self.component_scores = component_scores
        self.analyst_verdict = analyst_verdict  # "confirmed_fraud" | "false_positive" | "true_negative"
        self.notes = notes
        self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_dict(self):
        return self.__dict__


class AnalystFeedbackSystem:
    """
    Closed-loop operational feedback.
    Bridges analyst decisions back into the risk engine weights.
    Shows learning capability without ML.
    """

    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.feedback_log: List[FeedbackRecord] = []
        self.stats = {
            "confirmed_fraud": 0,
            "false_positive": 0,
            "true_negative": 0,
            "weight_updates": 0
        }

    def submit_feedback(self, txn_id: str, decision: str, risk_score: float,
                        component_scores: Dict[str, float], analyst_verdict: str,
                        notes: str = "") -> Dict:
        """
        Submit analyst verdict.
        - confirmed_fraud: Increase weights of top contributing features
        - false_positive: Decrease weights of top contributing features
        - true_negative: No weight change (correct allow)
        """
        record = FeedbackRecord(txn_id, decision, risk_score,
                                component_scores, analyst_verdict, notes)
        self.feedback_log.append(record)
        self.stats[analyst_verdict] = self.stats.get(analyst_verdict, 0) + 1

        weight_changes = {}

        if analyst_verdict == "confirmed_fraud":
            # Increase weights of features that contributed most
            top_features = self._top_contributors(component_scores, n=3)
            for feature in top_features:
                if feature in FEATURE_MAP:
                    self.risk_engine.weights.adjust(FEATURE_MAP[feature], "increase")
                    weight_changes[feature] = "+0.02"
            self.stats["weight_updates"] += 1

        elif analyst_verdict == "false_positive":
            # Decrease weights of features that over-triggered
            top_features = self._top_contributors(component_scores, n=2)
            for feature in top_features:
                if feature in FEATURE_MAP:
                    self.risk_engine.weights.adjust(FEATURE_MAP[feature], "decrease")
                    weight_changes[feature] = "-0.02"
            self.stats["weight_updates"] += 1

        return {
            "feedback_recorded": True,
            "txn_id": txn_id,
            "verdict": analyst_verdict,
            "weight_changes": weight_changes,
            "new_weights": self.risk_engine.weights.as_dict(),
            "timestamp": record.timestamp
        }

    def _top_contributors(self, component_scores: Dict[str, float], n: int = 3) -> List[str]:
        """Return feature names sorted by their score contribution (descending)."""
        sorted_features = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)
        return [f for f, _ in sorted_features[:n]]

    def get_stats(self) -> Dict:
        return {
            "feedback_stats": self.stats,
            "current_weights": self.risk_engine.weights.as_dict(),
            "total_feedback_submissions": len(self.feedback_log),
            "feedback_log": [r.to_dict() for r in self.feedback_log[-10:]]  # last 10
        }

    def export_log(self, path: str = "feedback_log.json"):
        with open(path, "w") as f:
            json.dump([r.to_dict() for r in self.feedback_log], f, indent=2)
        return path


if __name__ == "__main__":
    from backend.risk_engine import RiskEngine

    re = RiskEngine()
    feedback = AnalystFeedbackSystem(re)

    print("Initial weights:", re.weights.as_dict())

    # Analyst confirms fraud
    result = feedback.submit_feedback(
        txn_id="TXN_MULE001",
        decision="INTERCEPT",
        risk_score=92,
        component_scores={"velocity": 85, "hop": 90, "channel_switch": 80, "new_account": 95, "cross_border": 80},
        analyst_verdict="confirmed_fraud",
        notes="Confirmed mule chain via ATM"
    )
    print("After fraud confirmation:", result["new_weights"])

    # Analyst marks false positive
    result2 = feedback.submit_feedback(
        txn_id="TXN_BIZ001",
        decision="STEP_UP_VERIFICATION",
        risk_score=72,
        component_scores={"velocity": 70, "hop": 30, "channel_switch": 20, "new_account": 0, "cross_border": 0},
        analyst_verdict="false_positive",
        notes="Business user with high but legit activity"
    )
    print("After false positive:", result2["new_weights"])
    print("Stats:", feedback.get_stats()["feedback_stats"])

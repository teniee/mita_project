from app.logic.adaptive_behavior_agent import AdaptiveBehaviorAgent
from app.logic.category_priority import get_priority
from app.logic.cohort_drift_tracker import CohortDriftTracker
from app.services.core.engine.expense_journal import ExpenseJournal


class AdaptiveBehaviorLogic:
    def __init__(self):
        self.agent = AdaptiveBehaviorAgent()
        self.drift = CohortDriftTracker()
        self.journal = ExpenseJournal()

    def evaluate_user(self, user_id: str, cluster_id: int):
        policy = self.agent.get_policy(cluster_id)
        drift_events = self.drift.get_drift(user_id)
        redis_freq = len(self.journal.filter_by_action(user_id, "redistribute"))
        last_action = self.journal.get_last(user_id)

        recommendations = []
        if drift_events:
            recommendations.append("Cohort drift detected — re-onboard user")
        if redis_freq > 3:
            recommendations.append("User is unstable — tighten discretionary budget")
        if (
            last_action
            and last_action["action"] == "edit"
            and last_action["data"]["category"] == "entertainment"
        ):
            if get_priority("entertainment") < 30:
                recommendations.append(
                    "Too many impulse edits — recommend control challenge"
                )

        return {"cluster_policy": policy, "recommendations": recommendations}

from typing import Dict


class AdaptiveBehaviorAgent:
    def __init__(self):
        self.policies = {
            0: {
                "push_frequency": "weekly",
                "challenge_level": "low",
                "budget_tightness": "loose",
            },
            1: {
                "push_frequency": "daily",
                "challenge_level": "high",
                "budget_tightness": "strict",
            },
            2: {
                "push_frequency": "every_3_days",
                "challenge_level": "medium",
                "budget_tightness": "balanced",
            },
            3: {
                "push_frequency": "weekly",
                "challenge_level": "medium",
                "budget_tightness": "moderate",
            },
        }

    def get_policy(self, cluster_id: int) -> Dict:
        return self.policies.get(
            cluster_id,
            {
                "push_frequency": "weekly",
                "challenge_level": "medium",
                "budget_tightness": "moderate",
            },
        )

    def adapt(self, user_id: str, cluster_id: int):
        policy = self.get_policy(cluster_id)
        print(f"User {user_id} → Cluster {cluster_id} → Policy: {policy}")
        return policy

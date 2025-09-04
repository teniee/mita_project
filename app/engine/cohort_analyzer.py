from typing import Dict
from app.services.core.income_classification_service import classify_income, get_tier_string


class CohortAnalyzer:
    def __init__(self):
        self.user_profiles = {}  # user_id -> profile data

    def register_user(self, user_id: str, profile: Dict):
        self.user_profiles[user_id] = profile

    def assign_cohort(self, user_id: str):
        profile = self.user_profiles.get(user_id, {})

        income = profile.get("income", 0)  # Monthly income
        behavior = profile.get("behavior", "neutral")
        categories = profile.get("categories", [])
        region = profile.get("region", "US-CA")
        
        # Use centralized income classification service
        income_tier = classify_income(income, region)
        income_band = get_tier_string(income_tier)

        if behavior in ["frugal", "conservative"]:
            style = "saver"
        elif behavior in ["impulsive", "spender"]:
            style = "spender"
        else:
            style = "neutral"

        challenge_engaged = any(
            cat in ["coffee", "entertainment"] for cat in categories
        )
        tag = "challenge-prone" if challenge_engaged else "core-user"

        cohort = f"{region}-{income_band}-{style}-{tag}"
        return cohort


# Simple helper used by the API
def determine_cohort(profile: Dict) -> str:
    analyzer = CohortAnalyzer()
    analyzer.register_user("temp_user", profile)
    return analyzer.assign_cohort("temp_user")


# Example manual test
if __name__ == "__main__":
    demo = {
        "income": 4500,
        "behavior": "impulsive",
        "categories": ["coffee", "shopping", "rent"],
    }
    print(determine_cohort(demo))

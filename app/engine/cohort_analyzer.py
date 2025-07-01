from typing import Dict

class CohortAnalyzer:
    def __init__(self):
        self.user_profiles = {}  # user_id -> profile data

    def register_user(self, user_id: str, profile: Dict):
        self.user_profiles[user_id] = profile

    def assign_cohort(self, user_id: str):
        profile = self.user_profiles.get(user_id, {})

        income = profile.get("income", 0)
        behavior = profile.get("behavior", "neutral")
        categories = profile.get("categories", [])

        if income >= 7000:
            income_band = "high"
        elif income >= 3000:
            income_band = "mid"
        else:
            income_band = "low"

        if behavior in ["frugal", "conservative"]:
            style = "saver"
        elif behavior in ["impulsive", "spender"]:
            style = "spender"
        else:
            style = "neutral"

        challenge_engaged = any(cat in ["coffee", "entertainment"] for cat in categories)
        tag = "challenge-prone" if challenge_engaged else "core-user"

        region = profile.get("region", "US-CA")
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
        "categories": ["coffee", "shopping", "rent"]
    }
    print(determine_cohort(demo))

from typing import Dict
from app.services.core.income_classification_service import classify_income, get_tier_string


class CohortAnalyzer:
    def assign_cohort(self, profile: Dict) -> str:
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

        return f"{region}-{income_band}-{style}-{tag}"


def determine_cohort(profile: Dict) -> str:
    return CohortAnalyzer().assign_cohort(profile)

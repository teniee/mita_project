from typing import Dict
from app.config.country_profiles_loader import get_profile


class CohortAnalyzer:
    def assign_cohort(self, profile: Dict) -> str:
        income = profile.get("income", 0)  # Monthly income
        behavior = profile.get("behavior", "neutral")
        categories = profile.get("categories", [])
        region = profile.get("region", "US-CA")
        
        # Get state-specific thresholds from country profiles
        country_profile = get_profile(region)
        thresholds = country_profile.get("class_thresholds", {})
        
        # Convert monthly income to annual for threshold comparison
        annual_income = income * 12
        
        # Use 5-tier classification with state-specific thresholds
        if annual_income <= thresholds.get("low", 36000):
            income_band = "low"
        elif annual_income <= thresholds.get("lower_middle", 57600):
            income_band = "lower_middle"
        elif annual_income <= thresholds.get("middle", 86400):
            income_band = "middle"
        elif annual_income <= thresholds.get("upper_middle", 144000):
            income_band = "upper_middle"
        else:
            income_band = "high"

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

from typing import Dict


class CohortAnalyzer:
    def assign_cohort(self, profile: Dict) -> str:
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

        challenge_engaged = any(
            cat in ["coffee", "entertainment"] for cat in categories
        )
        tag = "challenge-prone" if challenge_engaged else "core-user"

        region = profile.get("region", "US-CA")
        return f"{region}-{income_band}-{style}-{tag}"


def determine_cohort(profile: Dict) -> str:
    return CohortAnalyzer().assign_cohort(profile)

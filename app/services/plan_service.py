from datetime import date
from decimal import Decimal
from collections import defaultdict
from app.config.country_profiles import COUNTRY_PROFILES

def generate_monthly_plan(user_profile: dict, year: int, month: int) -> dict:
    """
    Returns per-day planned budget allocation for a given user profile.
    Output format: {day: {category: amount}}
    """

    # Region and income
    region = user_profile.get("region", "US-CA")
    income = user_profile.get("monthly_income", 3000)
    profile = COUNTRY_PROFILES.get(region, {})
    class_thresholds = profile.get("class_thresholds", {})
    split_profiles = profile.get("split_profiles", {})

    # Determine class
    user_class = "low"
    for k, v in class_thresholds.items():
        if income <= v:
            user_class = k
            break

    class_split = split_profiles.get(user_class, {})
    if not class_split:
        raise ValueError(f"No budget split config for class: {user_class}")

    # Days in month
    days_in_month = (date(year + (month // 12), ((month % 12) + 1), 1) - date(year, month, 1)).days

    # Daily allocation
    calendar_plan = defaultdict(dict)
    for cat, share in class_split.items():
        per_day = (Decimal(str(income)) * Decimal(str(share))) / days_in_month
        for d in range(1, days_in_month + 1):
            calendar_plan[d][cat] = round(float(per_day), 2)

    return dict(calendar_plan)
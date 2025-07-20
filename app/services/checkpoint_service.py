from statistics import mean
from typing import Any, Dict


def calculate_checkpoint(
    user_profile: Dict[str, Any], transaction_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate a financial checkpoint for the user.

    :param user_profile: dict with user attributes (age, income, etc.)
    :param transaction_data: dict of transactions per category: {"food": [10, 20, 30], ...}
    :return: dict with calculation results
    """

    # 1. Sum per category
    category_totals = {
        category: sum(values)
        for category, values in transaction_data.items()
        if isinstance(values, list) and all(isinstance(v, (int, float)) for v in values)
    }

    # 2. Total amount spent
    total_spent = sum(category_totals.values())

    # 3. Average spend per category
    category_averages = {
        category: round(mean(values), 2)
        for category, values in transaction_data.items()
        if isinstance(values, list) and values
    }

    # 4. Basic behavior assessment
    behavior_score = assess_behavior(user_profile, category_totals)

    # 5. Final response
    return {
        "user_profile": user_profile,
        "total_spent": round(total_spent, 2),
        "category_totals": category_totals,
        "category_averages": category_averages,
        "behavior_score": behavior_score,
        "checkpoint_status": "generated",
    }


def assess_behavior(
    user_profile: Dict[str, Any], category_totals: Dict[str, float]
) -> str:
    """Simple behavior analysis.

    If spending on ``entertainment`` exceeds 30% of total, or ``dining out`` is
    more than 25%, the user is flagged as overspending.
    Returns ``'balanced'`` or ``'overspending'``.
    """
    total = sum(category_totals.values())
    if not total:
        return "no_activity"

    entertainment = category_totals.get("entertainment", 0)
    dining = category_totals.get("dining out", 0)

    if entertainment / total > 0.3 or dining / total > 0.25:
        return "overspending"

    return "balanced"

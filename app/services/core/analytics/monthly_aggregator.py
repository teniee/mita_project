from typing import Dict, List


def aggregate_monthly_data(calendar: List[Dict], month: str) -> Dict[str, float]:
    """
    Aggregates actual spent and planned per category for the given month (e.g. "2025-04").
    Returns totals and savings per category.
    """
    result = {}

    for day in calendar:
        if not day.get("date", "").startswith(month):
            continue
        planned = day.get("planned_budget", {})
        spent = day.get("actual_spent", {})
        for category, amount in planned.items():
            if category not in result:
                result[category] = {"planned": 0.0, "spent": 0.0}
            result[category]["planned"] += amount
            result[category]["spent"] += spent.get(category, 0.0)

    for category in result:
        planned = result[category]["planned"]
        spent = result[category]["spent"]
        result[category]["savings"] = round(max(planned - spent, 0.0), 2)

    return {k: {k2: round(v2, 2) for k2, v2 in v.items()} for k, v in result.items()}

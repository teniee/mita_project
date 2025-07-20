from typing import Dict


def suggest_budget_adjustments(
    calendar: Dict[str, Dict], income: float
) -> Dict[str, str]:
    """
    Suggests how to adjust user's budget.
    Returns dict: category -> suggestion
    """
    suggestions = {}
    for date, day in calendar.items():
        actual = day.get("actual_spending", {})
        planned = day.get("planned_budget", {})

        for cat, planned_amt in planned.items():
            spent = actual.get(cat, 0.0)
            if spent > planned_amt * 1.25:
                suggestions[cat] = "Consider reducing this category"
            elif spent < planned_amt * 0.5:
                suggestions[cat] = "You may be able to save more here"

    return suggestions

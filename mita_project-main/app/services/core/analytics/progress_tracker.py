from datetime import datetime
from typing import Any, Dict, List, Tuple


def calculate_monthly_savings_progress(
    current_month: List[Dict], previous_month: List[Dict]
) -> Dict[str, Any]:
    """
    Compares current and previous month savings.
    Returns % improvement or decline, and absolute difference.
    """

    def get_total_saved(month: List[Dict]) -> float:
        total_saved = 0.0
        for day in month:
            planned = day.get("planned_budget") or day.get("planned", {})
            spent = day.get("actual_spent") or day.get("actual", {})
            for cat, planned_amt in planned.items():
                actual_amt = spent.get(cat, 0.0)
                diff = round(planned_amt - actual_amt, 2)
                total_saved += max(diff, 0.0)
        return round(total_saved, 2)

    current_saved = get_total_saved(current_month)
    previous_saved = get_total_saved(previous_month)

    change = current_saved - previous_saved
    percent_change = (change / previous_saved * 100.0) if previous_saved > 0 else 0.0

    return {
        "current_saved": current_saved,
        "previous_saved": previous_saved,
        "difference": round(change, 2),
        "percent_change": round(percent_change, 1),
        "status": "improved" if change > 0 else "declined" if change < 0 else "same",
    }

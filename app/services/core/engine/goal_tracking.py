from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional


def calculate_goal_progress(goal: Dict, calendar: Dict[int, Dict]) -> Dict:
    """
    Calculate current savings progress toward a financial goal.

    Parameters
    ----------
    goal : dict
        {
            "name": "Vacation",
            "target_amount": 1000,
            "start_date": "2025-05-01",
            "end_date": "2025-08-01"
        }
    calendar : dict[int, dict]
        {
            1: {"savings": 15.0, ...},
            2: {"savings": 10.5, ...},
            ...
        }

    Returns
    -------
    dict
        {
            "goal_name": "Vacation",
            "target_amount": 1000,
            "saved": 120.5,
            "percent_complete": 12.05,
            "status": "in_progress"  # or "completed"
        }
    """
    saved_total = sum(day.get("savings", 0.0) for day in calendar.values())
    percent = min(round((saved_total / goal["target_amount"]) * 100, 2), 100.0)

    return {
        "goal_name": goal["name"],
        "target_amount": goal["target_amount"],
        "saved": round(saved_total, 2),
        "percent_complete": percent,
        "status": "completed" if percent >= 100.0 else "in_progress",
    }


def estimate_completion_date(goal: Dict, calendar: Dict[int, Dict]) -> Optional[str]:
    """
    Estimate the date (YYYY‑MM‑DD) when the user will reach the target amount,
    based on the current average daily savings.

    Returns None if prediction is impossible (no data or zero/negative average).
    """
    saved_total = sum(day.get("savings", 0.0) for day in calendar.values())
    days_tracked = sum(1 for day in calendar.values() if "savings" in day)

    if days_tracked == 0 or saved_total == 0:
        return None

    daily_avg = saved_total / days_tracked
    remaining = goal["target_amount"] - saved_total
    if daily_avg <= 0 or remaining <= 0:
        return None

    est_days = int(remaining / daily_avg)
    est_completion = datetime.today().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=est_days)
    return est_completion.strftime("%Y-%m-%d")

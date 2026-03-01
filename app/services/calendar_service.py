"""In-memory calendar service used during development.

These helper functions are sufficient for the backend to start and for
the Swagger endpoints to return valid responses. There is no persistent
storage here—the data is generated on the fly. In production these
functions should access the ``DailyPlan`` table or a Redis cache.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Union

###############################################################################
#                           HELPER UTILITIES
###############################################################################


def _date_range(start: date, num_days: int) -> List[date]:
    """Generate a list of dates starting from ``start`` (inclusive)."""
    return [start + timedelta(days=i) for i in range(num_days)]


def _iso(d: date) -> str:
    return d.isoformat()


###############################################################################
#                        MAIN API (used in routes)
###############################################################################

# ------------------------------------------------------------------ generate_calendar


def generate_calendar(
    calendar_id: str,
    start_date: date,
    num_days: int,
    budget_plan: Dict[str, Union[float, int]],
) -> List[Dict[str, Any]]:
    """Build a calendar with a planned budget for each day.

    ``budget_plan`` contains monthly sums per category.
    The daily limit is ``sum(categories) / num_days``.

    Returns a list of dictionaries like::

        {
            "date": "2025-05-01",
            "planned_budget": {"groceries": 10.0, ...},
            "limit": 30.0,
            "total": 0.0,
        }
    """
    days = _date_range(start_date, num_days)
    per_day_budget = {
        cat: round(Decimal(str(total)) / Decimal(num_days), 2)
        for cat, total in budget_plan.items()
    }
    day_limit = round(sum(per_day_budget.values()), 2)

    return [
        {
            "calendar_id": calendar_id,
            "date": _iso(d),
            "planned_budget": per_day_budget,
            "limit": day_limit,
            "total": Decimal("0.0"),
        }
        for d in days
    ]


# ------------------------------------------------------------------ fetch_calendar


def fetch_calendar(user_id: str, year: int, month: int) -> Dict[int, Dict[str, Any]]:
    """Return a simplified month calendar for the user."""
    first_day = date(year, month, 1)
    num_days = (date(year + month // 12, month % 12 + 1, 1) - first_day).days
    return {
        day: {
            "date": _iso(first_day + timedelta(days=day - 1)),
            "total": Decimal("0.0"),
            "limit": Decimal("0.0"),
            "status": "free",
        }
        for day in range(1, num_days + 1)
    }


# ------------------------------------------------------------------ update_day


def update_day(
    calendar: Dict[int, Dict[str, Any]], day: int, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update the day entry in the given calendar and return it."""
    if day not in calendar:
        raise KeyError("day not in calendar")

    calendar[day].update(updates)
    return calendar[day]


# ------------------------------------------------------------------ fetch_day_state


def fetch_day_state(user_id: str, year: int, month: int, day: int) -> Dict[str, Any]:
    """Return a placeholder day state with a static task list."""
    return {
        "user_id": user_id,
        "date": f"{year}-{month:02d}-{day:02d}",
        "status": "planned",
        "tasks": ["Review budget", "Log expenses"],
    }


# ------------------------------------------------------------------ generate_shell_calendar


def generate_shell_calendar(
    user_id: str, payload: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Used during onboarding to build a shell calendar so that the frontend can
    show an example budget without persisting it.

    ``payload`` expects keys:
        start_date: str (ISO ``YYYY-MM-DD``)
        num_days:   int
        budget_plan: dict[cat, amount]
    """
    start_date = date.fromisoformat(payload["start_date"])
    num_days = int(payload["num_days"])
    budget_plan = payload["budget_plan"]

    # Just reuse ``generate_calendar`` (calendar_id is not needed)
    return generate_calendar("__shell__", start_date, num_days, budget_plan)

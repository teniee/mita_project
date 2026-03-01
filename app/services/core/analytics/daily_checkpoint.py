from typing import Dict, List, Union


def get_today_budget(
    calendar: Union[Dict[int, Dict], List[Dict]], today_date: str
) -> Dict[str, float]:
    """
    Returns remaining budget for each category on today's calendar entry.
    Supports both indexed dicts and date-keyed list formats.
    """

    # Convert 'YYYY-MM-DD' to day number if needed
    try:
        day_key = int(today_date.split("-")[-1])
    except Exception:
        return {"error": "Invalid date format"}

    # Handle dict[int -> day] format
    if isinstance(calendar, dict) and isinstance(next(iter(calendar)), int):
        day_data = calendar.get(day_key)
    # Handle list of days with date keys
    elif isinstance(calendar, list):
        day_data = next((d for d in calendar if d.get("date") == today_date), None)
    else:
        return {"error": "Unsupported calendar format"}

    if not day_data:
        return {"error": "today_date not found in calendar"}

    planned = day_data.get("planned_budget", {}) or day_data.get("planned", {})
    spent = day_data.get("actual_spent", {}) or day_data.get("actual", {})

    remaining = {
        category: round(planned.get(category, 0.0) - spent.get(category, 0.0), 2)
        for category in planned
    }

    return {"date": today_date, "remaining_budget": remaining}

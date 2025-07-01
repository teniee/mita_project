def check_spending(calendar: list, day: int, category: str) -> float:
    """Return amount spent on a given day for a category."""
    for item in calendar:
        if item.get("day") == day and item.get("category") == category:
            return float(item.get("spent", 0.0))
    return 0.0

def check_limit(calendar: list, day: int, category: str) -> float:
    """Return remaining budget for a category on a given day."""
    for item in calendar:
        if item.get("day") == day and item.get("category") == category:
            planned = float(item.get("planned", 0.0))
            spent = float(item.get("spent", 0.0))
            return planned - spent
    return 0.0

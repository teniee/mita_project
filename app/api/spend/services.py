def check_spending(calendar: list, day: int, category: str) -> float:
    """Возвращает потраченную сумму в выбранный день по категории."""
    for item in calendar:
        if item.get("day") == day and item.get("category") == category:
            return float(item.get("spent", 0.0))
    return 0.0

def check_limit(calendar: list, day: int, category: str) -> float:
    """Возвращает остаток бюджета по категории на выбранный день."""
    for item in calendar:
        if item.get("day") == day and item.get("category") == category:
            planned = float(item.get("planned", 0.0))
            spent = float(item.get("spent", 0.0))
            return planned - spent
    return 0.0

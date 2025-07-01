
from app.engine.daily_checkpoint import get_today_checkpoint

def calculate_checkpoint(calendar: list, income: float, day: int) -> float:
    return get_today_checkpoint(calendar, income, day)

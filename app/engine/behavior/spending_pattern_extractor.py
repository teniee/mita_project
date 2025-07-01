# Extract behavioral spending flags from calendar

from datetime import date

from app.engine.calendar_store import get_calendar_for_user


def extract_patterns(user_id: str, year: int, month: int) -> dict:
    cal = get_calendar_for_user(user_id, year, month)
    patterns = set()

    weekend_spikes = 0
    food_dominance = 0
    emotional_spike = False

    for day_str, data in cal.items():
        # fmt: off
        categories = [
            k
            for k in data.keys()
            if k not in ["planned", "redistributed"]
        ]
        # fmt: on
        total = sum(data.get(k, 0) for k in categories)

        if "food" in categories and data.get("food", 0) > 0.5 * total:
            food_dominance += 1

        if "shopping" in categories and data.get("shopping", 0) > 100:
            emotional_spike = True

        d = date.fromisoformat(day_str)
        if d.weekday() >= 5:
            weekend_spikes += 1

    if weekend_spikes >= 3:
        patterns.add("weekend_spender")
    if food_dominance >= 5:
        patterns.add("food_dominated")
    if emotional_spike:
        patterns.add("emotional_spending")

    return {"patterns": list(patterns)}

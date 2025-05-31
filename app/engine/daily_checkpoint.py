from datetime import date
from typing import Dict


def get_today_checkpoint(user_id: str, calendar: Dict[str, Dict]) -> Dict:
    """
    Возвращает информацию о текущем дне в календаре.
    Ключи календаря должны быть в формате 'YYYY-MM-DD'.
    """
    today = date.today().isoformat()

    if today not in calendar:
        return {"error": "today not found in calendar"}

    today_data = calendar[today]

    return {
        "date": today,
        "planned": today_data.get("planned", {}),
        "actual": today_data.get("actual", {}),
        "total": today_data.get("total", 0),
        "status": today_data.get("status", {})
    }

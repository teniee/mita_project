from datetime import date

def get_today_checkpoint(user_id: str, calendar: dict) -> dict:
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

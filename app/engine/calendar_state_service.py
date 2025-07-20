from datetime import date

from app.core.logger import get_logger
from app.engine.calendar_store import get_calendar_for_user
from app.services.core.engine.calendar_ai_advisor import explain_day_status

logger = get_logger("calendar_state_service")


def get_calendar_day_state(user_id: str, year: int, month: int, day: int):
    cal = get_calendar_for_user(user_id, year, month)
    if not cal:
        logger.warning(f"[user={user_id}] Calendar not found for {year}-{month}")
        return {"error": "calendar not found"}

    day_str = f"{year:04d}-{month:02d}-{day:02d}"
    matched = [d for d in cal if d.get("date") == day_str]
    if not matched:
        logger.warning(f"[user={user_id}] Day {day_str} not found in calendar")
        return {"error": "day not found"}

    day_data = matched[0]
    status = day_data.get("status", "unknown")
    recommendations = day_data.get("recommendations", [])
    explanation = None

    if status in ["yellow", "red"]:
        try:
            from app.core.session import SessionLocal

            with SessionLocal() as db:
                explanation = explain_day_status(
                    status=status,
                    recommendations=recommendations,
                    db=db,
                    user_id=user_id,
                    date=day_str,
                )
        except Exception as e:
            logger.error(
                f"[user={user_id}] Failed to get AI advice for {day_str}: {str(e)}"
            )
            explanation = "AI comment temporarily unavailable."

    return {
        "planned": day_data.get("planned_budget", {}),
        "actual": day_data.get("actual_spending", {}),
        "redistributed": day_data.get("redistributed", {}),
        "status": status,
        "recommendations": recommendations,
        "advisor_comment": explanation,
    }

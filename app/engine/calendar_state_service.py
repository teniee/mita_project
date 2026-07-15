from datetime import date

from app.core.date_utils import day_to_range
from app.core.logger import get_logger
from app.services.core.engine.calendar_ai_advisor import explain_day_status

logger = get_logger("calendar_state_service")


def _day_status(planned_total: float, spent_total: float) -> str:
    """Traffic-light status from the day's totals (advisor contract)."""
    if planned_total > 0 and spent_total > planned_total:
        return "red"
    if planned_total > 0 and spent_total > planned_total * 0.85:
        return "yellow"
    return "green"


def get_calendar_day_state(user_id: str, year: int, month: int, day: int):
    """Planned/actual/status breakdown for one calendar day.

    Reads the user's DailyPlan rows directly. The previous implementation
    iterated get_calendar_for_user()'s {date: {category: planned}} dict as
    if it were a list of shell-calendar day maps — `d.get("date")` on the
    string keys raised AttributeError on every call with saved data, and
    none of the shell fields (status/actual_spending/recommendations) exist
    in that shape anyway.
    """
    from app.core.session import create_sync_session
    from app.db.models.daily_plan import DailyPlan

    day_str = f"{year:04d}-{month:02d}-{day:02d}"

    db = create_sync_session()
    try:
        month_start = date(year, month, 1)
        month_end = (
            date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        )
        month_rows_exist = (
            db.query(DailyPlan.id)
            .filter(
                DailyPlan.user_id == user_id,
                DailyPlan.date >= month_start,
                DailyPlan.date < month_end,
            )
            .first()
            is not None
        )
        if not month_rows_exist:
            logger.warning(f"[user={user_id}] Calendar not found for {year}-{month}")
            return {"error": "calendar not found"}

        day_start, day_end = day_to_range(date(year, month, day))
        rows = (
            db.query(DailyPlan)
            .filter(
                DailyPlan.user_id == user_id,
                DailyPlan.date >= day_start,
                DailyPlan.date <= day_end,
            )
            .all()
        )
        if not rows:
            logger.warning(f"[user={user_id}] Day {day_str} not found in calendar")
            return {"error": "day not found"}

        planned = {
            row.category: float(row.planned_amount or 0) for row in rows
        }
        actual = {row.category: float(row.spent_amount or 0) for row in rows}
        status = _day_status(sum(planned.values()), sum(actual.values()))
        recommendations: list = []

        explanation = None
        if status in ["yellow", "red"]:
            try:
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
            "planned": planned,
            "actual": actual,
            "redistributed": {},
            "status": status,
            "recommendations": recommendations,
            "advisor_comment": explanation,
        }
    finally:
        db.close()

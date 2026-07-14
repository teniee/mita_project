# isort: off
from app.engine.analytics_engine import AnalyticsEngine
from app.engine.progress_logic import get_progress_data

# isort: on


def compute_goal_progress(goal_data: dict) -> dict:
    saved = goal_data["saved"]
    goal = goal_data["goal"]
    if saved >= goal:
        try:
            analytics = AnalyticsEngine()
            analytics.log_behavior(
                user_id=goal_data["user_id"],
                region=goal_data["region"],
                cohort=goal_data["cohort"],
                behavior_tag=goal_data["behavior"],
                challenge_success=False,
                goal_completed=True,
            )
        except Exception as e:
            from app.core.logging_config import get_logger

            logger = get_logger(__name__)
            logger.warning(
                "Analytics error during goal completion", extra={"error": str(e)}
            )
    progress_pct = round(min(saved / goal * 100, 100), 2) if goal > 0 else 0
    return {
        "progress_pct": progress_pct,
        "target": goal,
        "saved": saved,
        "remaining": max(goal - saved, 0),
    }


def compute_calendar_progress(calendar: list, target: float) -> float:
    """Percent progress toward a savings target from calendar-day savings.

    Wired to goal_tracking.calculate_goal_progress (sums day["savings"]
    against the target). The previous alias pointed at
    goal_mode_ui_api.get_goal_progress(state) — a 1-argument function — so
    every call raised TypeError -> 500.
    """
    if not target or target <= 0:
        return 0.0
    from app.services.core.engine.goal_tracking import (
        calculate_goal_progress as _calendar_goal_progress,
    )

    result = _calendar_goal_progress(
        {"name": "goal", "target_amount": target},
        {i: (day or {}) for i, day in enumerate(calendar)},
    )
    return result["percent_complete"]


def get_user_progress(
    user_id: str,
    year: int,
    month: int,
    config: dict,
) -> dict:
    return get_progress_data(
        user_id,
        year,
        month,
        {},
    )

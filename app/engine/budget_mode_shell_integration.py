### budget_mode_shell_integration.py — connects budget mode to shell/calendar UI

from app.engine.budget_mode_selector import resolve_budget_mode
from app.engine.calendar_engine_behavioral import build_calendar


def get_shell_calendar(user_id: str, user_settings: dict) -> dict:
    mode = resolve_budget_mode(user_settings)
    config = {**user_settings, "mode": mode, "user_id": user_id}
    return build_calendar(config)

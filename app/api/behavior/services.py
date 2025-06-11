from app.services.core.behavior.behavioral_budget_allocator import (
    get_behavioral_allocation as generate_behavioral_calendar,
)


def generate_behavior(
    user_id: str,
    year: int,
    month: int,
    profile: dict,
    mood_log: dict,
    challenge_log: dict,
    calendar_log: dict
) -> dict:
    return generate_behavioral_calendar(
        user_id,
        year,
        month,
        profile,
        mood_log,
        challenge_log,
        calendar_log
    )

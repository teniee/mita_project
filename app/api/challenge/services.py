from app.services.core.api.challenge_engine import check_monthly_challenge_eligibility


def check_eligibility(user_id: str, current_month: str):
    return check_monthly_challenge_eligibility(user_id, current_month)


def evaluate_challenge(calendar: list, today_date: str, challenge_log: dict):
    return check_monthly_challenge_eligibility(calendar, today_date, challenge_log)


from app.engine.challenge_engine_auto import auto_run_challenge_streak


def run_streak_challenge(calendar: list, user_id: str, log_data: dict):
    return auto_run_challenge_streak(calendar, user_id, log_data)

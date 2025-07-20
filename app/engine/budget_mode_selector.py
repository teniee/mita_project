### budget_mode_selector.py — determines active budget mode for the user


def resolve_budget_mode(user_settings: dict) -> str:
    if user_settings.get("savings_target"):
        return "goal"
    return "default"

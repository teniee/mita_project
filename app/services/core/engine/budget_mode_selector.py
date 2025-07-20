def resolve_budget_mode(user_settings: dict) -> str:
    """
    Determine user's budget mode based on settings or behavior patterns.
    Modes: 'aggressive', 'balanced', 'default'
    """
    if (
        user_settings.get("aggressive_savings")
        and user_settings.get("income_stability", "") == "high"
    ):
        return "aggressive"

    if user_settings.get("income_stability", "") == "medium" or user_settings.get(
        "has_family"
    ):
        return "balanced"

    return "default"

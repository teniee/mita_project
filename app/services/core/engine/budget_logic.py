from app.config.country_profiles_loader import get_profile
from app.services.core.income_classification_service import classify_income, get_tier_string


def generate_budget_from_answers(answers: dict) -> dict:
    region = answers.get("region", "US")
    profile = get_profile(region)
    behavior = profile.get("default_behavior", "balanced")

    income_data = answers.get("income", {})
    monthly_income = income_data.get("monthly_income", 0)
    additional_income = income_data.get("additional_income", 0)
    income = monthly_income + additional_income

    # Use centralized income classification service
    income_tier = classify_income(income, region)
    user_class = get_tier_string(income_tier)

    fixed = answers.get("fixed_expenses", {})
    fixed_total = sum(fixed.values())

    if fixed_total > income:
        raise ValueError("Fixed expenses exceed income. Cannot generate budget.")

    discretionary = income - fixed_total

    savings_goal = answers.get("goals", {}).get("savings_goal_amount_per_month", 0)
    discretionary -= savings_goal
    if discretionary < 0:
        savings_goal = max(0, savings_goal + discretionary)
        discretionary = 0

    freq = answers.get("spending_habits", {})
    freq_weights = {
        "dining out": freq.get("dining_out_per_month", 0),
        "entertainment events": freq.get("entertainment_per_month", 0),
        "clothing": freq.get("clothing_per_month", 0),
        "travel": freq.get("travel_per_year", 0) / 12,
        "coffee": freq.get("coffee_per_week", 0) * 4,
        "transport": freq.get("transport_per_month", 0),
    }

    total_freq = sum(freq_weights.values())
    if total_freq == 0:
        weights = {k: 1 / len(freq_weights) for k in freq_weights}
    else:
        weights = {k: v / total_freq for k, v in freq_weights.items()}

    return {
        "savings_goal": round(savings_goal, 2),
        "user_class": user_class,
        "behavior": behavior,
        "total_income": round(income, 2),
        "fixed_expenses_total": round(fixed_total, 2),  # Renamed to avoid overwriting dict
        "discretionary_total": round(discretionary, 2),
        "discretionary_breakdown": {
            k: round(discretionary * w, 2) for k, w in weights.items()
        },
    }

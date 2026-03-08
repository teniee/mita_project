from app.config.country_profiles_loader import get_profile
from app.services.core.income_classification_service import classify_income, get_tier_string, get_budget_weights


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

    # ✅ FIX: Use tier-based budget weights from YAML profiles
    # Get economically optimized weights for user's income tier and location
    tier_weights = get_budget_weights(income_tier, region)

    # Map YAML categories to specific spending categories
    # YAML has: housing, food, transport, utilities, healthcare, savings, entertainment, miscellaneous
    # We need: groceries, dining out, transport, entertainment, etc.

    # Calculate base allocations using tier-specific percentages
    base_allocations = {}

    # Food category splits between groceries and dining out
    food_total = tier_weights.get("food", 0.12) * income
    dining_ratio = 0.4  # Default: 40% dining out, 60% groceries
    freq = answers.get("spending_habits", {})
    dining_freq = freq.get("dining_out_per_month", 0)
    if dining_freq > 0:
        # Adjust ratio based on frequency: high frequency = more dining budget
        dining_ratio = min(0.6, 0.3 + (dining_freq / 30))  # Cap at 60%

    base_allocations["groceries"] = food_total * (1 - dining_ratio)
    base_allocations["dining out"] = food_total * dining_ratio

    # Transport category
    transport_total = tier_weights.get("transport", 0.15) * income
    base_allocations["transport public"] = transport_total * 0.7  # 70% public/regular
    base_allocations["transport gas"] = transport_total * 0.3    # 30% gas/car

    # Entertainment
    entertainment_total = tier_weights.get("entertainment", 0.08) * income
    base_allocations["entertainment events"] = entertainment_total

    # Shopping/Clothing
    misc_total = tier_weights.get("miscellaneous", 0.05) * income
    base_allocations["clothing"] = misc_total * 0.6
    base_allocations["hobbies"] = misc_total * 0.4

    # Travel/Vacation (from miscellaneous or entertainment)
    travel_freq = freq.get("travel_per_year", 0)
    if travel_freq > 0:
        # Allocate from entertainment/misc budget
        travel_monthly = min(entertainment_total * 0.3, misc_total * 0.5)
        base_allocations["flights"] = travel_monthly

    # Healthcare (if not in fixed expenses)
    healthcare_total = tier_weights.get("healthcare", 0.06) * income
    base_allocations["insurance medical"] = healthcare_total * 0.6
    base_allocations["out of pocket medical"] = healthcare_total * 0.4

    # Coffee/Daily treats (SPREAD pattern - daily habit)
    coffee_freq = freq.get("coffee_per_week", 0)
    if coffee_freq > 0:
        # Allocate small amount from dining/entertainment
        # Average coffee: $5 per visit, weekly frequency → monthly budget
        coffee_monthly = min(50.0 * coffee_freq, food_total * 0.15)
        base_allocations["coffee"] = coffee_monthly  # FIXED: use "coffee" not "delivery"
        # Reduce dining out accordingly
        base_allocations["dining out"] = max(0, base_allocations["dining out"] - coffee_monthly)

    # Calculate total allocated
    total_allocated = sum(base_allocations.values())

    # Adjust to match discretionary budget (scale if needed)
    if total_allocated > 0 and total_allocated != discretionary:
        scale_factor = discretionary / total_allocated
        base_allocations = {k: v * scale_factor for k, v in base_allocations.items()}

    # Remove zero or negative allocations
    discretionary_breakdown = {
        k: round(v, 2) for k, v in base_allocations.items() if v > 0
    }

    return {
        "savings_goal": round(savings_goal, 2),
        "user_class": user_class,
        "behavior": behavior,
        "total_income": round(income, 2),
        "fixed_expenses_total": round(fixed_total, 2),
        "discretionary_total": round(discretionary, 2),
        "discretionary_breakdown": discretionary_breakdown,
        "income_tier": income_tier.value,  # Include tier for reference
        "tier_weights_used": tier_weights,  # Include original tier weights for debugging
    }

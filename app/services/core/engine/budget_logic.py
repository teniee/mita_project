from decimal import ROUND_HALF_UP, Decimal

from app.config.country_profiles_loader import get_profile
from app.services.core.income_classification_service import (
    IncomeTier,
    classify_income,
    get_budget_weights,
    get_tier_string,
)

_CENT = Decimal("0.01")


def _money(value) -> Decimal:
    """Convert any numeric input to a 2-dp Decimal using financial rounding.

    Money math must not run in binary float: sub-cent inputs broke the
    reconciliation invariant (income == fixed + savings + discretionary to
    the cent) and round() rounds half-to-even ('banker's'), not half-up
    (V2 / INV-6).
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def generate_budget_from_answers(answers: dict) -> dict:
    region = answers.get("region", "US")
    profile = get_profile(region)
    behavior = profile.get("default_behavior", "balanced")

    income_data = answers.get("income") or {}
    monthly_income = _money(income_data.get("monthly_income") or 0)
    additional_income = _money(income_data.get("additional_income") or 0)
    income = monthly_income + additional_income

    # Use centralized income classification service (float interface)
    income_tier = classify_income(float(income), region)
    user_class = get_tier_string(income_tier)

    fixed = answers.get("fixed_expenses") or {}
    fixed_total = sum((_money(v) for v in fixed.values()), Decimal("0.00"))

    if fixed_total > income:
        raise ValueError("Fixed expenses exceed income. Cannot generate budget.")

    discretionary = income - fixed_total

    savings_goal = _money(
        (answers.get("goals") or {}).get("savings_goal_amount_per_month") or 0
    )
    discretionary -= savings_goal
    if discretionary < 0:
        savings_goal = max(Decimal("0.00"), savings_goal + discretionary)
        discretionary = Decimal("0.00")

    # ✅ FIX: Use tier-based budget weights from YAML profiles
    # Get economically optimized weights for user's income tier and location
    tier_weights = get_budget_weights(income_tier, region)

    def weight(name: str, default: float) -> Decimal:
        return Decimal(str(tier_weights.get(name, default)))

    # Map YAML categories to specific spending categories
    # YAML has: housing, food, transport, utilities, healthcare, savings, entertainment, miscellaneous
    # We need: groceries, dining out, transport, entertainment, etc.

    # Calculate base allocations using tier-specific percentages
    base_allocations = {}

    # Food category splits between groceries and dining out
    food_total = weight("food", 0.12) * income
    dining_ratio = Decimal("0.4")  # Default: 40% dining out, 60% groceries
    freq = answers.get("spending_habits") or {}
    dining_freq = freq.get("dining_out_per_month", 0)
    if dining_freq > 0:
        # Adjust ratio based on frequency: high frequency = more dining budget
        dining_ratio = min(
            Decimal("0.6"), Decimal("0.3") + (Decimal(str(dining_freq)) / 30)
        )  # Cap at 60%

    base_allocations["groceries"] = food_total * (1 - dining_ratio)
    base_allocations["dining out"] = food_total * dining_ratio

    # Transport category
    transport_total = weight("transport", 0.15) * income
    base_allocations["transport public"] = transport_total * Decimal(
        "0.7"
    )  # 70% public/regular
    base_allocations["transport gas"] = transport_total * Decimal("0.3")  # 30% gas/car

    # Entertainment
    entertainment_total = weight("entertainment", 0.08) * income
    base_allocations["entertainment events"] = entertainment_total

    # Shopping/Clothing
    misc_total = weight("miscellaneous", 0.05) * income
    base_allocations["clothing"] = misc_total * Decimal("0.6")
    base_allocations["hobbies"] = misc_total * Decimal("0.4")

    # Travel/Vacation (from miscellaneous or entertainment)
    travel_freq = freq.get("travel_per_year", 0)
    if travel_freq > 0:
        # Allocate from entertainment/misc budget
        travel_monthly = min(
            entertainment_total * Decimal("0.3"), misc_total * Decimal("0.5")
        )
        base_allocations["flights"] = travel_monthly

    # Healthcare (if not in fixed expenses)
    healthcare_total = weight("healthcare", 0.06) * income
    base_allocations["insurance medical"] = healthcare_total * Decimal("0.6")
    base_allocations["out of pocket medical"] = healthcare_total * Decimal("0.4")

    # Coffee/Daily treats (SPREAD pattern - daily habit)
    coffee_freq = freq.get("coffee_per_week", 0)
    if coffee_freq > 0:
        # ✅ TIER & LOCATION AWARE: Coffee price varies by income tier and regional cost of living
        # Base coffee prices per tier (per visit, US national average)
        COFFEE_PRICE_BY_TIER = {
            IncomeTier.LOW: Decimal("3.5"),  # Budget coffee (e.g., McDonald's, 7-11)
            IncomeTier.LOWER_MIDDLE: Decimal("4.5"),  # Chain coffee (e.g., Dunkin')
            IncomeTier.MIDDLE: Decimal("5.5"),  # Standard Starbucks latte
            IncomeTier.UPPER_MIDDLE: Decimal("7.0"),  # Premium coffee (specialty)
            IncomeTier.HIGH: Decimal("10.0"),  # Artisan/specialty coffee shops
        }

        # Get base price for user's income tier
        base_coffee_price = COFFEE_PRICE_BY_TIER.get(income_tier, Decimal("5.5"))

        # Adjust for regional cost of living (CA: 1.25x, TX: 0.92x, NY: 1.35x)
        regional_adjustment = Decimal(
            str(profile.get("cost_of_living_adjustment", 1.0))
        )
        coffee_price_per_visit = base_coffee_price * regional_adjustment

        # Calculate monthly budget: (price per visit) × (visits per week) × 4 weeks
        # Cap at 15% of food budget to prevent over-allocation
        coffee_monthly = min(
            coffee_price_per_visit * Decimal(str(coffee_freq)) * 4,
            food_total * Decimal("0.15"),
        )
        base_allocations["coffee"] = coffee_monthly

        # Reduce dining out accordingly
        base_allocations["dining out"] = max(
            Decimal("0.00"), base_allocations["dining out"] - coffee_monthly
        )

    # Calculate total allocated
    total_allocated = sum(base_allocations.values(), Decimal("0.00"))

    # ✅ FIX: Only DOWNSCALE if allocations exceed discretionary
    # Don't UPSCALE when discretionary > allocations (happens when no fixed expenses)
    # This preserves tier-based coffee prices instead of inflating them
    if total_allocated > discretionary and total_allocated > 0:
        # Overspent - scale down proportionally
        scale_factor = discretionary / total_allocated
        base_allocations = {k: v * scale_factor for k, v in base_allocations.items()}
    # If total_allocated < discretionary: leave unallocated (user can spend freely)

    # Remove zero or negative allocations.
    # JSON contract stays numeric (floats of 2-dp values) for the mobile app.
    discretionary_breakdown = {
        k: float(_money(v)) for k, v in base_allocations.items() if v > 0
    }

    return {
        "savings_goal": float(_money(savings_goal)),
        "user_class": user_class,
        "behavior": behavior,
        "total_income": float(_money(income)),
        "fixed_expenses_total": float(_money(fixed_total)),
        "discretionary_total": float(_money(discretionary)),
        "discretionary_breakdown": discretionary_breakdown,
        "income_tier": income_tier.value,  # Include tier for reference
        "tier_weights_used": tier_weights,  # Include original tier weights for debugging
    }

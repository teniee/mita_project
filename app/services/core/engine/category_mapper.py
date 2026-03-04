"""
Category name mapper for MITA.

Maps mobile app category names to backend CATEGORY_BEHAVIOR pattern names.
This ensures budget distribution patterns (FIXED/SPREAD/CLUSTERED) work correctly.
"""
from typing import Dict

# Mobile app → Backend pattern mapping
CATEGORY_NAME_MAPPING: Dict[str, str] = {
    # Housing (mobile) → rent/mortgage (backend FIXED pattern)
    "housing": "rent",
    "rent_or_mortgage": "rent",
    "rent": "rent",
    "mortgage": "mortgage",

    # Food (mobile) → groceries/dining out (backend SPREAD/CLUSTERED)
    "food": "groceries",  # Default food to groceries (SPREAD pattern)
    "groceries": "groceries",
    "dining_out": "dining out",
    "dining out": "dining out",
    "restaurants": "dining out",

    # Transportation (mobile) → transport public/gas (backend SPREAD/CLUSTERED)
    "transportation": "transport public",  # Default to public transport (SPREAD)
    "transport": "transport public",
    "transport_per_month": "transport public",
    "gas": "transport gas",
    "fuel": "transport gas",
    "car": "transport gas",

    # Utilities (mobile) → utilities (backend FIXED) ✓ Already matches
    "utilities": "utilities",

    # Healthcare (mobile) → insurance medical (backend FIXED)
    "healthcare": "insurance medical",
    "health": "insurance medical",
    "medical": "out of pocket medical",
    "insurance": "insurance medical",

    # Entertainment (mobile) → entertainment events (backend CLUSTERED)
    "entertainment": "entertainment events",
    "entertainment_per_month": "entertainment events",
    "fun": "entertainment events",

    # Savings (mobile) → savings emergency/goal based (backend SPREAD)
    "savings": "savings goal based",
    "emergency_fund": "savings emergency",
    "emergency": "savings emergency",

    # Additional common categories
    "subscriptions": "subscriptions software",
    "subscription": "subscriptions software",
    "streaming": "media streaming",
    "netflix": "media streaming",
    "spotify": "media streaming",

    "gym": "gym fitness",
    "fitness": "gym fitness",

    "shopping": "clothing",
    "clothes": "clothing",
    "clothing": "clothing",
    "clothing_per_month": "clothing",

    "travel": "flights",
    "travel_per_year": "flights",
    "vacation": "hotels",

    # Coffee is a daily habit - should be SPREAD pattern, not clustered
    # Kept as separate category for accurate budgeting
    "coffee": "coffee",
    "coffee_per_week": "coffee",

    "loans": "debt repayment",
    "debt": "debt repayment",
    "credit_card": "debt repayment",

    "childcare": "school fees",
    "education": "school fees",
    "childcare_or_education": "school fees",
    "school": "school fees",

    "phone": "subscriptions software",
    "internet": "utilities",
    "electricity": "utilities",
    "water": "utilities",
    "gas_utility": "utilities",
}


def map_category_name(category: str) -> str:
    """
    Map mobile app category name to backend CATEGORY_BEHAVIOR pattern name.

    Args:
        category: Category name from mobile app or user input

    Returns:
        Backend pattern name for CATEGORY_BEHAVIOR lookup

    Examples:
        >>> map_category_name("housing")
        'rent'
        >>> map_category_name("food")
        'groceries'
        >>> map_category_name("entertainment")
        'entertainment events'
    """
    # Normalize: lowercase, strip whitespace
    normalized = category.lower().strip()

    # Direct lookup
    if normalized in CATEGORY_NAME_MAPPING:
        return CATEGORY_NAME_MAPPING[normalized]

    # Fallback: return original (will default to "spread" in distribute_budget_over_days)
    return normalized


def map_budget_categories(budget: Dict[str, float]) -> Dict[str, float]:
    """
    Map all category names in a budget dictionary.

    Args:
        budget: Dict of {category_name: amount}

    Returns:
        Dict with mapped category names {backend_pattern_name: amount}

    Example:
        >>> map_budget_categories({"housing": 1500, "food": 600})
        {'rent': 1500, 'groceries': 600}
    """
    return {
        map_category_name(category): amount
        for category, amount in budget.items()
    }


def get_category_display_name(backend_name: str) -> str:
    """
    Reverse mapping: backend pattern name → user-friendly display name.

    Args:
        backend_name: Backend CATEGORY_BEHAVIOR pattern name

    Returns:
        User-friendly display name

    Examples:
        >>> get_category_display_name("rent")
        'Housing'
        >>> get_category_display_name("groceries")
        'Food'
    """
    # Reverse mapping for display
    DISPLAY_NAMES = {
        "rent": "Housing",
        "mortgage": "Housing",
        "groceries": "Food & Groceries",
        "dining out": "Dining Out",
        "transport public": "Transportation",
        "transport gas": "Gas & Fuel",
        "utilities": "Utilities",
        "insurance medical": "Healthcare",
        "out of pocket medical": "Medical Expenses",
        "entertainment events": "Entertainment",
        "savings goal based": "Savings",
        "savings emergency": "Emergency Fund",
        "subscriptions software": "Subscriptions",
        "media streaming": "Streaming Services",
        "gym fitness": "Gym & Fitness",
        "clothing": "Shopping & Clothing",
        "flights": "Travel",
        "hotels": "Accommodation",
        "debt repayment": "Debt Payments",
        "school fees": "Education",
    }

    return DISPLAY_NAMES.get(backend_name, backend_name.title())

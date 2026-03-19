"""
Category priority registry for budget redistribution.

PHILOSOPHY (from product owner):
- Savings are SACRED — the whole point of MITA.
- MITA is an advisor, not a judge.
- Never take from savings or essentials when rebalancing.
- Take from discretionary (entertainment, dining) first.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Dict


class CategoryLevel(IntEnum):
    SACRED = 0        # Never use as donor. Ever. (savings, rent, etc.)
    PROTECTED = 1     # Last resort only (groceries, transport)
    FLEXIBLE = 2      # Second priority (coffee, clothing)
    DISCRETIONARY = 3 # First priority donor (entertainment, dining)


CATEGORY_PRIORITY: Dict[str, CategoryLevel] = {
    # LEVEL 0 — SACRED
    # goal_savings: rows auto-created by GoalBudgetSyncService (Problem 4).
    # Each row is linked to a specific Goal via DailyPlan.goal_id.
    "goal_savings": CategoryLevel.SACRED,
    "savings_goal": CategoryLevel.SACRED,
    "savings goal based": CategoryLevel.SACRED,
    "savings goal": CategoryLevel.SACRED,
    "savings_emergency": CategoryLevel.SACRED,
    "savings emergency": CategoryLevel.SACRED,
    "investment_contribution": CategoryLevel.SACRED,
    "investment contribution": CategoryLevel.SACRED,
    "rent": CategoryLevel.SACRED,
    "mortgage": CategoryLevel.SACRED,
    "debt_repayment": CategoryLevel.SACRED,
    "debt repayment": CategoryLevel.SACRED,
    "utilities": CategoryLevel.SACRED,
    "insurance_medical": CategoryLevel.SACRED,
    "insurance medical": CategoryLevel.SACRED,
    "school_fees": CategoryLevel.SACRED,
    "school fees": CategoryLevel.SACRED,
    "courses_online": CategoryLevel.SACRED,
    "courses online": CategoryLevel.SACRED,
    # LEVEL 1 — PROTECTED
    "groceries": CategoryLevel.PROTECTED,
    "transport_public": CategoryLevel.PROTECTED,
    "transport public": CategoryLevel.PROTECTED,
    "local_transport": CategoryLevel.PROTECTED,
    "local transport": CategoryLevel.PROTECTED,
    "out_of_pocket_medical": CategoryLevel.PROTECTED,
    "out of pocket medical": CategoryLevel.PROTECTED,
    "home_repairs": CategoryLevel.PROTECTED,
    "home repairs": CategoryLevel.PROTECTED,
    # LEVEL 2 — FLEXIBLE
    "coffee": CategoryLevel.FLEXIBLE,
    "clothing": CategoryLevel.FLEXIBLE,
    "personal_care": CategoryLevel.FLEXIBLE,
    "personal care": CategoryLevel.FLEXIBLE,
    "home_goods": CategoryLevel.FLEXIBLE,
    "home goods": CategoryLevel.FLEXIBLE,
    "car_maintenance": CategoryLevel.FLEXIBLE,
    "car maintenance": CategoryLevel.FLEXIBLE,
    "transport_gas": CategoryLevel.FLEXIBLE,
    "transport gas": CategoryLevel.FLEXIBLE,
    # LEVEL 3 — DISCRETIONARY (take from these first)
    "dining_out": CategoryLevel.DISCRETIONARY,
    "dining out": CategoryLevel.DISCRETIONARY,
    "delivery": CategoryLevel.DISCRETIONARY,
    "entertainment_events": CategoryLevel.DISCRETIONARY,
    "entertainment events": CategoryLevel.DISCRETIONARY,
    "gaming": CategoryLevel.DISCRETIONARY,
    "hobbies": CategoryLevel.DISCRETIONARY,
    "books": CategoryLevel.DISCRETIONARY,
    "tech_gadgets": CategoryLevel.DISCRETIONARY,
    "tech gadgets": CategoryLevel.DISCRETIONARY,
    "media_streaming": CategoryLevel.DISCRETIONARY,
    "subscriptions_software": CategoryLevel.DISCRETIONARY,
    "subscriptions software": CategoryLevel.DISCRETIONARY,
    "subscriptions_media": CategoryLevel.DISCRETIONARY,
    "taxi_ridehailing": CategoryLevel.DISCRETIONARY,
    "taxi ridehailing": CategoryLevel.DISCRETIONARY,
    "flights": CategoryLevel.DISCRETIONARY,
    "hotels": CategoryLevel.DISCRETIONARY,
}


def get_category_level(category: str) -> CategoryLevel:
    """Get priority level. Unknown categories default to FLEXIBLE."""
    return CATEGORY_PRIORITY.get(category.lower().strip(), CategoryLevel.FLEXIBLE)


def is_sacred(category: str) -> bool:
    """True if category must never be used as a redistribution donor."""
    return get_category_level(category) == CategoryLevel.SACRED


def donor_sort_key(category: str) -> int:
    """Higher value = take from this category first. Use as sorted() key."""
    return int(get_category_level(category))

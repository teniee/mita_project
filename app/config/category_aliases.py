"""Bridge between the category names the app sends and the ones the plan uses.

Three vocabularies exist in this system and they do not agree:

* the **plan** vocabulary — what ``build_monthly_budget`` emits and what
  ``daily_plan.category`` therefore contains for a real onboarded user:
  ``groceries``, ``dining out``, ``coffee``, ``transport public``,
  ``transport gas``, ``entertainment events``, ``hobbies``, ``clothing``,
  ``flights``, ``insurance medical``, ``out of pocket medical``, ``rent`` …
  (note the spaces — these are display-ish slugs, not identifiers).
* the **API** vocabulary — the allow-list on
  ``POST /transactions/check-affordability``: ``food``, ``transportation``,
  ``entertainment``, ``healthcare``, ``shopping``, ``utilities``, ``travel`` …
* the **mobile UI** vocabulary — what the Add Expense picker posts, which is a
  subset of the API one (``food`` for "Food & Dining", and so on).

``SpendingPreventionService`` looked up ``DailyPlan.category == category`` with
an exact string match, so *every* category the app can send missed *every* row
the planner writes. The result was a user who had just been shown "Groceries
$14 / Coffee $5 / Transport public $30" for today being told, on the very next
screen, "⚠️ No budget set for 'food'" — with a suggestion to "set a daily
budget for 'food' in settings", which is not a thing that exists. Spending
prevention, the product's stated core differentiator, matched nothing for
anybody.

This module is the one place that says which plan buckets an API category
covers. It is deliberately a lookup table and nothing else: the planner keeps
emitting what it emits, the app keeps sending what it sends, and neither has to
change.
"""

from typing import Dict, Set

# API/UI category -> the plan buckets it spends from.
#
# Keys must stay in step with ``valid_categories`` in
# app/api/transactions/routes.py; values with the categories produced by
# app/services/core/engine/monthly_budget_engine.py and the fixed-expense ids
# submitted by onboarding (mobile_app/lib/screens/onboarding_expenses_screen.dart).
CATEGORY_ALIASES: Dict[str, Set[str]] = {
    "food": {"groceries", "dining out", "coffee", "restaurants", "food"},
    "groceries": {"groceries"},
    "dining": {"dining out", "restaurants"},
    "transportation": {
        "transport public",
        "transport gas",
        "transport",
        "car_payment",
    },
    "public_transport": {"transport public"},
    "gas": {"transport gas"},
    "entertainment": {"entertainment events", "hobbies", "entertainment"},
    "shopping": {"clothing", "shopping", "personal_care"},
    "clothing": {"clothing"},
    "healthcare": {
        "insurance medical",
        "out of pocket medical",
        "health",
        "gym",
    },
    "insurance": {"insurance", "insurance medical"},
    "travel": {"flights", "travel"},
    "utilities": {"utilities", "internet"},
    "rent": {"rent"},
    "mortgage": {"rent"},
    "subscriptions": {"subscriptions"},
    "education": {"education"},
    "childcare": {"childcare"},
    "pets": {"pets"},
    "gifts": {"gifts"},
    "charity": {"donations", "charity"},
    "other": {"other"},
}


def plan_categories_for(category: str) -> Set[str]:
    """Plan buckets that [category] draws from.

    The category itself is always included, so a caller that already speaks the
    plan vocabulary (or an unmapped/custom category) still matches its own row
    and nothing regresses.
    """
    key = (category or "").strip().lower()
    return {key} | CATEGORY_ALIASES.get(key, set())


def matches_category(plan_category: str, requested: str) -> bool:
    """True when a ``daily_plan`` row belongs to the requested API category."""
    return (plan_category or "").strip().lower() in plan_categories_for(requested)

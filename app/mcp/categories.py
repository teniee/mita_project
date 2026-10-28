"""How MITA categories are shown in ChatGPT: one label per category, everywhere.

MITA stores two category vocabularies and both stay canonical (backend finding
F-2): the plan buckets the budget engine writes to ``daily_plan``
(``transport gas``, ``dining out`` … — ``calendar_engine.CATEGORY_BEHAVIOR``)
and the categories recorded expenses carry (``gas``, ``dining`` … —
``FinancialConstants.VALID_TRANSACTION_CATEGORIES``). Nothing here changes what
is stored or how the ledger accrues spending; it only decides the name a
category is SHOWN under, so every tool result names the same thing the same
way and ChatGPT has no reason to rename it.

Where an expense category plainly spends from one plan bucket, the two share a
label ("Fuel" for ``gas`` and ``transport gas``), and budget status and the
forecast show them as ONE line when the month's plan has that bucket. Every
such pair is one the API already declares in ``app/config/category_aliases.py``
(the table spending prevention uses) — ``tests_mcp/test_categories.py``
enforces it — so this never invents a relationship. Categories that could
belong to several buckets (``transportation``, ``food``, ``shopping``,
``insurance``…) keep their own line.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from app.core.category_priority import is_set_aside
from app.services.core.engine.user_budget_lines import (
    ENGINE_BUCKETS,
    is_user_line,
    label_of,
)

UNCATEGORIZED = "uncategorized"

# Plan buckets (``CATEGORY_BEHAVIOR``) plus the plan rows MITA writes besides
# them (goal reservations).
PLAN_LABELS: Dict[str, str] = {
    "books": "Books",
    "car maintenance": "Car maintenance",
    "clothing": "Clothing",
    "cloud storage": "Cloud storage",
    "coffee": "Coffee",
    "courses online": "Online courses",
    "debt repayment": "Debt repayment",
    "delivery": "Food delivery",
    "dining out": "Dining out",
    "entertainment events": "Entertainment",
    "flights": "Flights",
    "gaming": "Gaming",
    "goal_savings": "Set aside for goals",
    "groceries": "Groceries",
    "gym fitness": "Gym and fitness",
    "hobbies": "Hobbies",
    "home goods": "Home goods",
    "home repairs": "Home repairs",
    "hotels": "Hotels",
    "insurance medical": "Medical insurance",
    "investment contribution": "Investments",
    "local transport": "Local transport",
    "media streaming": "Streaming services",
    "mortgage": "Mortgage",
    "out of pocket medical": "Healthcare",
    "rent": "Rent",
    "savings emergency": "Emergency savings",
    "savings goal based": "Savings",
    "school fees": "School fees",
    "subscriptions software": "Software subscriptions",
    "taxi ridehailing": "Taxis and ride-hailing",
    "tech gadgets": "Tech and gadgets",
    "transport gas": "Fuel",
    "transport public": "Public transport",
    "utilities": "Utilities",
}

# The categories an expense can be recorded under (the API's list).
EXPENSE_LABELS: Dict[str, str] = {
    "charity": "Charity",
    "childcare": "Childcare",
    "clothing": "Clothing",
    "dining": "Dining out",
    "education": "Education",
    "entertainment": "Entertainment",
    "food": "Food",
    "gas": "Fuel",
    "gifts": "Gifts",
    "groceries": "Groceries",
    "healthcare": "Healthcare",
    "income": "Income",
    "insurance": "Insurance",
    "mortgage": "Mortgage",
    "other": "Other",
    "pets": "Pets",
    "public_transport": "Public transport",
    "rent": "Rent",
    "shopping": "Shopping",
    "subscriptions": "Subscriptions",
    "transportation": "Transport",
    "travel": "Travel",
    "utilities": "Utilities",
}

# Expense category -> the one plan bucket it is shown with. Each pair is in
# category_aliases.CATEGORY_ALIASES (tested). Same-name categories (groceries,
# clothing, rent, mortgage, utilities) already share a line.
PRIMARY_PLAN_BUCKET: Dict[str, str] = {
    "dining": "dining out",
    "entertainment": "entertainment events",
    "gas": "transport gas",
    "healthcare": "out of pocket medical",
    "public_transport": "transport public",
}

GOAL_LABELS: Dict[str, str] = {
    "debt_payoff": "Debt payoff",
    "education": "Education",
    "emergency_fund": "Emergency fund",
    "healthcare": "Healthcare",
    "investment": "Investment",
    "other": "Other",
    "purchase": "Purchase",
    "retirement": "Retirement",
    "savings": "Savings",
    "travel": "Travel",
}

LABEL_RULE = (
    "`label` is MITA's display name for the category: show it exactly as given "
    "(translated consistently if you answer in another language) and never rename "
    "or merge categories yourself."
)


def label(code: Optional[str]) -> str:
    """The display name of a stored category code (plan or expense vocabulary).

    Codes outside both tables (older onboarding names, custom rows) get a
    deterministic fallback: underscores as spaces, first letter capitalised.
    """
    if not code or code == UNCATEGORIZED:
        return "Uncategorized"
    if is_user_line(code):
        return label_of(code)  # the user's own words (F-11)
    found = EXPENSE_LABELS.get(code) or PLAN_LABELS.get(code)
    if found:
        return found
    text = code.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


# Who decides a budget line's amount.
SET_BY_YOU = "set_by_you"
CALCULATED_BY_MITA = "calculated_by_mita"
FIXED_PAYMENT = "fixed_payment"
SAVINGS = "savings"


def source_of(code: str) -> str:
    """A line the user set (F-11), money set aside, one of MITA's engine
    lines, or a fixed payment (every other stored line: rent, utilities and
    saved payments the plan was built with)."""
    if is_user_line(code):
        return SET_BY_YOU
    if is_set_aside(code):
        return SAVINGS
    if code in ENGINE_BUCKETS:
        return CALCULATED_BY_MITA
    return FIXED_PAYMENT


def line_source(codes: Iterable[str], planned: Decimal) -> Optional[str]:
    """The source of a display line adding up several stored codes (a plan
    bucket and the expenses recorded for it); None with nothing planned."""
    if planned <= 0:
        return None
    sources = {source_of(code) for code in codes}
    for source in (SET_BY_YOU, SAVINGS, CALCULATED_BY_MITA):
        if source in sources:
            return source
    return FIXED_PAYMENT


def goal_label(code: Optional[str]) -> str:
    if not code:
        return GOAL_LABELS["savings"]
    return GOAL_LABELS.get(code) or label(code)


def line_key(code: str, plan_buckets: Set[str]) -> str:
    """The budget line a stored category belongs to: its paired plan bucket
    when the month's plan has that bucket, otherwise the category itself."""
    bucket = PRIMARY_PLAN_BUCKET.get(code)
    return bucket if bucket is not None and bucket in plan_buckets else code


def group_lines(
    planned: Mapping[str, Decimal], spent: Mapping[str, Decimal]
) -> List[Tuple[str, str, List[str], Decimal, Decimal]]:
    """Combine per-category plan and spend into display lines.

    Returns ``(key, label, codes, planned, spent)`` per line. The figures are
    sums of the stored ones; nothing is estimated or moved. If two different
    lines would still carry the same label (only possible with uncommon stored
    names), the code is appended to keep them apart.
    """
    buckets = set(planned)
    members: Dict[str, Set[str]] = defaultdict(set)
    for code in set(planned) | set(spent):
        members[line_key(code, buckets)].add(code)
    by_label: Dict[str, List[str]] = defaultdict(list)
    for key in members:
        by_label[label(key)].append(key)
    lines = []
    for key, codes in members.items():
        name = label(key)
        if len(by_label[name]) > 1:
            name = f"{name} ({key})"
        lines.append(
            (
                key,
                name,
                sorted(codes),
                sum((planned.get(c, Decimal("0")) for c in codes), Decimal("0")),
                sum((spent.get(c, Decimal("0")) for c in codes), Decimal("0")),
            )
        )
    return lines


def regroup_by_day(
    amounts: Mapping[Tuple[object, str], Decimal], plan_buckets: Iterable[str]
) -> Dict[Tuple[object, str], Decimal]:
    """Per-(day, category) amounts re-keyed by budget line (for the forecast)."""
    buckets = set(plan_buckets)
    out: Dict[Tuple[object, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for (day, code), amount in amounts.items():
        out[(day, line_key(code, buckets))] += amount
    return dict(out)

"""The sign-in page's fictional month — computed by MITA's own code.

Nothing on the page is drawn from a made-up figure: the month below is a
fictional family's inputs (monthly allocations, recorded expenses, saved
payments) run through the code the product uses:

* the day-by-day layout: ``monthly_plan_service.month_calendar`` (the
  canonical distributor a reviewed budget is saved with);
* every figure: ``queries.calendar.build_calendar`` and
  ``queries.plan.forecast_from_rows`` — what ``show_financial_calendar`` and
  ``get_budget_forecast`` return for the same rows.

The expenses stay within each date's plan and use categories whose plan line
has the same name (groceries, rent, utilities, clothing), so MITA's
automatic rebalancing would not move anything: the plan shown is the plan
MITA would hold (``realtime_rebalancer`` acts only on a day that goes over;
a category recorded under another name than its plan line — backend finding
F-2 — would count as unplanned). ``tests_mcp/test_auth_ui.py`` recomputes
the figures the page shows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple

from app.mcp.queries.calendar import CalendarMonth, SavedPayment, build_calendar
from app.mcp.queries.plan import forecast_from_rows
from app.services.core.engine.budget_forecast_engine import commitment_expectations
from app.services.monthly_obligations import due_in_month
from app.services.monthly_plan_service import month_calendar

YEAR, MONTH = 2026, 10
TODAY = date(2026, 10, 19)  # a Monday: 19 days begun, 12 left

# The reviewed budget: income 3,200.00, savings target 400.00, saved
# obligations rent (1st), utilities and home internet.
ALLOCATIONS: Dict[str, str] = {
    "rent": "850.00",
    "utilities": "120.00",
    "subscriptions": "30.00",
    "groceries": "420.00",
    "dining out": "180.00",
    "transport public": "60.00",
    "transport gas": "110.00",
    "entertainment events": "90.00",
    "clothing": "80.00",
    "savings goal based": "400.00",
}

# (day of October, category, amount) — each within that date's plan line.
EXPENSES: Tuple[Tuple[int, str, str], ...] = (
    (1, "rent", "850.00"),
    (1, "groceries", "18.40"),
    (2, "groceries", "12.35"),
    (4, "clothing", "19.99"),
    (5, "utilities", "120.00"),
    (5, "groceries", "17.80"),
    (6, "groceries", "9.60"),
    (7, "groceries", "16.25"),
    (8, "groceries", "19.05"),
    (9, "groceries", "14.70"),
    (11, "clothing", "15.00"),
    (12, "groceries", "18.30"),
    (13, "groceries", "11.90"),
    (14, "groceries", "18.95"),
    (15, "groceries", "8.75"),
    (16, "groceries", "17.40"),
    (19, "groceries", "6.40"),
)

PAYMENTS: List[SavedPayment] = [
    SavedPayment(
        "rent", Decimal("850.00"), "Apartment rent", date(2026, 11, 1), "monthly"
    ),
    SavedPayment(
        "utilities",
        Decimal("120.00"),
        "Electricity and water",
        date(2026, 11, 5),
        "monthly",
    ),
    SavedPayment(
        "subscriptions",
        Decimal("30.00"),
        "Home internet",
        date(2026, 10, 27),
        "monthly",
    ),
]


def demo_month() -> CalendarMonth:
    layout = month_calendar(
        YEAR, MONTH, {k: Decimal(v) for k, v in ALLOCATIONS.items()}
    )
    planned = {
        (date.fromisoformat(day), category): Decimal(str(amount))
        for day, categories in layout.items()
        for category, amount in categories.items()
    }
    spent: Dict[Tuple[date, str], Decimal] = {}
    for day, category, amount in EXPENSES:
        key = (date(YEAR, MONTH, day), category)
        spent[key] = spent.get(key, Decimal("0")) + Decimal(amount)
    return build_calendar(
        year=YEAR,
        month=MONTH,
        today=TODAY,
        planned=planned,
        spent=spent,
        payments=PAYMENTS,
        plan_generated=True,
        forecast=forecast_from_rows(
            planned, spent, YEAR, MONTH, TODAY, demo_commitments()
        ),
    )


def demo_commitments() -> Dict[str, Decimal]:
    """What the fictional bills still need, by MITA's rule
    (``commitment_expectations``): the reviewed plan of each bill line
    and the saved payments due in October."""
    base = {k: Decimal(v) for k, v in ALLOCATIONS.items()}
    due: Dict[str, Decimal] = {}
    for p in PAYMENTS:
        amount = due_in_month(p.amount, p.anchor, p.recurrence, YEAR, MONTH)
        if amount > 0:
            due[p.category] = due.get(p.category, Decimal("0")) + amount
    return commitment_expectations(base, due)


DEMO = demo_month()

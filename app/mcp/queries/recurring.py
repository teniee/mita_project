"""Recurring and scheduled expenses the user has declared.

Only user-confirmed items: scheduled expenses the user created, and
transactions the user marked ``is_recurring`` when recording them. MITA has
no subscription-detection engine, so nothing is inferred from merchant names.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense, Transaction
from app.mcp.queries.periods import UserContext, utc_window
from app.services.core.engine.expense_tracker import local_day_of

MARKED_LOOKBACK_DAYS = 180
UPCOMING_ONE_TIME_DAYS = 60
# ScheduledExpenseIn accepts recurrence in {"once", "weekly", "monthly"} or
# null; "once" is a one-time expense, not a recurring one.
REPEATING = {"weekly", "monthly"}


@dataclass(frozen=True)
class ScheduledItem:
    category: str
    amount: Decimal
    merchant: Optional[str]
    next_date: date
    recurrence: Optional[str]


@dataclass(frozen=True)
class MarkedRecurring:
    label: str  # merchant when recorded, otherwise the category
    category: str
    last_amount: Decimal
    last_date: date
    occurrences: int


@dataclass(frozen=True)
class RecurringView:
    scheduled_recurring: List[ScheduledItem]
    upcoming_one_time: List[ScheduledItem]
    marked_recurring: List[MarkedRecurring]
    lookback_start: date


def recurring_expenses(db: Session, ctx: UserContext) -> RecurringView:
    pending = (
        db.query(ScheduledExpense)
        .filter(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
        .order_by(ScheduledExpense.scheduled_date, ScheduledExpense.category)
        .all()
    )
    horizon = ctx.today + timedelta(days=UPCOMING_ONE_TIME_DAYS)

    def item(row: ScheduledExpense) -> ScheduledItem:
        return ScheduledItem(
            category=row.category,
            amount=Decimal(str(row.amount)),
            merchant=(row.merchant or "").strip() or None,
            next_date=row.scheduled_date,
            recurrence=row.recurrence,
        )

    scheduled_recurring = [item(r) for r in pending if r.recurrence in REPEATING]
    upcoming_one_time = [
        item(r)
        for r in pending
        if r.recurrence not in REPEATING and ctx.today <= r.scheduled_date <= horizon
    ]

    lookback_start = ctx.today - timedelta(days=MARKED_LOOKBACK_DAYS - 1)
    lower, upper = utc_window(lookback_start, ctx.today, ctx.timezone)
    rows = (
        db.query(
            Transaction.spent_at,
            Transaction.amount,
            Transaction.category,
            Transaction.merchant,
        )
        .filter(
            Transaction.user_id == ctx.user_id,
            Transaction.deleted_at.is_(None),
            Transaction.is_recurring.is_(True),
            Transaction.spent_at >= lower,
            Transaction.spent_at < upper,
        )
        .order_by(Transaction.spent_at.desc())
        .all()
    )
    grouped: dict = {}
    for spent_at, amount, category, merchant in rows:
        merchant_label = (merchant or "").strip()
        key = (merchant_label.casefold() or category, category)
        if key not in grouped:
            grouped[key] = {
                "label": merchant_label or category,
                "category": category,
                "last_amount": Decimal(str(amount)),
                "last_date": local_day_of(spent_at, ctx.timezone),
                "occurrences": 0,
            }
        grouped[key]["occurrences"] += 1
    marked = sorted(
        (MarkedRecurring(**values) for values in grouped.values()),
        key=lambda m: (m.last_date, m.label),
        reverse=True,
    )
    return RecurringView(
        scheduled_recurring=scheduled_recurring,
        upcoming_one_time=upcoming_one_time,
        marked_recurring=marked,
        lookback_start=lookback_start,
    )

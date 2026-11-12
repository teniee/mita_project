"""What the user's saved regular payments ask of one month, and on which dates.

One rule for every surface — the reviewed budget's obligations and its
day-by-day layout (``app/mcp/queries/budget_draft.py``), the month rollover
(``monthly_plan_service``), the calendar's commitments and bill dates, the
ledger rebuild that keeps a bill's money on its own line
(``expense_tracker.rebuild_month_plan``) and the forecast's reserve for bills
(``budget_forecast_engine``), in ChatGPT and in the mobile API alike:

* a repeating payment counts for a month once it is running — its next date
  is before the end of the following month: a monthly one once, on its day of
  the month (the month's last day when the month is shorter), a weekly one
  on every matching weekday of the month;
* a one-time payment counts only in its own month, on its date.

``due_dates_in_month`` is that rule; ``due_in_month`` is its amount, so the
money a month holds for a payment and the dates it is laid out on can never
disagree.

Dependency-free (SQLAlchemy only): the MCP image and the API both import it.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense

ZERO = Decimal("0.00")
MONTHLY = "monthly"
WEEKLY = "weekly"
ONE_TIME = (None, "once")


def _first_of_month_after_next(year: int, month: int) -> date:
    index = year * 12 + (month - 1) + 2
    return date(index // 12, index % 12 + 1, 1)


def weekday_count(year: int, month: int, weekday: int) -> int:
    days = calendar.monthrange(year, month)[1]
    return sum(
        1 for day in range(1, days + 1) if date(year, month, day).weekday() == weekday
    )


def due_dates_in_month(
    next_date: date, recurrence: Optional[str], year: int, month: int
) -> List[date]:
    """The dates one saved payment is due in ``(year, month)``, in order;
    empty when it does not count there. ``next_date`` is the payment's stored
    next due date (``scheduled_date``)."""
    last = calendar.monthrange(year, month)[1]
    if recurrence in (MONTHLY, WEEKLY):
        if next_date >= _first_of_month_after_next(year, month):
            return []  # not running yet
        if recurrence == MONTHLY:
            return [date(year, month, min(next_date.day, last))]
        first = date(year, month, 1)
        offset = (next_date.weekday() - first.weekday()) % 7
        return [first + timedelta(days=day) for day in range(offset, last, 7)]
    if recurrence in ONE_TIME:
        if date(year, month, 1) <= next_date <= date(year, month, last):
            return [next_date]
    return []


def due_in_month(
    amount: Decimal,
    next_date: date,
    recurrence: Optional[str],
    year: int,
    month: int,
) -> Decimal:
    """What one saved payment asks of ``(year, month)``; 0 when it does not
    count there. ``next_date`` is the payment's stored next due date."""
    return amount * len(due_dates_in_month(next_date, recurrence, year, month))


@dataclass(frozen=True)
class DueOccurrence:
    """One date a saved payment is due on in a month, for its full amount."""

    obligation_id: UUID  # the saved payment (scheduled_expenses.id)
    day: date
    category: str
    amount: Decimal
    merchant: Optional[str]
    recurrence: Optional[str]  # "monthly" | "weekly" | None (one-time)
    scheduled_from: date  # the payment's stored next due date


def _pending_payments(db: Session, user_id: UUID):
    return db.execute(
        select(
            ScheduledExpense.id,
            ScheduledExpense.category,
            ScheduledExpense.amount,
            ScheduledExpense.merchant,
            ScheduledExpense.scheduled_date,
            ScheduledExpense.recurrence,
        )
        .where(
            ScheduledExpense.user_id == user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
        .order_by(
            ScheduledExpense.scheduled_date,
            ScheduledExpense.category,
            ScheduledExpense.id,
        )
    ).all()


def dated_obligations(
    db: Session, user_id: UUID, year: int, month: int
) -> List[DueOccurrence]:
    """Every date the user's pending saved payments are due on in the month
    (cancelled and deleted ones never count), ordered by date. Summed per
    category it is exactly ``obligations_due``."""
    found: List[DueOccurrence] = []
    for (
        obligation_id,
        category,
        amount,
        merchant,
        next_date,
        recurrence,
    ) in _pending_payments(db, user_id):
        value = Decimal(str(amount))
        for day in due_dates_in_month(next_date, recurrence, year, month):
            found.append(
                DueOccurrence(
                    obligation_id=obligation_id,
                    day=day,
                    category=category,
                    amount=value,
                    merchant=(merchant or "").strip() or None,
                    recurrence=(
                        recurrence if recurrence in (MONTHLY, WEEKLY) else None
                    ),
                    scheduled_from=next_date,
                )
            )
    found.sort(key=lambda o: (o.day, o.category, -o.amount, str(o.obligation_id)))
    return found


def obligations_due(
    db: Session, user_id: UUID, year: int, month: int
) -> Dict[str, Decimal]:
    """``{category: amount}`` the user's pending saved payments ask of the
    month (cancelled and deleted ones never count)."""
    due: Dict[str, Decimal] = {}
    for occurrence in dated_obligations(db, user_id, year, month):
        if occurrence.amount > ZERO:
            due[occurrence.category] = (
                due.get(occurrence.category, ZERO) + occurrence.amount
            )
    return due

"""What the user's saved regular payments ask of one month.

One rule for every surface — the reviewed budget's obligations
(``app/mcp/queries/budget_draft.py``), the calendar's commitments and the
forecast's reserve for bills (``budget_forecast_engine``), in ChatGPT and in
the mobile API alike:

* a repeating payment counts for a month once it is running — its next date
  is before the end of the following month: a monthly one once, a weekly one
  once per matching weekday of the month;
* a one-time payment counts only in its own month.

Dependency-free (SQLAlchemy only): the MCP image and the API both import it.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Dict, Optional
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


def due_in_month(
    amount: Decimal,
    next_date: date,
    recurrence: Optional[str],
    year: int,
    month: int,
) -> Decimal:
    """What one saved payment asks of ``(year, month)``; 0 when it does not
    count there. ``next_date`` is the payment's stored next due date."""
    if recurrence in (MONTHLY, WEEKLY):
        if next_date >= _first_of_month_after_next(year, month):
            return ZERO
        if recurrence == MONTHLY:
            return amount
        return amount * weekday_count(year, month, next_date.weekday())
    if recurrence in ONE_TIME:
        last = calendar.monthrange(year, month)[1]
        if date(year, month, 1) <= next_date <= date(year, month, last):
            return amount
    return ZERO


def obligations_due(
    db: Session, user_id: UUID, year: int, month: int
) -> Dict[str, Decimal]:
    """``{category: amount}`` the user's pending saved payments ask of the
    month (cancelled and deleted ones never count)."""
    rows = db.execute(
        select(
            ScheduledExpense.category,
            ScheduledExpense.amount,
            ScheduledExpense.scheduled_date,
            ScheduledExpense.recurrence,
        ).where(
            ScheduledExpense.user_id == user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
    ).all()
    due: Dict[str, Decimal] = {}
    for category, amount, next_date, recurrence in rows:
        value = due_in_month(Decimal(str(amount)), next_date, recurrence, year, month)
        if value > ZERO:
            due[category] = due.get(category, ZERO) + value
    return due

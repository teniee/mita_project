"""Scheduling a recurring obligation through the canonical scheduled-expense writer.

The row is created by ``scheduled_expense_service.create_scheduled_expense``
(the function the API's ``POST /scheduled-expenses`` uses), with the API's
bounds. What MITA adds here is only the due date, computed deterministically
from what the user said ("on the 1st", "every Friday") — never guessed: with
no day and no first date the call is refused so ChatGPT asks.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense
from app.mcp.errors import ValidationError
from app.mcp.queries.periods import UserContext

# ScheduledExpenseIn (app/api/scheduled_expenses/routes.py): 0 < amount <= 100000.
MAX_SCHEDULED_AMOUNT = Decimal("100000.00")

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True)
class DueDate:
    day: date
    clamped_from: Optional[int] = None  # e.g. 31 when the month has only 30 days


def _clamped(year: int, month: int, day_of_month: int) -> DueDate:
    last = calendar.monthrange(year, month)[1]
    if day_of_month <= last:
        return DueDate(date(year, month, day_of_month))
    return DueDate(date(year, month, last), clamped_from=day_of_month)


def next_due_date(
    ctx: UserContext,
    recurrence: str,
    *,
    day_of_month: Optional[int],
    weekday: Optional[str],
    first_date: Optional[date],
) -> DueDate:
    """The next occurrence on or after the user's local today."""
    today = ctx.today
    if first_date is not None:
        if first_date < today:
            raise ValidationError(
                "first_date cannot be in the past; give the next date it is due."
            )
        if first_date > today + timedelta(days=366):
            raise ValidationError("first_date must be within the next year.")
        return DueDate(first_date)
    if recurrence == "monthly":
        if day_of_month is None:
            raise ValidationError(
                "Ask the user which day of the month it is due (or the next due "
                "date); MITA does not guess due dates."
            )
        due = _clamped(today.year, today.month, day_of_month)
        if due.day < today:
            nxt = today.replace(day=1) + timedelta(days=32)
            due = _clamped(nxt.year, nxt.month, day_of_month)
        return due
    if weekday is None:
        raise ValidationError(
            "Ask the user which day of the week it is due (or the next due date); "
            "MITA does not guess due dates."
        )
    ahead = (WEEKDAYS.index(weekday) - today.weekday()) % 7
    return DueDate(today + timedelta(days=ahead))


def similar_pending(
    db: Session, ctx: UserContext, category: str, amount: Decimal, recurrence: str
) -> List[Tuple[Optional[str], date]]:
    """Already scheduled repeating items with the same category, amount and
    rule — reported to the user, never merged or refused."""
    rows = db.execute(
        select(ScheduledExpense.merchant, ScheduledExpense.scheduled_date).where(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
            ScheduledExpense.category == category,
            ScheduledExpense.amount == amount,
            ScheduledExpense.recurrence == recurrence,
        )
    ).all()
    return [(merchant, due) for merchant, due in rows]

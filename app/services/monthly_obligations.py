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
* a one-time payment counts only in its own month, on its date;
* a payment scheduled in the mobile app (``origin = "app"``) never counts
  before its own date: each such row is ONE occurrence — the legacy
  scheduled-expense processor records it as an expense on that date and
  schedules the next row — so the month before it, and the month whose
  occurrence the processor already recorded, hold nothing for it. A payment
  saved in ChatGPT (``"chatgpt"``) is the obligation itself, never processed,
  and keeps the rule above; so does a row of unknown origin (``"unknown"``:
  saved before 0045 and not proven to be ChatGPT's) — PR #288 review P1.

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
# Where a saved payment was made (scheduled_expenses.origin, migration 0045).
APP_ORIGIN = "app"  # the mobile app: one row per occurrence, processable
CHATGPT_ORIGIN = "chatgpt"  # ChatGPT: the row is the obligation itself
# No source recorded: rows saved before 0045 not proven to be ChatGPT's, and
# any writer that does not say. Never processed; due dates as before 0045.
UNKNOWN_ORIGIN = "unknown"
ORIGINS = (APP_ORIGIN, CHATGPT_ORIGIN, UNKNOWN_ORIGIN)


def _first_of_month_after_next(year: int, month: int) -> date:
    index = year * 12 + (month - 1) + 2
    return date(index // 12, index % 12 + 1, 1)


def weekday_count(year: int, month: int, weekday: int) -> int:
    days = calendar.monthrange(year, month)[1]
    return sum(
        1 for day in range(1, days + 1) if date(year, month, day).weekday() == weekday
    )


def due_dates_in_month(
    next_date: date,
    recurrence: Optional[str],
    year: int,
    month: int,
    day_of_month: Optional[int] = None,
    origin: Optional[str] = None,
) -> List[date]:
    """The dates one saved payment is due in ``(year, month)``, in order;
    empty when it does not count there. ``next_date`` is the payment's stored
    next due date (``scheduled_date``); ``day_of_month`` the day the user
    asked for a monthly payment (``scheduled_expenses.day_of_month``), kept
    because ``next_date`` is clamped to its month — "the 31st" saved in
    November is due on 30 November and on 31 December, never on the 30th of
    every month. Without it (rows saved before migration 0045) the date's own
    day is used, as before: an original day is never guessed. ``origin``
    "app" (a row made in the mobile app, one occurrence) drops every date
    before ``next_date``."""
    last = calendar.monthrange(year, month)[1]
    if recurrence in (MONTHLY, WEEKLY):
        if next_date >= _first_of_month_after_next(year, month):
            return []  # not running yet
        if recurrence == MONTHLY:
            day = day_of_month if day_of_month is not None else next_date.day
            dates = [date(year, month, min(day, last))]
        else:
            first = date(year, month, 1)
            offset = (next_date.weekday() - first.weekday()) % 7
            dates = [first + timedelta(days=day) for day in range(offset, last, 7)]
        if origin == APP_ORIGIN:
            dates = [day for day in dates if day >= next_date]
        return dates
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
    day_of_month: Optional[int] = None,
    origin: Optional[str] = None,
) -> Decimal:
    """What one saved payment asks of ``(year, month)``; 0 when it does not
    count there. ``next_date`` is the payment's stored next due date."""
    return amount * len(
        due_dates_in_month(next_date, recurrence, year, month, day_of_month, origin)
    )


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
    day_of_month: Optional[int] = None  # the monthly day asked for (0045)


def _pending_payments(db: Session, user_id: UUID):
    return db.execute(
        select(
            ScheduledExpense.id,
            ScheduledExpense.category,
            ScheduledExpense.amount,
            ScheduledExpense.merchant,
            ScheduledExpense.scheduled_date,
            ScheduledExpense.recurrence,
            ScheduledExpense.day_of_month,
            ScheduledExpense.origin,
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
        day_of_month,
        origin,
    ) in _pending_payments(db, user_id):
        value = Decimal(str(amount))
        for day in due_dates_in_month(
            next_date, recurrence, year, month, day_of_month, origin
        ):
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
                    day_of_month=day_of_month,
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

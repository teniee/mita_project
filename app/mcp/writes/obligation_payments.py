"""Linking a recorded expense to the saved regular payment it paid.

The user's statement "this €270 was my car loan" is the only thing that
settles a fixed obligation (``obligation_lines``, migration 0041). Here:

* ``resolve`` turns an ``ob_…`` reference into the user's own pending saved
  payment (another user's reference does not decrypt: "not found");
* ``Allocator`` picks the due date an expense paid when ChatGPT did not say:
  the earliest due date of the expense's month not yet paid in full, else the
  next month's first (an early payment). An explicit date must be one of the
  payment's due dates (``monthly_obligations.due_dates_in_month``);
* ``link`` / ``unlink`` write ``obligation_payments`` inside the caller's unit
  of work — before the ledger rebuild, which must see the link.

A linked expense is recorded under the saved payment's own category, so a
plan saved before obligations had lines of their own (where that category
holds the payment's money) and a plan saved after agree.
"""

from __future__ import annotations

import calendar as calendar_module
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import ObligationPayment, ScheduledExpense
from app.mcp.categories import label as category_label
from app.mcp.crypto import DataKeys
from app.mcp.errors import ValidationError
from app.mcp.queries.obligations import owned_obligation
from app.mcp.queries.periods import UserContext
from app.services.monthly_obligations import due_dates_in_month
from app.services.obligation_lines import paid_by_occurrence, payments_for_due_dates

ZERO = Decimal("0.00")

NOT_FOUND = (
    "No saved regular payment of this user matches this obligation_ref. Use "
    "get_recurring_expenses or get_calendar_month to find it."
)


def resolve(
    db: Session, ctx: UserContext, keys: DataKeys, ref: str
) -> ScheduledExpense:
    obligation = owned_obligation(db, ctx, keys.obligation_id(ctx.user_id, ref))
    if obligation is None:
        raise ValidationError(NOT_FOUND)
    return obligation


def name_of(obligation: ScheduledExpense) -> str:
    return (obligation.merchant or "").strip() or category_label(obligation.category)


def _next_month(year: int, month: int) -> Tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _month_range(year: int, month: int) -> Tuple[date, date]:
    return date(year, month, 1), date(
        year, month, calendar_module.monthrange(year, month)[1]
    )


def due_dates_near(obligation: ScheduledExpense, day: date) -> List[date]:
    """The payment's due dates in ``day``'s month and the next one."""
    found: List[date] = []
    for year, month in ((day.year, day.month), _next_month(day.year, day.month)):
        found.extend(
            due_dates_in_month(
                obligation.scheduled_date, obligation.recurrence, year, month
            )
        )
    return found


def is_due_date(obligation: ScheduledExpense, due: date) -> bool:
    return due in due_dates_in_month(
        obligation.scheduled_date, obligation.recurrence, due.year, due.month
    )


@dataclass
class Allocator:
    """Due dates for the expenses of one request, counting what earlier items
    of the same request already paid (two parts of one bill in a batch)."""

    db: Session
    ctx: UserContext
    _paid: Dict[Tuple[UUID, date], Decimal] = None  # type: ignore[assignment]
    _loaded: set = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._paid = defaultdict(lambda: ZERO)
        self._loaded = set()

    def _load(self, year: int, month: int) -> None:
        if (year, month) in self._loaded:
            return
        first, last = _month_range(year, month)
        for key, amount in paid_by_occurrence(
            payments_for_due_dates(self.db, self.ctx.user_id, first, last)
        ).items():
            self._paid[key] += amount
        self._loaded.add((year, month))

    def due_date(
        self,
        obligation: ScheduledExpense,
        day: date,
        amount: Decimal,
        explicit: Optional[date],
    ) -> date:
        name = name_of(obligation)
        if explicit is not None:
            if not is_due_date(obligation, explicit):
                nearby = ", ".join(
                    d.isoformat() for d in due_dates_near(obligation, day)
                )
                raise ValidationError(
                    f"{explicit.isoformat()} is not a due date of {name}"
                    + (
                        f" (its due dates near this expense: {nearby})."
                        if nearby
                        else "."
                    )
                )
            due = explicit
        else:
            candidates = due_dates_near(obligation, day)
            for candidate in candidates:
                self._load(candidate.year, candidate.month)
            this_month = [
                d for d in candidates if (d.year, d.month) == (day.year, day.month)
            ]
            later = [d for d in candidates if d not in this_month]
            amount_due = Decimal(str(obligation.amount))
            open_ = [
                d
                for d in this_month + later
                if self._paid[(obligation.id, d)] < amount_due
            ]
            if not open_:
                raise ValidationError(
                    f"Every due date of {name} around {day.isoformat()} is already "
                    "paid in MITA. Ask the user which due date this expense paid and "
                    "send it as obligation_due_date."
                )
            due = open_[0]
        self._load(due.year, due.month)
        self._paid[(obligation.id, due)] += amount
        return due

    def forget(self, obligation_id: UUID, due: date, amount: Decimal) -> None:
        """Leave out an expense's own earlier payment (it is being re-linked)."""
        self._load(due.year, due.month)
        self._paid[(obligation_id, due)] -= amount

    def paid(self, obligation: ScheduledExpense, due: date) -> Decimal:
        self._load(due.year, due.month)
        return self._paid[(obligation.id, due)]


def link(
    db: Session,
    ctx: UserContext,
    transaction_id: UUID,
    obligation: ScheduledExpense,
    due: date,
) -> None:
    """Record that the expense paid that due date (replacing any earlier
    link of the same expense). Does not commit."""
    unlink(db, ctx, transaction_id)
    db.add(
        ObligationPayment(
            user_id=ctx.user_id,
            scheduled_expense_id=obligation.id,
            due_date=due,
            transaction_id=transaction_id,
        )
    )
    db.flush()


def unlink(db: Session, ctx: UserContext, transaction_id: UUID) -> bool:
    """Remove the expense's link, if any. Does not commit."""
    result = db.execute(
        delete(ObligationPayment).where(
            ObligationPayment.user_id == ctx.user_id,
            ObligationPayment.transaction_id == transaction_id,
        )
    )
    db.flush()
    return bool(result.rowcount)


def current_link(
    db: Session, ctx: UserContext, transaction_id: UUID
) -> Optional[ObligationPayment]:
    return (
        db.query(ObligationPayment)
        .filter(
            ObligationPayment.user_id == ctx.user_id,
            ObligationPayment.transaction_id == transaction_id,
        )
        .first()
    )


def require_category(obligation: ScheduledExpense, category: Optional[str]) -> str:
    """A payment of a saved payment is recorded under its category."""
    if category is not None and category != obligation.category:
        raise ValidationError(
            f"A payment of {name_of(obligation)} is recorded under its category "
            f"({category_label(obligation.category)}, '{obligation.category}'). "
            "Leave category out, or record it without obligation_ref if it is "
            "not that payment."
        )
    return obligation.category


def unpaid_in_category(
    db: Session, ctx: UserContext, category: str, day: date
) -> List[Tuple[ScheduledExpense, date, Decimal]]:
    """The user's saved payments under ``category`` with a due date in
    ``day``'s month not yet paid in full: ``(payment, due date, still due)``.
    For a note only — MITA never links an expense by itself."""
    rows = (
        db.query(ScheduledExpense)
        .filter(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
            ScheduledExpense.category == category,
        )
        .order_by(ScheduledExpense.scheduled_date, ScheduledExpense.id)
        .all()
    )
    if not rows:
        return []
    first, last = _month_range(day.year, day.month)
    paid = paid_by_occurrence(payments_for_due_dates(db, ctx.user_id, first, last))
    found = []
    for obligation in rows:
        amount = Decimal(str(obligation.amount))
        for due in due_dates_in_month(
            obligation.scheduled_date, obligation.recurrence, day.year, day.month
        ):
            left = amount - paid.get((obligation.id, due), ZERO)
            if left > ZERO:
                found.append((obligation, due, left))
                break
    return found

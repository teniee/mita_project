"""The user's saved regular payments as ChatGPT sees them: names, refs and
what is paid on each due date.

Only the user's own statements: a due date counts as paid by the expenses
the user linked to it (``obligation_payments``), never by spending that
happens to share its category (docs/chatgpt-app/behavioral-budget.md).
"""

from __future__ import annotations

import calendar as calendar_module
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense
from app.mcp.categories import label as category_label
from app.mcp.queries.periods import UserContext
from app.services.core.engine.expense_tracker import local_day_of
from app.services.obligation_lines import bill_key, payments_for_due_dates

ZERO = Decimal("0.00")


def obligation_names(db: Session, ctx: UserContext) -> Dict[str, str]:
    """``{"bill:<id>": the user's name for it}`` for every saved payment the
    user has, cancelled and deleted ones included (an earlier month's plan
    may still hold one). Payments named alike are told apart by category,
    then by their next due date."""
    rows = db.execute(
        select(
            ScheduledExpense.id,
            ScheduledExpense.merchant,
            ScheduledExpense.category,
            ScheduledExpense.scheduled_date,
        )
        .where(ScheduledExpense.user_id == ctx.user_id)
        .order_by(ScheduledExpense.scheduled_date, ScheduledExpense.id)
    ).all()
    base = {
        oid: ((merchant or "").strip() or category_label(category), category, due)
        for oid, merchant, category, due in rows
    }
    count: Dict[str, int] = defaultdict(int)
    for name, _category, _due in base.values():
        count[name.casefold()] += 1
    names: Dict[str, str] = {}
    seen: Dict[str, int] = defaultdict(int)
    for oid, (name, category, due) in base.items():
        if count[name.casefold()] > 1:
            labelled = f"{name} ({category_label(category)})"
            seen[labelled.casefold()] += 1
            if seen[labelled.casefold()] > 1:
                labelled = f"{name} ({category_label(category)}, {due.isoformat()})"
            name = labelled
        names[bill_key(oid)] = name
    return names


@dataclass(frozen=True)
class PaymentOnDue:
    """One expense the user linked to one due date."""

    transaction_id: UUID
    day: date  # local day it was recorded on
    amount: Decimal


def payments_by_due(
    db: Session, ctx: UserContext, year: int, month: int
) -> Dict[Tuple[UUID, date], List[PaymentOnDue]]:
    """What the user linked to each due date of the month, recorded in any
    month (a payment made early counts for its due date)."""
    first = date(year, month, 1)
    last = date(year, month, calendar_module.monthrange(year, month)[1])
    found: Dict[Tuple[UUID, date], List[PaymentOnDue]] = defaultdict(list)
    for p in payments_for_due_dates(db, ctx.user_id, first, last):
        found[(p.obligation_id, p.due_date)].append(
            PaymentOnDue(
                p.transaction_id, local_day_of(p.spent_at, ctx.timezone), p.amount
            )
        )
    return dict(found)


def owned_obligation(
    db: Session, ctx: UserContext, obligation_id: Optional[UUID]
) -> Optional[ScheduledExpense]:
    """The user's own pending saved payment, or None."""
    if obligation_id is None:
        return None
    return db.execute(
        select(ScheduledExpense).where(
            ScheduledExpense.id == obligation_id,
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
    ).scalar_one_or_none()

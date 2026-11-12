"""Fixed obligations as plan lines of their own, settled only by their payments.

A saved regular payment (``scheduled_expenses``: car loan €270 on the 15th)
is an obligation with an identity. Until 2026-11-03 MITA settled it by
category: every expense recorded under ``transportation`` counted toward the
car loan, so a €60 car part "paid" €60 of it and the bills reserve held
€210. The owner's rule now (docs/chatgpt-app/behavioral-budget.md):

* **an obligation is settled only by an expense the user said paid it**
  (``obligation_payments``: expense → saved payment + due date). A purchase
  in the same category is ordinary spending; where MITA cannot tell, nothing
  is linked;
* **an obligation has its own plan line** ``"bill:<id>"`` in plans laid out
  from now on, so its money never shares a ``daily_plan`` row with everyday
  money of the same category. A plan saved earlier keeps its obligations
  under their categories ("legacy"); there the link still decides what pays
  them, and saving the month again moves them onto their own lines;
* **the reserve** (R3) per obligation is what its due dates this month ask
  for minus what linked expenses paid — never less than 0, never reduced by
  unrelated spending. Rent, mortgage and utilities lines stated in the mobile
  onboarding WITHOUT a saved payment have no identity: MITA can only see them
  paid by category (R3's rule, unchanged for them).

``plan_line_of`` is the one keying rule: ``rebuild_month_plan`` accrues the
ledger with it and the ChatGPT queries read spend with it, so the plan, the
spend cache and every MCP figure agree.

Dependency-free (SQLAlchemy only): the MCP image and the API both import it.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ObligationPayment, ScheduledExpense, Transaction
from app.services.core.engine.budget_forecast_engine import is_bill_line
from app.services.monthly_obligations import DueOccurrence, dated_obligations

ZERO = Decimal("0.00")
BILL_LINE_PREFIX = "bill:"


def bill_key(obligation_id: UUID) -> str:
    """The plan line of one saved regular payment: ``"bill:"`` and a one-way
    digest of its id. Stored as ``daily_plan.category`` and shown to ChatGPT
    as the line's code, so it must not carry the database id (ids leave MITA
    only as user-bound refs, ``ob_…``). Nothing needs to read the id back:
    every reader starts from the saved payments and derives their keys."""
    digest = hashlib.sha256(b"mita/bill-line/v1:" + obligation_id.bytes).hexdigest()
    return BILL_LINE_PREFIX + digest[:24]


def is_bill_key(key: Optional[str]) -> bool:
    return bool(key) and str(key).startswith(BILL_LINE_PREFIX)


def month_is_keyed(categories: Iterable[Optional[str]]) -> bool:
    """True for a month laid out with obligations on their own lines."""
    return any(is_bill_key(c) for c in categories)


@dataclass(frozen=True)
class PaymentLink:
    """The due date of a saved payment one expense paid."""

    obligation_id: UUID
    due_date: date


def plan_line_of(category: str, link: Optional[PaymentLink], keyed: bool) -> str:
    """The plan line an expense counts on: its obligation's own line when it
    paid one and the month keeps obligations on their own lines, otherwise
    its category (a legacy month holds an obligation's money under it)."""
    if link is not None and keyed:
        return bill_key(link.obligation_id)
    return category


def links_for_transactions(
    db: Session, user_id: UUID, transaction_ids: Sequence[UUID]
) -> Dict[UUID, PaymentLink]:
    """``{expense id: what it paid}`` for the given expenses of this user."""
    ids = list(transaction_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(
            ObligationPayment.transaction_id,
            ObligationPayment.scheduled_expense_id,
            ObligationPayment.due_date,
        ).where(
            ObligationPayment.user_id == user_id,
            ObligationPayment.transaction_id.in_(ids),
        )
    ).all()
    return {txn: PaymentLink(obligation, due) for txn, obligation, due in rows}


def obligation_amounts(
    db: Session, user_id: UUID, obligation_ids: Iterable[UUID]
) -> Dict[UUID, Decimal]:
    """What each saved payment asks for on one due date."""
    ids = sorted(set(obligation_ids), key=str)
    if not ids:
        return {}
    rows = db.execute(
        select(ScheduledExpense.id, ScheduledExpense.amount).where(
            ScheduledExpense.user_id == user_id, ScheduledExpense.id.in_(ids)
        )
    ).all()
    return {oid: Decimal(str(amount)) for oid, amount in rows}


@dataclass(frozen=True)
class LinkedPayment:
    """One non-deleted expense linked to one due date."""

    transaction_id: UUID
    obligation_id: UUID
    due_date: date
    spent_at: object  # stored UTC instant; callers take the local day
    amount: Decimal


def payments_for_due_dates(
    db: Session, user_id: UUID, first: date, last: date
) -> List[LinkedPayment]:
    """Every non-deleted expense linked to a due date in ``[first, last]``,
    whenever it was recorded (a payment made early counts for its due date)."""
    rows = db.execute(
        select(
            ObligationPayment.transaction_id,
            ObligationPayment.scheduled_expense_id,
            ObligationPayment.due_date,
            Transaction.spent_at,
            Transaction.amount,
        )
        .join(Transaction, Transaction.id == ObligationPayment.transaction_id)
        .where(
            ObligationPayment.user_id == user_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            ObligationPayment.due_date >= first,
            ObligationPayment.due_date <= last,
        )
        .order_by(Transaction.spent_at, ObligationPayment.transaction_id)
    ).all()
    return [
        LinkedPayment(txn, obligation, due, spent_at, Decimal(str(amount)))
        for txn, obligation, due, spent_at, amount in rows
    ]


def paid_by_occurrence(
    payments: Iterable[LinkedPayment],
) -> Dict[Tuple[UUID, date], Decimal]:
    paid: Dict[Tuple[UUID, date], Decimal] = defaultdict(lambda: ZERO)
    for p in payments:
        paid[(p.obligation_id, p.due_date)] += p.amount
    return dict(paid)


def occurrence_line(occurrence: DueOccurrence, keyed: bool) -> str:
    """The plan line holding one due date's money."""
    return bill_key(occurrence.obligation_id) if keyed else occurrence.category


@dataclass(frozen=True)
class MonthCommitments:
    """What the month's fixed obligations need, by plan line.

    ``needs``: the line's reviewed (base) plan, or what its due dates ask
    for when more. ``paid``: for lines whose payments MITA can identify
    (saved payments), what linked expenses paid toward this month's due
    dates. A line in ``needs`` but not in ``paid`` is an essential line with
    no saved payment behind it (rent, mortgage, utilities stated in the
    mobile onboarding): what is recorded on it counts (R3's category rule).
    """

    needs: Dict[str, Decimal]
    paid: Dict[str, Decimal]
    # lines whose money only a linked payment may use (the identified ones)
    linked_only: FrozenSet[str]

    @property
    def lines(self) -> FrozenSet[str]:
        return frozenset(self.needs)


def commitments_for(
    occurrences: Sequence[DueOccurrence],
    paid: Mapping[Tuple[UUID, date], Decimal],
    base_by_line: Mapping[str, Decimal],
    keyed: bool,
) -> MonthCommitments:
    """Pure: the month's commitments from its due dates, the payments linked
    to them and the base plan (in-month rebalancing backed out — a
    rebalancing credit to a bill's line is not a second bill)."""
    due: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    paid_by_line: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    obligation_categories = set()
    for o in occurrences:
        if o.amount <= ZERO:
            continue
        line = occurrence_line(o, keyed)
        due[line] += o.amount
        # A due date is paid up to its amount: paying more never pays
        # another due date (that is spending beyond the bill).
        paid_by_line[line] += min(o.amount, paid.get((o.obligation_id, o.day), ZERO))
        obligation_categories.add(o.category)
    # A line of an obligation no longer due (cancelled after the plan was
    # saved) is not here: it holds nothing back, its money is free to spend.
    needs: Dict[str, Decimal] = {
        line: max(base_by_line.get(line, ZERO), amount) for line, amount in due.items()
    }
    for line, amount in base_by_line.items():
        if (
            amount > ZERO
            and line not in needs
            and is_bill_line(line)
            and line not in obligation_categories
        ):
            needs[line] = amount  # paid by category: no identity to link to
    identified = frozenset(due)
    return MonthCommitments(
        needs=dict(needs),
        paid={line: paid_by_line[line] for line in identified},
        linked_only=identified,
    )


def month_commitments(
    db: Session,
    user_id: UUID,
    year: int,
    month: int,
    base_by_line: Mapping[str, Decimal],
    keyed: bool,
) -> MonthCommitments:
    """``commitments_for`` over the database: the month's due dates (pending
    saved payments, ``monthly_obligations``) and the expenses linked to them."""
    import calendar as _calendar

    occurrences = dated_obligations(db, user_id, year, month)
    first = date(year, month, 1)
    last = date(year, month, _calendar.monthrange(year, month)[1])
    paid = paid_by_occurrence(payments_for_due_dates(db, user_id, first, last))
    return commitments_for(occurrences, paid, base_by_line, keyed)


def protected_lines(
    rows_categories: Iterable[Optional[str]], commitments
) -> FrozenSet[str]:
    """Lines that are never rebalancing donors: every commitment line and
    every obligation line in the plan (one no longer due included)."""
    return frozenset(commitments.lines) | frozenset(
        c for c in rows_categories if is_bill_key(c)
    )

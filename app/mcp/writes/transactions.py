"""Recording and correcting expenses through the canonical ledger writers.

* Create: ``Transaction`` rows built exactly as the API's ``add_transaction``
  builds them, inserted by ``expense_tracker.add_transactions_to_ledger``
  (per-user advisory lock, month rebuild, redistribution audit) — no commit
  here; the tool commits the rows and the idempotency record together.
* Update / delete: the API's own ``update_transaction`` / ``delete_transaction``
  (``app/api/transactions/services.py``): ownership filter, advisory lock,
  rebuild of every affected month, soft delete. They commit themselves.

Not reproduced on purpose: the API's push alerts (budget, velocity, large
transaction) need Firebase, which the MCP image does not install. The plan
itself is updated identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import List, Optional, Sequence, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.api.transactions import services as transaction_services
from app.db.models import Transaction
from app.mcp.crypto import DataKeys
from app.mcp.errors import ValidationError
from app.mcp.queries.periods import UserContext
from app.services.core.engine.expense_tracker import (
    _safe_zone,
    add_transactions_to_ledger,
    local_day_of,
)

# TxnIn (app/api/transactions/schemas.py) keeps 7 years of history.
MAX_PAST_DAYS = 365 * 7

NOT_FOUND = (
    "No MITA expense matches this reference. Use list_transactions to find the "
    "expense and its ref."
)


@dataclass(frozen=True)
class Expense:
    amount: Decimal
    category: str
    day: Optional[date]
    merchant: Optional[str]


def clean_merchant(value: Optional[str]) -> Optional[str]:
    """The user's text, trimmed; never rewritten otherwise."""
    if value is None:
        return None
    text = value.strip()
    if any(ord(ch) < 32 for ch in text):
        raise ValidationError("merchant must not contain control characters.")
    return text or None


def resolve_day(ctx: UserContext, day: Optional[date]) -> date:
    if day is None:
        return ctx.today
    if day > ctx.today:
        raise ValidationError(
            "An expense cannot be dated in the future. For a planned future "
            "payment use add_recurring_expense."
        )
    if day < ctx.today - timedelta(days=MAX_PAST_DAYS):
        raise ValidationError("An expense cannot be more than 7 years in the past.")
    return day


def instant_for(ctx: UserContext, day: date, now: datetime) -> datetime:
    """The stored (UTC) instant: now for today, local noon for another day —
    noon keeps the expense on that local day whatever DST does."""
    if day == ctx.today:
        return now.astimezone(timezone.utc)
    zone: ZoneInfo = _safe_zone(ctx.timezone)
    return datetime.combine(day, time(12, 0), tzinfo=zone).astimezone(timezone.utc)


def require_currency(ctx: UserContext, currency_known: bool) -> None:
    if not currency_known:
        raise ValidationError(
            "MITA does not know this user's currency yet. Ask the user which "
            "currency they use and save it with update_financial_profile first."
        )


def build_rows(
    ctx: UserContext, expenses: Sequence[Expense], now: datetime
) -> List[Transaction]:
    """Validate every expense first, then build the rows: one bad item fails
    the whole batch, named by its position, before anything is written."""
    rows = []
    for index, expense in enumerate(expenses, start=1):
        try:
            day = resolve_day(ctx, expense.day)
            merchant = clean_merchant(expense.merchant)
        except ValidationError as exc:
            if len(expenses) == 1:
                raise
            raise ValidationError(
                f"Item {index}: {exc.message} Nothing was recorded."
            ) from None
        rows.append(
            Transaction(
                user_id=ctx.user_id,
                category=expense.category,
                amount=expense.amount,
                currency=ctx.currency,
                merchant=merchant,
                spent_at=instant_for(ctx, day, now),
                is_recurring=False,
            )
        )
    return rows


def insert(db: Session, rows: Sequence[Transaction]) -> None:
    """All rows and their plan updates, one unit of work, not committed."""
    add_transactions_to_ledger(db, rows)


def load_owned(
    db: Session, ctx: UserContext, ids: Sequence[UUID], *, include_deleted=False
) -> List[Transaction]:
    if not ids:
        return []
    query = db.query(Transaction).filter(
        Transaction.user_id == ctx.user_id, Transaction.id.in_(list(ids))
    )
    if not include_deleted:
        query = query.filter(Transaction.deleted_at.is_(None))
    by_id = {row.id: row for row in query.all()}
    return [by_id[i] for i in ids if i in by_id]


def resolve_ref(
    db: Session, ctx: UserContext, keys: DataKeys, ref: str
) -> Tuple[UUID, Optional[Transaction]]:
    """The transaction id behind ``ref`` and its row (None when deleted).

    A reference minted for another user does not decrypt here, so it is
    "not found" — never someone else's expense."""
    txn_id = keys.transaction_id(ctx.user_id, ref)
    if txn_id is None:
        raise ValidationError(NOT_FOUND)
    row = (
        db.query(Transaction)
        .filter(Transaction.id == txn_id, Transaction.user_id == ctx.user_id)
        .first()
    )
    if row is None:
        raise ValidationError(NOT_FOUND)
    return txn_id, (row if row.deleted_at is None else None)


def local_parts(ctx: UserContext, row: Transaction) -> Tuple[date, time]:
    local = row.spent_at
    if local.tzinfo is None:
        local = local.replace(tzinfo=timezone.utc)
    local = local.astimezone(_safe_zone(ctx.timezone))
    return local.date(), local.time()


def apply_update(
    db: Session,
    ctx: UserContext,
    txn_id: UUID,
    *,
    amount: Optional[Decimal],
    category: Optional[str],
    day: Optional[date],
    merchant: Optional[str],
    merchant_sent: bool,
) -> None:
    """The API's update_transaction (commits). Only sent fields change."""
    row = db.get(Transaction, txn_id)
    fields = {}
    if amount is not None:
        fields["amount"] = amount
    if category is not None:
        fields["category"] = category
    if merchant_sent:
        # "" stores an empty merchant, which every reader treats as none: the
        # API's updater cannot set NULL (None means "not sent" there).
        fields["merchant"] = clean_merchant(merchant) or ""
    if day is not None:
        new_day = resolve_day(ctx, day)
        _, local_time = local_parts(ctx, row)
        # Keep the time of day the user recorded; move only the calendar day.
        fields["spent_at"] = datetime.combine(new_day, local_time)
    updated = transaction_services.update_transaction(
        _owner(ctx), txn_id, SimpleNamespace(**fields), db
    )
    if updated is None:
        raise ValidationError(NOT_FOUND)


def apply_delete(db: Session, ctx: UserContext, txn_id: UUID) -> bool:
    """The API's soft delete (commits). False when already deleted."""
    return transaction_services.delete_transaction(_owner(ctx), txn_id, db)


def _owner(ctx: UserContext) -> SimpleNamespace:
    """What the API's updater/deleter read from ``user``: its id and timezone.

    Not the ORM row: the helpers call ``ZoneInfo(user.timezone)`` after their
    commit, which raises for a legacy account whose timezone is NULL — the
    write would be committed but reported as failed. ``ctx.timezone`` is the
    same fallback (UTC) every MITA reader uses for such an account.
    """
    return SimpleNamespace(id=ctx.user_id, timezone=ctx.timezone)


def month_to_date_spent(db: Session, ctx: UserContext) -> Decimal:
    from app.mcp.queries import ledger

    start = date(ctx.today.year, ctx.today.month, 1)
    totals = ledger.totals_by_category(db, ctx, start, ctx.today)
    return sum((t.total for t in totals), Decimal("0.00"))


def local_day(ctx: UserContext, row: Transaction) -> date:
    return local_day_of(row.spent_at, ctx.timezone)

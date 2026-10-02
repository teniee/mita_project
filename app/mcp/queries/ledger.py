"""The ledger: non-deleted transactions, bucketed by the user's local day.

This is the only place the MCP service reads spend from. It mirrors the
filter and bucketing ``rebuild_month_plan`` uses to accrue
``daily_plan.spent_amount`` (``deleted_at IS NULL``, ``local_day_of``), so
budget figures here equal what the app shows once its plan cache is current —
and stay correct when that cache lags.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.mcp.queries.periods import UserContext, utc_window
from app.services.core.engine.expense_tracker import local_day_of

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class LedgerEntry:
    day: date  # user-local calendar day
    amount: Decimal
    currency: str
    category: str
    merchant: Optional[str]


@dataclass(frozen=True)
class LedgerPage:
    entries: List[LedgerEntry]
    has_more: bool
    matching_count: int
    matching_total: Decimal
    other_currencies: Tuple[str, ...]  # recorded currencies other than the user's


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _base_query(db: Session, ctx: UserContext, start: date, end: date):
    lower, upper = utc_window(start, end, ctx.timezone)
    return db.query(Transaction).filter(
        Transaction.user_id == ctx.user_id,
        Transaction.deleted_at.is_(None),
        Transaction.spent_at >= lower,
        Transaction.spent_at < upper,
    )


def list_entries(
    db: Session,
    ctx: UserContext,
    start: date,
    end: date,
    *,
    category: Optional[str] = None,
    merchant: Optional[str] = None,
    limit: int = 50,
) -> LedgerPage:
    query = _base_query(db, ctx, start, end)
    if category:
        query = query.filter(func.lower(Transaction.category) == category.lower())
    if merchant:
        query = query.filter(
            Transaction.merchant.ilike(f"%{_escape_like(merchant)}%", escape="\\")
        )

    count, total = query.with_entities(
        func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0)
    ).one()

    rows = (
        query.with_entities(
            Transaction.spent_at,
            Transaction.amount,
            Transaction.currency,
            Transaction.category,
            Transaction.merchant,
        )
        .order_by(Transaction.spent_at.desc(), Transaction.id.desc())
        .limit(limit + 1)
        .all()
    )
    entries = [
        LedgerEntry(
            day=local_day_of(spent_at, ctx.timezone),
            amount=Decimal(str(amount)),
            currency=(currency or ctx.currency).upper(),
            category=category_name,
            merchant=(merchant_name or "").strip() or None,
        )
        for spent_at, amount, currency, category_name, merchant_name in rows[:limit]
    ]
    return LedgerPage(
        entries=entries,
        has_more=len(rows) > limit,
        matching_count=int(count),
        matching_total=Decimal(str(total)),
        other_currencies=_other_currencies(query, ctx),
    )


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    total: Decimal
    count: int


def totals_by_category(
    db: Session, ctx: UserContext, start: date, end: date
) -> List[CategoryTotal]:
    rows = (
        _base_query(db, ctx, start, end)
        .with_entities(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0),
            func.count(Transaction.id),
        )
        .group_by(Transaction.category)
        .all()
    )
    totals = [
        CategoryTotal(category=c, total=Decimal(str(t)), count=int(n))
        for c, t, n in rows
    ]
    return sorted(totals, key=lambda item: (-item.total, item.category))


def spend_by_day_and_category(
    db: Session, ctx: UserContext, start: date, end: date
) -> Dict[Tuple[date, str], Decimal]:
    """Ledger spend keyed exactly as ``rebuild_month_plan`` keys plan rows."""
    rows = (
        _base_query(db, ctx, start, end)
        .with_entities(Transaction.spent_at, Transaction.category, Transaction.amount)
        .all()
    )
    totals: Dict[Tuple[date, str], Decimal] = defaultdict(lambda: ZERO)
    for spent_at, category, amount in rows:
        if category:
            totals[(local_day_of(spent_at, ctx.timezone), category)] += Decimal(
                str(amount or 0)
            )
    return dict(totals)


def other_currencies_in_range(
    db: Session, ctx: UserContext, start: date, end: date
) -> Tuple[str, ...]:
    return _other_currencies(_base_query(db, ctx, start, end), ctx)


def _other_currencies(query, ctx: UserContext) -> Tuple[str, ...]:
    """Recorded transaction currencies that differ from the user's currency.

    MITA aggregates every amount in the user's currency without conversion;
    a different recorded code is surfaced so ChatGPT can say so instead of
    silently presenting a mixed sum.
    """
    rows = (
        query.with_entities(func.upper(Transaction.currency))
        .filter(
            Transaction.currency.isnot(None),
            func.upper(Transaction.currency) != ctx.currency,
        )
        .distinct()
        .all()
    )
    return tuple(sorted(c for (c,) in rows if c))

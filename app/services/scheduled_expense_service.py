"""
Scheduled Expense Service — async DB operations for the API layer.

Called from API routes (AsyncSession).
The cron task uses its own sync implementations (see cron_task_scheduled_expenses.py).

Responsibilities:
• CRUD for ScheduledExpense rows
• Impact computation (delegates to the pure engine)
• No business-logic duplication — reuses scheduled_expense_engine.py
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.daily_plan import DailyPlan
from app.db.models.scheduled_expense import ScheduledExpense
from app.services.core.engine.scheduled_expense_engine import (
    DailyBudgetData,
    ScheduledExpenseData,
    ScheduledImpactResult,
    compute_scheduled_impact,
)

logger = logging.getLogger(__name__)


# ─── Read ─────────────────────────────────────────────────────────────────────


async def get_all_expenses(
    db: AsyncSession,
    user_id: UUID,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[ScheduledExpense]:
    """List all scheduled expenses for a user (not soft-deleted), newest first."""
    filters = [
        ScheduledExpense.user_id == user_id,
        ScheduledExpense.deleted_at.is_(None),
    ]
    if status:
        filters.append(ScheduledExpense.status == status)
    if from_date:
        filters.append(ScheduledExpense.scheduled_date >= from_date)
    if to_date:
        filters.append(ScheduledExpense.scheduled_date <= to_date)

    result = await db.execute(
        select(ScheduledExpense)
        .where(and_(*filters))
        .order_by(ScheduledExpense.scheduled_date.desc())
    )
    return list(result.scalars().all())


async def get_pending_expenses(
    db: AsyncSession,
    user_id: UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> List[ScheduledExpense]:
    """Return only pending expenses (not processed/cancelled/failed)."""
    if from_date is None:
        from_date = date.today()

    filters = [
        ScheduledExpense.user_id == user_id,
        ScheduledExpense.status == "pending",
        ScheduledExpense.deleted_at.is_(None),
        ScheduledExpense.scheduled_date >= from_date,
    ]
    if to_date:
        filters.append(ScheduledExpense.scheduled_date <= to_date)

    result = await db.execute(
        select(ScheduledExpense)
        .where(and_(*filters))
        .order_by(ScheduledExpense.scheduled_date)
    )
    return list(result.scalars().all())


async def get_expense_by_id(
    db: AsyncSession,
    expense_id: UUID,
    user_id: UUID,
) -> Optional[ScheduledExpense]:
    result = await db.execute(
        select(ScheduledExpense).where(
            and_(
                ScheduledExpense.id == expense_id,
                ScheduledExpense.user_id == user_id,
                ScheduledExpense.deleted_at.is_(None),
            )
        )
    )
    return result.scalar_one_or_none()


# ─── Write ────────────────────────────────────────────────────────────────────


async def create_scheduled_expense(
    db: AsyncSession,
    user_id: UUID,
    category: str,
    amount: Decimal,
    scheduled_date: date,
    description: Optional[str] = None,
    merchant: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> ScheduledExpense:
    """Create a new scheduled expense row.  Caller commits the session."""
    expense = ScheduledExpense(
        user_id=user_id,
        category=category,
        amount=amount,
        scheduled_date=scheduled_date,
        description=description,
        merchant=merchant,
        recurrence=recurrence,
        status="pending",
    )
    db.add(expense)
    await db.flush()  # assign id before returning

    logger.info(
        "scheduled_expense: created id=%s user=%s cat=%s amount=%.2f date=%s",
        expense.id,
        user_id,
        category,
        float(amount),
        scheduled_date,
    )
    return expense


async def cancel_scheduled_expense(
    db: AsyncSession,
    expense_id: UUID,
    user_id: UUID,
) -> Optional[ScheduledExpense]:
    """
    Soft-cancel a pending scheduled expense.

    Returns:
        The expense (updated or already non-pending) — or None if not found.
    """
    expense = await get_expense_by_id(db, expense_id, user_id)
    if expense is None:
        return None

    if expense.status != "pending":
        # Already processed / cancelled — return as-is (idempotent)
        return expense

    expense.status = "cancelled"
    expense.deleted_at = datetime.utcnow()
    await db.flush()

    logger.info(
        "scheduled_expense: cancelled id=%s user=%s", expense_id, user_id
    )
    return expense


# ─── Impact computation ───────────────────────────────────────────────────────


async def get_impact(
    db: AsyncSession,
    user_id: UUID,
    year: int,
    month: int,
    preview_expense: Optional[ScheduledExpenseData] = None,
) -> ScheduledImpactResult:
    """
    Compute how pending scheduled expenses affect safe_daily_limit.

    Args:
        preview_expense: if provided, include it in the calculation even though
                         it hasn't been saved yet (used by POST endpoint to show
                         impact immediately upon creation).

    Returns:
        ScheduledImpactResult with adjusted_safe_daily_limit and per-expense breakdown.
    """
    today = date.today()
    last_day = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    # ── Fetch pending scheduled expenses ─────────────────────────────────────
    pending = await get_pending_expenses(db, user_id, month_start, month_end)
    expense_data: List[ScheduledExpenseData] = [
        ScheduledExpenseData(
            expense_id=str(e.id),
            category=e.category,
            amount=Decimal(str(e.amount)),
            scheduled_date=e.scheduled_date,
            description=e.description,
            merchant=e.merchant,
        )
        for e in pending
    ]
    if preview_expense is not None:
        expense_data.append(preview_expense)

    # ── Fetch DailyPlan rows for this month ───────────────────────────────────
    month_start_dt = datetime(year, month, 1, 0, 0, 0)
    month_end_dt = datetime(year, month, last_day, 23, 59, 59)

    result = await db.execute(
        select(DailyPlan).where(
            and_(
                DailyPlan.user_id == user_id,
                DailyPlan.date >= month_start_dt,
                DailyPlan.date <= month_end_dt,
            )
        )
    )
    plans_orm = result.scalars().all()

    plan_data: List[DailyBudgetData] = [
        DailyBudgetData(
            date=p.date.date() if isinstance(p.date, datetime) else p.date,
            category=p.category or "",
            planned_amount=Decimal(str(p.planned_amount or 0)),
            spent_amount=Decimal(str(p.spent_amount or 0)),
        )
        for p in plans_orm
    ]

    return compute_scheduled_impact(expense_data, plan_data, today)

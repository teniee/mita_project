"""
Scheduled Expenses API — Problem 6 fix.

User schedules a future expense → MITA:
  • immediately shows the impact on safe_daily_limit
  • sends a push reminder 3 days before
  • auto-creates the transaction + rebalances on the scheduled date

Endpoints:
  POST   /scheduled-expenses/              create + return budget impact
  GET    /scheduled-expenses/              list (filterable)
  GET    /scheduled-expenses/impact        month-level impact summary
  GET    /scheduled-expenses/{id}          single expense
  DELETE /scheduled-expenses/{id}          cancel (soft) + return updated impact
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db
from app.db.models.user import User
from app.services.scheduled_expense_service import (
    cancel_scheduled_expense,
    create_scheduled_expense,
    get_all_expenses,
    get_expense_by_id,
    get_impact,
)
from app.services.core.engine.scheduled_expense_engine import ScheduledExpenseData
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-expenses", tags=["scheduled-expenses"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class ScheduledExpenseIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=Decimal("0"), le=Decimal("100000"))
    scheduled_date: date
    description: Optional[str] = Field(None, max_length=500)
    merchant: Optional[str] = Field(None, max_length=200)
    recurrence: Optional[str] = Field(
        None,
        description="Repeat pattern: 'once', 'weekly', or 'monthly'",
    )

    @field_validator("scheduled_date")
    @classmethod
    def must_be_today_or_future(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("scheduled_date must be today or in the future")
        return v

    @field_validator("recurrence")
    @classmethod
    def valid_recurrence(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"once", "weekly", "monthly"}:
            raise ValueError("recurrence must be 'once', 'weekly', or 'monthly'")
        return v

    @field_validator("amount")
    @classmethod
    def round_to_cents(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/", response_model=None)
async def create_expense(
    body: ScheduledExpenseIn,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Schedule a future expense.

    Returns the new expense record plus its immediate impact on
    safe_daily_limit for the current month.
    """
    expense = await create_scheduled_expense(
        db=db,
        user_id=user.id,
        category=body.category,
        amount=body.amount,
        scheduled_date=body.scheduled_date,
        description=body.description,
        merchant=body.merchant,
        recurrence=body.recurrence,
    )
    await db.commit()

    # Compute impact for the month of the scheduled date so the caller
    # can immediately show the adjusted safe_daily_limit.
    impact = await get_impact(
        db, user.id, body.scheduled_date.year, body.scheduled_date.month
    )

    return success_response(
        {
            "expense": _to_dict(expense),
            "budget_impact": impact.to_dict(),
        },
        "Scheduled expense created",
    )


@router.get("/", response_model=None)
async def list_expenses(
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """List all scheduled expenses for the current user."""
    expenses = await get_all_expenses(db, user.id, status, from_date, to_date)
    return success_response([_to_dict(e) for e in expenses])


@router.get("/impact", response_model=None)
async def budget_impact(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Get how all pending scheduled expenses affect safe_daily_limit.

    Returns:
        adjusted_safe_daily_limit — daily budget after reserving for
        all scheduled expenses, plus a per-expense breakdown.
    """
    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month

    if not (2020 <= y <= 2030):
        raise HTTPException(status_code=422, detail="year must be between 2020 and 2030")
    if not (1 <= m <= 12):
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")

    impact = await get_impact(db, user.id, y, m)
    return success_response(impact.to_dict())


@router.get("/{expense_id}", response_model=None)
async def get_expense(
    expense_id: UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get a single scheduled expense by ID."""
    expense = await get_expense_by_id(db, expense_id, user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Scheduled expense not found")
    return success_response(_to_dict(expense))


@router.delete("/{expense_id}", response_model=None)
async def cancel_expense(
    expense_id: UUID,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Cancel a pending scheduled expense.

    Returns the updated expense plus the recalculated budget_impact
    so the mobile app can refresh safe_daily_limit immediately.
    """
    expense = await cancel_scheduled_expense(db, expense_id, user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Scheduled expense not found")

    await db.commit()

    now = datetime.utcnow()
    impact = await get_impact(db, user.id, now.year, now.month)

    return success_response(
        {
            "expense": _to_dict(expense),
            "budget_impact": impact.to_dict(),
        },
        "Scheduled expense cancelled",
    )


# ─── Helper ───────────────────────────────────────────────────────────────────


def _to_dict(expense) -> dict:
    return {
        "id": str(expense.id),
        "user_id": str(expense.user_id),
        "category": expense.category,
        "amount": float(expense.amount),
        "scheduled_date": (
            expense.scheduled_date.isoformat()
            if expense.scheduled_date
            else None
        ),
        "description": expense.description,
        "merchant": expense.merchant,
        "recurrence": expense.recurrence,
        "status": expense.status,
        "reminder_sent_at": (
            expense.reminder_sent_at.isoformat()
            if expense.reminder_sent_at
            else None
        ),
        "processed_at": (
            expense.processed_at.isoformat() if expense.processed_at else None
        ),
        "transaction_id": (
            str(expense.transaction_id) if expense.transaction_id else None
        ),
        "created_at": (
            expense.created_at.isoformat() if expense.created_at else None
        ),
    }

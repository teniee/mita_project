"""Creating a savings goal the way the API creates one.

``Goal`` built as ``POST /api/goals/`` builds it (``update_progress`` included),
then ``goal_budget_sync.sync_goal_to_daily_plan`` reserves the daily amounts
in the current month's plan — inside a SAVEPOINT and non-blocking, exactly
as the API treats it: a failed reservation never fails the goal. (Backend
finding F-1: with a second dated goal the reservation hits
``uq_daily_plan_user_date_category``; the API answers 500 after committing
the goal, MITA's ChatGPT path saves the goal and says the reservation was not
made.)

Differences from the API, on purpose: no Premium gate (v1 is free), and no
push notification (Firebase is not in the MCP image).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyPlan, Goal
from app.mcp.queries.periods import UserContext
from app.services.core.engine.goal_budget_sync import (
    calculate_required_monthly_contribution,
    sync_goal_to_daily_plan,
)


def build_goal(
    ctx: UserContext,
    *,
    title: str,
    target_amount: Decimal,
    saved_amount: Decimal,
    target_date: Optional[date],
    category: str,
) -> Goal:
    goal = Goal(
        user_id=ctx.user_id,
        title=title,
        description=None,
        category=category,
        target_amount=target_amount,
        saved_amount=saved_amount,
        monthly_contribution=None,
        target_date=target_date,
        priority="medium",
        status="active",
    )
    goal.update_progress()
    return goal


async def reserve_in_plan(session: AsyncSession, goal: Goal, ctx: UserContext) -> bool:
    """True when the daily reservation was written; False when it failed (the
    goal is kept either way)."""
    try:
        async with session.begin_nested():
            await sync_goal_to_daily_plan(session, goal, ctx.user_id, today=ctx.today)
        return True
    except Exception:  # noqa: BLE001 - the API treats this step as non-blocking
        return False


def required_monthly(goal: Goal, today: date) -> Decimal:
    """The canonical figure (30.44-day months, at least one month)."""
    return calculate_required_monthly_contribution(goal, today)


async def has_reservation(session: AsyncSession, goal: Goal) -> bool:
    """Whether the goal currently has daily amounts set aside in the plan."""
    return bool(
        await session.scalar(select(exists().where(DailyPlan.goal_id == goal.id)))
    )

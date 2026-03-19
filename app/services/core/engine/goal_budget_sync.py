"""
Goal-Budget Sync Engine — MITA Problem 4 fix.

Core promise: when a user creates (or updates) a goal with a target_date,
the required daily savings are automatically reserved in DailyPlan as
SACRED rows.  This prevents the rebalancer from consuming money that is
earmarked for goal savings, and keeps the "safe daily limit" shown to the
user honest.

Design principles
─────────────────
• Pure computation helpers are synchronous — trivially unit-testable.
• DB operations are async (matches the goals API stack — AsyncSession).
• Sync is idempotent: calling it twice produces the same result.
• Only present and future days are created/updated. Past rows are
  never modified (historical integrity).
• When a goal is paused, completed, cancelled, or deleted — all future
  reservation rows are removed, freeing up the daily budget.
• Failures are non-blocking: if sync fails, goal CRUD still succeeds.
  The caller wraps this in try/except and logs the error.

Category used: "goal_savings"
  Registered as SACRED in category_priority.py — the rebalancer will
  never use these rows as donors when balancing other categories.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.daily_plan import DailyPlan
from app.db.models.goal import Goal

logger = logging.getLogger(__name__)

# Category name for goal savings rows in DailyPlan.
# Must match the entry added to category_priority.CATEGORY_PRIORITY.
GOAL_SAVINGS_CATEGORY = "goal_savings"

# Goal statuses that mean "not actively saving right now".
# Future DailyPlan rows must be released when a goal enters any of these.
_INACTIVE_STATUSES = frozenset({"paused", "cancelled", "completed"})


# ─────────────────────────────────────────────────────────────────────────────
# Pure computation helpers (synchronous, no DB access)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_required_monthly_contribution(
    goal: Goal,
    today: date,
) -> Decimal:
    """
    How much must be saved per month to reach goal.target_amount by
    goal.target_date given what has already been saved.

    Returns Decimal("0") when:
        • goal has no target_date
        • goal is paused, cancelled, or completed
        • target_date is today or in the past (can't save retroactively)
        • goal is already fully funded (saved_amount >= target_amount)

    We intentionally ignore goal.monthly_contribution (the user-supplied
    hint) and recompute from first principles so DailyPlan stays accurate
    when the user modifies target_amount, saved_amount, or target_date.
    """
    if not goal.target_date:
        return Decimal("0")
    if goal.status in _INACTIVE_STATUSES:
        return Decimal("0")
    if goal.target_date <= today:
        return Decimal("0")

    remaining = (
        Decimal(str(goal.target_amount)) - Decimal(str(goal.saved_amount))
    ).quantize(Decimal("0.01"), ROUND_HALF_UP)

    if remaining <= Decimal("0"):
        return Decimal("0")

    # Fractional months remaining — 30.44 days/month average.
    # Floor at 1 month to avoid dividing near-zero on very tight deadlines.
    delta_days = (goal.target_date - today).days
    months = Decimal(str(delta_days)) / Decimal("30.44")
    months = max(months, Decimal("1"))

    return (remaining / months).quantize(Decimal("0.01"), ROUND_HALF_UP)


def calculate_daily_savings_amount(
    monthly_contribution: Decimal,
    year: int,
    month: int,
) -> Decimal:
    """
    Daily savings = monthly_contribution / days_in_month.

    We divide by the *total* days in the month (not the remaining days)
    so the daily reservation is constant throughout the month.  If a goal
    is created mid-month, rows are inserted only for remaining days — the
    "missed" past days are accepted as a partial-month shortfall, which is
    honest and predictable for the user.
    """
    if monthly_contribution <= Decimal("0"):
        return Decimal("0")
    days_in_month = calendar.monthrange(year, month)[1]
    return (monthly_contribution / Decimal(str(days_in_month))).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async DB operations
# ─────────────────────────────────────────────────────────────────────────────

async def sync_goal_to_daily_plan(
    db: AsyncSession,
    goal: Goal,
    user_id: UUID,
    today: Optional[date] = None,
) -> Tuple[int, int]:
    """
    Synchronise one goal's required daily savings into DailyPlan.

    Active goal with target_date
        → upsert SACRED rows (category="goal_savings", goal_id=goal.id)
          for every remaining day of the *current* month.

    Inactive goal (paused/cancelled/completed) OR no target_date
        → delete all future rows for this goal (free up budget).

    Idempotent — safe to call multiple times; the result is always the
    same regardless of current DailyPlan state.

    The caller is responsible for committing the session.

    Returns
    ───────
    (upserted_count, removed_count)
    """
    if today is None:
        today = date.today()

    goal_id: UUID = goal.id
    year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]

    monthly = calculate_required_monthly_contribution(goal, today)
    daily = calculate_daily_savings_amount(monthly, year, month)

    if monthly <= Decimal("0") or daily <= Decimal("0"):
        # Goal inactive or already fully funded — release future reservations.
        removed = await remove_goal_daily_plan_rows(
            db, goal_id, user_id, from_date=today
        )
        logger.info(
            "goal_sync: freed=%d rows goal=%s user=%s reason=inactive_or_funded",
            removed,
            goal_id,
            user_id,
        )
        return 0, removed

    # Upsert one SACRED row per remaining day of the current month.
    upserted = 0
    for day_num in range(today.day, last_day + 1):
        day_start = datetime(year, month, day_num, 0, 0, 0)
        day_end = datetime(year, month, day_num, 23, 59, 59)

        result = await db.execute(
            select(DailyPlan).where(
                and_(
                    DailyPlan.user_id == user_id,
                    DailyPlan.goal_id == goal_id,
                    DailyPlan.date >= day_start,
                    DailyPlan.date <= day_end,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Update planned_amount in case goal parameters changed.
            # Never touch spent_amount — it tracks actual savings deposits.
            existing.planned_amount = daily
        else:
            db.add(
                DailyPlan(
                    user_id=user_id,
                    goal_id=goal_id,
                    date=datetime(year, month, day_num, 0, 0, 0),
                    category=GOAL_SAVINGS_CATEGORY,
                    planned_amount=daily,
                    spent_amount=Decimal("0"),
                    status="green",
                )
            )

        upserted += 1

    await db.flush()

    logger.info(
        "goal_sync: upserted=%d rows goal=%s user=%s "
        "daily=%.2f monthly=%.2f days=%d-%d",
        upserted,
        goal_id,
        user_id,
        float(daily),
        float(monthly),
        today.day,
        last_day,
    )
    return upserted, 0


async def remove_goal_daily_plan_rows(
    db: AsyncSession,
    goal_id: UUID,
    user_id: UUID,
    from_date: Optional[date] = None,
) -> int:
    """
    Bulk-delete future DailyPlan rows tied to this goal.

    Only rows from from_date onwards (inclusive) are removed.
    Past rows are preserved for historical accuracy and audit.

    Returns: count of deleted rows.
    """
    if from_date is None:
        from_date = date.today()

    from_dt = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)

    result = await db.execute(
        delete(DailyPlan).where(
            and_(
                DailyPlan.user_id == user_id,
                DailyPlan.goal_id == goal_id,
                DailyPlan.date >= from_dt,
            )
        )
    )
    return result.rowcount

"""Budget allocation (``daily_plan``) joined with ledger spend.

Allocation comes from persisted plan rows only. A month the app has not
materialized yet has no allocation here — this layer never calls
``ensure_month_plan`` (it writes) and never computes a preview.

Lines are grouped for display by ``app.mcp.categories`` (an expense category
is shown with its paired plan bucket, e.g. ``gas`` with ``transport gas``);
every figure is still a sum of stored rows.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.category_priority import is_set_aside
from app.db.models import DailyPlan
from app.mcp.categories import group_lines, regroup_by_day
from app.mcp.queries import ledger
from app.mcp.queries.periods import UserContext, month_days, month_position
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    ForecastResult,
    compute_forecast,
)
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.monthly_plan_service import month_bounds, month_has_plan

ZERO = Decimal("0.00")


def planned_by_day_and_category(
    db: Session, ctx: UserContext, year: int, month: int
) -> Dict[Tuple[date, str], Decimal]:
    start, end = month_bounds(year, month)
    rows = (
        db.query(DailyPlan.date, DailyPlan.category, DailyPlan.planned_amount)
        .filter(
            DailyPlan.user_id == ctx.user_id,
            DailyPlan.date >= start,
            DailyPlan.date < end,
        )
        .all()
    )
    planned: Dict[Tuple[date, str], Decimal] = defaultdict(lambda: ZERO)
    for row_date, category, amount in rows:
        # daily_plan.date is midnight UTC of the user's LOCAL day; its UTC
        # date is that local day (monthly_plan_service invariant).
        day = row_date.date() if hasattr(row_date, "date") else row_date
        planned[(day, category or "uncategorized")] += Decimal(str(amount or 0))
    return dict(planned)


def redistributed_total(
    db: Session, ctx: UserContext, year: int, month: int
) -> Decimal:
    """Money MITA's in-month redistribution moved INTO categories this month
    (the positive ``_mita_realtime_adjustment_v1`` amounts)."""
    start, end = month_bounds(year, month)
    rows = (
        db.query(DailyPlan.plan_json)
        .filter(
            DailyPlan.user_id == ctx.user_id,
            DailyPlan.date >= start,
            DailyPlan.date < end,
        )
        .all()
    )
    moved = ZERO
    for (meta,) in rows:
        if isinstance(meta, dict):
            adjustment = Decimal(str(meta.get(REALTIME_ADJUSTMENT_KEY) or 0))
            if adjustment > ZERO:
                moved += adjustment
    return moved


@dataclass(frozen=True)
class CategoryStatus:
    category: str
    planned: Decimal
    spent: Decimal
    label: str = ""
    codes: Tuple[str, ...] = ()

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent


@dataclass(frozen=True)
class DayStatus:
    day: date
    planned: Decimal
    spent: Decimal


@dataclass(frozen=True)
class BudgetStatus:
    year: int
    month: int
    position: str  # past | current | future
    plan_generated: bool
    categories: List[CategoryStatus]
    total_planned: Decimal
    total_spent: Decimal
    today: Optional[DayStatus]
    other_currencies: Tuple[str, ...]
    redistributed: Decimal = ZERO


def _merged_buckets(
    db: Session, ctx: UserContext, year: int, month: int
) -> Tuple[Dict[Tuple[date, str], Decimal], Dict[Tuple[date, str], Decimal]]:
    first, last = month_days(year, month)
    planned = planned_by_day_and_category(db, ctx, year, month)
    spent = ledger.spend_by_day_and_category(db, ctx, first, last)
    return planned, spent


def budget_status(
    db: Session,
    ctx: UserContext,
    year: int,
    month: int,
    *,
    with_redistribution: bool = True,
) -> BudgetStatus:
    plan_generated = month_has_plan(db, ctx.user_id, year, month)
    planned, spent = _merged_buckets(db, ctx, year, month)

    planned_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    spent_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (_, category), amount in planned.items():
        planned_by_cat[category] += amount
    for (_, category), amount in spent.items():
        spent_by_cat[category] += amount

    categories = sorted(
        (
            CategoryStatus(
                category=key,
                planned=line_planned,
                spent=line_spent,
                label=name,
                codes=tuple(codes),
            )
            for key, name, codes, line_planned, line_spent in group_lines(
                planned_by_cat, spent_by_cat
            )
        ),
        key=lambda item: (-item.planned, -item.spent, item.category),
    )

    position = month_position(ctx, year, month)
    today = None
    if position == "current":
        # Today's spending allocations: a line that sets money aside (savings,
        # goal reservations) is not something to spend today.
        today = DayStatus(
            day=ctx.today,
            planned=sum(
                (
                    v
                    for (d, c), v in planned.items()
                    if d == ctx.today and not is_set_aside(c)
                ),
                ZERO,
            ),
            spent=sum(
                (
                    v
                    for (d, c), v in spent.items()
                    if d == ctx.today and not is_set_aside(c)
                ),
                ZERO,
            ),
        )

    first, last = month_days(year, month)
    return BudgetStatus(
        year=year,
        month=month,
        position=position,
        plan_generated=plan_generated,
        categories=categories,
        total_planned=sum(planned.values(), ZERO),
        total_spent=sum(spent.values(), ZERO),
        today=today,
        other_currencies=ledger.other_currencies_in_range(db, ctx, first, last),
        redistributed=(
            redistributed_total(db, ctx, year, month)
            if plan_generated and with_redistribution
            else ZERO
        ),
    )


@dataclass(frozen=True)
class MonthForecast:
    year: int
    month: int
    position: str
    plan_generated: bool
    result: Optional[ForecastResult]


def month_forecast(
    db: Session, ctx: UserContext, year: int, month: int
) -> MonthForecast:
    """``compute_forecast`` over persisted allocation + ledger spend.

    The engine is called with the user's LOCAL today. Goals are reported by
    the goals tool, so none are passed here.
    """
    position = month_position(ctx, year, month)
    if not month_has_plan(db, ctx.user_id, year, month):
        return MonthForecast(year, month, position, False, None)

    planned, spent = _merged_buckets(db, ctx, year, month)
    buckets = {category for _, category in planned}
    planned = regroup_by_day(planned, buckets)
    spent = regroup_by_day(spent, buckets)
    keys = set(planned) | set(spent)
    plan_data = [
        DailyPlanData(
            date=day,
            category=category,
            planned_amount=planned.get((day, category), ZERO),
            spent_amount=spent.get((day, category), ZERO),
        )
        for day, category in sorted(keys)
    ]
    result = compute_forecast(
        daily_plans=plan_data, goals=[], year=year, month=month, today=ctx.today
    )
    return MonthForecast(year, month, position, True, result)

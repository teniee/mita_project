"""Budget allocation (``daily_plan``) joined with ledger spend.

Allocation comes from persisted plan rows only. A month the app has not
materialized yet has no allocation here — this layer never calls
``ensure_month_plan`` (it writes) and never computes a preview.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import DailyPlan
from app.mcp.queries import ledger
from app.mcp.queries.periods import UserContext, month_days, month_position
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    ForecastResult,
    compute_forecast,
)
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


@dataclass(frozen=True)
class CategoryStatus:
    category: str
    planned: Decimal
    spent: Decimal

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


def _merged_buckets(
    db: Session, ctx: UserContext, year: int, month: int
) -> Tuple[Dict[Tuple[date, str], Decimal], Dict[Tuple[date, str], Decimal]]:
    first, last = month_days(year, month)
    planned = planned_by_day_and_category(db, ctx, year, month)
    spent = ledger.spend_by_day_and_category(db, ctx, first, last)
    return planned, spent


def budget_status(db: Session, ctx: UserContext, year: int, month: int) -> BudgetStatus:
    plan_generated = month_has_plan(db, ctx.user_id, year, month)
    planned, spent = _merged_buckets(db, ctx, year, month)

    planned_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    spent_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (_, category), amount in planned.items():
        planned_by_cat[category] += amount
    for (_, category), amount in spent.items():
        spent_by_cat[category] += amount

    names = set(planned_by_cat) | set(spent_by_cat)
    categories = sorted(
        (
            CategoryStatus(
                category=name,
                planned=planned_by_cat.get(name, ZERO),
                spent=spent_by_cat.get(name, ZERO),
            )
            for name in names
        ),
        key=lambda item: (-item.planned, -item.spent, item.category),
    )

    position = month_position(ctx, year, month)
    today = None
    if position == "current":
        today = DayStatus(
            day=ctx.today,
            planned=sum((v for (d, _), v in planned.items() if d == ctx.today), ZERO),
            spent=sum((v for (d, _), v in spent.items() if d == ctx.today), ZERO),
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

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
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.category_priority import is_set_aside
from app.db.models import DailyPlan
from app.mcp.categories import group_lines, line_key, line_source, regroup_by_day
from app.mcp.queries import ledger
from app.mcp.queries.periods import UserContext, month_days, month_position
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    ForecastResult,
    commitment_expectations,
    compute_forecast,
    is_bill_line,
    is_recordable,
)
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.monthly_obligations import obligations_due
from app.services.monthly_plan_service import (
    month_base_plan,
    month_bounds,
    month_has_plan,
)

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
    # Who decides the line's amount (categories.line_source); None for
    # spending with nothing planned.
    source: Optional[str] = None

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent


@dataclass(frozen=True)
class DayStatus:
    day: date
    planned: Decimal
    spent: Decimal
    # the same day without bill lines (R3): what today's plan leaves for
    # everything that is not a bill or money set aside
    everyday_planned: Decimal = ZERO
    everyday_spent: Decimal = ZERO


def bill_line_keys(
    codes: Iterable[str], buckets: Set[str], due_categories: Iterable[str]
) -> Set[str]:
    """The budget lines that are bills (R3, ``commitment_expectations``): the
    lines holding an essential MITA can see paid (``is_bill_line``) and the
    lines of the recordable categories of saved payments that count in the
    month. The calendar's "Bills & commitments" group and ``today``'s
    everyday figures use this one rule."""
    return {line_key(c, buckets) for c in codes if is_bill_line(c)} | {
        line_key(c, buckets) for c in due_categories if is_recordable(c)
    }


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
                source=line_source(codes, line_planned),
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
        # goal reservations) is not something to spend today; a bill line is
        # not free to spend either (R3), so the everyday figures leave it out.
        buckets = {c for _, c in planned}
        bills = bill_line_keys(
            {c for _, c in planned} | {c for _, c in spent},
            buckets,
            obligations_due(db, ctx.user_id, year, month),
        )

        def day_sum(amounts, everyday_only: bool) -> Decimal:
            return sum(
                (
                    v
                    for (d, c), v in amounts.items()
                    if d == ctx.today
                    and not is_set_aside(c)
                    and not (everyday_only and line_key(c, buckets) in bills)
                ),
                ZERO,
            )

        today = DayStatus(
            day=ctx.today,
            planned=day_sum(planned, False),
            spent=day_sum(spent, False),
            everyday_planned=day_sum(planned, True),
            everyday_spent=day_sum(spent, True),
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
    commitments = month_commitments(db, ctx, year, month, planned)
    result = forecast_from_rows(planned, spent, year, month, ctx.today, commitments)
    return MonthForecast(year, month, position, True, result)


def month_commitments(
    db: Session,
    ctx: UserContext,
    year: int,
    month: int,
    planned: Mapping[Tuple[date, str], Decimal],
) -> Dict[str, Decimal]:
    """What each bill needs this month (``commitment_expectations``), computed
    on the stored categories exactly as the mobile API computes it — the
    reviewed plan, rebalancing backed out, or the saved payments due — and
    then keyed by the budget line it is shown on. A bill shown on a paired
    line ("public_transport" on "transport public") never takes that line's
    everyday allowance with it."""
    base: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (_, category), amount in month_base_plan(db, ctx.user_id, year, month).items():
        base[category] += amount
    needs = commitment_expectations(base, obligations_due(db, ctx.user_id, year, month))
    buckets = {category for _, category in planned}
    by_line: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for category, need in needs.items():
        by_line[line_key(category, buckets)] += need
    return dict(by_line)


def forecast_from_rows(
    planned: Dict[Tuple[date, str], Decimal],
    spent: Dict[Tuple[date, str], Decimal],
    year: int,
    month: int,
    today: date,
    commitments: Optional[Mapping[str, Decimal]] = None,
) -> ForecastResult:
    """The forecast engine over per-(day, category) plan and spend, regrouped
    by budget line exactly as ``get_budget_forecast`` does. Shared with the
    calendar so both report the same safe daily figure. ``commitments``:
    ``month_commitments`` (unpaid bills are kept out of the safe daily figure)."""
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
    return compute_forecast(
        daily_plans=plan_data,
        goals=[],
        year=year,
        month=month,
        today=today,
        commitments=commitments,
    )

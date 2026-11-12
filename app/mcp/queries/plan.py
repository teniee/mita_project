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
from app.mcp.categories import group_lines, line_key, line_source, regroup_by_day
from app.mcp.queries import ledger
from app.mcp.queries.obligations import obligation_names
from app.mcp.queries.periods import UserContext, month_days, month_position
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    ForecastResult,
    compute_forecast,
)
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.core.engine.spending_schedule import line_kinds_of
from app.services.monthly_plan_service import (
    base_planned_amount,
    budget_rows,
    month_plan_rows,
)
from app.services.obligation_lines import MonthCommitments, is_bill_key
from app.services.obligation_lines import month_commitments as shared_commitments
from app.services.obligation_lines import month_is_keyed

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class MonthPlan:
    """One read of the month's ``daily_plan`` rows and everything the
    status, the forecast and the calendar derive from it."""

    # every row, as stored: (local day, line) -> planned_amount
    planned: Dict[Tuple[date, str], Decimal]
    # real budget rows with every in-month adjustment backed out (the
    # reviewed plan, ``monthly_plan_service.month_base_plan``)
    base: Dict[Tuple[date, str], Decimal]
    # line kinds stamped on the rows (``spending_schedule``); empty = legacy
    kinds: Dict[str, str]
    generated: bool  # ``month_has_plan``
    # money MITA's in-month redistribution moved INTO lines (the positive
    # ``_mita_realtime_adjustment_v1`` amounts)
    redistributed: Decimal

    @property
    def keyed(self) -> bool:
        return month_is_keyed(c for _, c in self.planned)

    def base_by_line(self) -> Dict[str, Decimal]:
        totals: Dict[str, Decimal] = defaultdict(lambda: ZERO)
        for (_, line), amount in self.base.items():
            totals[line] += amount
        return dict(totals)


def month_plan(db: Session, ctx: UserContext, year: int, month: int) -> MonthPlan:
    """The month's plan rows, read once (an indexed range scan)."""
    rows = month_plan_rows(db, ctx.user_id, year, month)
    planned: Dict[Tuple[date, str], Decimal] = defaultdict(lambda: ZERO)
    moved = ZERO
    for row in rows:
        # daily_plan.date is midnight UTC of the user's LOCAL day; its UTC
        # date is that local day (monthly_plan_service invariant).
        day = row.date.date() if hasattr(row.date, "date") else row.date
        planned[(day, row.category or "uncategorized")] += Decimal(
            str(row.planned_amount or 0)
        )
        meta = row.plan_json if isinstance(row.plan_json, dict) else {}
        adjustment = Decimal(str(meta.get(REALTIME_ADJUSTMENT_KEY) or 0))
        if adjustment > ZERO:
            moved += adjustment
    real = budget_rows(rows)
    base: Dict[Tuple[date, str], Decimal] = {}
    for row in real:
        day = row.date.date() if hasattr(row.date, "date") else row.date
        key = (day, row.category or "")
        base[key] = base.get(key, ZERO) + base_planned_amount(row)
    return MonthPlan(
        planned=dict(planned),
        base=base,
        kinds=line_kinds_of(r for r in rows if r.goal_id is None),
        generated=bool(real),
        redistributed=moved,
    )


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
    codes: Iterable[str], buckets: Set[str], commitment_lines: Iterable[str]
) -> Set[str]:
    """The budget lines that are bills (R3): the month's commitments
    (``obligation_lines.month_commitments``: each saved payment counting in
    the month, on its own line or — in a legacy plan — its category's, and
    rent / mortgage / utilities lines without a saved payment) and every
    saved payment's own line in the plan. The calendar's "Bills &
    commitments" group and ``today``'s everyday figures use this one rule."""
    return {line_key(c, buckets) for c in commitment_lines} | {
        c for c in codes if is_bill_key(c)
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


def month_spent(
    db: Session, ctx: UserContext, year: int, month: int, view: MonthPlan
) -> Dict[Tuple[date, str], Decimal]:
    """The month's spend keyed by plan line exactly as the ledger rebuild
    keys it (a linked payment on its obligation's line in a keyed month)."""
    first, last = month_days(year, month)
    return ledger.spend_by_day_and_category(db, ctx, first, last, keyed=view.keyed)


def budget_status(
    db: Session,
    ctx: UserContext,
    year: int,
    month: int,
    *,
    with_redistribution: bool = True,
) -> BudgetStatus:
    view = month_plan(db, ctx, year, month)
    plan_generated = view.generated
    planned = view.planned
    spent = month_spent(db, ctx, year, month, view)

    planned_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    spent_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (_, category), amount in planned.items():
        planned_by_cat[category] += amount
    for (_, category), amount in spent.items():
        spent_by_cat[category] += amount

    names = obligation_names(db, ctx)
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
                planned_by_cat, spent_by_cat, names
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
            commitments_from(db, ctx, year, month, view).lines,
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
            view.redistributed if plan_generated and with_redistribution else ZERO
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
    view = month_plan(db, ctx, year, month)
    if not view.generated:
        return MonthForecast(year, month, position, False, None)

    spent = month_spent(db, ctx, year, month, view)
    commitments, paid = by_display_line(
        commitments_from(db, ctx, year, month, view), view.planned
    )
    result = forecast_from_rows(
        view.planned, spent, year, month, ctx.today, commitments, paid
    )
    return MonthForecast(year, month, position, True, result)


def commitments_from(
    db: Session, ctx: UserContext, year: int, month: int, view: MonthPlan
) -> MonthCommitments:
    """The month's commitments on the stored lines, exactly as the ledger
    rebuild and the mobile API compute them (``obligation_lines``): the
    reviewed (base) plan, the saved payments due and what linked expenses
    paid."""
    return shared_commitments(
        db, ctx.user_id, year, month, view.base_by_line(), view.keyed
    )


def by_display_line(
    commitments: MonthCommitments, planned: Mapping[Tuple[date, str], Decimal]
) -> Tuple[Dict[str, Decimal], Dict[str, Decimal]]:
    """What each bill needs this month and what the expenses linked to it
    paid, keyed by the budget line it is shown on. A bill shown on a paired
    line ("public_transport" on "transport public") never takes that line's
    everyday allowance with it."""
    buckets = {category for _, category in planned}
    needs: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    paid: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for line, need in commitments.needs.items():
        needs[line_key(line, buckets)] += need
    for line, amount in commitments.paid.items():
        paid[line_key(line, buckets)] += amount
    return dict(needs), dict(paid)


def forecast_from_rows(
    planned: Dict[Tuple[date, str], Decimal],
    spent: Dict[Tuple[date, str], Decimal],
    year: int,
    month: int,
    today: date,
    commitments: Optional[Mapping[str, Decimal]] = None,
    commitments_paid: Optional[Mapping[str, Decimal]] = None,
) -> ForecastResult:
    """The forecast engine over per-(day, category) plan and spend, regrouped
    by budget line exactly as ``get_budget_forecast`` does. Shared with the
    calendar so both report the same safe daily figure. ``commitments`` and
    ``commitments_paid``: ``month_commitments`` (unpaid bills are kept out of
    the safe daily figure; only a linked expense pays a saved payment)."""
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
        commitments_paid=commitments_paid,
    )

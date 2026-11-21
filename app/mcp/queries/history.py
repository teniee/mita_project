"""Multi-month spending history and the "financial climate", aggregated in SQL.

Everything is computed server-side from persisted MITA data — the ledger
(non-deleted ``transactions``), the plan (``daily_plan``), scheduled
obligations and goals — bucketed by the user's LOCAL calendar month. No raw
transaction list is returned; a six-month answer is a few dozen numbers.

Data completeness is explicit, never guessed:

* a month before the user's first recorded expense is ``before_tracking``
  (MITA has no record of it — not "zero spending");
* a complete month after that with no expenses is ``recorded`` with 0
  transactions ("nothing recorded", not necessarily "nothing spent");
* the current month is ``in_progress`` and never enters an average.

Rules that need several months (trends, the late-month share) require
``MIN_MONTHS_FOR_TREND`` complete months and otherwise report
``insufficient_data``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Goal, Transaction
from app.mcp.queries import ledger
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.expense_tracker import _safe_zone, local_day_start_utc
from app.services.monthly_plan_service import month_bounds

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
TENTH = Decimal("0.1")
MIN_MONTHS_FOR_TREND = 3
LATE_MONTH_DAYS = 7
TOP_CATEGORY_TRENDS = 5

MonthKey = Tuple[int, int]


def _shift(key: MonthKey, months: int) -> MonthKey:
    index = key[0] * 12 + key[1] - 1 + months
    return index // 12, index % 12 + 1


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MonthRecord:
    key: MonthKey
    status: str  # before_tracking | recorded | in_progress
    transaction_count: int
    total: Decimal
    categories: Dict[str, Tuple[Decimal, int]]  # category -> (total, count)

    @property
    def label(self) -> str:
        return f"{self.key[0]:04d}-{self.key[1]:02d}"


@dataclass(frozen=True)
class Trend:
    status: str  # ok | insufficient_data
    latest_month: Optional[str] = None
    latest_total: Optional[Decimal] = None
    earlier_average: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    direction: Optional[str] = None  # up | down | unchanged


@dataclass(frozen=True)
class History:
    months: List[MonthRecord]
    first_recorded: Optional[date]
    category: Optional[str]

    @property
    def complete(self) -> List[MonthRecord]:
        return [m for m in self.months if m.status == "recorded"]

    @property
    def in_progress(self) -> Optional[MonthRecord]:
        return next((m for m in self.months if m.status == "in_progress"), None)

    @property
    def months_with_data(self) -> int:
        return sum(1 for m in self.months if m.transaction_count > 0)

    def average(self) -> Optional[Decimal]:
        complete = self.complete
        if not complete:
            return None
        return _q(sum((m.total for m in complete), ZERO) / len(complete))

    def median(self) -> Optional[Decimal]:
        complete = self.complete
        if not complete:
            return None
        return _q(Decimal(median([m.total for m in complete])))

    def category_totals(self) -> Dict[str, Decimal]:
        totals: Dict[str, Decimal] = defaultdict(lambda: ZERO)
        for month in self.months:
            for category, (total, _) in month.categories.items():
                totals[category] += total
        return dict(totals)

    def trend(self, category: Optional[str] = None) -> Trend:
        """Latest complete month vs the average of the earlier complete ones."""
        complete = self.complete
        if len(complete) < MIN_MONTHS_FOR_TREND:
            return Trend("insufficient_data")

        def value(month: MonthRecord) -> Decimal:
            if category is None:
                return month.total
            return month.categories.get(category, (ZERO, 0))[0]

        latest = complete[-1]
        earlier = complete[:-1]
        earlier_avg = _q(sum((value(m) for m in earlier), ZERO) / len(earlier))
        latest_total = value(latest)
        if earlier_avg == ZERO:
            change = None
        else:
            change = ((latest_total - earlier_avg) / earlier_avg * 100).quantize(
                TENTH, rounding=ROUND_HALF_UP
            )
        direction = (
            "up"
            if latest_total > earlier_avg
            else "down" if latest_total < earlier_avg else "unchanged"
        )
        return Trend("ok", latest.label, latest_total, earlier_avg, change, direction)


def window(
    ctx: UserContext, months: int, end: Optional[MonthKey] = None
) -> List[MonthKey]:
    last = end or (ctx.today.year, ctx.today.month)
    return [_shift(last, -back) for back in range(months - 1, -1, -1)]


def _utc_bounds(ctx: UserContext, keys: List[MonthKey]) -> Tuple[datetime, datetime]:
    first = date(*keys[0], 1)
    after = date(*_shift(keys[-1], 1), 1)
    return (
        local_day_start_utc(first, ctx.timezone),
        local_day_start_utc(after, ctx.timezone),
    )


def _local_month(ctx: UserContext):
    zone = _safe_zone(ctx.timezone).key
    return func.date_trunc("month", func.timezone(zone, Transaction.spent_at))


def spending_history(
    db: Session,
    ctx: UserContext,
    keys: List[MonthKey],
    *,
    category: Optional[str] = None,
) -> History:
    lower, upper = _utc_bounds(ctx, keys)
    month_col = _local_month(ctx).label("month")
    query = (
        select(
            month_col,
            Transaction.category,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(
            Transaction.user_id == ctx.user_id,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= lower,
            Transaction.spent_at < upper,
        )
        .group_by(month_col, Transaction.category)
    )
    if category:
        query = query.where(func.lower(Transaction.category) == category.lower())
    buckets: Dict[MonthKey, Dict[str, Tuple[Decimal, int]]] = defaultdict(dict)
    for month_start, name, count, total in db.execute(query).all():
        key = (month_start.year, month_start.month)
        buckets[key][name] = (Decimal(str(total)), int(count))

    first = ledger.first_expense_day(db, ctx)
    first_key = (first.year, first.month) if first else None
    current = (ctx.today.year, ctx.today.month)
    records = []
    for key in keys:
        cats = buckets.get(key, {})
        if key == current:
            status = "in_progress"
        elif first_key is None or key < first_key:
            status = "before_tracking"
        else:
            status = "recorded"
        records.append(
            MonthRecord(
                key=key,
                status=status,
                transaction_count=sum(c for _, c in cats.values()),
                total=sum((t for t, _ in cats.values()), ZERO),
                categories=cats,
            )
        )
    return History(records, first, category)


@dataclass(frozen=True)
class PaceComparison:
    day_of_month: int
    spent_to_date: Decimal
    prior_average_to_same_day: Optional[Decimal]
    months_compared: int


@dataclass(frozen=True)
class PlanAdherence:
    months_with_plan: int
    months_within_plan: int
    months_over_plan: int


@dataclass(frozen=True)
class GoalsSummary:
    active_count: int
    total_target: Decimal
    total_saved: Decimal


@dataclass(frozen=True)
class Climate:
    history: History
    pace: Optional[PaceComparison]
    adherence: PlanAdherence
    late_month_share: Optional[Decimal]  # percent, None when insufficient
    goals: GoalsSummary
    obligations_count: int
    obligations_total: Decimal
    extra: Dict[str, object] = field(default_factory=dict)


def _daily_by_month(
    db: Session, ctx: UserContext, keys: List[MonthKey]
) -> Dict[MonthKey, Dict[int, Decimal]]:
    lower, upper = _utc_bounds(ctx, keys)
    zone = _safe_zone(ctx.timezone).key
    local = func.timezone(zone, Transaction.spent_at)
    month_col = func.date_trunc("month", local).label("month")
    day_col = func.extract("day", local).label("day")
    rows = db.execute(
        select(month_col, day_col, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == ctx.user_id,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= lower,
            Transaction.spent_at < upper,
        )
        .group_by(month_col, day_col)
    ).all()
    out: Dict[MonthKey, Dict[int, Decimal]] = defaultdict(dict)
    for month_start, day, total in rows:
        out[(month_start.year, month_start.month)][int(day)] = Decimal(str(total))
    return out


def _plan_totals(
    db: Session, ctx: UserContext, keys: List[MonthKey]
) -> Dict[MonthKey, Tuple[Decimal, bool]]:
    """Per month: total allocation (non-goal rows; redistribution conserves
    it) and whether a real budget exists (``month_has_plan`` semantics)."""
    start, _ = month_bounds(*keys[0])
    _, end = month_bounds(*keys[-1])
    month_col = func.date_trunc("month", func.timezone("UTC", DailyPlan.date)).label(
        "month"
    )
    generated = DailyPlan.plan_json["_mita_transaction_generated_v1"].astext
    real_row = and_(
        DailyPlan.planned_amount != 0,
        func.coalesce(generated, "false") != "true",
    )
    rows = db.execute(
        select(
            month_col,
            func.coalesce(func.sum(DailyPlan.planned_amount), 0),
            func.count(DailyPlan.id).filter(real_row),
        )
        .where(
            DailyPlan.user_id == ctx.user_id,
            DailyPlan.goal_id.is_(None),
            DailyPlan.date >= start,
            DailyPlan.date < end,
        )
        .group_by(month_col)
    ).all()
    return {
        (month_start.year, month_start.month): (Decimal(str(total)), real > 0)
        for month_start, total, real in rows
    }


def climate(
    db: Session,
    ctx: UserContext,
    keys: List[MonthKey],
    obligations: Tuple[int, Decimal],
) -> Climate:
    history = spending_history(db, ctx, keys)
    daily = _daily_by_month(db, ctx, keys)

    pace = None
    current = history.in_progress
    if current is not None:
        day = ctx.today.day
        spent = sum(
            (v for d, v in daily.get(current.key, {}).items() if d <= day), ZERO
        )
        prior = []
        for month in history.complete:
            cutoff = min(day, month_days(*month.key)[1].day)
            prior.append(
                sum(
                    (v for d, v in daily.get(month.key, {}).items() if d <= cutoff),
                    ZERO,
                )
            )
        pace = PaceComparison(
            day_of_month=day,
            spent_to_date=spent,
            prior_average_to_same_day=(
                _q(sum(prior, ZERO) / len(prior)) if prior else None
            ),
            months_compared=len(prior),
        )

    plans = _plan_totals(db, ctx, keys)
    with_plan = within = over = 0
    for month in history.complete:
        planned, exists = plans.get(month.key, (ZERO, False))
        if not exists:
            continue
        with_plan += 1
        if month.total > planned:
            over += 1
        else:
            within += 1

    late_share = None
    spending_months = [m for m in history.complete if m.total > ZERO]
    if len(spending_months) >= MIN_MONTHS_FOR_TREND:
        shares = []
        for month in spending_months:
            last_day = month_days(*month.key)[1].day
            late = sum(
                (
                    v
                    for d, v in daily.get(month.key, {}).items()
                    if d > last_day - LATE_MONTH_DAYS
                ),
                ZERO,
            )
            shares.append(late / month.total * 100)
        late_share = (sum(shares, Decimal(0)) / len(shares)).quantize(
            TENTH, rounding=ROUND_HALF_UP
        )

    goal_row = db.execute(
        select(
            func.count(Goal.id),
            func.coalesce(func.sum(Goal.target_amount), 0),
            func.coalesce(func.sum(Goal.saved_amount), 0),
        ).where(
            Goal.user_id == ctx.user_id,
            Goal.deleted_at.is_(None),
            Goal.status == "active",
        )
    ).one()
    return Climate(
        history=history,
        pace=pace,
        adherence=PlanAdherence(with_plan, within, over),
        late_month_share=late_share,
        goals=GoalsSummary(
            int(goal_row[0]), Decimal(str(goal_row[1])), Decimal(str(goal_row[2]))
        ),
        obligations_count=obligations[0],
        obligations_total=obligations[1],
    )

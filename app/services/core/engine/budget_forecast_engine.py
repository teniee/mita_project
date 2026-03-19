"""
Budget Forecast Engine — MITA Problem 3.

"At current pace, you'll run out of dining_out budget in 6 days."
"Safe daily limit from today: $64.20"
"Projected month-end balance: -$278.00 (danger)"

DESIGN PHILOSOPHY:
- Pure computation, zero DB access. Route fetches data; engine calculates.
- All arithmetic in Decimal — never float for financial data.
- Graceful degradation: no data → "no_data" status, no crashes.
- Category "at risk" threshold: burning > 120% of planned daily pace.
- Status thresholds: warning when projected overspend < 10% of plan,
  danger when projected overspend >= 10% of plan.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# Category is "at risk" if its daily pace exceeds planned pace by this ratio.
RISK_PACE_RATIO: Decimal = Decimal("1.20")

# Projected balance thresholds: how far over budget before escalating status.
# warning  → projected overspend is in (0, DANGER_RATIO * total_planned)
# danger   → projected overspend >= DANGER_RATIO * total_planned
DANGER_RATIO: Decimal = Decimal("0.10")

# Average days per month (used only for fractional months_remaining on goals).
AVG_DAYS_MONTH: Decimal = Decimal("30.44")

_ZERO = Decimal("0")
_CENT = Decimal("0.01")


# ---------------------------------------------------------------------------
# Input data classes — DB-agnostic, set by the route layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DailyPlanData:
    """One row from the daily_plan table, pre-converted by the route."""
    date: date
    category: str
    planned_amount: Decimal
    spent_amount: Decimal


@dataclass(frozen=True)
class GoalData:
    """One active row from the goals table, pre-converted by the route."""
    goal_id: str
    title: str
    target_amount: Decimal
    saved_amount: Decimal
    monthly_contribution: Optional[Decimal]  # None if not set by user
    target_date: Optional[date]


# ---------------------------------------------------------------------------
# Output data classes
# ---------------------------------------------------------------------------

@dataclass
class CategoryForecast:
    """Spending projection for a single budget category."""

    category: str
    monthly_planned: Decimal    # total planned for the month
    monthly_spent: Decimal      # total spent so far this month
    daily_pace: Decimal         # avg actual spend per calendar day elapsed
    planned_per_day: Decimal    # monthly_planned / days_in_month
    overspend_ratio: Decimal    # daily_pace / planned_per_day; 1.0 = on track
    days_until_exhausted: Optional[int]  # None = no spending yet; 0 = already exhausted

    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "monthly_planned": float(self.monthly_planned),
            "monthly_spent": float(self.monthly_spent),
            "pace": float(self.daily_pace),
            "budget_per_day": float(self.planned_per_day),
            "overspend_ratio": float(self.overspend_ratio),
            "days_until_exhausted": self.days_until_exhausted,
        }


@dataclass
class GoalForecast:
    """Month-end projection for a single savings goal."""

    goal_id: str
    title: str
    target_amount: Decimal
    saved_amount: Decimal
    remaining: Decimal
    target_date: Optional[date]
    months_remaining: Optional[Decimal]
    required_monthly_contribution: Optional[Decimal]  # to hit goal on time
    projected_saved: Optional[Decimal]
    on_track: bool
    shortfall: Decimal  # 0 if on track

    def to_dict(self) -> Dict:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "target": float(self.target_amount),
            "saved": float(self.saved_amount),
            "remaining": float(self.remaining),
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "months_remaining": (
                float(self.months_remaining) if self.months_remaining is not None else None
            ),
            "required_monthly_contribution": (
                float(self.required_monthly_contribution)
                if self.required_monthly_contribution is not None
                else None
            ),
            "projected_saved": (
                float(self.projected_saved) if self.projected_saved is not None else None
            ),
            "on_track": self.on_track,
            "shortfall": float(self.shortfall),
        }


@dataclass
class ForecastResult:
    """Full budget forecast for a user for a given month."""

    year: int
    month: int
    days_in_month: int
    days_elapsed: int            # calendar days from month start to today (inclusive)
    days_remaining: int          # days_in_month - days_elapsed
    total_planned: Decimal       # sum of all planned_amount for the month
    total_spent: Decimal         # sum of all spent_amount so far
    remaining_budget: Decimal    # total_planned - total_spent
    current_daily_pace: Decimal  # total_spent / days_elapsed
    safe_daily_limit: Decimal    # remaining_budget / days_remaining
    projected_month_end_spend: Decimal   # total_spent + pace * days_remaining
    projected_month_end_balance: Decimal # total_planned - projected_spend
    status: str                  # "on_track" | "warning" | "danger" | "no_data"
    categories_at_risk: List[CategoryForecast]  # sorted desc by overspend_ratio
    all_categories: List[CategoryForecast]      # sorted desc by monthly_planned
    goals: List[GoalForecast]

    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "month": self.month,
            "days_in_month": self.days_in_month,
            "days_elapsed": self.days_elapsed,
            "days_remaining": self.days_remaining,
            "total_planned": float(self.total_planned),
            "total_spent": float(self.total_spent),
            "remaining_budget": float(self.remaining_budget),
            "current_daily_pace": float(self.current_daily_pace),
            "safe_daily_limit": float(self.safe_daily_limit),
            "projected_month_end_spend": float(self.projected_month_end_spend),
            "projected_month_end_balance": float(self.projected_month_end_balance),
            "status": self.status,
            "categories_at_risk": [c.to_dict() for c in self.categories_at_risk],
            "all_categories": [c.to_dict() for c in self.all_categories],
            "goals": [g.to_dict() for g in self.goals],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _q(value: Decimal) -> Decimal:
    """Quantize Decimal to 2 decimal places (half-up rounding)."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _months_remaining_from_today(target_date: date, today: date) -> Decimal:
    """
    Fractional months between today and target_date.

    Returns Decimal("0") if target_date is today or in the past.
    Uses 30.44 avg days/month for consistent projections.
    """
    if target_date <= today:
        return _ZERO
    days = (target_date - today).days
    return _q(Decimal(str(days)) / AVG_DAYS_MONTH)


def _compute_goal_forecast(goal: GoalData, today: date) -> GoalForecast:
    """Project a single savings goal forward in time."""
    remaining = max(_ZERO, _q(goal.target_amount - goal.saved_amount))

    # ── Goal already fully funded ────────────────────────────────────────────
    if remaining <= _ZERO:
        return GoalForecast(
            goal_id=goal.goal_id,
            title=goal.title,
            target_amount=goal.target_amount,
            saved_amount=goal.saved_amount,
            remaining=_ZERO,
            target_date=goal.target_date,
            months_remaining=None,
            required_monthly_contribution=_ZERO,
            projected_saved=goal.saved_amount,
            on_track=True,
            shortfall=_ZERO,
        )

    # ── No deadline: cannot project, show raw state ─────────────────────────
    if goal.target_date is None:
        return GoalForecast(
            goal_id=goal.goal_id,
            title=goal.title,
            target_amount=goal.target_amount,
            saved_amount=goal.saved_amount,
            remaining=remaining,
            target_date=None,
            months_remaining=None,
            required_monthly_contribution=None,
            projected_saved=None,
            on_track=False,
            shortfall=remaining,
        )

    months_remaining = _months_remaining_from_today(goal.target_date, today)

    # ── Deadline has passed ──────────────────────────────────────────────────
    if months_remaining <= _ZERO:
        return GoalForecast(
            goal_id=goal.goal_id,
            title=goal.title,
            target_amount=goal.target_amount,
            saved_amount=goal.saved_amount,
            remaining=remaining,
            target_date=goal.target_date,
            months_remaining=_ZERO,
            required_monthly_contribution=None,
            projected_saved=goal.saved_amount,
            on_track=False,
            shortfall=remaining,
        )

    # ── Normal case: project forward ─────────────────────────────────────────
    required_monthly = _q(remaining / months_remaining)

    monthly_contribution = goal.monthly_contribution or _ZERO
    projected_saved = _q(goal.saved_amount + monthly_contribution * months_remaining)

    on_track = projected_saved >= goal.target_amount
    shortfall = max(_ZERO, _q(goal.target_amount - projected_saved))

    return GoalForecast(
        goal_id=goal.goal_id,
        title=goal.title,
        target_amount=goal.target_amount,
        saved_amount=goal.saved_amount,
        remaining=remaining,
        target_date=goal.target_date,
        months_remaining=months_remaining,
        required_monthly_contribution=required_monthly,
        projected_saved=projected_saved,
        on_track=on_track,
        shortfall=shortfall,
    )


def _compute_category_forecasts(
    daily_plans: List[DailyPlanData],
    days_in_month: int,
    days_elapsed: int,
) -> List[CategoryForecast]:
    """
    Aggregate DailyPlan rows by category and compute per-category metrics.

    days_elapsed: number of calendar days since month start (inclusive of today).
    When days_elapsed == 0 (future month), all paces will be 0.
    """
    # Aggregate totals by category
    planned_by_cat: Dict[str, Decimal] = {}
    spent_by_cat: Dict[str, Decimal] = {}

    for p in daily_plans:
        cat = p.category
        planned_by_cat[cat] = planned_by_cat.get(cat, _ZERO) + p.planned_amount
        spent_by_cat[cat] = spent_by_cat.get(cat, _ZERO) + p.spent_amount

    days_in_month_d = Decimal(str(days_in_month))
    # Use max(1, days_elapsed) to avoid ZeroDivisionError; when days_elapsed==0
    # total_spent will also be 0, so pace stays 0 regardless.
    days_elapsed_d = Decimal(str(max(1, days_elapsed)))

    forecasts: List[CategoryForecast] = []

    for cat, monthly_planned in planned_by_cat.items():
        monthly_spent = spent_by_cat.get(cat, _ZERO)

        # Average spend per elapsed calendar day
        daily_pace = _q(monthly_spent / days_elapsed_d) if days_elapsed > 0 else _ZERO

        # How much was planned per day?
        planned_per_day = (
            _q(monthly_planned / days_in_month_d)
            if days_in_month_d > _ZERO and monthly_planned > _ZERO
            else _ZERO
        )

        # Overspend ratio: pace vs planned rate
        if planned_per_day > _ZERO:
            overspend_ratio = _q(daily_pace / planned_per_day)
        elif daily_pace > _ZERO:
            # spending in a category with $0 planned → effectively infinite ratio;
            # cap at 9.99 to keep JSON sane.
            overspend_ratio = Decimal("9.99")
        else:
            overspend_ratio = _ZERO

        # Days until budget is exhausted at current pace
        remaining_cat = monthly_planned - monthly_spent
        days_until_exhausted: Optional[int]
        if remaining_cat <= _ZERO:
            days_until_exhausted = 0        # already exhausted
        elif daily_pace > _ZERO:
            days_until_exhausted = int(
                (remaining_cat / daily_pace).to_integral_value(rounding=ROUND_HALF_UP)
            )
        else:
            days_until_exhausted = None     # no spending → not exhaustible

        forecasts.append(CategoryForecast(
            category=cat,
            monthly_planned=monthly_planned,
            monthly_spent=monthly_spent,
            daily_pace=daily_pace,
            planned_per_day=planned_per_day,
            overspend_ratio=overspend_ratio,
            days_until_exhausted=days_until_exhausted,
        ))

    return forecasts


def _determine_status(
    projected_balance: Decimal,
    total_planned: Decimal,
    days_elapsed: int,
) -> str:
    """
    Map (projected_balance, total_planned, days_elapsed) → status string.

    "no_data"  — no spending data available yet (future month or empty plan)
    "on_track" — projected month-end balance >= 0
    "warning"  — projected overspend < 10% of total plan
    "danger"   — projected overspend >= 10% of total plan
    """
    if days_elapsed == 0 or total_planned <= _ZERO:
        return "no_data"

    if projected_balance >= _ZERO:
        return "on_track"

    # How much over budget as a fraction of the plan?
    over_fraction = (-projected_balance) / total_planned
    return "danger" if over_fraction >= DANGER_RATIO else "warning"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_forecast(
    daily_plans: List[DailyPlanData],
    goals: List[GoalData],
    year: int,
    month: int,
    today: Optional[date] = None,
) -> ForecastResult:
    """
    Compute full budget forecast for a user for the given month.

    Args:
        daily_plans:  All DailyPlan rows for the month, pre-fetched by the route.
        goals:        Active Goal rows for the user, pre-fetched by the route.
        year:         Target year.
        month:        Target month (1–12).
        today:        Override date.today() for testing. Defaults to date.today().

    Returns:
        ForecastResult with all projection metrics.
    """
    if today is None:
        today = date.today()

    days_in_month = monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    # ── Temporal context ─────────────────────────────────────────────────────
    if today < month_start:
        # Querying a future month — no spending data exists yet
        days_elapsed = 0
        days_remaining = days_in_month
    elif today > month_end:
        # Past month — fully elapsed, no future days
        days_elapsed = days_in_month
        days_remaining = 0
    else:
        # Current month
        days_elapsed = today.day
        days_remaining = days_in_month - today.day

    # ── Goal forecasts (computed even when no plan data) ─────────────────────
    goal_forecasts = [_compute_goal_forecast(g, today) for g in goals]

    # ── No DailyPlan data ────────────────────────────────────────────────────
    if not daily_plans:
        logger.info(
            "forecast: no DailyPlan rows for %d-%02d, returning no_data", year, month
        )
        return ForecastResult(
            year=year,
            month=month,
            days_in_month=days_in_month,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            total_planned=_ZERO,
            total_spent=_ZERO,
            remaining_budget=_ZERO,
            current_daily_pace=_ZERO,
            safe_daily_limit=_ZERO,
            projected_month_end_spend=_ZERO,
            projected_month_end_balance=_ZERO,
            status="no_data",
            categories_at_risk=[],
            all_categories=[],
            goals=goal_forecasts,
        )

    # ── Global aggregates ────────────────────────────────────────────────────
    total_planned = sum((p.planned_amount for p in daily_plans), _ZERO)
    total_spent = sum((p.spent_amount for p in daily_plans), _ZERO)
    remaining_budget = total_planned - total_spent

    days_remaining_d = Decimal(str(days_remaining))

    # Pace: if no days elapsed yet, pace = 0 (nothing spent in a future month)
    if days_elapsed > 0:
        days_elapsed_d = Decimal(str(days_elapsed))
        current_daily_pace = _q(total_spent / days_elapsed_d)
    else:
        current_daily_pace = _ZERO

    # Safe limit: how much can be spent per remaining day and still end at 0
    safe_daily_limit = (
        _q(remaining_budget / days_remaining_d) if days_remaining > 0 else _ZERO
    )

    # Projection: if no pace yet, projected spend = total already spent
    projected_month_end_spend = _q(
        total_spent + current_daily_pace * days_remaining_d
    )
    projected_month_end_balance = _q(total_planned - projected_month_end_spend)

    # ── Category-level forecasts ─────────────────────────────────────────────
    all_categories = _compute_category_forecasts(daily_plans, days_in_month, days_elapsed)

    categories_at_risk = sorted(
        [c for c in all_categories if c.overspend_ratio >= RISK_PACE_RATIO],
        key=lambda c: c.overspend_ratio,
        reverse=True,
    )

    # all_categories ordered by monthly_planned desc (biggest budget first)
    all_categories_sorted = sorted(
        all_categories,
        key=lambda c: c.monthly_planned,
        reverse=True,
    )

    # ── Overall status ───────────────────────────────────────────────────────
    status = _determine_status(projected_month_end_balance, total_planned, days_elapsed)

    logger.info(
        "forecast: %d-%02d status=%s pace=%.2f safe_limit=%.2f balance=%.2f at_risk=%d",
        year, month, status,
        float(current_daily_pace),
        float(safe_daily_limit),
        float(projected_month_end_balance),
        len(categories_at_risk),
    )

    return ForecastResult(
        year=year,
        month=month,
        days_in_month=days_in_month,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        total_planned=total_planned,
        total_spent=total_spent,
        remaining_budget=remaining_budget,
        current_daily_pace=current_daily_pace,
        safe_daily_limit=safe_daily_limit,
        projected_month_end_spend=projected_month_end_spend,
        projected_month_end_balance=projected_month_end_balance,
        status=status,
        categories_at_risk=categories_at_risk,
        all_categories=all_categories_sorted,
        goals=goal_forecasts,
    )

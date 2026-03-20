"""
Velocity Alert Engine — Pure computation, zero DB access.

Calculates spending velocity (actual daily pace vs planned daily pace) per
category and determines which categories are burning budget too fast.
Also detects positive spending win-streaks.

Velocity ratio definition:
    velocity_ratio = (monthly_spent / days_elapsed) / (monthly_planned / days_in_month)

Alert levels:
    WATCH    (≥ 1.20): spending 20 % ahead of plan — gentle heads-up
    WARNING  (≥ 1.50): budget will exhaust significantly early — real risk
    CRITICAL (≥ 2.00): emergency — budget runs out very soon

Usage:
    result = compute_velocity_alerts(daily_plans, goals, year=2026, month=3)
    for alert in result.alerts:
        ...
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Dict, List, Optional, Sequence

from app.core.category_priority import is_sacred

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VELOCITY_WATCH = Decimal("1.20")           # 120 % of planned pace → heads-up
VELOCITY_WARNING = Decimal("1.50")         # 150 % → real budget risk
VELOCITY_CRITICAL = Decimal("2.00")        # 200 % → emergency

MIN_DAYS_FOR_VELOCITY: int = 3             # need ≥ 3 days of data before alerting
MIN_PLANNED_FOR_ALERT = Decimal("1.00")    # skip near-zero / unplanned categories

WIN_DAILY_UNDER_PCT = Decimal("0.80")      # spent < 80 % of daily planned = good day
WIN_STREAK_MILESTONES = (30, 14, 7)        # report the highest milestone only


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VelocityAlertLevel(str, Enum):
    WATCH = "watch"        # 1.20 – 1.49 ×  informational
    WARNING = "warning"    # 1.50 – 1.99 ×  high priority
    CRITICAL = "critical"  # 2.00 +          critical


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DailyPlanData:
    """One row from the DailyPlan table (pre-fetched by the caller)."""
    plan_date: date
    category: str
    planned_amount: Decimal
    spent_amount: Decimal


@dataclass(frozen=True)
class GoalData:
    """One active goal (pre-fetched by the caller)."""
    goal_id: str
    title: str
    target_amount: Decimal
    saved_amount: Decimal
    monthly_contribution: Optional[Decimal]
    target_date: Optional[date]


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CategoryVelocity:
    """Velocity metrics for a single budget category."""

    category: str
    monthly_planned: Decimal
    monthly_spent: Decimal
    days_elapsed: int
    days_in_month: int
    daily_pace: Decimal         # actual: monthly_spent / days_elapsed
    planned_per_day: Decimal    # target: monthly_planned / days_in_month
    velocity_ratio: Decimal     # daily_pace / planned_per_day
    days_until_exhausted: Optional[Decimal]   # None if daily_pace == 0
    alert_level: Optional[VelocityAlertLevel]
    is_sacred_category: bool

    @property
    def days_remaining(self) -> int:
        return self.days_in_month - self.days_elapsed

    @property
    def percent_spent(self) -> Decimal:
        if self.monthly_planned > 0:
            return (self.monthly_spent / self.monthly_planned * 100).quantize(
                Decimal("0.1"), ROUND_HALF_UP
            )
        return Decimal("0")

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "monthly_planned": float(self.monthly_planned),
            "monthly_spent": float(self.monthly_spent),
            "days_elapsed": self.days_elapsed,
            "days_remaining": self.days_remaining,
            "daily_pace": float(self.daily_pace),
            "planned_per_day": float(self.planned_per_day),
            "velocity_ratio": float(self.velocity_ratio),
            "days_until_exhausted": (
                float(self.days_until_exhausted)
                if self.days_until_exhausted is not None
                else None
            ),
            "alert_level": self.alert_level.value if self.alert_level else None,
            "percent_spent": float(self.percent_spent),
        }


@dataclass
class GoalImpact:
    """How current over-pace affects a savings goal timeline."""
    goal_id: str
    goal_title: str
    projected_shortfall: Decimal   # how much less will be saved vs goal
    delay_days: int                # approximate goal delay in calendar days


@dataclass
class SpendingWin:
    """A positive spending achievement worth celebrating."""
    win_type: str           # "streak_7" | "streak_14" | "streak_30"
    surplus_amount: Decimal # total money saved below plan during the streak
    streak_days: int        # length of the current good-day streak


@dataclass
class VelocityAlertResult:
    """Full output of compute_velocity_alerts()."""
    year: int
    month: int
    days_elapsed: int
    days_in_month: int
    alerts: List[CategoryVelocity] = field(default_factory=list)
    all_categories: List[CategoryVelocity] = field(default_factory=list)
    goal_impacts: List[GoalImpact] = field(default_factory=list)
    wins: List[SpendingWin] = field(default_factory=list)

    def has_alerts(self) -> bool:
        return bool(self.alerts)

    def has_wins(self) -> bool:
        return bool(self.wins)

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "days_elapsed": self.days_elapsed,
            "days_in_month": self.days_in_month,
            "alerts": [a.to_dict() for a in self.alerts],
            "all_categories": [c.to_dict() for c in self.all_categories],
            "goal_impacts": [
                {
                    "goal_id": gi.goal_id,
                    "goal_title": gi.goal_title,
                    "projected_shortfall": float(gi.projected_shortfall),
                    "delay_days": gi.delay_days,
                }
                for gi in self.goal_impacts
            ],
            "wins": [
                {
                    "win_type": w.win_type,
                    "surplus_amount": float(w.surplus_amount),
                    "streak_days": w.streak_days,
                }
                for w in self.wins
            ],
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_velocity_alerts(
    daily_plans: Sequence[DailyPlanData],
    goals: Sequence[GoalData],
    year: int,
    month: int,
    today: Optional[date] = None,
    category: Optional[str] = None,
) -> VelocityAlertResult:
    """
    Pure function: compute velocity alerts from pre-fetched data.

    Args:
        daily_plans:  All DailyPlan rows for the month.
        goals:        All active goals for the user.
        year, month:  The budget month being evaluated.
        today:        Override for "today" (default: date.today()).
        category:     If provided, only evaluate this single category.
                      Win detection is skipped when filtering by category.

    Returns:
        VelocityAlertResult — may have empty alerts/wins if nothing to report.
    """
    if today is None:
        today = date.today()

    days_in_month: int = calendar.monthrange(year, month)[1]
    days_elapsed: int = today.day  # 1-based, matches days already completed

    result = VelocityAlertResult(
        year=year,
        month=month,
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
    )

    # Need at least MIN_DAYS_FOR_VELOCITY of data to compute meaningful pace
    if days_elapsed < MIN_DAYS_FOR_VELOCITY:
        return result

    # ------------------------------------------------------------------
    # Aggregate DailyPlan rows by category for the target month
    # ------------------------------------------------------------------
    cat_totals: Dict[str, Dict[str, Decimal]] = {}

    for plan in daily_plans:
        if plan.plan_date.year != year or plan.plan_date.month != month:
            continue
        if category is not None and plan.category != category:
            continue
        if not plan.category:
            continue

        cat = plan.category
        if cat not in cat_totals:
            cat_totals[cat] = {
                "monthly_planned": Decimal("0"),
                "monthly_spent": Decimal("0"),
            }
        cat_totals[cat]["monthly_planned"] += plan.planned_amount
        cat_totals[cat]["monthly_spent"] += plan.spent_amount

    if not cat_totals:
        return result

    # ------------------------------------------------------------------
    # Compute velocity per category
    # ------------------------------------------------------------------
    days_elapsed_d = Decimal(str(days_elapsed))
    days_in_month_d = Decimal(str(days_in_month))

    all_velocities: List[CategoryVelocity] = []
    alert_list: List[CategoryVelocity] = []

    for cat, totals in cat_totals.items():
        monthly_planned = totals["monthly_planned"]
        monthly_spent = totals["monthly_spent"]

        # Skip trivially small / unplanned categories
        if monthly_planned < MIN_PLANNED_FOR_ALERT:
            continue

        cat_is_sacred = is_sacred(cat)

        # Velocity metrics — all Decimal
        daily_pace = (monthly_spent / days_elapsed_d).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        planned_per_day = (monthly_planned / days_in_month_d).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        if planned_per_day > 0:
            velocity_ratio = (daily_pace / planned_per_day).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
        else:
            velocity_ratio = Decimal("0")

        # Days until budget is exhausted at current pace
        remaining_budget = monthly_planned - monthly_spent
        if daily_pace > 0 and remaining_budget > 0:
            days_until_exhausted = (remaining_budget / daily_pace).quantize(
                Decimal("0.1"), ROUND_HALF_UP
            )
        elif remaining_budget <= 0:
            days_until_exhausted = Decimal("0")
        else:
            days_until_exhausted = None  # no spending at all

        # Alert level — sacred categories never alert
        alert_level: Optional[VelocityAlertLevel] = None
        if not cat_is_sacred:
            if velocity_ratio >= VELOCITY_CRITICAL:
                alert_level = VelocityAlertLevel.CRITICAL
            elif velocity_ratio >= VELOCITY_WARNING:
                alert_level = VelocityAlertLevel.WARNING
            elif velocity_ratio >= VELOCITY_WATCH:
                alert_level = VelocityAlertLevel.WATCH

        cv = CategoryVelocity(
            category=cat,
            monthly_planned=monthly_planned,
            monthly_spent=monthly_spent,
            days_elapsed=days_elapsed,
            days_in_month=days_in_month,
            daily_pace=daily_pace,
            planned_per_day=planned_per_day,
            velocity_ratio=velocity_ratio,
            days_until_exhausted=days_until_exhausted,
            alert_level=alert_level,
            is_sacred_category=cat_is_sacred,
        )
        all_velocities.append(cv)
        if alert_level is not None:
            alert_list.append(cv)

    # Sort alerts: CRITICAL first, then WARNING, then WATCH; break ties by ratio desc
    _level_rank = {
        VelocityAlertLevel.CRITICAL: 3,
        VelocityAlertLevel.WARNING: 2,
        VelocityAlertLevel.WATCH: 1,
    }
    alert_list.sort(
        key=lambda x: (-_level_rank.get(x.alert_level, 0), -float(x.velocity_ratio))
    )

    result.all_categories = all_velocities
    result.alerts = alert_list

    # ------------------------------------------------------------------
    # Goal impact (only when there are alerts to report)
    # ------------------------------------------------------------------
    if alert_list and goals:
        result.goal_impacts = _compute_goal_impacts(
            goals=goals,
            all_categories=all_velocities,
            year=year,
            month=month,
            days_elapsed=days_elapsed,
            days_in_month=days_in_month,
        )

    # ------------------------------------------------------------------
    # Win detection (full scan only — not triggered per-category)
    # ------------------------------------------------------------------
    if category is None:
        result.wins = _detect_wins(
            daily_plans=daily_plans,
            year=year,
            month=month,
            today=today,
        )

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_goal_impacts(
    goals: Sequence[GoalData],
    all_categories: List[CategoryVelocity],
    year: int,
    month: int,
    days_elapsed: int,
    days_in_month: int,
) -> List[GoalImpact]:
    """
    Project monthly spending deficit and map it to goal delays.

    Logic: if total spending pace projects a month-end deficit vs planned,
    that deficit comes at the expense of goal contributions.
    """
    impacts: List[GoalImpact] = []

    total_planned = sum(cv.monthly_planned for cv in all_categories)
    total_spent = sum(cv.monthly_spent for cv in all_categories)

    if total_planned <= 0 or days_elapsed <= 0:
        return impacts

    days_elapsed_d = Decimal(str(days_elapsed))
    days_in_month_d = Decimal(str(days_in_month))
    days_remaining = days_in_month - days_elapsed

    total_daily_pace = total_spent / days_elapsed_d
    projected_month_spend = (
        total_spent + total_daily_pace * Decimal(str(days_remaining))
    )
    projected_deficit = projected_month_spend - total_planned

    if projected_deficit <= 0:
        return impacts  # on track — goals are safe

    for goal in goals:
        if not goal.monthly_contribution or goal.monthly_contribution <= 0:
            continue
        if goal.target_date is None:
            continue

        # How much of this goal's contribution is eaten by the deficit
        shortfall = min(projected_deficit, goal.monthly_contribution)

        # Convert shortfall to days of delay
        delay_days = int(
            (shortfall / goal.monthly_contribution * days_in_month_d).to_integral_value(
                ROUND_HALF_UP
            )
        )

        if shortfall > Decimal("0.01") and delay_days > 0:
            impacts.append(
                GoalImpact(
                    goal_id=goal.goal_id,
                    goal_title=goal.title,
                    projected_shortfall=shortfall.quantize(
                        Decimal("0.01"), ROUND_HALF_UP
                    ),
                    delay_days=delay_days,
                )
            )

    impacts.sort(key=lambda x: -x.delay_days)
    return impacts


def _detect_wins(
    daily_plans: Sequence[DailyPlanData],
    year: int,
    month: int,
    today: date,
) -> List[SpendingWin]:
    """
    Detect positive spending streaks.

    A day is "good" when total_spent_that_day < WIN_DAILY_UNDER_PCT * total_planned_that_day.
    Only past days with planned_amount > 0 are counted.
    Reports the highest streak milestone reached (7 / 14 / 30 days).
    """
    wins: List[SpendingWin] = []

    # Bucket by date: sum planned and spent across all categories
    buckets: Dict[date, Dict[str, Decimal]] = defaultdict(
        lambda: {"planned": Decimal("0"), "spent": Decimal("0")}
    )

    for plan in daily_plans:
        if plan.plan_date.year != year or plan.plan_date.month != month:
            continue
        if plan.plan_date > today:
            continue
        if plan.planned_amount <= 0:
            continue
        buckets[plan.plan_date]["planned"] += plan.planned_amount
        buckets[plan.plan_date]["spent"] += plan.spent_amount

    if not buckets:
        return wins

    # Walk backward from today counting consecutive good days
    sorted_dates = sorted(buckets.keys(), reverse=True)
    consecutive = 0
    total_surplus = Decimal("0")

    for d in sorted_dates:
        bucket = buckets[d]
        if bucket["planned"] <= 0:
            break
        ratio = bucket["spent"] / bucket["planned"]
        if ratio <= WIN_DAILY_UNDER_PCT:
            consecutive += 1
            total_surplus += bucket["planned"] - bucket["spent"]
        else:
            break

    # Report the highest milestone
    for milestone in WIN_STREAK_MILESTONES:
        if consecutive >= milestone:
            wins.append(
                SpendingWin(
                    win_type=f"streak_{milestone}",
                    surplus_amount=total_surplus.quantize(
                        Decimal("0.01"), ROUND_HALF_UP
                    ),
                    streak_days=consecutive,
                )
            )
            break  # only report the highest milestone

    return wins

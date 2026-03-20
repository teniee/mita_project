"""
Scheduled Expense Engine — MITA Problem 6 fix.

Pure computation: no DB access, no side effects.
The route fetches data and passes it in; this engine crunches numbers.

Core promise: user schedules a future expense → safe_daily_limit
immediately drops to account for the coming payment.  No surprises.

Design:
• All money arithmetic uses Decimal (never float).
• float appears only in to_dict() for JSON serialisation.
• Computation anchor is injected via `today` parameter — trivially testable.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional


# ─── Input dataclasses ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScheduledExpenseData:
    """Pre-fetched scheduled expense row — input to the engine."""

    expense_id: str
    category: str
    amount: Decimal
    scheduled_date: date
    description: Optional[str] = None
    merchant: Optional[str] = None


@dataclass(frozen=True)
class DailyBudgetData:
    """
    One DailyPlan row flattened to a value object.
    date is a Python date (not datetime) — callers normalise it.
    """

    date: date
    category: str
    planned_amount: Decimal
    spent_amount: Decimal


# ─── Output dataclasses ───────────────────────────────────────────────────────


@dataclass
class ExpenseImpact:
    """Impact analysis for a single scheduled expense."""

    expense_id: str
    category: str
    amount: Decimal
    scheduled_date: date
    days_until: int
    # planned_amount already in DailyPlan for this category on scheduled_date
    same_day_planned: Decimal
    # How much this expense shaves off each remaining day's safe limit
    daily_reduction: Decimal
    # Remaining category budget from today → scheduled_date
    category_remaining: Decimal
    # True if the category alone has enough remaining budget to absorb the expense
    category_can_cover: bool

    def to_dict(self) -> dict:
        return {
            "expense_id": self.expense_id,
            "category": self.category,
            "amount": float(self.amount),
            "scheduled_date": self.scheduled_date.isoformat(),
            "days_until": self.days_until,
            "same_day_planned": float(self.same_day_planned),
            "daily_reduction": float(self.daily_reduction),
            "category_remaining": float(self.category_remaining),
            "category_can_cover": self.category_can_cover,
        }


@dataclass
class ScheduledImpactResult:
    """Full impact of all pending scheduled expenses for a given month."""

    year: int
    month: int
    today: date
    days_remaining: int
    # safe_daily_limit ignoring scheduled expenses
    base_safe_daily_limit: Decimal
    # safe_daily_limit after reserving for scheduled expenses
    adjusted_safe_daily_limit: Decimal
    # Sum of all pending scheduled amounts in this month
    total_committed: Decimal
    impacts: List[ExpenseImpact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "today": self.today.isoformat(),
            "days_remaining": self.days_remaining,
            "base_safe_daily_limit": float(self.base_safe_daily_limit),
            "adjusted_safe_daily_limit": float(self.adjusted_safe_daily_limit),
            "total_committed": float(self.total_committed),
            "impacts": [i.to_dict() for i in self.impacts],
        }


# ─── Engine ───────────────────────────────────────────────────────────────────


def compute_scheduled_impact(
    pending_expenses: List[ScheduledExpenseData],
    daily_plans: List[DailyBudgetData],
    today: Optional[date] = None,
) -> ScheduledImpactResult:
    """
    Compute how pending scheduled expenses affect the safe daily budget limit.

    Args:
        pending_expenses:  rows with status="pending" and scheduled_date >= today.
                           Caller is responsible for filtering; engine trusts its input.
        daily_plans:       this month's DailyPlan rows (all categories, all days).
        today:             anchor date; defaults to date.today() — override in tests.

    Returns:
        ScheduledImpactResult with adjusted_safe_daily_limit and per-expense impacts.
        All Decimal fields are rounded to 2 decimal places (ROUND_HALF_UP).
    """
    if today is None:
        today = date.today()

    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]
    last_day = date(year, month, days_in_month)
    days_remaining = max((last_day - today).days + 1, 1)

    # ── Total planned / spent for the month ──────────────────────────────────
    total_planned = _sum(p.planned_amount for p in daily_plans)
    total_spent = _sum(p.spent_amount for p in daily_plans)
    remaining_budget = _q(total_planned - total_spent)

    base_safe_daily_limit = _q(remaining_budget / Decimal(str(days_remaining)))

    # ── Filter: only THIS month's pending expenses ≥ today ───────────────────
    this_month = [
        e for e in pending_expenses
        if e.scheduled_date >= today
        and e.scheduled_date.year == year
        and e.scheduled_date.month == month
    ]

    total_committed = _q(_sum(e.amount for e in this_month))

    # adjusted remaining = remaining minus what is already earmarked
    adjusted_remaining = _q(max(remaining_budget - total_committed, Decimal("0")))
    adjusted_safe_daily_limit = _q(
        adjusted_remaining / Decimal(str(days_remaining))
    )

    # ── Per-category lookup: date → DailyBudgetData ──────────────────────────
    # cat_by_date[category][date] = DailyBudgetData
    cat_by_date: Dict[str, Dict[date, DailyBudgetData]] = {}
    for p in daily_plans:
        cat_by_date.setdefault(p.category, {})[p.date] = p

    # ── Per-expense impact ────────────────────────────────────────────────────
    impacts: List[ExpenseImpact] = []
    for expense in this_month:
        days_until = (expense.scheduled_date - today).days
        cat = expense.category
        amount = _d(expense.amount)

        # Budget already allocated on the scheduled day for this category
        same_day_planned = Decimal("0")
        if cat in cat_by_date and expense.scheduled_date in cat_by_date[cat]:
            same_day_planned = _d(cat_by_date[cat][expense.scheduled_date].planned_amount)

        # Category budget remaining between today and the scheduled date (inclusive)
        cat_planned_window = Decimal("0")
        cat_spent_window = Decimal("0")
        if cat in cat_by_date:
            for d, entry in cat_by_date[cat].items():
                if today <= d <= expense.scheduled_date:
                    cat_planned_window += _d(entry.planned_amount)
                    cat_spent_window += _d(entry.spent_amount)

        category_remaining = _q(max(cat_planned_window - cat_spent_window, Decimal("0")))
        category_can_cover = category_remaining >= amount

        # How much per day the user must "save" to cover this expense
        window_days = max(days_until + 1, 1)
        daily_reduction = _q(amount / Decimal(str(window_days)))

        impacts.append(
            ExpenseImpact(
                expense_id=str(expense.expense_id),
                category=cat,
                amount=amount,
                scheduled_date=expense.scheduled_date,
                days_until=days_until,
                same_day_planned=same_day_planned,
                daily_reduction=daily_reduction,
                category_remaining=category_remaining,
                category_can_cover=category_can_cover,
            )
        )

    # Sort by date ascending — soonest first
    impacts.sort(key=lambda i: i.scheduled_date)

    return ScheduledImpactResult(
        year=year,
        month=month,
        today=today,
        days_remaining=days_remaining,
        base_safe_daily_limit=base_safe_daily_limit,
        adjusted_safe_daily_limit=adjusted_safe_daily_limit,
        total_committed=total_committed,
        impacts=impacts,
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _d(value) -> Decimal:
    """Convert any numeric value to Decimal."""
    return Decimal(str(value))


def _q(value: Decimal) -> Decimal:
    """Quantise to 2 d.p. with ROUND_HALF_UP."""
    return value.quantize(Decimal("0.01"), ROUND_HALF_UP)


def _sum(iterable) -> Decimal:
    """Sum an iterable of Decimal-convertible values, returning Decimal("0") for empty."""
    return sum((_d(v) for v in iterable), Decimal("0"))

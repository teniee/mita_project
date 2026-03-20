"""
Unit tests for scheduled_expense_engine.py — pure computation, zero DB access.

All tests inject data directly; no mocking or patching needed.
Run: pytest tests/test_scheduled_expense_engine.py -v
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.core.engine.scheduled_expense_engine import (
    DailyBudgetData,
    ScheduledExpenseData,
    ScheduledImpactResult,
    compute_scheduled_impact,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


TODAY = date(2026, 3, 20)
MARCH_END = date(2026, 3, 31)
DAYS_REMAINING = 12  # 20..31 inclusive


def _plan(day: int, category: str, planned: str, spent: str = "0") -> DailyBudgetData:
    """Helper: build a DailyBudgetData for March 2026."""
    return DailyBudgetData(
        date=date(2026, 3, day),
        category=category,
        planned_amount=Decimal(planned),
        spent_amount=Decimal(spent),
    )


def _expense(
    expense_id: str,
    category: str,
    amount: str,
    day: int,
    month: int = 3,
    year: int = 2026,
) -> ScheduledExpenseData:
    return ScheduledExpenseData(
        expense_id=expense_id,
        category=category,
        amount=Decimal(amount),
        scheduled_date=date(year, month, day),
    )


# ─── TestNoExpenses ───────────────────────────────────────────────────────────


class TestNoExpenses:
    def test_no_expenses_base_equals_adjusted(self):
        """Without scheduled expenses, both limits are identical."""
        plans = [_plan(d, "dining_out", "30") for d in range(20, 32)]
        result = compute_scheduled_impact([], plans, TODAY)
        assert result.base_safe_daily_limit == result.adjusted_safe_daily_limit
        assert result.total_committed == Decimal("0")
        assert result.impacts == []

    def test_no_plans_no_expenses(self):
        """Edge: empty month — limits are zero."""
        result = compute_scheduled_impact([], [], TODAY)
        assert result.base_safe_daily_limit == Decimal("0")
        assert result.adjusted_safe_daily_limit == Decimal("0")
        assert result.total_committed == Decimal("0")

    def test_all_fields_present_in_to_dict(self):
        result = compute_scheduled_impact([], [], TODAY)
        d = result.to_dict()
        assert "year" in d
        assert "month" in d
        assert "today" in d
        assert "days_remaining" in d
        assert "base_safe_daily_limit" in d
        assert "adjusted_safe_daily_limit" in d
        assert "total_committed" in d
        assert "impacts" in d

    def test_days_remaining_calculation(self):
        """March 20 → 31 = 12 days remaining (inclusive)."""
        result = compute_scheduled_impact([], [], TODAY)
        assert result.days_remaining == DAYS_REMAINING


# ─── TestBasicImpact ─────────────────────────────────────────────────────────


class TestBasicImpact:
    def test_single_expense_reduces_adjusted_limit(self):
        """$300 scheduled on March 25 reduces adjusted safe daily limit."""
        # 12 remaining days × $10/day → $120 remaining budget
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]
        expenses = [_expense("e1", "insurance", "30", 25)]

        result = compute_scheduled_impact(expenses, plans, TODAY)

        assert result.total_committed == Decimal("30.00")
        assert result.adjusted_safe_daily_limit < result.base_safe_daily_limit
        # adjusted = (120 - 30) / 12 = 7.50
        assert result.adjusted_safe_daily_limit == Decimal("7.50")

    def test_impact_list_contains_one_entry(self):
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]
        expenses = [_expense("e1", "insurance", "30", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert len(result.impacts) == 1

    def test_impact_expense_id_preserved(self):
        plans = []
        expenses = [_expense("my-uuid-123", "insurance", "50", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].expense_id == "my-uuid-123"

    def test_days_until_correct(self):
        """Expense on March 25, today March 20 → 5 days until."""
        plans = []
        expenses = [_expense("e1", "insurance", "50", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].days_until == 5

    def test_expense_today_days_until_zero(self):
        plans = []
        expenses = [_expense("e1", "insurance", "50", 20)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].days_until == 0

    def test_impact_to_dict_float_values(self):
        """to_dict must return floats, not Decimal."""
        plans = []
        expenses = [_expense("e1", "insurance", "50", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        d = result.impacts[0].to_dict()
        assert isinstance(d["amount"], float)
        assert isinstance(d["daily_reduction"], float)
        assert isinstance(d["category_remaining"], float)


# ─── TestMultipleExpenses ─────────────────────────────────────────────────────


class TestMultipleExpenses:
    def test_two_expenses_stack(self):
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]  # 120 total
        expenses = [
            _expense("e1", "insurance", "30", 25),
            _expense("e2", "rent", "60", 28),
        ]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.total_committed == Decimal("90.00")
        # adjusted = (120 - 90) / 12 = 2.50
        assert result.adjusted_safe_daily_limit == Decimal("2.50")
        assert len(result.impacts) == 2

    def test_impacts_sorted_by_date_ascending(self):
        """Soonest expense must come first in impacts list."""
        plans = []
        expenses = [
            _expense("late", "insurance", "50", 30),
            _expense("soon", "rent", "50", 22),
            _expense("mid", "utilities", "50", 26),
        ]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        dates = [i.scheduled_date for i in result.impacts]
        assert dates == sorted(dates)

    def test_adjusted_never_negative(self):
        """Committed > remaining → adjusted_safe_daily_limit == 0, not negative."""
        plans = [_plan(d, "dining_out", "5") for d in range(20, 32)]  # 60 total
        expenses = [_expense("e1", "insurance", "100", 25)]  # 100 > 60
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.adjusted_safe_daily_limit >= Decimal("0")


# ─── TestExpenseOutsideMonth ─────────────────────────────────────────────────


class TestExpenseOutsideMonth:
    def test_next_month_expense_ignored(self):
        """Expenses in April don't affect March's safe_daily_limit."""
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]
        april_expense = _expense("e1", "insurance", "300", 15, month=4)
        result = compute_scheduled_impact([april_expense], plans, TODAY)
        assert result.total_committed == Decimal("0")
        assert result.base_safe_daily_limit == result.adjusted_safe_daily_limit
        assert result.impacts == []

    def test_past_expense_in_march_ignored(self):
        """Expenses before today (March 19) are not included."""
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]
        past_expense = _expense("e1", "insurance", "100", 15)  # March 15 < March 20
        result = compute_scheduled_impact([past_expense], plans, TODAY)
        assert result.total_committed == Decimal("0")
        assert result.impacts == []

    def test_last_day_of_month_included(self):
        """March 31 is valid — must be included."""
        plans = []
        expenses = [_expense("e1", "insurance", "50", 31)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.total_committed == Decimal("50.00")
        assert len(result.impacts) == 1


# ─── TestCategoryCanCover ─────────────────────────────────────────────────────


class TestCategoryCanCover:
    def test_can_cover_true_when_category_has_enough(self):
        # insurance has $400 planned, $0 spent → can cover $300
        plans = [_plan(d, "insurance", "100") for d in range(20, 26)]  # 6 days × 100 = 600
        expenses = [_expense("e1", "insurance", "300", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].category_can_cover is True

    def test_can_cover_false_when_category_insufficient(self):
        # insurance has only $10 across remaining days → cannot cover $300
        plans = [_plan(d, "insurance", "2") for d in range(20, 26)]  # 12 total
        expenses = [_expense("e1", "insurance", "300", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].category_can_cover is False

    def test_category_remaining_includes_spending(self):
        """Category remaining = planned - spent, not just planned."""
        plans = [
            _plan(20, "insurance", "100", spent="80"),  # 20 remaining on day 20
            _plan(25, "insurance", "100", spent="0"),   # 100 remaining on day 25
        ]
        expenses = [_expense("e1", "insurance", "50", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        # Remaining in window [20..25] = (100-80) + (100-0) = 120
        assert result.impacts[0].category_remaining == Decimal("120.00")
        assert result.impacts[0].category_can_cover is True


# ─── TestDailyReduction ───────────────────────────────────────────────────────


class TestDailyReduction:
    def test_daily_reduction_formula(self):
        """daily_reduction = amount / (days_until + 1)"""
        # Expense on March 25, today March 20 → 5 days_until → window = 6 days
        expenses = [_expense("e1", "insurance", "60", 25)]
        result = compute_scheduled_impact(expenses, [], TODAY)
        # 60 / 6 = 10.00
        assert result.impacts[0].daily_reduction == Decimal("10.00")

    def test_daily_reduction_same_day(self):
        """days_until=0 → window=1 → reduction=amount."""
        expenses = [_expense("e1", "insurance", "50", 20)]  # today
        result = compute_scheduled_impact(expenses, [], TODAY)
        assert result.impacts[0].daily_reduction == Decimal("50.00")

    def test_same_day_planned_populated(self):
        """same_day_planned reflects the existing DailyPlan amount for that day."""
        plans = [_plan(25, "insurance", "40")]
        expenses = [_expense("e1", "insurance", "100", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].same_day_planned == Decimal("40.00")

    def test_same_day_planned_zero_when_no_plan(self):
        plans = []  # no DailyPlan for insurance
        expenses = [_expense("e1", "insurance", "100", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        assert result.impacts[0].same_day_planned == Decimal("0.00")


# ─── TestDecimalPrecision ─────────────────────────────────────────────────────


class TestDecimalPrecision:
    def test_rounding_to_two_decimal_places(self):
        """All Decimal outputs must be rounded to exactly 2 d.p."""
        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]  # 120
        expenses = [_expense("e1", "insurance", "7", 25)]  # 7/12 = 0.58333...
        result = compute_scheduled_impact(expenses, plans, TODAY)
        # (120 - 7) / 12 = 9.416... → 9.42
        assert result.adjusted_safe_daily_limit == Decimal("9.42")

    def test_result_type_is_decimal(self):
        plans = [_plan(20, "dining_out", "10")]
        result = compute_scheduled_impact([], plans, TODAY)
        assert isinstance(result.base_safe_daily_limit, Decimal)
        assert isinstance(result.adjusted_safe_daily_limit, Decimal)
        assert isinstance(result.total_committed, Decimal)

    def test_to_dict_base_safe_is_float(self):
        result = compute_scheduled_impact([], [], TODAY)
        d = result.to_dict()
        assert isinstance(d["base_safe_daily_limit"], float)
        assert isinstance(d["adjusted_safe_daily_limit"], float)
        assert isinstance(d["total_committed"], float)


# ─── TestEdgeCases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_month_end_anchor_date(self):
        """On the last day of the month, days_remaining = 1."""
        last_day = date(2026, 3, 31)
        result = compute_scheduled_impact([], [], last_day)
        assert result.days_remaining == 1

    def test_first_day_of_month(self):
        """On March 1, days_remaining = 31."""
        first_day = date(2026, 3, 1)
        result = compute_scheduled_impact([], [], first_day)
        assert result.days_remaining == 31

    def test_february_non_leap(self):
        """February 2025 (non-leap) has 28 days."""
        feb = date(2025, 2, 1)
        result = compute_scheduled_impact([], [], feb)
        assert result.days_remaining == 28

    def test_february_leap(self):
        """February 2024 (leap) has 29 days."""
        feb_leap = date(2024, 2, 1)
        result = compute_scheduled_impact([], [], feb_leap)
        assert result.days_remaining == 29

    def test_different_categories_dont_interfere(self):
        """Insurance expense shouldn't affect dining_out category_remaining."""
        plans = [_plan(d, "dining_out", "20") for d in range(20, 32)]
        expenses = [_expense("e1", "insurance", "100", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        impact = result.impacts[0]
        # insurance category has no DailyPlan rows → remaining=0
        assert impact.category_remaining == Decimal("0.00")
        assert impact.category_can_cover is False

    def test_zero_amount_expense_excluded_from_committed(self):
        """Zero-amount expenses should not appear — but if they somehow do, total is correct."""
        plans = [_plan(20, "dining_out", "10")]
        expenses = [_expense("e1", "insurance", "0", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        # Engine still includes it in this_month, total_committed = 0
        assert result.total_committed == Decimal("0.00")


# ─── TestFullScenario ─────────────────────────────────────────────────────────


class TestFullScenario:
    def test_realistic_march_scenario(self):
        """
        Realistic scenario: user has $3000/month income, March 20,
        two scheduled expenses: $300 insurance (March 25) + $150 phone (March 28).
        Plans: 12 remaining days × $25 dining + $50 savings = $900 total.
        """
        plans = (
            [_plan(d, "dining_out", "25") for d in range(20, 32)]
            + [_plan(d, "goal_savings", "50") for d in range(20, 32)]
        )
        expenses = [
            _expense("ins", "insurance", "300", 25),
            _expense("phone", "utilities", "150", 28),
        ]
        result = compute_scheduled_impact(expenses, plans, TODAY)

        # Total planned = 12*25 + 12*50 = 300 + 600 = 900
        # Total spent = 0
        # remaining = 900
        # total_committed = 300 + 150 = 450
        # adjusted_remaining = 900 - 450 = 450
        # adjusted_safe_daily_limit = 450 / 12 = 37.50
        assert result.total_committed == Decimal("450.00")
        assert result.adjusted_safe_daily_limit == Decimal("37.50")

        # base = 900 / 12 = 75.00
        assert result.base_safe_daily_limit == Decimal("75.00")

        assert len(result.impacts) == 2
        # Sorted by date: insurance (Mar 25) first, phone (Mar 28) second
        assert result.impacts[0].expense_id == "ins"
        assert result.impacts[1].expense_id == "phone"

    def test_to_dict_full_round_trip(self):
        """to_dict must produce JSON-serialisable output (all Python primitives)."""
        import json

        plans = [_plan(d, "dining_out", "10") for d in range(20, 32)]
        expenses = [_expense("e1", "insurance", "50", 25)]
        result = compute_scheduled_impact(expenses, plans, TODAY)
        d = result.to_dict()

        serialised = json.dumps(d)  # must not raise
        parsed = json.loads(serialised)
        assert parsed["total_committed"] == float(result.total_committed)
        assert len(parsed["impacts"]) == 1

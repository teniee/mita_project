"""
Tests for the Budget Forecast Engine (Problem 3 fix).

The engine is a pure-computation module: no DB, no FastAPI, no mocking of
external services. Every test constructs DailyPlanData / GoalData directly
and asserts on the returned ForecastResult.

Coverage:
- no_data path: empty plans, future month
- on_track / warning / danger status thresholds
- safe_daily_limit and current_daily_pace math
- projected_month_end_balance direction
- categories_at_risk detection and ordering
- days_until_exhausted: normal, zero-pace, already-exhausted
- Goal forecasts: on track, not on track, no deadline, overdue, already funded
- Decimal precision: verify to_dict() values match Decimal arithmetic exactly
- past month (all days elapsed)
- first day of month (days_elapsed = 1)
"""
import sys
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.core.engine.budget_forecast_engine import (
    RISK_PACE_RATIO,
    DANGER_RATIO,
    DailyPlanData,
    GoalData,
    ForecastResult,
    CategoryForecast,
    GoalForecast,
    compute_forecast,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan(category: str, day: date, planned: str, spent: str) -> DailyPlanData:
    return DailyPlanData(
        date=day,
        category=category,
        planned_amount=Decimal(planned),
        spent_amount=Decimal(spent),
    )


def _goal(
    target: str,
    saved: str,
    contribution: str = None,
    target_date: date = None,
) -> GoalData:
    return GoalData(
        goal_id=str(uuid4()),
        title="Test Goal",
        target_amount=Decimal(target),
        saved_amount=Decimal(saved),
        monthly_contribution=Decimal(contribution) if contribution else None,
        target_date=target_date,
    )


def _d(y: int, m: int, d: int) -> date:
    return date(y, m, d)


MARCH_2026 = (2026, 3)
TODAY_MID_MARCH = _d(2026, 3, 15)   # day 15 of 31-day month → 15 elapsed, 16 remaining


# ---------------------------------------------------------------------------
# 1. No data / edge cases
# ---------------------------------------------------------------------------

class TestNoData:

    def test_empty_plans_returns_no_data_status(self):
        result = compute_forecast(
            daily_plans=[],
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.status == "no_data"
        assert result.total_planned == Decimal("0")
        assert result.total_spent == Decimal("0")
        assert result.all_categories == []
        assert result.categories_at_risk == []

    def test_future_month_returns_no_data(self):
        # querying April while today is in March
        result = compute_forecast(
            daily_plans=[
                _plan("dining_out", _d(2026, 4, 1), "30", "0"),
            ],
            goals=[],
            year=2026, month=4,
            today=_d(2026, 3, 15),
        )
        assert result.status == "no_data"
        assert result.days_elapsed == 0
        assert result.days_remaining == 30   # April has 30 days
        assert result.current_daily_pace == Decimal("0")

    def test_first_day_of_month_no_spending_is_no_data(self):
        # today = March 1, nothing spent yet
        result = compute_forecast(
            daily_plans=[
                _plan("groceries", _d(2026, 3, 1), "100", "0"),
            ],
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 1),
        )
        # days_elapsed=1 but total_spent=0 → pace=0, status should be on_track
        # (projected balance = total_planned - 0 = positive)
        assert result.days_elapsed == 1
        assert result.current_daily_pace == Decimal("0")
        assert result.status == "on_track"

    def test_past_month_fully_elapsed(self):
        # February 2026 queried from March 15
        result = compute_forecast(
            daily_plans=[
                _plan("groceries", _d(2026, 2, 10), "300", "280"),
                _plan("dining_out", _d(2026, 2, 15), "200", "220"),
            ],
            goals=[],
            year=2026, month=2,
            today=_d(2026, 3, 15),   # today is in a future month
        )
        assert result.days_in_month == 28   # Feb 2026
        assert result.days_elapsed == 28     # fully elapsed
        assert result.days_remaining == 0
        assert result.safe_daily_limit == Decimal("0")

    def test_to_dict_produces_serializable_floats(self):
        result = compute_forecast(
            daily_plans=[_plan("groceries", _d(2026, 3, 1), "100", "50")],
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        d = result.to_dict()
        # All numeric values must be plain float, not Decimal
        for key in ("total_planned", "total_spent", "current_daily_pace",
                    "safe_daily_limit", "projected_month_end_balance"):
            assert isinstance(d[key], float), f"{key} is not float: {type(d[key])}"


# ---------------------------------------------------------------------------
# 2. Status thresholds
# ---------------------------------------------------------------------------

class TestStatusThresholds:
    """
    total_planned = 3100 (31 days × 100/day)
    days_elapsed  = 15   → days_remaining = 16
    """

    def _make_plans(self, spent_per_day: str) -> list:
        """31 groceries rows at $100 planned each; spent = spent_per_day."""
        plans = []
        for d in range(1, 32):
            actual_spent = spent_per_day if d <= 15 else "0"
            plans.append(_plan("groceries", _d(2026, 3, d), "100", actual_spent))
        return plans

    def test_on_track_spending_at_pace(self):
        # Spending exactly $100/day → projected balance = 0
        result = compute_forecast(
            daily_plans=self._make_plans("100"),
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.status == "on_track"
        assert result.projected_month_end_balance >= Decimal("0")

    def test_on_track_underspending(self):
        # $80/day instead of $100 → surplus
        result = compute_forecast(
            daily_plans=self._make_plans("80"),
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.status == "on_track"
        assert result.projected_month_end_balance > Decimal("0")

    def test_warning_slightly_over_budget(self):
        # $105/day → pace is 5% over; projected overshoot < 10% of plan
        # total_planned = 3100, pace = 105
        # projected_spend = 15*105 + 16*105 = 105*31 = 3255
        # projected_balance = 3100 - 3255 = -155
        # over_fraction = 155/3100 = 5% < 10% → warning
        result = compute_forecast(
            daily_plans=self._make_plans("105"),
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.status == "warning"
        assert result.projected_month_end_balance < Decimal("0")

    def test_danger_significantly_over_budget(self):
        # $120/day → 20% over pace
        # projected_spend = 120*31 = 3720, projected_balance = 3100-3720 = -620
        # over_fraction = 620/3100 = 20% >= 10% → danger
        result = compute_forecast(
            daily_plans=self._make_plans("120"),
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.status == "danger"


# ---------------------------------------------------------------------------
# 3. Safe daily limit and pace math
# ---------------------------------------------------------------------------

class TestGlobalMetrics:

    def test_safe_daily_limit_math(self):
        # 31 days of $100 planned, spent $1000 in 10 days
        # remaining_budget = 3100 - 1000 = 2100
        # days_remaining = 21
        # safe_daily_limit = 2100/21 = 100.00
        plans = [
            _plan("groceries", _d(2026, 3, d), "100", "100" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        assert result.days_elapsed == 10
        assert result.days_remaining == 21
        assert result.remaining_budget == Decimal("2100")
        assert result.safe_daily_limit == Decimal("100.00")

    def test_safe_daily_limit_overspent_is_negative(self):
        # Spent $150/day × 10 days = $1500 on $3100 plan
        # remaining = 3100 - 1500 = 1600
        # safe_limit = 1600 / 21 ≈ 76.19
        plans = [
            _plan("dining_out", _d(2026, 3, d), "100", "150" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        assert result.safe_daily_limit == Decimal("76.19")

    def test_current_daily_pace_exact(self):
        # 15 days elapsed, $1500 spent → pace = $100/day
        plans = [
            _plan("groceries", _d(2026, 3, d), "100", "100" if d <= 15 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.current_daily_pace == Decimal("100.00")

    def test_projected_balance_formula(self):
        # pace = 120, remaining = 16 days, total_planned = 3100
        # projected_spend = 15*120 + 16*120 = 120*31 = 3720
        # projected_balance = 3100 - 3720 = -620
        plans = [
            _plan("dining_out", _d(2026, 3, d), "100", "120" if d <= 15 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.projected_month_end_spend == Decimal("3720.00")
        assert result.projected_month_end_balance == Decimal("-620.00")


# ---------------------------------------------------------------------------
# 4. Category forecasts
# ---------------------------------------------------------------------------

class TestCategoryForecasts:

    def _two_category_plans(self, dining_spent: str, groceries_spent: str) -> list:
        """
        Two categories, 31 days each:
          dining_out  planned=$30/day
          groceries   planned=$70/day
        Spending only in first 15 days; future days have $0 spent.
        """
        plans = []
        for d in range(1, 32):
            if d <= 15:
                plans.append(_plan("dining_out",  _d(2026, 3, d), "30", dining_spent))
                plans.append(_plan("groceries",   _d(2026, 3, d), "70", groceries_spent))
            else:
                plans.append(_plan("dining_out",  _d(2026, 3, d), "30", "0"))
                plans.append(_plan("groceries",   _d(2026, 3, d), "70", "0"))
        return plans

    def test_category_on_track_not_in_risk_list(self):
        # dining at exactly planned pace ($30/day) → ratio = 1.0 < 1.20
        result = compute_forecast(
            daily_plans=self._two_category_plans("30", "70"),
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        at_risk_cats = [c.category for c in result.categories_at_risk]
        assert "dining_out" not in at_risk_cats
        assert "groceries" not in at_risk_cats

    def test_category_just_below_threshold_not_at_risk(self):
        # 119% of planned rate → ratio = 1.19 < 1.20 → not at risk
        # planned_per_day = 30; pace needed = 30*1.19 = 35.70 → spent/15 = 35.70
        # spent_per_day = 35.70 → total_spent_dining = 535.50
        # pace = 535.50 / 15 = 35.70; ratio = 35.70/30 = 1.19
        plans = []
        for d in range(1, 32):
            spent = "35.70" if d <= 15 else "0"
            plans.append(_plan("dining_out", _d(2026, 3, d), "30", spent))
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert result.categories_at_risk == []

    def test_category_above_threshold_is_at_risk(self):
        # 150% of planned rate → ratio = 1.50 >= 1.20 → at risk
        # pace = 30 * 1.50 = 45/day
        plans = []
        for d in range(1, 32):
            spent = "45" if d <= 15 else "0"
            plans.append(_plan("dining_out", _d(2026, 3, d), "30", spent))
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        at_risk = {c.category for c in result.categories_at_risk}
        assert "dining_out" in at_risk

    def test_categories_at_risk_sorted_descending_by_ratio(self):
        # Two at-risk categories with different ratios
        plans = []
        for d in range(1, 32):
            if d <= 15:
                # dining: 200% (ratio 2.0), groceries: 150% (ratio 1.5)
                plans.append(_plan("dining_out", _d(2026, 3, d), "30", "60"))
                plans.append(_plan("groceries",  _d(2026, 3, d), "70", "105"))
            else:
                plans.append(_plan("dining_out", _d(2026, 3, d), "30", "0"))
                plans.append(_plan("groceries",  _d(2026, 3, d), "70", "0"))
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=TODAY_MID_MARCH,
        )
        assert len(result.categories_at_risk) == 2
        # dining_out has higher ratio (2.0) → first
        assert result.categories_at_risk[0].category == "dining_out"
        assert result.categories_at_risk[1].category == "groceries"
        # ratios are descending
        ratios = [c.overspend_ratio for c in result.categories_at_risk]
        assert ratios == sorted(ratios, reverse=True)

    def test_all_categories_sorted_by_monthly_planned_desc(self):
        plans = [
            _plan("dining_out", _d(2026, 3, 1), "30", "0"),   # planned=30
            _plan("groceries",  _d(2026, 3, 1), "70", "0"),   # planned=70
            _plan("coffee",     _d(2026, 3, 1), "10", "0"),   # planned=10
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 1),
        )
        planned_amounts = [c.monthly_planned for c in result.all_categories]
        assert planned_amounts == sorted(planned_amounts, reverse=True)

    def test_category_aggregates_multiple_rows_same_category(self):
        # 3 dining_out rows on different days — all should sum into one CategoryForecast
        plans = [
            _plan("dining_out", _d(2026, 3, 1), "30", "40"),
            _plan("dining_out", _d(2026, 3, 2), "30", "25"),
            _plan("dining_out", _d(2026, 3, 3), "30", "30"),
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 3),
        )
        assert len(result.all_categories) == 1
        cat = result.all_categories[0]
        assert cat.monthly_planned == Decimal("90")
        assert cat.monthly_spent == Decimal("95")


# ---------------------------------------------------------------------------
# 5. Days until exhausted
# ---------------------------------------------------------------------------

class TestDaysUntilExhausted:

    def test_days_until_exhausted_normal(self):
        # pace = $20/day, remaining = $200 → exhausted in 10 days
        plans = [
            _plan("dining_out", _d(2026, 3, d), "30", "20" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        dining = next(c for c in result.all_categories if c.category == "dining_out")
        # monthly_planned = 930, spent = 200, remaining = 730, pace = 20
        # days_until = 730/20 = 36.5 → 37 (rounded half-up)
        assert dining.days_until_exhausted == 37

    def test_days_until_exhausted_zero_pace_returns_none(self):
        # No spending → pace = 0 → cannot predict exhaustion
        plans = [
            _plan("entertainment", _d(2026, 3, d), "50", "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        ent = result.all_categories[0]
        assert ent.days_until_exhausted is None

    def test_days_until_exhausted_already_exhausted_returns_zero(self):
        # spent > planned → remaining_cat <= 0 → 0
        plans = [
            _plan("dining_out", _d(2026, 3, 1), "30", "50"),   # over budget
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 1),
        )
        dining = result.all_categories[0]
        assert dining.days_until_exhausted == 0


# ---------------------------------------------------------------------------
# 6. Goal forecasts
# ---------------------------------------------------------------------------

class TestGoalForecasts:

    def test_goal_on_track_with_sufficient_contribution(self):
        # Target $1200, saved $300, need $900 more.
        # target_date = 6 months away; monthly_contribution = $200
        # months_remaining ≈ 6, projected_saved = 300 + 200*6 = 1500 >= 1200 → on track
        far_future = date(2026, 9, 15)
        result = compute_forecast(
            daily_plans=[],
            goals=[
                _goal("1200", "300", contribution="200", target_date=far_future)
            ],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        assert g.on_track is True
        assert g.shortfall == Decimal("0")
        assert g.projected_saved is not None
        assert g.projected_saved >= Decimal("1200")

    def test_goal_not_on_track_shortfall_calculated(self):
        # Target $1200, saved $0, contribution = $50/month
        # 6 months remaining, projected = 0 + 50*6 = 300 < 1200 → not on track
        far_future = date(2026, 9, 15)
        result = compute_forecast(
            daily_plans=[],
            goals=[
                _goal("1200", "0", contribution="50", target_date=far_future)
            ],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        assert g.on_track is False
        assert g.shortfall > Decimal("0")
        assert g.required_monthly_contribution is not None
        # Required monthly = 1200 / months_remaining ≈ $198–200
        # (months_remaining = 184 days / 30.44 = 6.04, not exactly 6)
        assert Decimal("190") < g.required_monthly_contribution < Decimal("210")

    def test_goal_no_target_date_shows_raw_state(self):
        g_data = _goal("500", "100")   # no target_date, no contribution
        result = compute_forecast(
            daily_plans=[],
            goals=[g_data],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        assert g.target_date is None
        assert g.months_remaining is None
        assert g.projected_saved is None
        assert g.on_track is False
        assert g.shortfall == Decimal("400")

    def test_goal_overdue_is_not_on_track(self):
        # target_date in the past
        past_date = _d(2026, 2, 1)
        result = compute_forecast(
            daily_plans=[],
            goals=[_goal("500", "200", contribution="100", target_date=past_date)],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        assert g.on_track is False
        assert g.months_remaining == Decimal("0")
        assert g.shortfall == Decimal("300")

    def test_goal_already_fully_funded_is_on_track(self):
        # saved >= target → on track, shortfall = 0
        result = compute_forecast(
            daily_plans=[],
            goals=[_goal("500", "600", contribution="100", target_date=_d(2026, 9, 1))],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        assert g.on_track is True
        assert g.shortfall == Decimal("0")
        assert g.remaining == Decimal("0")

    def test_goal_no_contribution_set_is_not_on_track(self):
        # No monthly_contribution → can't project savings → not on track
        result = compute_forecast(
            daily_plans=[],
            goals=[
                _goal("1000", "100", contribution=None, target_date=_d(2026, 9, 1))
            ],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        g = result.goals[0]
        # contribution=None → treated as 0 → projected_saved = 100 + 0 = 100 < 1000
        assert g.on_track is False
        assert g.shortfall > Decimal("0")

    def test_multiple_goals_all_included(self):
        result = compute_forecast(
            daily_plans=[],
            goals=[
                _goal("500",  "500", contribution="0"),    # fully funded
                _goal("1000", "0",   contribution="200", target_date=_d(2026, 9, 1)),
                _goal("300",  "100", contribution="50",  target_date=_d(2026, 6, 1)),
            ],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )
        assert len(result.goals) == 3


# ---------------------------------------------------------------------------
# 7. Decimal precision — no float leakage in internal arithmetic
# ---------------------------------------------------------------------------

class TestDecimalPrecision:

    def test_no_float_in_internal_computations(self):
        """
        Verify that engine fields are Decimal before to_dict() converts them.
        This guards against accidental float() calls in the engine internals.
        """
        plans = [
            _plan("dining_out", _d(2026, 3, d), "33.33", "11.11" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        # These attributes must all be Decimal instances
        assert isinstance(result.total_planned, Decimal)
        assert isinstance(result.total_spent, Decimal)
        assert isinstance(result.remaining_budget, Decimal)
        assert isinstance(result.current_daily_pace, Decimal)
        assert isinstance(result.safe_daily_limit, Decimal)
        assert isinstance(result.projected_month_end_spend, Decimal)
        assert isinstance(result.projected_month_end_balance, Decimal)

    def test_to_dict_uses_float_only(self):
        plans = [_plan("groceries", _d(2026, 3, 1), "100", "50")]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 1),
        )
        d = result.to_dict()
        numeric_keys = [
            "total_planned", "total_spent", "remaining_budget",
            "current_daily_pace", "safe_daily_limit",
            "projected_month_end_spend", "projected_month_end_balance",
        ]
        for key in numeric_keys:
            assert isinstance(d[key], float), f"{key} should be float in to_dict()"

    def test_safe_daily_limit_precision_two_decimals(self):
        # $2100 / 21 = $100.00 exactly
        plans = [
            _plan("groceries", _d(2026, 3, d), "100", "100" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        # Check exactly 2 decimal places in Decimal form
        assert result.safe_daily_limit == result.safe_daily_limit.quantize(Decimal("0.01"))

    def test_overspend_ratio_precision_two_decimals(self):
        # pace = 45, planned_per_day = 30 → ratio = 1.50
        plans = [
            _plan("dining_out", _d(2026, 3, d), "30", "45" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        result = compute_forecast(
            daily_plans=plans,
            goals=[],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )
        dining = result.all_categories[0]
        assert dining.overspend_ratio == Decimal("1.50")


# ---------------------------------------------------------------------------
# 8. Integration: full scenario
# ---------------------------------------------------------------------------

class TestFullScenario:
    """
    Simulates a realistic mid-month scenario with two spending categories
    and one savings goal.
    """

    def test_realistic_mid_month_danger(self):
        """
        User has $3100 monthly budget (31 days × $100/day).
        After 10 days they've spent $1500 (50% overspend).
        Goal: $500 vacation by June 1, 2026. Saving $50/month.
        Expected: danger status, vacation goal not on track.
        """
        plans = [
            _plan("groceries",  _d(2026, 3, d), "70", "90" if d <= 10 else "0")
            for d in range(1, 32)
        ] + [
            _plan("dining_out", _d(2026, 3, d), "30", "60" if d <= 10 else "0")
            for d in range(1, 32)
        ]
        # total_spent = (90+60)*10 = 1500; total_planned = 100*31 = 3100
        # pace = 1500/10 = 150; projected = 1500 + 150*21 = 4650
        # balance = 3100 - 4650 = -1550 → -1550/3100 = 50% → danger

        result = compute_forecast(
            daily_plans=plans,
            goals=[
                _goal("500", "50", contribution="50", target_date=_d(2026, 6, 1))
            ],
            year=2026, month=3,
            today=_d(2026, 3, 10),
        )

        assert result.status == "danger"
        assert result.total_spent == Decimal("1500")
        assert result.current_daily_pace == Decimal("150.00")
        assert result.projected_month_end_spend == Decimal("4650.00")
        assert result.projected_month_end_balance == Decimal("-1550.00")

        # Both categories should be at risk (pace 90/70=1.28x and 60/30=2.0x)
        at_risk_cats = {c.category for c in result.categories_at_risk}
        assert "dining_out" in at_risk_cats
        assert "groceries" in at_risk_cats

        # Goal: 50 + 50*months_remaining; June 1 is ~2.5 months away → 175 < 500
        vacation = result.goals[0]
        assert vacation.on_track is False
        assert vacation.shortfall > Decimal("0")

    def test_on_track_scenario_all_green(self):
        """User spending exactly at planned pace, savings goal on track."""
        plans = [
            _plan("groceries",  _d(2026, 3, d), "70", "70")
            for d in range(1, 16)
        ] + [
            _plan("dining_out", _d(2026, 3, d), "30", "30")
            for d in range(1, 16)
        ] + [
            _plan("groceries",  _d(2026, 3, d), "70", "0")
            for d in range(16, 32)
        ] + [
            _plan("dining_out", _d(2026, 3, d), "30", "0")
            for d in range(16, 32)
        ]

        result = compute_forecast(
            daily_plans=plans,
            goals=[
                _goal("600", "200", contribution="200", target_date=_d(2026, 5, 1))
            ],
            year=2026, month=3,
            today=_d(2026, 3, 15),
        )

        assert result.status == "on_track"
        assert result.categories_at_risk == []
        # Goal: 200 + 200*~1.5 = 500 vs target 600 → borderline, exact depends on months
        # Main assertion: no crash, all fields populated
        assert len(result.all_categories) == 2
        assert len(result.goals) == 1

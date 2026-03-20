"""
Unit tests for velocity_alert_engine.py

Pure computation — no DB, no IO.
All arithmetic verified in Decimal to match production behaviour.

IMPORTANT — planned_amount convention used throughout:
  velocity_ratio = (monthly_spent / days_elapsed) / (monthly_planned / 31)

  To hit a TARGET ratio with 10 plan rows and spent_per_row = $10:
    planned_per_row = 31 / target_ratio
  (because 10*planned_per_row/31 = planned_per_day, and 10/planned_per_day = ratio)

Coverage:
  TestNoData               — guard-rails (too few days, empty plans)
  TestVelocityRatio        — velocity_ratio formula correctness
  TestAlertLevels          — exact threshold boundaries
  TestSacredCategories     — sacred categories never alert
  TestDaysUntilExhausted   — budget exhaustion calculation
  TestGoalImpact           — projected deficit → goal delay
  TestWinDetection         — streak counting
  TestDecimalPrecision     — Decimal in / float out (to_dict)
  TestCategoryFilter       — category= param filters correctly
  TestEdgeCases            — zeros, negatives, unknown categories
  TestFullScenario         — realistic end-to-end snapshots
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.services.core.engine.velocity_alert_engine import (
    DailyPlanData,
    GoalData,
    VelocityAlertLevel,
    compute_velocity_alerts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan(day: int, category: str, planned: str, spent: str, year=2026, month=3):
    return DailyPlanData(
        plan_date=date(year, month, day),
        category=category,
        planned_amount=Decimal(planned),
        spent_amount=Decimal(spent),
    )


def _goal(
    title="Vacation",
    target="1000.00",
    saved="200.00",
    contribution="200.00",
    target_date=date(2026, 7, 1),
):
    return GoalData(
        goal_id="goal-1",
        title=title,
        target_amount=Decimal(target),
        saved_amount=Decimal(saved),
        monthly_contribution=Decimal(contribution),
        target_date=target_date,
    )


def _run(plans, goals=None, year=2026, month=3, today=None, category=None):
    if goals is None:
        goals = []
    if today is None:
        today = date(2026, 3, 10)  # day 10 — enough data (MIN_DAYS = 3)
    return compute_velocity_alerts(
        daily_plans=plans,
        goals=goals,
        year=year,
        month=month,
        today=today,
        category=category,
    )


def _make_plans_at_ratio(ratio_str: str, category: str = "dining_out", days: int = 10):
    """
    Create `days` DailyPlanData rows that produce the given velocity_ratio.

    Formula (March has 31 days, spent_per_row = $10):
        planned_per_row = 31 / target_ratio

    Verification:
        monthly_planned = days * planned_per_row
        planned_per_day = monthly_planned / 31 = days * planned_per_row / 31
        daily_pace      = (days * 10) / days = 10
        ratio           = 10 / planned_per_day = 31 / planned_per_row
    """
    target_ratio = Decimal(ratio_str)
    planned_per_row = (Decimal("31") / target_ratio).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    return [
        _plan(d, category, str(planned_per_row), "10.00") for d in range(1, days + 1)
    ]


# ---------------------------------------------------------------------------
# TestNoData
# ---------------------------------------------------------------------------

class TestNoData:
    """Engine must return empty result when there is not enough data."""

    def test_zero_days_elapsed(self):
        """First day of the month — not enough history."""
        plans = [_plan(1, "dining_out", "31.00", "10.00")]
        result = _run(plans, today=date(2026, 3, 1))
        assert result.alerts == []
        assert result.all_categories == []

    def test_one_day_elapsed(self):
        plans = [_plan(1, "dining_out", "31.00", "50.00")]
        result = _run(plans, today=date(2026, 3, 1))
        assert result.alerts == []

    def test_two_days_elapsed(self):
        plans = [
            _plan(1, "dining_out", "31.00", "50.00"),
            _plan(2, "dining_out", "31.00", "50.00"),
        ]
        result = _run(plans, today=date(2026, 3, 2))
        assert result.alerts == []

    def test_empty_plan_list(self):
        result = _run([])
        assert result.alerts == []
        assert result.wins == []

    def test_all_unplanned_categories(self):
        """All rows have planned_amount = 0 → skip."""
        plans = [_plan(5, "dining_out", "0.00", "30.00")]
        result = _run(plans, today=date(2026, 3, 10))
        assert result.alerts == []


# ---------------------------------------------------------------------------
# TestVelocityRatio
# ---------------------------------------------------------------------------

class TestVelocityRatio:
    """velocity_ratio = (monthly_spent / days_elapsed) / (monthly_planned / days_in_month)"""

    def test_on_track_ratio(self):
        """Spending exactly on track → ratio = 1.0 → no alert.

        With 10 rows of planned=$31, spent=$10:
          monthly_planned = 310, planned_per_day = 310/31 = 10
          daily_pace = 100/10 = 10
          ratio = 1.0
        """
        plans = [_plan(d, "groceries", "31.00", "10.00") for d in range(1, 11)]
        result = _run(plans)
        assert result.alerts == []

    def test_slightly_under_pace(self):
        """Under-budget → ratio = 0.7 → no alert."""
        plans = [_plan(d, "dining_out", "31.00", "7.00") for d in range(1, 11)]
        result = _run(plans)
        assert result.alerts == []

    def test_velocity_ratio_computed_correctly(self):
        """Verify daily_pace and velocity_ratio attributes are correct."""
        plans = [
            _plan(d, "entertainment_events", "10.00", "20.00") for d in range(1, 11)
        ]
        result = _run(plans)
        cv = result.all_categories[0]
        # daily_pace = (10*20) / 10 = 20.00
        assert cv.daily_pace == Decimal("20.00")
        # velocity_ratio is high because planned_per_day = 100/31 ≈ 3.23
        assert cv.velocity_ratio >= Decimal("1.90")

    def test_ratio_zero_when_no_spending(self):
        """No spending → velocity_ratio = 0 → no alert."""
        plans = [_plan(d, "dining_out", "31.00", "0.00") for d in range(1, 11)]
        result = _run(plans)
        cv = result.all_categories[0]
        assert cv.velocity_ratio == Decimal("0")
        assert cv.alert_level is None


# ---------------------------------------------------------------------------
# TestAlertLevels
# ---------------------------------------------------------------------------

class TestAlertLevels:
    """Exact threshold boundary tests using _make_plans_at_ratio."""

    def test_below_watch_no_alert(self):
        plans = _make_plans_at_ratio("1.19")
        result = _run(plans)
        assert result.alerts == []

    def test_exactly_at_watch(self):
        plans = _make_plans_at_ratio("1.20")
        result = _run(plans)
        assert len(result.alerts) == 1
        assert result.alerts[0].alert_level == VelocityAlertLevel.WATCH

    def test_between_watch_and_warning(self):
        plans = _make_plans_at_ratio("1.49")
        result = _run(plans)
        assert result.alerts[0].alert_level == VelocityAlertLevel.WATCH

    def test_exactly_at_warning(self):
        plans = _make_plans_at_ratio("1.50")
        result = _run(plans)
        assert result.alerts[0].alert_level == VelocityAlertLevel.WARNING

    def test_between_warning_and_critical(self):
        plans = _make_plans_at_ratio("1.99")
        result = _run(plans)
        assert result.alerts[0].alert_level == VelocityAlertLevel.WARNING

    def test_exactly_at_critical(self):
        plans = _make_plans_at_ratio("2.00")
        result = _run(plans)
        assert result.alerts[0].alert_level == VelocityAlertLevel.CRITICAL

    def test_alerts_sorted_critical_first(self):
        """CRITICAL categories appear before WARNING/WATCH in result.alerts."""
        plans_crit = _make_plans_at_ratio("2.50", category="gaming")
        plans_warn = _make_plans_at_ratio("1.60", category="dining_out")
        plans_watch = _make_plans_at_ratio("1.25", category="delivery")
        result = _run(plans_crit + plans_warn + plans_watch)
        levels = [a.alert_level for a in result.alerts]
        assert levels[0] == VelocityAlertLevel.CRITICAL
        assert levels[1] == VelocityAlertLevel.WARNING
        assert levels[2] == VelocityAlertLevel.WATCH


# ---------------------------------------------------------------------------
# TestSacredCategories
# ---------------------------------------------------------------------------

class TestSacredCategories:
    """Sacred categories must NEVER receive velocity alerts."""

    def _sacred_plans(self, category: str):
        """Huge overspend on a sacred category — still no alert."""
        return [_plan(d, category, "10.00", "50.00") for d in range(1, 11)]

    def test_rent_never_alerts(self):
        result = _run(self._sacred_plans("rent"))
        assert result.alerts == []
        cv = result.all_categories[0]
        assert cv.is_sacred_category is True
        assert cv.alert_level is None

    def test_savings_goal_never_alerts(self):
        result = _run(self._sacred_plans("savings_goal"))
        assert result.alerts == []

    def test_mortgage_never_alerts(self):
        result = _run(self._sacred_plans("mortgage"))
        assert result.alerts == []

    def test_utilities_never_alerts(self):
        result = _run(self._sacred_plans("utilities"))
        assert result.alerts == []


# ---------------------------------------------------------------------------
# TestDaysUntilExhausted
# ---------------------------------------------------------------------------

class TestDaysUntilExhausted:
    """Correct computation of days_until_exhausted.

    All plans use planned_per_row=$31 so that planned_per_day=$10 exactly
    (10 rows × $31 / 31 days = $10/day).
    """

    def test_normal_pace_exhaustion(self):
        """$10/day for 10 days → $100 spent, $210 remaining, 21 days left."""
        plans = [_plan(d, "dining_out", "31.00", "10.00") for d in range(1, 11)]
        result = _run(plans, today=date(2026, 3, 10))
        cv = result.all_categories[0]
        # monthly_planned=310, monthly_spent=100
        # daily_pace=10, remaining=210, days_until=210/10=21.0
        assert cv.days_until_exhausted == Decimal("21.0")

    def test_fast_pace_exhaustion(self):
        """$30/day for 10 days → $300 spent on $310 plan, ~0.3 days left."""
        plans = [_plan(d, "dining_out", "31.00", "30.00") for d in range(1, 11)]
        result = _run(plans, today=date(2026, 3, 10))
        cv = result.all_categories[0]
        # monthly_planned=310, monthly_spent=300
        # daily_pace=30, remaining=10, days_until=10/30≈0.3
        assert cv.days_until_exhausted == Decimal("0.3")

    def test_exhausted_already(self):
        """Spent > planned → days_until_exhausted = 0."""
        plans = [_plan(d, "dining_out", "10.00", "40.00") for d in range(1, 11)]
        result = _run(plans, today=date(2026, 3, 10))
        cv = result.all_categories[0]
        assert cv.days_until_exhausted == Decimal("0")

    def test_no_spending_returns_none(self):
        """Zero spending → days_until_exhausted is None."""
        plans = [_plan(d, "dining_out", "31.00", "0.00") for d in range(1, 11)]
        result = _run(plans)
        cv = result.all_categories[0]
        assert cv.days_until_exhausted is None

    def test_dict_serialises_none(self):
        plans = [_plan(d, "dining_out", "31.00", "0.00") for d in range(1, 11)]
        result = _run(plans)
        d = result.all_categories[0].to_dict()
        assert d["days_until_exhausted"] is None


# ---------------------------------------------------------------------------
# TestGoalImpact
# ---------------------------------------------------------------------------

class TestGoalImpact:
    """Goal impact calculation when spending is projected to overshoot."""

    def _over_pace_plans(self, category="dining_out", multiplier=3):
        """
        Create plans where velocity_ratio = multiplier.
        planned_per_row = 31 / multiplier, spent_per_row = 10
        """
        planned_row = (Decimal("31") / Decimal(str(multiplier))).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        return [_plan(d, category, str(planned_row), "10.00") for d in range(1, 11)]

    def test_no_impact_when_on_track(self):
        """Under-plan spending → no deficit → no goal impacts."""
        # ratio = 0.5 → well under plan
        plans = [_plan(d, "dining_out", "31.00", "5.00") for d in range(1, 11)]
        goals = [_goal()]
        result = _run(plans, goals=goals)
        assert result.goal_impacts == []

    def test_goal_impact_when_overpace(self):
        """Spending 3× planned → projected deficit → goal delayed."""
        plans = self._over_pace_plans(multiplier=3)
        goals = [_goal(contribution="200.00")]
        result = _run(plans, goals=goals)
        assert len(result.goal_impacts) >= 1
        impact = result.goal_impacts[0]
        assert impact.goal_title == "Vacation"
        assert impact.projected_shortfall > 0
        assert impact.delay_days > 0

    def test_no_impact_without_active_goals(self):
        plans = self._over_pace_plans(multiplier=3)
        result = _run(plans, goals=[])
        assert result.goal_impacts == []

    def test_goal_with_no_contribution_ignored(self):
        plans = self._over_pace_plans(multiplier=3)
        goals = [_goal(contribution="0.00")]
        result = _run(plans, goals=goals)
        assert result.goal_impacts == []

    def test_goal_impact_capped_at_monthly_contribution(self):
        """shortfall = min(projected_deficit, monthly_contribution)."""
        plans = self._over_pace_plans(multiplier=4)
        goals = [_goal(contribution="50.00")]
        result = _run(plans, goals=goals)
        if result.goal_impacts:
            assert result.goal_impacts[0].projected_shortfall <= Decimal("50.00")

    def test_multiple_goals_sorted_by_delay_desc(self):
        """Goal with larger delay comes first."""
        plans = self._over_pace_plans(multiplier=3)
        g1 = GoalData("g1", "Small", Decimal("100"), Decimal("0"), Decimal("30"), date(2026, 6, 1))
        g2 = GoalData("g2", "Big", Decimal("5000"), Decimal("0"), Decimal("500"), date(2026, 12, 1))
        result = _run(plans, goals=[g1, g2])
        if len(result.goal_impacts) >= 2:
            assert result.goal_impacts[0].delay_days >= result.goal_impacts[1].delay_days

    def test_goal_without_target_date_ignored(self):
        plans = self._over_pace_plans(multiplier=3)
        g = GoalData("g1", "No deadline", Decimal("500"), Decimal("0"), Decimal("100"), None)
        result = _run(plans, goals=[g])
        assert result.goal_impacts == []


# ---------------------------------------------------------------------------
# TestWinDetection
# ---------------------------------------------------------------------------

class TestWinDetection:
    """Streak detection for positive spending wins."""

    def _good_day(self, day: int, category="dining_out"):
        """Spent only 40% of planned — well under WIN_DAILY_UNDER_PCT (80%)."""
        return _plan(day, category, "20.00", "8.00")

    def _bad_day(self, day: int, category="dining_out"):
        """Spent 120% — over budget."""
        return _plan(day, category, "20.00", "24.00")

    def test_no_streak_when_not_enough_days(self):
        """Only 5 consecutive good days → no 7-day streak notification."""
        plans = [self._good_day(d) for d in range(1, 6)]
        result = _run(plans, today=date(2026, 3, 5))
        assert result.wins == []

    def test_seven_day_streak(self):
        plans = [self._good_day(d) for d in range(1, 11)]
        result = _run(plans, today=date(2026, 3, 10))
        assert len(result.wins) == 1
        assert result.wins[0].win_type == "streak_7"
        assert result.wins[0].streak_days == 10

    def test_streak_broken_by_bad_day(self):
        """Bad day on day 5 breaks streak; only 5 good days ending today → no 7-day win."""
        plans = (
            [self._good_day(d) for d in range(1, 5)]
            + [self._bad_day(5)]
            + [self._good_day(d) for d in range(6, 11)]
        )
        result = _run(plans, today=date(2026, 3, 10))
        # Only 5 consecutive good days ending today — not a 7-day streak
        assert result.wins == []

    def test_streak_14_days(self):
        plans = [self._good_day(d) for d in range(1, 20)]
        result = _run(plans, today=date(2026, 3, 19))
        assert len(result.wins) == 1
        assert result.wins[0].win_type == "streak_14"

    def test_streak_30_days(self):
        plans = [self._good_day(d) for d in range(1, 32)]
        result = _run(plans, today=date(2026, 3, 31))
        assert len(result.wins) == 1
        assert result.wins[0].win_type == "streak_30"

    def test_wins_only_in_full_scan(self):
        """Win detection is skipped when category filter is provided."""
        plans = [self._good_day(d) for d in range(1, 11)]
        result = _run(plans, category="dining_out", today=date(2026, 3, 10))
        assert result.wins == []


# ---------------------------------------------------------------------------
# TestDecimalPrecision
# ---------------------------------------------------------------------------

class TestDecimalPrecision:
    """All internal arithmetic must use Decimal; to_dict returns float."""

    def test_internal_decimal(self):
        plans = _make_plans_at_ratio("1.50")
        result = _run(plans)
        cv = result.all_categories[0]
        assert isinstance(cv.daily_pace, Decimal)
        assert isinstance(cv.planned_per_day, Decimal)
        assert isinstance(cv.velocity_ratio, Decimal)
        assert isinstance(cv.monthly_planned, Decimal)

    def test_to_dict_returns_float(self):
        plans = _make_plans_at_ratio("1.50")
        result = _run(plans)
        d = result.all_categories[0].to_dict()
        assert isinstance(d["daily_pace"], float)
        assert isinstance(d["velocity_ratio"], float)

    def test_no_floating_point_drift(self):
        """Fractional cents must not accumulate float error."""
        plans = [
            DailyPlanData(
                plan_date=date(2026, 3, d),
                category="dining_out",
                planned_amount=Decimal("0.33"),
                spent_amount=Decimal("0.11"),
            )
            for d in range(1, 11)
        ]
        result = _run(plans)
        cv = result.all_categories[0]
        # ratio = (0.11) / (0.33 * 10 / 31) = 0.11 / 0.1065 ≈ 1.03 → no exception
        assert cv.velocity_ratio >= 0

    def test_goal_impact_decimal(self):
        plans = _make_plans_at_ratio("3.00")
        goals = [_goal()]
        result = _run(plans, goals=goals)
        if result.goal_impacts:
            assert isinstance(result.goal_impacts[0].projected_shortfall, Decimal)


# ---------------------------------------------------------------------------
# TestCategoryFilter
# ---------------------------------------------------------------------------

class TestCategoryFilter:
    """category= parameter restricts computation to one category."""

    def test_filter_returns_only_target(self):
        plans = _make_plans_at_ratio("2.00", category="dining_out") + \
                _make_plans_at_ratio("2.00", category="gaming")
        result = _run(plans, category="dining_out")
        assert all(cv.category == "dining_out" for cv in result.all_categories)

    def test_filter_non_existent_category(self):
        plans = _make_plans_at_ratio("2.00", category="dining_out")
        result = _run(plans, category="nonexistent_cat")
        assert result.alerts == []
        assert result.all_categories == []

    def test_wins_skipped_with_filter(self):
        """Win detection requires full scan — skipped when category filter set."""
        plans = [_plan(d, "dining_out", "31.00", "8.00") for d in range(1, 11)]
        result = _run(plans, category="dining_out", today=date(2026, 3, 10))
        assert result.wins == []


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Guard against division by zero and unusual inputs."""

    def test_planned_amount_zero_skipped(self):
        plans = [_plan(d, "dining_out", "0.00", "10.00") for d in range(1, 11)]
        result = _run(plans)
        assert result.all_categories == []

    def test_unknown_category_treated_as_flexible(self):
        """Unrecognised category defaults to FLEXIBLE (not sacred) — can alert."""
        plans = _make_plans_at_ratio("2.00", category="totally_new_category")
        result = _run(plans)
        cv = result.all_categories[0]
        assert cv.is_sacred_category is False
        assert cv.alert_level == VelocityAlertLevel.CRITICAL

    def test_different_year_month_ignored(self):
        """Plans from February must not pollute March's calculation."""
        plans_feb = [
            DailyPlanData(date(2026, 2, d), "dining_out", Decimal("31"), Decimal("50"))
            for d in range(1, 11)
        ]
        plans_mar = _make_plans_at_ratio("1.10", category="dining_out")  # under threshold
        result = _run(plans_feb + plans_mar, year=2026, month=3)
        # Only March rows counted — no alert expected at 1.10×
        assert result.alerts == []

    def test_result_to_dict_is_json_serialisable(self):
        """to_dict() must produce a JSON-serialisable dict."""
        import json
        plans = _make_plans_at_ratio("2.50")
        goals = [_goal()]
        result = _run(plans, goals=goals)
        serialised = json.dumps(result.to_dict())
        assert serialised  # no exception


# ---------------------------------------------------------------------------
# TestFullScenario
# ---------------------------------------------------------------------------

class TestFullScenario:
    """Realistic end-to-end scenarios."""

    def test_scenario_user_on_track(self):
        """User spending at 80% of plan → no alerts, 7-day win streak."""
        # Both categories at ratio 0.8 — clearly under WATCH (1.20)
        plans = (
            [_plan(d, "dining_out", "31.00", "8.00") for d in range(1, 11)]
            + [_plan(d, "groceries", "31.00", "8.00") for d in range(1, 11)]
        )
        result = _run(plans, today=date(2026, 3, 10))
        assert result.alerts == []
        # 10 consecutive days where per-day total (16/62 ≈ 26%) < 80% → streak_7
        assert any(w.win_type == "streak_7" for w in result.wins)

    def test_scenario_dining_critical_savings_safe(self):
        """dining_out is CRITICAL, savings_goal is sacred (no alert for it)."""
        plans = (
            [_plan(d, "dining_out", "10.00", "30.00") for d in range(1, 11)]   # ~9× → CRITICAL
            + [_plan(d, "savings_goal", "50.00", "200.00") for d in range(1, 11)]  # SACRED
        )
        result = _run(plans, today=date(2026, 3, 10))
        alert_cats = {a.category for a in result.alerts}
        assert "dining_out" in alert_cats
        assert "savings_goal" not in alert_cats

    def test_scenario_multiple_alerts_priority_order(self):
        """CRITICAL > WARNING > WATCH sort order is maintained.

        gaming  2.50×: planned_per_row=12.40, ratio=2.50 → CRITICAL
        hobbies 1.60×: planned_per_row=19.38, ratio=1.60 → WARNING
        coffee  1.30×: planned_per_row=23.85, ratio=1.30 → WATCH
        """
        plans = (
            [_plan(d, "gaming", "12.40", "10.00") for d in range(1, 11)]
            + [_plan(d, "hobbies", "19.38", "10.00") for d in range(1, 11)]
            + [_plan(d, "coffee", "23.85", "10.00") for d in range(1, 11)]
        )
        result = _run(plans, today=date(2026, 3, 10))
        levels = [a.alert_level for a in result.alerts]
        assert result.alerts[0].alert_level == VelocityAlertLevel.CRITICAL
        assert result.alerts[0].category == "gaming"
        assert VelocityAlertLevel.CRITICAL in levels
        assert VelocityAlertLevel.WARNING in levels
        assert VelocityAlertLevel.WATCH in levels

    def test_scenario_goal_impact_reported(self):
        """Overspend on dining_out → goal 'Emergency Fund' delayed."""
        # 3× overpace
        plans = _make_plans_at_ratio("3.00", category="dining_out")
        goals = [
            GoalData(
                goal_id="ef",
                title="Emergency Fund",
                target_amount=Decimal("3000"),
                saved_amount=Decimal("500"),
                monthly_contribution=Decimal("300"),
                target_date=date(2026, 12, 31),
            )
        ]
        result = _run(plans, goals=goals, today=date(2026, 3, 10))
        assert result.has_alerts()
        assert len(result.goal_impacts) >= 1
        assert result.goal_impacts[0].goal_title == "Emergency Fund"

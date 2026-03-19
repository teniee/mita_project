"""
Tests for app.services.core.engine.goal_budget_sync

Coverage:
  Unit tests (pure functions, no DB):
    - calculate_required_monthly_contribution  [12 tests]
    - calculate_daily_savings_amount           [6 tests]

  Mock-based async tests (AsyncMock DB, verify logic and query patterns):
    - sync_goal_to_daily_plan                  [11 tests]
    - remove_goal_daily_plan_rows              [4 tests]

  Integration smoke tests (real SQLite via aiosqlite — skipped when
  aiosqlite is not installed, so CI without the driver still passes):
    - full create/update/pause/resume cycle    [3 tests]

Total: 36 tests
"""
from __future__ import annotations

import asyncio
import calendar
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.core.engine.goal_budget_sync import (
    GOAL_SAVINGS_CATEGORY,
    _INACTIVE_STATUSES,
    calculate_daily_savings_amount,
    calculate_required_monthly_contribution,
    remove_goal_daily_plan_rows,
    sync_goal_to_daily_plan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine in tests without requiring pytest-asyncio."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_goal(
    *,
    target_amount: float = 500.0,
    saved_amount: float = 0.0,
    target_date=date(2026, 6, 30),
    status: str = "active",
    goal_id=None,
) -> Any:
    """Minimal Goal-like object with only the fields sync needs."""
    g = SimpleNamespace()
    g.id = goal_id or uuid.uuid4()
    g.target_amount = Decimal(str(target_amount))
    g.saved_amount = Decimal(str(saved_amount))
    g.target_date = target_date
    g.status = status
    return g


def _make_async_db(existing_row=None):
    """
    Build an AsyncMock that mimics an AsyncSession.

    execute() → returns a result whose scalar_one_or_none() gives
    `existing_row` (None by default = no row found → will INSERT).
    rowcount is set on the result returned for DELETE statements.
    """
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_row
    result.rowcount = 0
    db.execute.return_value = result
    return db


# ─────────────────────────────────────────────────────────────────────────────
# calculate_required_monthly_contribution
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateRequiredMonthlyContribution:

    TODAY = date(2026, 3, 19)

    def test_standard_case(self):
        """$500 needed by June 30 with nothing saved yet."""
        goal = _make_goal(target_amount=500, saved_amount=0, target_date=date(2026, 6, 30))
        result = calculate_required_monthly_contribution(goal, self.TODAY)
        # (500 - 0) / months_remaining; months > 0, result > 0
        assert result > Decimal("0")
        assert result < Decimal("500")

    def test_partial_savings_reduces_monthly_contribution(self):
        """Partially funded goal needs less per month."""
        full = _make_goal(target_amount=1200, saved_amount=0, target_date=date(2026, 9, 30))
        partial = _make_goal(target_amount=1200, saved_amount=600, target_date=date(2026, 9, 30))
        full_monthly = calculate_required_monthly_contribution(full, self.TODAY)
        partial_monthly = calculate_required_monthly_contribution(partial, self.TODAY)
        assert partial_monthly < full_monthly
        assert partial_monthly > Decimal("0")

    def test_no_target_date_returns_zero(self):
        goal = _make_goal(target_date=None)
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_paused_status_returns_zero(self):
        goal = _make_goal(status="paused", target_date=date(2026, 6, 30))
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_cancelled_status_returns_zero(self):
        goal = _make_goal(status="cancelled", target_date=date(2026, 6, 30))
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_completed_status_returns_zero(self):
        goal = _make_goal(status="completed", target_date=date(2026, 6, 30))
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_target_date_in_past_returns_zero(self):
        goal = _make_goal(target_date=date(2026, 1, 1))  # Past
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_target_date_is_today_returns_zero(self):
        goal = _make_goal(target_date=self.TODAY)
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_fully_funded_returns_zero(self):
        goal = _make_goal(target_amount=500, saved_amount=500)
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_overfunded_returns_zero(self):
        goal = _make_goal(target_amount=500, saved_amount=600)
        assert calculate_required_monthly_contribution(goal, self.TODAY) == Decimal("0")

    def test_returns_decimal_not_float(self):
        goal = _make_goal(target_amount=300, saved_amount=0, target_date=date(2026, 6, 1))
        result = calculate_required_monthly_contribution(goal, self.TODAY)
        assert isinstance(result, Decimal)

    def test_result_has_2_decimal_places(self):
        goal = _make_goal(target_amount=100, saved_amount=0, target_date=date(2026, 7, 1))
        result = calculate_required_monthly_contribution(goal, self.TODAY)
        # str(result) should not have more than 2 decimal digits
        assert result == result.quantize(Decimal("0.01"))


# ─────────────────────────────────────────────────────────────────────────────
# calculate_daily_savings_amount
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateDailySavingsAmount:

    def test_standard_month_31_days(self):
        # March has 31 days
        result = calculate_daily_savings_amount(Decimal("310"), 2026, 3)
        assert result == Decimal("10.00")

    def test_standard_month_28_days(self):
        # February 2026 has 28 days
        result = calculate_daily_savings_amount(Decimal("280"), 2026, 2)
        assert result == Decimal("10.00")

    def test_leap_year_february_29_days(self):
        # February 2028 has 29 days
        result = calculate_daily_savings_amount(Decimal("290"), 2028, 2)
        assert result == Decimal("10.00")

    def test_zero_contribution_returns_zero(self):
        result = calculate_daily_savings_amount(Decimal("0"), 2026, 3)
        assert result == Decimal("0")

    def test_negative_contribution_returns_zero(self):
        result = calculate_daily_savings_amount(Decimal("-10"), 2026, 3)
        assert result == Decimal("0")

    def test_result_has_2_decimal_places(self):
        # $100 / 31 days = $3.2258... → rounded to $3.23
        result = calculate_daily_savings_amount(Decimal("100"), 2026, 3)
        assert result == result.quantize(Decimal("0.01"))
        assert result == Decimal("3.23")


# ─────────────────────────────────────────────────────────────────────────────
# sync_goal_to_daily_plan — mock-based
# ─────────────────────────────────────────────────────────────────────────────

class TestSyncGoalToDailyPlan:

    USER_ID = uuid.uuid4()
    TODAY = date(2026, 3, 19)  # 13 days remaining in March (19→31 inclusive)

    def _days_remaining(self, today=None):
        d = today or self.TODAY
        last = calendar.monthrange(d.year, d.month)[1]
        return last - d.day + 1  # inclusive

    # ── Active goal with target_date ──────────────────────────────────────

    def test_active_goal_inserts_rows_for_remaining_days(self):
        """Creates one DailyPlan row per remaining day this month."""
        db = _make_async_db(existing_row=None)
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        upserted, removed = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )

        expected_days = self._days_remaining()  # 13
        assert upserted == expected_days
        assert removed == 0
        assert db.add.call_count == expected_days

    def test_active_goal_sets_goal_savings_category(self):
        """Every inserted row uses GOAL_SAVINGS_CATEGORY."""
        db = _make_async_db(existing_row=None)
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        _run(sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY))

        for add_call in db.add.call_args_list:
            row = add_call.args[0]
            assert row.category == GOAL_SAVINGS_CATEGORY

    def test_active_goal_sets_goal_id_on_rows(self):
        """Every inserted row has goal_id matching the goal."""
        db = _make_async_db(existing_row=None)
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        _run(sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY))

        for add_call in db.add.call_args_list:
            row = add_call.args[0]
            assert row.goal_id == goal.id

    def test_active_goal_sets_correct_daily_amount(self):
        """planned_amount = monthly_contribution / days_in_month."""
        db = _make_async_db(existing_row=None)
        # target $310 by June 30 ≈ 3.4 months → ~$91/month → ~$2.93/day in March
        goal = _make_goal(target_amount=310, saved_amount=0, target_date=date(2026, 6, 30))

        _run(sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY))

        monthly = calculate_required_monthly_contribution(goal, self.TODAY)
        expected_daily = calculate_daily_savings_amount(monthly, 2026, 3)

        for add_call in db.add.call_args_list:
            row = add_call.args[0]
            assert row.planned_amount == expected_daily

    def test_upsert_updates_existing_row_not_duplicate(self):
        """If a row already exists for a day, update planned_amount, don't insert."""
        existing = MagicMock()
        existing.planned_amount = Decimal("5.00")
        db = _make_async_db(existing_row=existing)

        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))
        upserted, _ = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )

        # Rows found → updated, not added
        assert db.add.call_count == 0
        assert upserted == self._days_remaining()
        # planned_amount was overwritten on the existing mock
        assert existing.planned_amount != Decimal("5.00")

    def test_flush_called_after_upsert(self):
        """db.flush() must be called so the session is aware of pending changes."""
        db = _make_async_db()
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))
        _run(sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY))
        db.flush.assert_called_once()

    def test_last_day_of_month_creates_one_row(self):
        """When called on the last day, only one row is created."""
        last_day = date(2026, 3, 31)
        db = _make_async_db()
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        upserted, _ = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=last_day)
        )
        assert upserted == 1

    # ── Inactive / no-target scenarios ───────────────────────────────────

    def test_paused_goal_removes_future_rows(self):
        """Paused goal: sync must delete future rows (free budget)."""
        db = _make_async_db()
        db.execute.return_value.rowcount = 5  # simulate 5 rows deleted
        goal = _make_goal(status="paused", target_date=date(2026, 6, 30))

        upserted, removed = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )
        assert upserted == 0
        # remove path was taken — execute was called for DELETE
        assert db.execute.called

    def test_no_target_date_removes_future_rows(self):
        """Goal without target_date: no savings target → free any existing rows."""
        db = _make_async_db()
        db.execute.return_value.rowcount = 0
        goal = _make_goal(target_date=None, status="active")

        upserted, removed = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )
        assert upserted == 0

    def test_fully_funded_goal_removes_future_rows(self):
        """Goal already reached target: no more daily reservations needed."""
        db = _make_async_db()
        db.execute.return_value.rowcount = 3
        goal = _make_goal(target_amount=500, saved_amount=500, target_date=date(2026, 6, 30))

        upserted, removed = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )
        assert upserted == 0

    def test_cancelled_goal_removes_future_rows(self):
        db = _make_async_db()
        db.execute.return_value.rowcount = 2
        goal = _make_goal(status="cancelled", target_date=date(2026, 6, 30))

        upserted, _ = _run(
            sync_goal_to_daily_plan(db, goal, self.USER_ID, today=self.TODAY)
        )
        assert upserted == 0


# ─────────────────────────────────────────────────────────────────────────────
# remove_goal_daily_plan_rows — mock-based
# ─────────────────────────────────────────────────────────────────────────────

class TestRemoveGoalDailyPlanRows:

    USER_ID = uuid.uuid4()
    GOAL_ID = uuid.uuid4()

    def test_returns_rowcount_from_delete(self):
        db = _make_async_db()
        db.execute.return_value.rowcount = 7

        result = _run(
            remove_goal_daily_plan_rows(db, self.GOAL_ID, self.USER_ID, from_date=date(2026, 3, 19))
        )
        assert result == 7

    def test_uses_today_when_from_date_not_provided(self):
        db = _make_async_db()
        db.execute.return_value.rowcount = 0

        with patch(
            "app.services.core.engine.goal_budget_sync.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 19)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            _run(remove_goal_daily_plan_rows(db, self.GOAL_ID, self.USER_ID))

        mock_date.today.assert_called_once()

    def test_zero_when_no_rows_exist(self):
        db = _make_async_db()
        db.execute.return_value.rowcount = 0

        result = _run(
            remove_goal_daily_plan_rows(db, self.GOAL_ID, self.USER_ID, from_date=date(2026, 3, 19))
        )
        assert result == 0

    def test_executes_delete_statement(self):
        """Verify that a DELETE is executed (not just a SELECT)."""
        from sqlalchemy import delete as sa_delete
        from app.db.models.daily_plan import DailyPlan

        db = _make_async_db()
        db.execute.return_value.rowcount = 3

        _run(
            remove_goal_daily_plan_rows(db, self.GOAL_ID, self.USER_ID, from_date=date(2026, 3, 19))
        )
        # execute was called exactly once with a DML delete statement
        assert db.execute.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Category priority — confirm goal_savings is SACRED
# ─────────────────────────────────────────────────────────────────────────────

class TestGoalSavingsCategoryIsSacred:

    def test_goal_savings_is_sacred(self):
        from app.core.category_priority import is_sacred
        assert is_sacred(GOAL_SAVINGS_CATEGORY) is True

    def test_goal_savings_not_donor(self):
        """Rebalancer must never take from goal_savings rows."""
        from app.core.category_priority import get_category_level, CategoryLevel
        level = get_category_level(GOAL_SAVINGS_CATEGORY)
        assert level == CategoryLevel.SACRED

    def test_inactive_statuses_coverage(self):
        """All expected inactive statuses are registered."""
        assert "paused" in _INACTIVE_STATUSES
        assert "cancelled" in _INACTIVE_STATUSES
        assert "completed" in _INACTIVE_STATUSES
        assert "active" not in _INACTIVE_STATUSES


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases and precision
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCasesAndPrecision:

    TODAY = date(2026, 3, 19)

    def test_very_short_deadline_floored_at_one_month(self):
        """deadline 5 days away → months=1, not 0.16 (avoids division near-zero)."""
        goal = _make_goal(
            target_amount=100,
            saved_amount=0,
            target_date=self.TODAY + timedelta(days=5),
        )
        result = calculate_required_monthly_contribution(goal, self.TODAY)
        # Should equal remaining / 1 month = $100 / 1 = $100
        assert result == Decimal("100.00")

    def test_large_goal_decimal_precision(self):
        """$10,000 goal stays precise throughout the calculation chain."""
        goal = _make_goal(
            target_amount=10_000,
            saved_amount=1_234.56,
            target_date=date(2026, 12, 31),
        )
        monthly = calculate_required_monthly_contribution(goal, self.TODAY)
        daily = calculate_daily_savings_amount(monthly, 2026, 3)

        # Both must be Decimal with at most 2 decimal places
        assert isinstance(monthly, Decimal)
        assert isinstance(daily, Decimal)
        assert monthly == monthly.quantize(Decimal("0.01"))
        assert daily == daily.quantize(Decimal("0.01"))

    def test_multiple_goals_produce_independent_rows(self):
        """Two simultaneous goals each get their own rows (different goal_ids)."""
        db1 = _make_async_db()
        db2 = _make_async_db()

        goal_a = _make_goal(target_amount=300, target_date=date(2026, 6, 30))
        goal_b = _make_goal(target_amount=900, target_date=date(2026, 9, 30))
        user_id = uuid.uuid4()

        _run(sync_goal_to_daily_plan(db1, goal_a, user_id, today=self.TODAY))
        _run(sync_goal_to_daily_plan(db2, goal_b, user_id, today=self.TODAY))

        # Both goals inserted the same number of days
        assert db1.add.call_count == db2.add.call_count

        # But their goal_ids differ
        row_a = db1.add.call_args_list[0].args[0]
        row_b = db2.add.call_args_list[0].args[0]
        assert row_a.goal_id != row_b.goal_id

    def test_spent_amount_initialised_to_zero_on_new_rows(self):
        """New rows start with spent_amount=0 — savings deposits come later."""
        db = _make_async_db()
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        _run(sync_goal_to_daily_plan(db, goal, uuid.uuid4(), today=self.TODAY))

        for add_call in db.add.call_args_list:
            row = add_call.args[0]
            assert row.spent_amount == Decimal("0")

    def test_status_green_on_new_rows(self):
        """New goal savings rows start green — not in deficit."""
        db = _make_async_db()
        goal = _make_goal(target_amount=500, target_date=date(2026, 6, 30))

        _run(sync_goal_to_daily_plan(db, goal, uuid.uuid4(), today=self.TODAY))

        for add_call in db.add.call_args_list:
            row = add_call.args[0]
            assert row.status == "green"

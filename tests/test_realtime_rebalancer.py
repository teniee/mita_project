"""
Tests for the Real-time Budget Rebalancer (Problem 1 fix).

Verifies that when a user overspends in a category, the system
automatically redistributes budget from future days of lower-priority
categories.

Coverage:
- No overspend → no rebalance triggered
- Overspend in DISCRETIONARY covered by another DISCRETIONARY donor
- SACRED categories are never touched as donors
- PROTECTED categories are used only when DISCRETIONARY is exhausted
- Partial coverage when total surplus is insufficient
- No future entries → returns early, no crash
- planned_amount on overspent day is credited after rebalance
- Dry-run mode: calculates but does not commit
- Float precision: all amounts stored as Decimal, no float leakage
"""
import sys
import os
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.core.engine.realtime_rebalancer import (
    RebalancePlan,
    check_and_rebalance,
    rebalance_after_overspend,
)


# ---------------------------------------------------------------------------
# Helpers — build fake DailyPlan objects without a real DB
# ---------------------------------------------------------------------------

def _make_plan(category, day, planned, spent, user_id=None):
    """Create a mock DailyPlan row."""
    m = MagicMock()
    m.category = category
    m.date = datetime(day.year, day.month, day.day, 12, 0, 0)
    m.planned_amount = Decimal(str(planned))
    m.spent_amount = Decimal(str(spent))
    m.user_id = user_id or uuid4()
    return m


def _make_db_with_entries(entries, overspent_entry=None):
    """
    Build a mock Session that returns `entries` from query().filter(...).all()
    and `overspent_entry` from query().filter(...).first().
    """
    db = MagicMock()

    class _Query:
        def __init__(self, call_count=[0]):
            self._count = call_count

        def filter(self, *args, **kwargs):
            return self

        def filter_by(self, *args, **kwargs):
            return self

        def order_by(self, *args):
            return self

        def all(self):
            return entries

        def first(self):
            return overspent_entry

    db.query.return_value = _Query()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


# ---------------------------------------------------------------------------
# RebalancePlan unit tests
# ---------------------------------------------------------------------------

class TestRebalancePlan:
    def test_fully_covered_true(self):
        rp = RebalancePlan()
        rp.covered = Decimal("10.00")
        rp.uncovered = Decimal("0.00")
        assert rp.fully_covered is True

    def test_fully_covered_within_threshold(self):
        rp = RebalancePlan()
        rp.covered = Decimal("9.99")
        rp.uncovered = Decimal("0.005")  # below 0.01 threshold
        assert rp.fully_covered is True

    def test_not_fully_covered(self):
        rp = RebalancePlan()
        rp.covered = Decimal("5.00")
        rp.uncovered = Decimal("5.00")
        assert rp.fully_covered is False

    def test_to_dict_structure(self):
        rp = RebalancePlan()
        rp.overspent_category = "dining_out"
        rp.overspend_amount = Decimal("10.00")
        rp.covered = Decimal("8.00")
        rp.uncovered = Decimal("2.00")
        rp.transfers = [{"from_category": "entertainment", "total_taken": 8.0}]
        d = rp.to_dict()
        assert d["overspent_category"] == "dining_out"
        assert d["overspend_amount"] == 10.0
        assert d["covered"] == 8.0
        assert d["uncovered"] == 2.0
        assert len(d["transfers"]) == 1
        assert d["fully_covered"] is False


# ---------------------------------------------------------------------------
# rebalance_after_overspend
# ---------------------------------------------------------------------------

class TestRebalanceAfterOverspend:
    """Core algorithm tests using mock DB."""

    @pytest.fixture
    def user_id(self):
        return uuid4()

    @pytest.fixture
    def txn_date(self):
        return date(2026, 3, 10)

    def test_no_future_entries_returns_uncovered(self, user_id, txn_date):
        """If there are no future DailyPlan rows, deficit stays uncovered."""
        db = _make_db_with_entries(entries=[])
        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("20.00"),
            transaction_date=txn_date,
            dry_run=True,
        )
        assert result.uncovered == Decimal("20.00")
        assert result.covered == Decimal("0.00")
        assert result.transfers == []

    def test_discretionary_donor_covers_deficit(self, user_id, txn_date):
        """DISCRETIONARY category donates to cover overspend."""
        future_day = date(2026, 3, 15)
        # entertainment has $40 planned, $0 spent → $40 surplus
        donor = _make_plan("entertainment", future_day, planned=40, spent=0, user_id=user_id)
        # overspent entry on txn_date
        overspent = _make_plan("dining_out", txn_date, planned=25, spent=35, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("10.00"),
            transaction_date=txn_date,
            dry_run=False,
        )

        # $10 should be covered
        assert result.covered == Decimal("10.00")
        assert result.uncovered == Decimal("0.00")
        assert result.fully_covered is True
        assert len(result.transfers) == 1
        assert result.transfers[0]["from_category"] == "entertainment"
        # DB commit should have been called
        db.commit.assert_called_once()

    def test_sacred_category_never_touched(self, user_id, txn_date):
        """SACRED categories (rent, savings_goal, etc.) must NOT donate."""
        future_day = date(2026, 3, 20)
        sacred_donor = _make_plan("rent", future_day, planned=1000, spent=0, user_id=user_id)
        savings_donor = _make_plan("savings_goal", future_day, planned=500, spent=0, user_id=user_id)

        db = _make_db_with_entries(entries=[sacred_donor, savings_donor])

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("50.00"),
            transaction_date=txn_date,
            dry_run=True,
        )

        assert result.covered == Decimal("0.00")
        assert result.uncovered == Decimal("50.00")
        assert result.transfers == []

    def test_50_percent_cap_on_donor(self, user_id, txn_date):
        """Max 50% of any donor category can be taken."""
        future_day = date(2026, 3, 18)
        # $100 entertainment surplus
        donor = _make_plan("entertainment", future_day, planned=100, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=20, spent=120, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("100.00"),
            transaction_date=txn_date,
            dry_run=True,
        )

        # Capped at 50% of $100 = $50
        assert result.covered <= Decimal("50.00")
        assert result.uncovered >= Decimal("50.00")

    def test_discretionary_taken_before_protected(self, user_id, txn_date):
        """DISCRETIONARY (priority 3) must be drained before PROTECTED (priority 1)."""
        future_day = date(2026, 3, 25)
        # entertainment = DISCRETIONARY, groceries = PROTECTED
        entertainment = _make_plan("entertainment", future_day, planned=30, spent=0, user_id=user_id)
        groceries = _make_plan("groceries", future_day, planned=50, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=10, spent=20, user_id=user_id)

        db = _make_db_with_entries(entries=[entertainment, groceries], overspent_entry=overspent)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("10.00"),
            transaction_date=txn_date,
            dry_run=True,
        )

        # Should only need entertainment, not touch groceries
        categories_donated = [t["from_category"] for t in result.transfers]
        assert "entertainment" in categories_donated
        # Groceries should NOT be needed since entertainment covers it
        assert "groceries" not in categories_donated

    def test_partial_coverage_when_surplus_insufficient(self, user_id, txn_date):
        """When total surplus < deficit, partially cover and report uncovered."""
        future_day = date(2026, 3, 20)
        # Only $5 available in entertainment
        donor = _make_plan("entertainment", future_day, planned=10, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=10, spent=60, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("50.00"),
            transaction_date=txn_date,
            dry_run=True,
        )

        # covered < deficit
        assert result.covered < Decimal("50.00")
        assert result.uncovered > Decimal("0.00")
        assert result.covered + result.uncovered == Decimal("50.00")

    def test_dry_run_does_not_commit(self, user_id, txn_date):
        """dry_run=True must calculate but never call db.commit()."""
        future_day = date(2026, 3, 28)
        donor = _make_plan("gaming", future_day, planned=60, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=20, spent=40, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("20.00"),
            transaction_date=txn_date,
            dry_run=True,
        )

        assert result.covered > Decimal("0.00")
        db.commit.assert_not_called()

    def test_overspent_entry_planned_amount_increased(self, user_id, txn_date):
        """After rebalance, planned_amount on overspent day must increase."""
        future_day = date(2026, 3, 22)
        donor = _make_plan("entertainment", future_day, planned=40, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=20, spent=35, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        original_planned = Decimal(str(overspent.planned_amount))

        rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("15.00"),
            transaction_date=txn_date,
            dry_run=False,
        )

        # planned_amount must have been increased on the overspent entry
        new_planned = Decimal(str(overspent.planned_amount))
        assert new_planned > original_planned

    def test_no_float_in_planned_amount_updates(self, user_id, txn_date):
        """Verify planned_amount is set to Decimal, not float."""
        future_day = date(2026, 3, 26)
        donor = _make_plan("hobbies", future_day, planned=30, spent=0, user_id=user_id)
        overspent = _make_plan("dining_out", txn_date, planned=10, spent=20, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        rebalance_after_overspend(
            db=db,
            user_id=user_id,
            overspent_category="dining_out",
            overspend_amount=Decimal("10.00"),
            transaction_date=txn_date,
            dry_run=False,
        )

        # After rebalance, donor's planned_amount must be Decimal not float
        new_val = donor.planned_amount
        assert isinstance(new_val, Decimal), (
            f"planned_amount should be Decimal, got {type(new_val)}: {new_val}"
        )


# ---------------------------------------------------------------------------
# check_and_rebalance — the public entry point
# ---------------------------------------------------------------------------

class TestCheckAndRebalance:
    """Tests for the check_and_rebalance wrapper."""

    @pytest.fixture
    def user_id(self):
        return uuid4()

    def test_returns_none_when_not_overspent(self, user_id):
        """Returns None when spent <= planned — fast path."""
        txn_date = date(2026, 3, 5)
        # planned=50, spent=30 — no overspend
        entry = _make_plan("coffee", txn_date, planned=50, spent=30, user_id=user_id)
        db = _make_db_with_entries(entries=[], overspent_entry=entry)

        result = check_and_rebalance(db, user_id, "coffee", txn_date)
        assert result is None

    def test_returns_none_when_no_plan_entry(self, user_id):
        """Returns None when there is no DailyPlan entry for that day/category."""
        txn_date = date(2026, 3, 5)
        db = _make_db_with_entries(entries=[], overspent_entry=None)

        result = check_and_rebalance(db, user_id, "coffee", txn_date)
        assert result is None

    def test_triggers_rebalance_when_overspent(self, user_id):
        """Returns a RebalancePlan when category is overspent."""
        txn_date = date(2026, 3, 10)
        future_day = date(2026, 3, 25)

        overspent = _make_plan("dining_out", txn_date, planned=20, spent=35, user_id=user_id)
        donor = _make_plan("entertainment", future_day, planned=60, spent=0, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = check_and_rebalance(db, user_id, "dining_out", txn_date)

        assert result is not None
        assert isinstance(result, RebalancePlan)
        assert result.overspent_category == "dining_out"
        assert result.overspend_amount == Decimal("15.00")  # 35 - 20

    def test_exact_break_even_not_triggered(self, user_id):
        """spent == planned exactly → no rebalance."""
        txn_date = date(2026, 3, 7)
        entry = _make_plan("coffee", txn_date, planned=10, spent=10, user_id=user_id)
        db = _make_db_with_entries(entries=[], overspent_entry=entry)

        result = check_and_rebalance(db, user_id, "coffee", txn_date)
        assert result is None

    def test_dry_run_propagated(self, user_id):
        """dry_run=True is passed through to rebalance_after_overspend."""
        txn_date = date(2026, 3, 14)
        future_day = date(2026, 3, 28)

        overspent = _make_plan("delivery", txn_date, planned=15, spent=30, user_id=user_id)
        donor = _make_plan("gaming", future_day, planned=50, spent=0, user_id=user_id)

        db = _make_db_with_entries(entries=[donor], overspent_entry=overspent)

        result = check_and_rebalance(db, user_id, "delivery", txn_date, dry_run=True)

        assert result is not None
        assert result.covered > Decimal("0.00")
        # dry_run → no commit
        db.commit.assert_not_called()

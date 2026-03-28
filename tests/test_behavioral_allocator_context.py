"""
Tests for behavioral_budget_allocator.py — Problem 5 fix.

Verifies that allocate_behavioral_budget():
  1. Returns user_context_applied=True only when DynamicThresholdService
     actually provides personalised thresholds.
  2. Returns user_context_applied=False and falls back to hardcoded defaults
     when the service raises or returns an empty dict.
  3. Exposes allocation_method ("dynamic" | "hardcoded_fallback") so callers
     and log aggregators can measure the real-context usage rate.
  4. Logs a WARNING on every fallback (not silent swallowing).
  5. Logs an INFO on every successful dynamic path.
  6. Adjusts confidence score to reflect actual method quality.
"""
import logging
import pytest
from unittest.mock import MagicMock, patch

from app.services.core.behavior.behavioral_budget_allocator import allocate_behavioral_budget


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_ALLOCATOR_MODULE = (
    "app.services.core.behavior.behavioral_budget_allocator"
)
_DYN_SVC_PATH = f"{_ALLOCATOR_MODULE}.DynamicThresholdService"


def _make_db(monthly_income=3000, country="US", age=30):
    """Return a mock DB session whose User query returns a configured user."""
    user = MagicMock()
    user.id = 42
    user.monthly_income = monthly_income
    user.country = country
    user.age = age
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    return db


_VALID_THRESHOLDS = {
    "food": 0.25,
    "transportation": 0.12,
    "utilities": 0.08,
    "entertainment": 0.12,
    "savings": 0.25,
    "other": 0.18,
}


# ─────────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────────

class TestAllocateBehavioralBudget:

    # ── happy path ──────────────────────────────────────────────────────── #

    def test_dynamic_context_applied_flag_true(self):
        """user_context_applied=True when DynamicThresholdService returns valid thresholds."""
        db = _make_db(monthly_income=5000)
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=5000.0, db=db)

        assert result["user_context_applied"] is True

    def test_allocation_method_dynamic(self):
        """allocation_method=='dynamic' on the happy path."""
        db = _make_db(monthly_income=5000)
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=5000.0, db=db)

        assert result["allocation_method"] == "dynamic"

    def test_high_confidence_on_dynamic_path(self):
        """confidence==0.85 when personalised thresholds are used."""
        db = _make_db(monthly_income=5000)
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=5000.0, db=db)

        assert result["confidence"] == pytest.approx(0.85)

    def test_income_tier_present_on_dynamic_path(self):
        """income_tier is populated and not 'unknown' for a normal user."""
        db = _make_db(monthly_income=5000, country="US")
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=5000.0, db=db)

        assert "income_tier" in result
        assert result["income_tier"] != "unknown"

    def test_categories_computed_from_thresholds(self):
        """Category amounts equal total_budget × weight from DynamicThresholdService."""
        db = _make_db(monthly_income=4000)
        thresholds = {"food": 0.30, "savings": 0.20, "other": 0.50}
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = thresholds
            result = allocate_behavioral_budget(user_id=42, total_budget=4000.0, db=db)

        assert result["categories"]["food"] == pytest.approx(1200.0, abs=0.01)
        assert result["categories"]["savings"] == pytest.approx(800.0, abs=0.01)

    def test_total_allocated_equals_sum_of_categories_dynamic(self):
        """total_allocated must match the actual sum (no rounding drift)."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert result["total_allocated"] == pytest.approx(
            sum(result["categories"].values()), abs=0.01
        )

    # ── fallback: service raises ─────────────────────────────────────────── #

    def test_fallback_flag_false_on_service_error(self):
        """user_context_applied=False when DynamicThresholdService raises."""
        db = _make_db(monthly_income=2000)
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError(
                "service unavailable"
            )
            result = allocate_behavioral_budget(user_id=42, total_budget=2000.0, db=db)

        assert result["user_context_applied"] is False

    def test_allocation_method_fallback_on_service_error(self):
        """allocation_method=='hardcoded_fallback' when service raises."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert result["allocation_method"] == "hardcoded_fallback"

    def test_low_confidence_on_fallback(self):
        """confidence==0.50 when hardcoded defaults are used."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert result["confidence"] == pytest.approx(0.50)

    def test_fallback_uses_hardcoded_food_30_pct(self):
        """Fallback categories use food=30% of total_budget."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=42, total_budget=2000.0, db=db)

        assert result["categories"]["food"] == pytest.approx(600.0, abs=0.01)

    def test_fallback_uses_hardcoded_savings_20_pct(self):
        """Fallback categories use savings=20% of total_budget."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=42, total_budget=2000.0, db=db)

        assert result["categories"]["savings"] == pytest.approx(400.0, abs=0.01)

    # ── fallback: empty dict ─────────────────────────────────────────────── #

    def test_fallback_when_thresholds_empty_dict(self):
        """Empty dict from service triggers fallback, not an empty allocation."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = {}
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert result["user_context_applied"] is False
        assert result["allocation_method"] == "hardcoded_fallback"
        assert len(result["categories"]) > 0

    def test_fallback_when_thresholds_none(self):
        """None from service triggers fallback."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = None
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert result["user_context_applied"] is False

    def test_total_allocated_equals_sum_of_categories_fallback(self):
        """total_allocated must match sum also in fallback path."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=42, total_budget=5000.0, db=db)

        assert result["total_allocated"] == pytest.approx(
            sum(result["categories"].values()), abs=0.01
        )

    # ── logging ─────────────────────────────────────────────────────────── #

    def test_fallback_emits_warning_log(self):
        """Every fallback must produce a WARNING — never silent.

        Uses a mock on the module logger rather than caplog, because
        logging_config.py sets propagate=False on the 'app' logger which
        prevents records from reaching pytest's root-level caplog handler.
        """
        db = _make_db()
        with patch(f"{_ALLOCATOR_MODULE}.logger") as mock_logger:
            with patch(_DYN_SVC_PATH) as MockSvc:
                MockSvc.return_value.get_budget_allocation_thresholds.side_effect = ValueError(
                    "test error"
                )
                allocate_behavioral_budget(user_id=42, total_budget=1000.0, db=db)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "fallback" in call_args[0][0].lower()

    def test_dynamic_path_emits_info_log(self):
        """Dynamic path must produce an INFO log for observability.

        Uses a mock on the module logger rather than caplog for the same
        reason as test_fallback_emits_warning_log.
        """
        db = _make_db(monthly_income=6000)
        with patch(f"{_ALLOCATOR_MODULE}.logger") as mock_logger:
            with patch(_DYN_SVC_PATH) as MockSvc:
                MockSvc.return_value.get_budget_allocation_thresholds.return_value = {
                    "food": 0.25,
                    "savings": 0.30,
                    "other": 0.45,
                }
                allocate_behavioral_budget(user_id=42, total_budget=6000.0, db=db)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "dynamic" in call_args[0][0].lower()

    # ── edge cases ───────────────────────────────────────────────────────── #

    def test_no_user_in_db_does_not_crash(self):
        """If User not found, total_budget is used as income — must not raise."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            result = allocate_behavioral_budget(user_id=99, total_budget=2500.0, db=db)

        assert isinstance(result, dict)
        assert "categories" in result

    def test_return_dict_has_required_keys(self):
        """Response always contains the required contract keys."""
        db = _make_db()
        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        required_keys = {
            "categories",
            "total_allocated",
            "method",
            "allocation_method",
            "income_tier",
            "confidence",
            "user_context_applied",
        }
        assert required_keys.issubset(result.keys())

    def test_confidence_differs_between_paths(self):
        """Dynamic confidence must be strictly higher than fallback confidence."""
        db = _make_db()

        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.return_value = _VALID_THRESHOLDS
            dynamic_result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        with patch(_DYN_SVC_PATH) as MockSvc:
            MockSvc.return_value.get_budget_allocation_thresholds.side_effect = RuntimeError
            fallback_result = allocate_behavioral_budget(user_id=42, total_budget=3000.0, db=db)

        assert dynamic_result["confidence"] > fallback_result["confidence"]

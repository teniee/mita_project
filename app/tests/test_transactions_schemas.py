"""Regression tests for transaction schemas (DEF-002).

TxnUpdate previously re-registered TxnIn's already-decorated validators via
``field_validator(...)(TxnIn.validate_amount)``, which shifted the validator
arguments so every provided field raised (amount -> decimal.ConversionSyntax)
and PUT /api/transactions/{id} returned HTTP 500 for any body.

These tests exercise every TxnUpdate field plus the invalid-input matrix and
must keep failing loudly if the delegation pattern regresses.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pydantic
import pytest

from app.api.transactions.schemas import TxnIn, TxnUpdate


class TestTxnUpdateAmount:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (100.00, Decimal("100.00")),
            ("100.00", Decimal("100.00")),
            (100, Decimal("100.00")),
            (Decimal("100"), Decimal("100.00")),
            (42.5, Decimal("42.50")),
        ],
    )
    def test_valid_amounts_accepted(self, value, expected):
        assert TxnUpdate(amount=value).amount == expected

    def test_none_amount_is_noop(self):
        assert TxnUpdate(amount=None).amount is None
        assert TxnUpdate().amount is None

    @pytest.mark.parametrize(
        "value", [-5, 0, "NaN", "Infinity", "-Infinity", "abc", 2_000_000, "1e999"]
    )
    def test_invalid_amounts_rejected_as_validation_error(self, value):
        """Invalid values must surface as pydantic ValidationError (-> 422),
        never as a raw exception (-> 500)."""
        with pytest.raises(pydantic.ValidationError):
            TxnUpdate(amount=value)

    def test_create_schema_rejects_over_limit_as_422(self):
        # Same guarantee for the create schema: business-limit rejection must
        # be a pydantic ValidationError, not an unhandled custom exception.
        with pytest.raises(pydantic.ValidationError):
            TxnIn(amount=2_000_000, category="food")


class TestTxnUpdateOtherFields:
    def test_category(self):
        assert TxnUpdate(category="food").category == "food"

    def test_description(self):
        assert TxnUpdate(description="lunch at cafe").description == "lunch at cafe"

    def test_merchant(self):
        assert TxnUpdate(merchant="starbucks").merchant == "Starbucks"

    def test_location(self):
        assert TxnUpdate(location="varna").location == "Varna"

    def test_tags(self):
        assert TxnUpdate(tags=["coffee", "work"]).tags == ["coffee", "work"]

    def test_spent_at(self):
        ts = datetime.now(timezone.utc) - timedelta(days=1)
        assert TxnUpdate(spent_at=ts).spent_at == ts

    def test_spent_at_absent_stays_none(self):
        # A partial update must not default spent_at to "now" (TxnIn does).
        assert TxnUpdate(category="food").spent_at is None

    def test_all_none_defaults(self):
        update = TxnUpdate()
        for field in (
            "amount",
            "category",
            "description",
            "merchant",
            "location",
            "tags",
            "spent_at",
            "is_recurring",
        ):
            assert getattr(update, field) is None

    def test_future_spent_at_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            TxnUpdate(spent_at=datetime.now(timezone.utc) + timedelta(days=2))


class TestTxnInUnchanged:
    """TxnIn (create) behavior is production-verified; lock it in."""

    def test_create_amount(self):
        assert TxnIn(amount=42.00, category="food").amount == Decimal("42.00")

    def test_create_spent_at_defaults(self):
        # Absent -> stays None (the service layer defaults it to now);
        # explicit null -> the validator substitutes now.
        assert TxnIn(amount=1.00, category="food").spent_at is None
        explicit_null = TxnIn(amount=1.00, category="food", spent_at=None)
        assert explicit_null.spent_at is not None
        assert explicit_null.spent_at.tzinfo is not None

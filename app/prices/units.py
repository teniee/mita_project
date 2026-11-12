"""Quantities and unit prices. MITA computes the unit price itself from the
price and the package size; a unit price a page states is never taken."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Tuple

# Unit as written → (normalized unit, factor to it).
UNITS = {
    "g": ("kg", Decimal("0.001")),
    "kg": ("kg", Decimal("1")),
    "ml": ("l", Decimal("0.001")),
    "cl": ("l", Decimal("0.01")),
    "l": ("l", Decimal("1")),
    "piece": ("piece", Decimal("1")),
    "pieces": ("piece", Decimal("1")),
    "pcs": ("piece", Decimal("1")),
}
MAX_QUANTITY = Decimal("100000")


def normalize(quantity, unit) -> Optional[Tuple[Decimal, str]]:
    """``(quantity in kg / l / piece, unit)`` or None when not a plain,
    positive, known quantity."""
    if not isinstance(unit, str):
        return None
    known = UNITS.get(unit.strip().lower())
    if known is None:
        return None
    try:
        amount = Decimal(str(quantity))
    except Exception:  # noqa: BLE001 - anything unparsable is rejected
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_QUANTITY:
        return None
    base, factor = known
    return amount * factor, base


def unit_price(price: Decimal, normalized_quantity: Decimal) -> Decimal:
    return (price / normalized_quantity).quantize(Decimal("0.01"), ROUND_HALF_UP)

"""One normalized observation, and the checks every value passes before it
is stored.

Never a guess: a missing cell is not an observation (never zero), a value
outside what its unit allows is rejected, and the provider's own status flag
is kept and translated into MITA's quality flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Tuple

from app.regional.catalog import Dataset

# Provider status flags → MITA's quality flags (Eurostat flags are lower
# case, OECD's upper case; the World Bank sends none for these series).
STATUS_FLAGS = {
    "e": "estimated",
    "p": "provisional",
    "b": "break_in_series",
    "u": "low_reliability",
    "d": "definition_differs",
    "E": "estimated",
    "P": "provisional",
    "B": "break_in_series",
    "F": "forecast",
}

# What each unit can be. Outside → rejected (impossible); inside but beyond
# "extreme" → kept and flagged (real hyperinflation exists).
BOUNDS = {
    "percent_change": (Decimal("-100"), Decimal("10000")),
    "index": (Decimal("0.000001"), Decimal("100000")),
    "price_level_index": (Decimal("0.000001"), Decimal("1000")),
    "per_mille": (Decimal("0"), Decimal("1000")),
}
EXTREME = {"percent_change": Decimal("100")}


class RejectedValue(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    provider: str
    dataset: str
    series_key: str
    indicator: str
    classification: Optional[str]
    category: Optional[str]
    category_label: Optional[str]
    geo_code: str  # ISO 3166-1 alpha-2
    period: str
    period_type: str
    period_start: date
    value: Decimal
    unit_kind: str
    unit: str
    base_period: Optional[str]
    provider_status: Optional[str]
    published_at: Optional[datetime]
    source_url: str
    license: str
    transformation: str = "none"
    currency: Optional[str] = None
    geo_level: str = "country"
    quality_flags: Tuple[str, ...] = field(default=())

    @property
    def key(self) -> Tuple[str, str, str, str]:
        return (self.provider, self.dataset, self.series_key, self.period)


def parse_period(text: str) -> Tuple[str, date]:
    """``'2026-10'`` → month, ``'2026-Q2'`` → quarter, ``'2025'`` → year."""
    value = text.strip()
    if len(value) == 4 and value.isdigit():
        return "year", date(int(value), 1, 1)
    if len(value) == 7 and value[4] == "-" and value[5] == "Q":
        quarter = int(value[6])
        if not 1 <= quarter <= 4:
            raise RejectedValue(f"bad quarter {value!r}")
        return "quarter", date(int(value[:4]), 3 * quarter - 2, 1)
    if len(value) == 7 and value[4] == "-":
        return "month", date(int(value[:4]), int(value[5:]), 1)
    raise RejectedValue(f"unrecognised period {value!r}")


def build(
    spec: Dataset,
    *,
    series_key: str,
    category: Optional[str],
    category_label: Optional[str],
    geo_code: str,
    period: str,
    value,
    provider_status: Optional[str],
    published_at: Optional[datetime],
    source_url: str,
) -> Observation:
    """A checked observation of ``spec``, or ``RejectedValue``."""
    if value is None or value == "":
        raise RejectedValue("missing value")  # never stored as zero
    try:
        number = Decimal(str(value))
    except Exception:  # noqa: BLE001 - any unparsable cell is rejected
        raise RejectedValue("not a number") from None
    if not number.is_finite():
        raise RejectedValue("not a finite number")
    low, high = BOUNDS[spec.unit_kind]
    if not low <= number <= high:
        raise RejectedValue(f"{spec.unit_kind} out of bounds")
    period_type, start = parse_period(period)
    if period_type != spec.period_type:
        raise RejectedValue(f"{period_type} period in a {spec.period_type} dataset")
    flags = []
    status = (provider_status or "").strip() or None
    for char in status or "":
        flag = STATUS_FLAGS.get(char)
        if flag and flag not in flags:
            flags.append(flag)
    extreme = EXTREME.get(spec.unit_kind)
    if extreme is not None and abs(number) > extreme:
        flags.append("extreme_value")
    return Observation(
        provider=spec.provider,
        dataset=spec.dataset,
        series_key=series_key,
        indicator=spec.indicator,
        classification=spec.classification,
        category=category,
        category_label=category_label,
        geo_code=geo_code,
        period=period.strip(),
        period_type=period_type,
        period_start=start,
        value=number.quantize(Decimal("0.000001")),
        unit_kind=spec.unit_kind,
        unit=spec.unit,
        base_period=spec.base_period,
        provider_status=status[:8] if status else None,
        published_at=published_at,
        source_url=source_url,
        license=spec.license,
        quality_flags=tuple(flags),
    )


def is_stale(spec: Dataset, period_start: date, today: date) -> bool:
    return (today - period_start).days > spec.max_age_days

"""One price lookup: approval, area, quota, provider, verification — in that
order, failing closed at every step.

The quota guards spending before any call: a per-user daily number of
lookups and a monthly spend cap estimated per lookup. Its durable store
(one row per day and user key, an HMAC, never the user id) is part of the
activation work, described in ``docs/chatgpt-app/local-prices.md``.
``InMemoryQuota`` is for tests, and ``DenyAll`` is what runs until then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, Optional, Protocol, Tuple

from app.prices.approval import PriceSearchApproval
from app.prices.model import (
    ALL_REJECTED,
    NO_AREA,
    NO_CANDIDATES,
    NO_VERIFIED_PRICE,
    NOT_APPROVED,
    PROVIDER_FAILED,
    QUOTA_EXCEEDED,
    VERIFIED,
    LookupResult,
    PriceQuery,
    Rejection,
    SearchArea,
    VerifiedPrice,
)
from app.prices.providers import DisabledProvider, PriceProvider
from app.prices.validation import verify


class Quota(Protocol):
    def allow(self, user_key: str, day: date) -> bool: ...

    def record(self, user_key: str, day: date, calls: int) -> None: ...


class DenyAll:
    def allow(self, user_key: str, day: date) -> bool:
        return False

    def record(self, user_key: str, day: date, calls: int) -> None:
        return None


@dataclass
class InMemoryQuota:
    approval: PriceSearchApproval
    per_user: Dict[Tuple[str, date], int] = field(default_factory=dict)
    month_calls: Dict[Tuple[int, int], int] = field(default_factory=dict)

    def allow(self, user_key: str, day: date) -> bool:
        if (
            self.per_user.get((user_key, day), 0)
            >= self.approval.per_user_daily_lookups
        ):
            return False
        spent = (
            Decimal(self.month_calls.get((day.year, day.month), 0))
            * self.approval.estimated_cost_per_lookup_usd
        )
        return spent + self.approval.estimated_cost_per_lookup_usd <= (
            self.approval.monthly_cap_usd
        )

    def record(self, user_key: str, day: date, calls: int) -> None:
        self.per_user[(user_key, day)] = self.per_user.get((user_key, day), 0) + 1
        month = (day.year, day.month)
        self.month_calls[month] = self.month_calls.get(month, 0) + max(calls, 1)


def lookup_prices(
    query: PriceQuery,
    area: Optional[SearchArea],
    *,
    approval: Optional[PriceSearchApproval],
    provider: PriceProvider,
    quota: Quota,
    user_key: str,
    today: date,
) -> LookupResult:
    if approval is None or isinstance(provider, DisabledProvider):
        return LookupResult(NO_VERIFIED_PRICE, NOT_APPROVED, area=area)
    if area is None:
        return LookupResult(NO_VERIFIED_PRICE, NO_AREA)
    if not quota.allow(user_key, today):
        return LookupResult(NO_VERIFIED_PRICE, QUOTA_EXCEEDED, area=area)
    try:
        answer = provider.search(query, area)
    except Exception:  # noqa: BLE001 - any provider failure: no price, never a guess
        quota.record(user_key, today, 1)
        return LookupResult(NO_VERIFIED_PRICE, PROVIDER_FAILED, area=area)
    quota.record(user_key, today, answer.billable_calls)
    verified = []
    rejected = []
    for candidate in answer.candidates:
        checked = verify(
            candidate,
            query,
            area,
            allowed_domains=approval.allowed_domains,
            cited_urls=answer.cited_urls,
            today=today,
        )
        (verified if isinstance(checked, VerifiedPrice) else rejected).append(checked)
    if not verified:
        return LookupResult(
            NO_VERIFIED_PRICE,
            ALL_REJECTED if rejected else NO_CANDIDATES,
            rejected=tuple(r for r in rejected if isinstance(r, Rejection)),
            area=area,
        )
    verified.sort(key=lambda p: (p.price_type != "regular", p.unit_price, p.merchant))
    return LookupResult(
        VERIFIED, prices=tuple(verified), rejected=tuple(rejected), area=area
    )

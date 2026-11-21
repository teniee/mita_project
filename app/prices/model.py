"""What a price question, a search area, a candidate and a verified price are.

A candidate is what a provider returned — untrusted. A verified price is a
candidate that passed every check in ``validation.verify``; only it may be
shown, always with its source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

# Lookup outcomes.
VERIFIED = "verified"
NO_VERIFIED_PRICE = "no_verified_price"

# Why there is no verified price.
NOT_APPROVED = "price_search_not_approved"
QUOTA_EXCEEDED = "quota_exceeded"
NO_AREA = "no_search_area"
PROVIDER_FAILED = "provider_failed"
ALL_REJECTED = "no_candidate_passed_the_checks"
NO_CANDIDATES = "no_candidates"

# Where the search area came from. A city is only ever where ChatGPT says
# the user is now (approximate), never assumed to be where they live.
AREA_CONFIRMED_COUNTRY = "confirmed_country"
AREA_CURRENT_APPROXIMATE = "chatgpt_current_location_approximate"

COVERAGE = ("store", "city", "online_national")
PRICE_TYPES = ("regular", "promotion")


@dataclass(frozen=True)
class PriceQuery:
    """One product to price, in the user's currency (never converted)."""

    product: str  # what the user asked for, e.g. "white bread"
    currency: str  # ISO 4217, the user's
    quantity: Optional[Decimal] = None  # e.g. 500
    unit: Optional[str] = None  # g, kg, ml, l, piece


@dataclass(frozen=True)
class SearchArea:
    """Where to look. Never an address or coordinates; held for one call
    and never stored or logged."""

    country: str  # ISO 3166-1 alpha-2
    city: Optional[str]
    source: str  # AREA_CONFIRMED_COUNTRY | AREA_CURRENT_APPROXIMATE
    # True only when the country is the residence the user confirmed. A
    # city is never a confirmed residence: MITA does not store one.
    country_is_residence: bool


@dataclass(frozen=True)
class PriceCandidate:
    """A provider's claim about a price — untrusted until verified."""

    product_name: str
    price: object  # as the provider gave it: checked, never trusted
    currency: object
    quantity: object
    unit: object
    merchant: object
    source_url: object
    observed_on: object  # ISO date
    coverage: object = "store"
    price_type: object = "regular"
    valid_until: object = None
    delivery_cost: object = None
    deposit: object = None


@dataclass(frozen=True)
class VerifiedPrice:
    product_name: str
    price: Decimal
    currency: str
    quantity: Decimal
    unit: str  # as normalized: kg, l or piece
    unit_price: Decimal  # computed by MITA: price per kg, l or piece
    merchant: str
    source_url: str
    source_domain: str
    observed_on: date
    coverage: str
    price_type: str  # regular | promotion
    valid_until: Optional[date]
    extra_costs: Tuple[Tuple[str, Decimal], ...]  # ("delivery", 2.99)
    area: SearchArea
    # Never a transaction or a budget input: see the package docstring.


@dataclass(frozen=True)
class Rejection:
    reason: str  # the first check that failed
    field_name: Optional[str] = None


@dataclass(frozen=True)
class LookupResult:
    status: str  # VERIFIED | NO_VERIFIED_PRICE
    reason: Optional[str] = None
    prices: Tuple[VerifiedPrice, ...] = ()
    rejected: Tuple[Rejection, ...] = field(default_factory=tuple)
    area: Optional[SearchArea] = None

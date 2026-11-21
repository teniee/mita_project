"""Every check a provider's candidate must pass before MITA shows it.

Checks run in a fixed order and the first failure rejects the candidate. The
rules:

* **Web content never instructs MITA.** Only typed fields are read. Every
  string is length-bounded, limited to plain characters, and refused when it
  reads like an instruction or carries a link. Nothing in a candidate is
  executed, followed, or written to the ledger.
* **The source is real and allowed.** An https URL on an allowed domain that
  the provider actually cited, so the page cannot have been made up.
* **The money is what it says.** A positive price in the user's own currency
  (never converted) for a known quantity. MITA computes the unit price
  itself.
* **It is current, and labelled honestly.** Observed at most
  ``MAX_AGE_DAYS`` ago, never in the future. A promotion is labelled
  promotion and an ended one is refused. Delivery and deposit costs are
  stated apart from the price.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import FrozenSet, Iterable, Optional, Tuple, Union
from urllib.parse import urlsplit

from app.prices.model import (
    COVERAGE,
    PRICE_TYPES,
    PriceCandidate,
    PriceQuery,
    Rejection,
    SearchArea,
    VerifiedPrice,
)
from app.prices.units import normalize, unit_price

MAX_AGE_DAYS = 31
MAX_PRICE = Decimal("100000")
MAX_TEXT = 120
# Letters, digits, spaces and the punctuation of product and shop names.
PLAIN_TEXT = re.compile(r"^[\w .,'&()/%+\-]+$", re.UNICODE)
# What an instruction, a role or a link looks like. A real product or shop
# name that matches is refused too: the safe failure is no price.
INSTRUCTION_LIKE = re.compile(
    r"(ignore|disregard|instruction|prompt|assistant|developer|system|"
    r"you are|you must|as an ai|tool|function|http|www\.)",
    re.IGNORECASE,
)


def _text(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value).strip()
    if not 0 < len(text) <= MAX_TEXT or not PLAIN_TEXT.match(text):
        return None
    if INSTRUCTION_LIKE.search(text):
        return None
    return text


def _tokens(text: str) -> FrozenSet[str]:
    return frozenset(
        t for t in re.findall(r"\w+", text.casefold(), re.UNICODE) if len(t) >= 3
    )


def _money(value) -> Optional[Decimal]:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except Exception:  # noqa: BLE001 - anything unparsable is rejected
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_PRICE:
        return None
    if amount.as_tuple().exponent < -3:
        return None  # more precision than any price tag shows
    return amount


def _date(value) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def allowed_host(host: str, domains: Iterable[str]) -> bool:
    host = host.lower().rstrip(".")
    for domain in domains:
        d = domain.lower().strip().rstrip(".")
        if d and (host == d or host.endswith("." + d)):
            return True
    return False


def verify(
    candidate: PriceCandidate,
    query: PriceQuery,
    area: SearchArea,
    *,
    allowed_domains: Iterable[str],
    cited_urls: FrozenSet[str],
    today: date,
) -> Union[VerifiedPrice, Rejection]:
    name = _text(candidate.product_name)
    if name is None:
        return Rejection("unsafe_or_missing_text", "product_name")
    wanted = _tokens(query.product)
    if not wanted or not wanted <= _tokens(name):
        return Rejection("different_product", "product_name")

    price = _money(candidate.price)
    if price is None or price == 0:
        return Rejection("no_valid_price", "price")
    if not isinstance(candidate.currency, str) or (
        candidate.currency.strip().upper() != query.currency
    ):
        # Never converted: a price in another currency is not the user's.
        return Rejection("currency_mismatch", "currency")

    size = normalize(candidate.quantity, candidate.unit)
    if size is None:
        return Rejection("unknown_quantity", "quantity")
    quantity, unit = size
    if query.unit is not None:
        expected = normalize(query.quantity or 1, query.unit)
        if expected is None or expected[1] != unit:
            return Rejection("different_unit", "unit")

    merchant = _text(candidate.merchant)
    if merchant is None:
        return Rejection("unsafe_or_missing_text", "merchant")

    url = candidate.source_url
    if not isinstance(url, str) or len(url) > 2048:
        return Rejection("no_source", "source_url")
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.hostname:
        return Rejection("source_not_https", "source_url")
    if parts.username or parts.password or parts.port not in (None, 443):
        return Rejection("source_not_plain", "source_url")
    if not allowed_host(parts.hostname, allowed_domains):
        return Rejection("domain_not_allowed", "source_url")
    if url.strip() not in cited_urls:
        return Rejection("not_cited_by_the_search", "source_url")

    observed = _date(candidate.observed_on)
    if observed is None:
        return Rejection("no_date", "observed_on")
    if observed > today:
        return Rejection("date_in_the_future", "observed_on")
    if observed < today - timedelta(days=MAX_AGE_DAYS):
        return Rejection("too_old", "observed_on")

    if candidate.coverage not in COVERAGE:
        return Rejection("unknown_coverage", "coverage")
    if candidate.price_type not in PRICE_TYPES:
        return Rejection("unknown_price_type", "price_type")
    valid_until = None
    if candidate.valid_until is not None:
        valid_until = _date(candidate.valid_until)
        if valid_until is None:
            return Rejection("bad_valid_until", "valid_until")
        if valid_until < today:
            return Rejection("promotion_ended", "valid_until")

    extras: Tuple[Tuple[str, Decimal], ...] = ()
    for label, value in (
        ("delivery", candidate.delivery_cost),
        ("deposit", candidate.deposit),
    ):
        if value is None:
            continue
        amount = _money(value)
        if amount is None:
            return Rejection("bad_extra_cost", label)
        if amount > 0:
            extras += ((label, amount),)

    return VerifiedPrice(
        product_name=name,
        price=price,
        currency=query.currency,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price(price, quantity),
        merchant=merchant,
        source_url=url.strip(),
        source_domain=parts.hostname.lower(),
        observed_on=observed,
        coverage=candidate.coverage,
        price_type=candidate.price_type,
        valid_until=valid_until,
        extra_costs=extras,
        area=area,
    )

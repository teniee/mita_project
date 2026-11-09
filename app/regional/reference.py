"""Monthly spending references from official statistics (owner brief
"complete regional budget intelligence", 2026-11-09).

A reference answers one narrow question: on average, how much did
households in the user's country spend a month on one kind of spending,
at recent prices? It is computed from three Eurostat series with a stated
method, never from an index alone:

    amount per adult equivalent per year   hbs_exp_t111  (survey year Y)
  × share of that spending (per mille)     hbs_str_t211  (same year Y)
  × price index, latest year P / year Y    prc_hicp_aind (same COICOP code)
  ÷ 12

That gives one adult a month. For a stated household of n people it gives a
range on the survey's own equivalence scale (the modified OECD scale:
1 for the first adult, 0.5 for each other person aged 14 or over, 0.3 for
each child under 14). The household's ages are not known, so the low end
counts the others as children and the high end as adults. The scale is not
linear: four people are 1.9–2.5 adults, not 4.

What a reference is **not**:

* not a local price: it is national, never a city;
* not the user's cost: it is an average over every kind of household,
  including households that buy little or none of it;
* not a recommendation of what to spend;
* never a budget input;
* never in another currency: only the user's own currency, when it is the
  country's currency now, and nothing is ever converted.

Confidence is always ``low`` by construction. When the inputs are missing,
too old, unreliable or out of range, the answer is ``insufficient_data``
with a reason, never a substitute figure.

Pure: no database and no network. The rows come from MITA's own copy of the
statistics (``regional_observations``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from app.regional import catalog
from app.regional.observations import is_stale

# MITA's key → (COICOP 1999 code, Eurostat's label). Only kinds of spending
# where a national average says something about one household's line, and
# where the survey share and the price index use the same code.
CATEGORIES: Dict[str, Tuple[str, str]] = {
    "food": ("CP01", "Food and non-alcoholic beverages"),
    "clothing": ("CP03", "Clothing and footwear"),
    "household_energy": ("CP045", "Electricity, gas and other fuels"),
    "fuel": ("CP0722", "Fuels and lubricants for personal transport equipment"),
}
# Spending only some households have at all — fuel needs a vehicle. Its
# all-household average is spread over households without one (half of them
# in Bulgaria), so it is divided by the share of households that bought it in
# the survey (hbs_exp_t123b), assuming they are of average size. Spending
# with no such precondition (eating out) gets no reference.
BUYERS_ONLY = frozenset({"fuel"})
# Below this share of households, dividing by it amplifies noise.
MIN_BUYING_PERCENT = Decimal("20")

# A survey older than this many calendar years is not carried forward. The
# 2015 wave has been too old since 2024; the 2020 wave can be used until
# 2028, when the 2026 wave is due.
MAX_SURVEY_AGE_YEARS = 8
# Carrying a survey forward assumes people still buy the same quantities.
# When prices of that spending more than doubled or fell by half (Turkey's
# food prices rose 8-fold between 2020 and 2025; Estonia's energy prices
# 2.3-fold), that assumption no longer holds and there is no reference.
PRICE_FACTOR_RANGE = (Decimal("0.5"), Decimal("2.0"))

FIRST_ADULT = Decimal("1.0")
OTHER_AGED_14_PLUS = Decimal("0.5")
CHILD_UNDER_14 = Decimal("0.3")

AVAILABLE = "available"
INSUFFICIENT = "insufficient_data"
CONFIDENCE = "low"

# Why there is no reference: the code the tools return, in plain words.
REASONS: Dict[str, str] = {
    "no_country": "the user has not confirmed a country",
    "turned_off": "the user turned regional statistics off",
    "no_currency": "the user has not stated their currency",
    "not_covered": (
        "MITA has no household-spending survey it may use for this country "
        "(Eurostat's licence covers EU, EFTA and candidate countries)"
    ),
    "currency_mismatch": (
        "the figures are in the country's own currency and the budget is in "
        "another one; MITA never converts currencies"
    ),
    "no_survey": "MITA holds no household-spending survey for this country",
    "survey_too_old": "the latest household-spending survey is too old",
    "share_missing": "the survey has no share for this spending",
    "low_reliability": "the provider marks a figure as of low reliability",
    "price_index_missing": "there is no price index for this spending",
    "buyers_missing": "the survey does not say how many households buy it",
    "too_few_buyers": "too few households buy it in the survey",
    "prices_too_old": "the latest price index is too old",
    "prices_changed_too_much": (
        "prices of this spending changed too much since the survey to carry "
        "it forward"
    ),
}

METHOD = (
    "Eurostat household budget survey: average consumption expenditure per "
    "adult equivalent in the survey year × the share of this spending in that "
    "year × the change in its consumer price index from the survey year to the "
    "latest complete year ÷ 12 (for fuel, ÷ the share of households that "
    "bought fuel in the survey). One adult; a household as a range on the "
    "survey's modified OECD scale (1 first adult, 0.5 each other person aged "
    "14+, 0.3 each child under 14). Assumes the same quantities as in the "
    "survey year."
)
LIMITATION = (
    "A national average over every kind of household, carried forward with "
    "national price changes: not a city figure, not a shop price, not the "
    "user's own cost and not a recommendation of what to spend."
)

ONE = Decimal("1")


@dataclass(frozen=True)
class Reference:
    category: str  # MITA's key: food, clothing, household_energy
    code: str  # COICOP 1999
    label: str
    status: str  # available | insufficient_data
    reason: Optional[str] = None
    currency: Optional[str] = None
    # A month, in whole units of the currency (exact inputs below).
    per_adult: Optional[Decimal] = None
    household_size: Optional[int] = None
    household_low: Optional[Decimal] = None
    household_high: Optional[Decimal] = None
    survey_year: Optional[int] = None
    price_year: Optional[int] = None
    yearly_per_adult: Optional[Decimal] = None  # hbs_exp_t111
    share_per_mille: Optional[Decimal] = None  # hbs_str_t211
    price_factor: Optional[Decimal] = None  # index P / index Y, 6 decimals
    per_adult_exact: Optional[Decimal] = None  # before rounding, 2 decimals
    # For spending only some households have: the % that bought it, and the
    # reference is for those households only.
    buying_percent: Optional[Decimal] = None
    quality_flags: Tuple[str, ...] = ()

    @property
    def confidence(self) -> Optional[str]:
        return CONFIDENCE if self.status == AVAILABLE else None


def household_scale(size: int) -> Tuple[Decimal, Decimal]:
    """(low, high) adult equivalents for ``size`` people of unknown ages: the
    others all children under 14, or all aged 14 and over."""
    if size < 1:
        raise ValueError("a household has at least one person")
    others = Decimal(size - 1)
    return (
        FIRST_ADULT + CHILD_UNDER_14 * others,
        FIRST_ADULT + OTHER_AGED_14_PLUS * others,
    )


def _year(row) -> int:
    return int(str(row.period)[:4])


def _flags(row) -> Tuple[str, ...]:
    return tuple(row.quality_flags or ())


def insufficient(key: str, reason: str, **extra) -> Reference:
    code, label = CATEGORIES[key]
    return Reference(key, code, label, INSUFFICIENT, reason=reason, **extra)


def references(
    rows: Iterable,
    *,
    country: Optional[str],
    currency: Optional[str],
    household_size: Optional[int],
    today: date,
    categories: Iterable[str] = tuple(CATEGORIES),
) -> Dict[str, Reference]:
    """One reference per category key, available or ``insufficient_data``.

    ``rows`` are ``regional_observations`` (or anything with the same
    attributes) for ``country``; rows of other countries are ignored.
    """
    keys = [k for k in categories if k in CATEGORIES]
    if not country:
        return {k: insufficient(k, "no_country") for k in keys}
    if country not in catalog.EUROSTAT_COUNTRIES:
        return {k: insufficient(k, "not_covered") for k in keys}
    current = catalog.national_currency(country, today.year)
    if current is None or currency != current:
        return {k: insufficient(k, "currency_mismatch") for k in keys}

    mine = [r for r in rows if r.geo_code == country and r.provider == catalog.EUROSTAT]
    surveys = sorted(
        (
            r
            for r in mine
            if r.indicator == catalog.HOUSEHOLD_EXPENDITURE and r.currency == currency
        ),
        # The latest wave; EUR_AE before NAC_AE when both are in euro (equal).
        key=lambda r: (-_year(r), r.series_key),
    )
    if not surveys:
        return {k: insufficient(k, "no_survey") for k in keys}
    survey = surveys[0]
    survey_year = _year(survey)
    if survey_year < today.year - MAX_SURVEY_AGE_YEARS:
        return {
            k: insufficient(k, "survey_too_old", survey_year=survey_year) for k in keys
        }
    if "low_reliability" in _flags(survey):
        return {
            k: insufficient(k, "low_reliability", survey_year=survey_year) for k in keys
        }
    yearly = Decimal(str(survey.value))
    index_spec = catalog.HICP_ANNUAL_INDEX

    found: Dict[str, Reference] = {}
    for key in keys:
        code, label = CATEGORIES[key]
        share_row = next(
            (
                r
                for r in mine
                if r.indicator == catalog.SPENDING_SHARE
                and r.category == code
                and _year(r) == survey_year
            ),
            None,
        )
        base = dict(survey_year=survey_year, currency=currency)
        if share_row is None:
            found[key] = insufficient(key, "share_missing", **base)
            continue
        if "low_reliability" in _flags(share_row):
            found[key] = insufficient(key, "low_reliability", **base)
            continue
        indices = {
            _year(r): r
            for r in mine
            if r.indicator == catalog.PRICE_INDEX_ANNUAL and r.category == code
        }
        latest_year = max(indices) if indices else None
        if survey_year not in indices or latest_year is None:
            found[key] = insufficient(key, "price_index_missing", **base)
            continue
        latest = indices[latest_year]
        if is_stale(index_spec, latest.period_start, today):
            found[key] = insufficient(
                key, "prices_too_old", price_year=latest_year, **base
            )
            continue
        factor = (
            Decimal(str(latest.value)) / Decimal(str(indices[survey_year].value))
        ).quantize(Decimal("0.000001"), ROUND_HALF_UP)
        low_factor, high_factor = PRICE_FACTOR_RANGE
        if not low_factor <= factor <= high_factor:
            found[key] = insufficient(
                key,
                "prices_changed_too_much",
                price_year=latest_year,
                price_factor=factor,
                **base,
            )
            continue
        share = Decimal(str(share_row.value))
        buying_row = None
        buying = None
        if key in BUYERS_ONLY:
            buying_row = next(
                (
                    r
                    for r in mine
                    if r.indicator == catalog.HOUSEHOLDS_BUYING
                    and r.category == code
                    and _year(r) == survey_year
                ),
                None,
            )
            if buying_row is None:
                found[key] = insufficient(key, "buyers_missing", **base)
                continue
            if "low_reliability" in _flags(buying_row):
                found[key] = insufficient(key, "low_reliability", **base)
                continue
            buying = Decimal(str(buying_row.value))
            if buying < MIN_BUYING_PERCENT:
                found[key] = insufficient(
                    key, "too_few_buyers", buying_percent=buying, **base
                )
                continue
        exact = yearly * share / Decimal(1000) * factor / Decimal(12)
        if buying is not None:
            exact = exact * Decimal(100) / buying
        per_adult = exact.quantize(ONE, ROUND_HALF_UP)
        low = high = None
        if household_size is not None:
            scale_low, scale_high = household_scale(household_size)
            low = (exact * scale_low).quantize(ONE, ROUND_HALF_UP)
            high = (exact * scale_high).quantize(ONE, ROUND_HALF_UP)
        flags: List[str] = []
        for row in (survey, share_row, indices[survey_year], latest, buying_row):
            for flag in _flags(row) if row is not None else ():
                if flag not in flags:
                    flags.append(flag)
        found[key] = Reference(
            key,
            code,
            label,
            AVAILABLE,
            currency=currency,
            per_adult=per_adult,
            household_size=household_size,
            household_low=low,
            household_high=high,
            survey_year=survey_year,
            price_year=latest_year,
            yearly_per_adult=yearly,
            share_per_mille=share,
            price_factor=factor,
            per_adult_exact=exact.quantize(Decimal("0.01"), ROUND_HALF_UP),
            buying_percent=buying,
            quality_flags=tuple(flags),
        )
    return found

"""Official statistics for the user's confirmed country, from MITA's own copy.

Reads ``regional_observations`` (migration 0044) only — never a provider —
so a provider outage cannot slow or fail a tool call; a value too old for its
cadence is returned marked ``stale``, never presented as current. One
DISTINCT ON query (latest period per series of the country) on the
``(geo_code, indicator, period_start)`` index.

Nothing about the user selects a row but the country they confirmed, and the
regional switch they control (``mcp_user_profiles.regional_context_enabled``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.regional import RegionalObservation
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import UserContext
from app.regional import catalog
from app.regional import reference as reference_engine
from app.regional.observations import is_stale

STATUS_AVAILABLE = "available"
STATUS_NO_COUNTRY = "no_country"
STATUS_TURNED_OFF = "turned_off"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Statistic:
    row: RegionalObservation
    spec: catalog.Dataset
    category_key: str
    stale: bool


@dataclass(frozen=True)
class RegionalContext:
    status: str
    country: Optional[str]
    statistics: Tuple[Statistic, ...] = ()


def regional_context(
    db: Session,
    ctx: UserContext,
    *,
    topic: Optional[str] = None,
    category: Optional[str] = None,
    today: Optional[date] = None,
) -> RegionalContext:
    if ctx.country is None:
        return RegionalContext(STATUS_NO_COUNTRY, None)
    if not ctx.regional_context_enabled:
        return RegionalContext(STATUS_TURNED_OFF, ctx.country)
    indicators = catalog.TOPICS.get(topic) if topic else catalog.SHOWN_INDICATORS
    query = (
        select(RegionalObservation)
        .where(RegionalObservation.geo_code == ctx.country)
        .distinct(
            RegionalObservation.provider,
            RegionalObservation.dataset,
            RegionalObservation.series_key,
        )
        .order_by(
            RegionalObservation.provider,
            RegionalObservation.dataset,
            RegionalObservation.series_key,
            RegionalObservation.period_start.desc(),
        )
    )
    query = query.where(RegionalObservation.indicator.in_(indicators))
    day = today or ctx.today
    candidates: Dict[Tuple[str, str], List[Statistic]] = {}
    for row in db.scalars(query):
        spec = catalog.dataset_of(row.provider, row.dataset)
        if spec is None:
            continue  # a dataset no longer in the catalog
        key = catalog.CATEGORY_KEYS.get(row.category)
        if key is None or (category and key != category):
            continue
        candidates.setdefault((row.indicator, key), []).append(
            Statistic(row, spec, key, is_stale(spec, row.period_start, day))
        )
    chosen: List[Statistic] = []
    for (indicator, _key), items in candidates.items():
        priority = catalog.PROVIDER_PRIORITY.get(indicator, ())

        def rank(item: Statistic):
            order = (
                priority.index(item.row.provider)
                if item.row.provider in priority
                else len(priority)
            )
            return (item.stale, order)

        chosen.append(min(items, key=rank))
    chosen.sort(
        key=lambda s: (
            [d.indicator for d in catalog.DATASETS].index(s.row.indicator),
            list(catalog.CATEGORY_KEYS.values()).index(s.category_key),
        )
    )
    if not chosen:
        return RegionalContext(STATUS_UNAVAILABLE, ctx.country)
    return RegionalContext(STATUS_AVAILABLE, ctx.country, tuple(chosen))


# Which official category a budget line is compared with (2.8 M4). MITA's own
# lines by code; a line of the user's by the MITA line it replaces. Bills keep
# their own figures: a rent or loan is a contract, not a price index.
LINE_CATEGORIES: Dict[str, str] = {
    "groceries": "food",
    "dining out": "restaurants",
    "coffee": "restaurants",
    "transport public": "transport",
    "transport gas": "transport",
    "clothing": "clothing",
    "entertainment events": "recreation",
    "hobbies": "recreation",
}


def comparison_category(line: str, replaces: Tuple[str, ...] = ()) -> Optional[str]:
    if line in LINE_CATEGORIES:
        return LINE_CATEGORIES[line]
    for code in replaces:
        if code in LINE_CATEGORIES:
            return LINE_CATEGORIES[code]
    return None


def inflation_by_category(result: RegionalContext) -> Dict[str, Statistic]:
    """The monthly inflation figure per category key (``all_items``, ``food``…)."""
    return {
        s.category_key: s
        for s in result.statistics
        if s.row.indicator == catalog.INFLATION
    }


# Spending references (app/regional/reference.py): what households in the
# user's country spend a month on average, from three official series and a
# stated method. Like every statistic here: read after a draft (never its
# input), national, and never in a currency other than the user's.
REFERENCE_INDICATORS = (
    catalog.HOUSEHOLD_EXPENDITURE,
    catalog.SPENDING_SHARE,
    catalog.PRICE_INDEX_ANNUAL,
    catalog.HOUSEHOLDS_BUYING,
)


@dataclass(frozen=True)
class SpendingReferences:
    status: str  # available | no_country | turned_off | unavailable
    country: Optional[str]
    references: Dict[str, reference_engine.Reference]


def spending_references(
    db: Session, ctx: UserContext, *, today: Optional[date] = None
) -> SpendingReferences:
    """One reference per category (food, clothing, household_energy, fuel),
    available or insufficient_data with its reason. One query on the
    ``(geo_code, indicator, period_start)`` index."""
    day = today or ctx.today
    keys = tuple(reference_engine.CATEGORIES)

    def every(reason: str) -> Dict[str, reference_engine.Reference]:
        return {k: reference_engine.insufficient(k, reason) for k in keys}

    if ctx.country is None:
        return SpendingReferences(STATUS_NO_COUNTRY, None, every("no_country"))
    if not ctx.regional_context_enabled:
        return SpendingReferences(STATUS_TURNED_OFF, ctx.country, every("turned_off"))
    if not setup_queries.currency_set(ctx):
        return SpendingReferences(STATUS_UNAVAILABLE, ctx.country, every("no_currency"))
    rows = list(
        db.scalars(
            select(RegionalObservation).where(
                RegionalObservation.geo_code == ctx.country,
                RegionalObservation.indicator.in_(REFERENCE_INDICATORS),
            )
        )
    )
    found = reference_engine.references(
        rows,
        country=ctx.country,
        currency=ctx.currency,
        household_size=ctx.household_size,
        today=day,
    )
    status = (
        STATUS_AVAILABLE
        if any(r.status == reference_engine.AVAILABLE for r in found.values())
        else STATUS_UNAVAILABLE
    )
    return SpendingReferences(status, ctx.country, found)


# Which reference a budget line is compared with — MITA's lines by code, a
# line of the user's by the MITA line it replaces — and, for every other
# line, why there is none. Never a guess: an unlisted line has no reference.
REFERENCE_LINES: Dict[str, str] = {
    "groceries": "food",
    "clothing": "clothing",
    "transport gas": "fuel",
}
NO_REFERENCE: Dict[str, str] = {
    "dining out": "participation_varies",
    "coffee": "category_mismatch",
    "transport public": "category_mismatch",
    "entertainment events": "category_mismatch",
    "hobbies": "category_mismatch",
    "flights": "participation_varies",
    "insurance medical": "category_mismatch",
    "out of pocket medical": "personal_circumstances",
}
LINE_REASONS: Dict[str, str] = {
    "participation_varies": (
        "a national average mixes people who spend on this with people who "
        "never do, so it says nothing about one person's line"
    ),
    "category_mismatch": (
        "the official category is broader or different (public transport is "
        "inside 'transport services' with flights and taxis)"
    ),
    "personal_circumstances": (
        "it depends on age and health far more than on the country"
    ),
    "no_statistic_for_line": "no official statistic matches this line",
}


def line_reference(
    line: str, replaces: Tuple[str, ...] = ()
) -> Tuple[Optional[str], Optional[str]]:
    """``(reference category, None)`` or ``(None, reason)`` for a line."""
    for code in (line, *replaces):
        if code in REFERENCE_LINES:
            return REFERENCE_LINES[code], None
    for code in (line, *replaces):
        if code in NO_REFERENCE:
            return None, NO_REFERENCE[code]
    return None, "no_statistic_for_line"

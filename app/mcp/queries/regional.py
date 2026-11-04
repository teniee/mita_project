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
from app.mcp.queries.periods import UserContext
from app.regional import catalog
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
    indicators = catalog.TOPICS.get(topic) if topic else None
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
    if indicators:
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

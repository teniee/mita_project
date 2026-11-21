"""World Bank Indicators API v2 (JSON).

``https://api.worldbank.org/v2/country/all/indicator/{id}?format=json&mrnev=N``
returns ``[meta, rows]``: one request for every economy (aggregates such as
"Euro area" are dropped: only ISO 3166-1 countries MITA knows are kept).
``mrnev`` asks for the most recent non-empty values, so a country without a
value has no row — never a zero.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import urlencode

from app.mcp.countries import COUNTRIES
from app.regional.catalog import Dataset
from app.regional.observations import Observation, RejectedValue, build

BASE = "https://api.worldbank.org/v2/country/all/indicator/"
MOST_RECENT = 3
PER_PAGE = 1000


def request_url(spec: Dataset, page: int = 1) -> str:
    params = {
        "format": "json",
        "mrnev": MOST_RECENT,
        "per_page": PER_PAGE,
        "page": page,
    }
    return BASE + spec.dataset + "?" + urlencode(params)


def _published(meta: dict) -> Optional[datetime]:
    text = meta.get("lastupdated")
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def pages(payload) -> int:
    meta = payload[0] if isinstance(payload, list) and payload else {}
    try:
        return max(1, int(meta.get("pages") or 1))
    except (TypeError, ValueError):
        return 1


def parse(spec: Dataset, payload, source_url: str) -> Tuple[List[Observation], int]:
    if not isinstance(payload, list) or len(payload) < 2:
        # The API answers errors as [{"message": [...]}] with HTTP 200.
        raise ValueError("unexpected World Bank response shape")
    meta, rows = payload[0], payload[1] or []
    published = _published(meta)
    found: List[Observation] = []
    rejected = 0
    for row in rows:
        country = (row.get("country") or {}).get("id")
        if country not in COUNTRIES:
            continue  # an aggregate ("Euro area", "World")
        if (row.get("indicator") or {}).get("id") != spec.dataset:
            rejected += 1
            continue
        try:
            found.append(
                build(
                    spec,
                    series_key=f"{spec.dataset}.{country}",
                    category=None,
                    category_label="All items",
                    geo_code=country,
                    period=str(row.get("date") or ""),
                    value=row.get("value"),
                    provider_status=(row.get("obs_status") or None),
                    published_at=published,
                    source_url=source_url,
                )
            )
        except RejectedValue:
            rejected += 1
    return found, rejected

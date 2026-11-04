"""Eurostat Statistics API (JSON-stat 2.0).

``https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}``
with one filter parameter per dimension value (repeated for several values).
The response has ``id`` (dimension order), ``size``, ``value`` keyed by the
flat cell index (only cells with data) and ``status`` (flags such as ``e``,
``p``). Geography is Eurostat's own code (``EL`` for Greece).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import urlencode

from app.regional import catalog
from app.regional.catalog import Dataset
from app.regional.observations import Observation, RejectedValue, build

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

# Fixed filters per dataset, besides geography and categories.
FILTERS = {
    "prc_hicp_minr": {"freq": "M", "unit": "RCH_A"},
    "prc_ppp_ind": {"freq": "A", "na_item": "PLI_EU27_2020"},
    "hbs_str_t211": {"freq": "A", "unit": "PM"},
    "nrg_pc_204": {
        "freq": "S",
        "nrg_cons": "KWH2500-4999",
        "unit": "KWH",
        "tax": "I_TAX",
        "currency": "EUR",
    },
    "nrg_pc_202": {
        "freq": "S",
        "nrg_cons": "GJ20-199",
        "unit": "KWH",
        "tax": "I_TAX",
        "currency": "EUR",
    },
}
CATEGORY_DIMENSION = {
    "prc_hicp_minr": "coicop18",
    "prc_ppp_ind": "ppp_cat",
    "hbs_str_t211": "coicop",
    "nrg_pc_204": "siec",
    "nrg_pc_202": "siec",
}


def request_url(spec: Dataset, countries: Sequence[str], since: str) -> str:
    """The query for ``spec``: only countries Eurostat data may be reused for."""
    allowed = [c for c in countries if c in catalog.EUROSTAT_COUNTRIES]
    if not allowed:
        raise ValueError("no country here may use Eurostat data")
    params: List[Tuple[str, str]] = [("format", "JSON"), ("lang", "EN")]
    params += sorted(FILTERS[spec.dataset].items())
    dimension = CATEGORY_DIMENSION[spec.dataset]
    params += [(dimension, code) for code, _label in spec.categories]
    params += [("geo", catalog.EUROSTAT_GEO.get(c, c)) for c in sorted(allowed)]
    params.append(("sinceTimePeriod", since))
    return BASE + spec.dataset + "?" + urlencode(params)


def _published(payload: dict):
    text = payload.get("updated")
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def parse(
    spec: Dataset, payload: dict, source_url: str
) -> Tuple[List[Observation], int]:
    """``(observations, rejected cells)``. Cells with no value are absent
    from JSON-stat and therefore never stored."""
    ids: List[str] = payload["id"]
    sizes: List[int] = payload["size"]
    dims = payload["dimension"]
    # Position → code, per dimension.
    codes = {}
    for dim in ids:
        index = dims[dim]["category"]["index"]
        if isinstance(index, list):
            codes[dim] = {i: code for i, code in enumerate(index)}
        else:
            codes[dim] = {position: code for code, position in index.items()}
    labels = {code: label for code, label in spec.categories}
    strides = []
    stride = 1
    for size in reversed(sizes):
        strides.append(stride)
        stride *= size
    strides.reverse()
    status = payload.get("status") or {}
    published = _published(payload)
    category_dim = CATEGORY_DIMENSION[spec.dataset]

    found: List[Observation] = []
    rejected = 0
    for flat, value in _cells(payload.get("value")):
        coordinate = {}
        rest = flat
        for dim, step in zip(ids, strides):
            coordinate[dim] = codes[dim][rest // step]
            rest %= step
        geo = catalog.EUROSTAT_ISO.get(coordinate["geo"], coordinate["geo"])
        if geo not in catalog.EUROSTAT_COUNTRIES:
            continue  # an aggregate (EU27_2020, EA) or a country not allowed
        category = coordinate[category_dim]
        series = ".".join(coordinate[d] for d in ids if d != "time")
        try:
            found.append(
                build(
                    spec,
                    series_key=series,
                    category=category,
                    category_label=labels.get(category),
                    geo_code=geo,
                    period=coordinate["time"],
                    value=value,
                    provider_status=status.get(str(flat)),
                    published_at=published,
                    source_url=source_url,
                    currency=coordinate.get("currency"),
                )
            )
        except RejectedValue:
            rejected += 1
    return found, rejected


def _cells(values) -> Iterable[Tuple[int, object]]:
    if isinstance(values, dict):
        for key, value in values.items():
            yield int(key), value
    elif isinstance(values, list):  # dense form
        for index, value in enumerate(values):
            if value is not None:
                yield index, value

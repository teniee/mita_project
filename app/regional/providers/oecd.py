"""OECD Data API (SDMX REST, CSV v2).

``https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{key}``
with the key ``REF_AREA.FREQ.METHODOLOGY.MEASURE.UNIT_MEASURE.EXPENDITURE.
ADJUSTMENT.TRANSFORMATION`` and ``+`` between values, so every country and
category comes in ONE download (the OECD publishes a limit of 60 downloads
an hour). Columns are named by code; an empty ``OBS_VALUE`` is no
observation. Expenditure codes are COICOP 1999 ("CP11: Restaurants and
hotels"), reference areas ISO alpha-3.
"""

from __future__ import annotations

import csv
import io
from typing import List, Sequence, Tuple
from urllib.parse import urlencode

from app.regional import catalog
from app.regional.catalog import Dataset
from app.regional.observations import Observation, RejectedValue, build

BASE = (
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
)
ACCEPT = "application/vnd.sdmx.data+csv; charset=utf-8; version=2"
SERIES_DIMENSIONS = (
    "REF_AREA",
    "FREQ",
    "METHODOLOGY",
    "MEASURE",
    "UNIT_MEASURE",
    "EXPENDITURE",
    "ADJUSTMENT",
    "TRANSFORMATION",
)
LAST_OBSERVATIONS = 3


def request_url(spec: Dataset, countries: Sequence[str]) -> str:
    areas = sorted(
        {catalog.OECD_AREAS[c] for c in countries if c in catalog.OECD_AREAS}
    )
    if not areas:
        raise ValueError("no OECD reference area for these countries")
    expenditure = "+".join(code for code, _label in spec.categories)
    key = f"{'+'.join(areas)}.M.N.CPI.PA.{expenditure}.N.GY"
    return BASE + key + "?" + urlencode({"lastNObservations": LAST_OBSERVATIONS})


def parse(spec: Dataset, text: str, source_url: str) -> Tuple[List[Observation], int]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    missing = {"REF_AREA", "EXPENDITURE", "TIME_PERIOD", "OBS_VALUE"} - set(
        reader.fieldnames or ()
    )
    if missing:
        raise ValueError(f"unexpected OECD columns: missing {sorted(missing)}")
    labels = {code: label for code, label in spec.categories}
    found: List[Observation] = []
    rejected = 0
    for row in reader:
        country = catalog.OECD_ISO.get(row["REF_AREA"])
        if country is None:
            continue
        if (row.get("TRANSFORMATION"), row.get("MEASURE")) != ("GY", "CPI"):
            rejected += 1
            continue
        category = row["EXPENDITURE"]
        try:
            found.append(
                build(
                    spec,
                    series_key=".".join(row.get(d, "") for d in SERIES_DIMENSIONS),
                    category=category,
                    category_label=labels.get(category),
                    geo_code=country,
                    period=row["TIME_PERIOD"],
                    value=(row.get("OBS_VALUE") or "").strip() or None,
                    provider_status=(row.get("OBS_STATUS") or "").strip() or None,
                    published_at=None,  # not in the CSV
                    source_url=source_url,
                )
            )
        except RejectedValue:
            rejected += 1
    return found, rejected

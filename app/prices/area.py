"""Where a price lookup looks, decided for one call.

ChatGPT may send ``_meta["openai/userLocation"]`` with an approximate
country and city. MITA's tools never take a city or coordinates as input
(OpenAI plugin guidelines), and MITA stores no city. So:

* a city is only ever "where ChatGPT says the user is now, approximately":
  a temporary search area, never assumed to be where they live;
* the user's confirmed country is their residence for budgets; when the hint
  is in another country, the result says so
  (``country_is_residence = False``);
* a city that is not a plain place name (digits, a street, a postcode,
  more than four words, or words that read like an instruction) is dropped;
  coordinates are never read;
* nothing here is stored or logged.
"""

from __future__ import annotations

import re
from typing import Optional

from app.mcp.countries import country_code
from app.prices.model import (
    AREA_CONFIRMED_COUNTRY,
    AREA_CURRENT_APPROXIMATE,
    SearchArea,
)
from app.prices.validation import INSTRUCTION_LIKE

PLACE_NAME = re.compile(r"^[^\W\d_][^\W\d_ .'\-]*(?:[ .'\-][^\W\d_]+)*\.?$", re.UNICODE)
MAX_CITY = 64
MAX_CITY_WORDS = 4


def _city(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not 0 < len(text) <= MAX_CITY or not PLACE_NAME.match(text):
        return None
    if len(text.split()) > MAX_CITY_WORDS or INSTRUCTION_LIKE.search(text):
        return None
    return text


def search_area(
    confirmed_country: Optional[str], meta: Optional[dict]
) -> Optional[SearchArea]:
    hint = (meta or {}).get("openai/userLocation") if isinstance(meta, dict) else None
    if isinstance(hint, dict):
        country = country_code(hint.get("country")) if hint.get("country") else None
        city = _city(hint.get("city"))
        if country and city:
            return SearchArea(
                country=country,
                city=city,
                source=AREA_CURRENT_APPROXIMATE,
                country_is_residence=(country == confirmed_country),
            )
    if confirmed_country:
        return SearchArea(
            country=confirmed_country,
            city=None,
            source=AREA_CONFIRMED_COUNTRY,
            country_is_residence=True,
        )
    return None

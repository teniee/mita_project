"""Mita Finance – runtime‑configurable country & class budget profiles.

Place this file as **app/logic/country_profiles/loader.py**
(or keep path consistent with your import statements).

Directory structure expected inside your project root::

    app/
      logic/
        country_profiles/
          loader.py          <-- this file
      config/
        country_profiles/
          US.yaml
          GB.yaml
          DEFAULT.yaml

Key ideas
---------
* No hard‑coded EXPENSE_PROFILE inside Python.
* Each country YAML defines:
    currency: "USD"
    classes:
      extremely_low:
        housing:   0.45
        food:      0.18
        transport: 0.12
      ...
    mandatory_categories: [housing, utilities, healthcare, debts, insurance]
    seasonal_factors:
      winter:
        utilities: 1.2
        clothing:  1.15
      summer:
        travel:    1.3
        utilities: 0.9

Function `get_profile(country_code)` returns the full dict;
`get_class_split(country_code, class_key)` returns {category: share}.

If YAML is missing or broken, we fall back to DEFAULT.yaml, then to built‑in stub.
"""

import datetime
import logging
from functools import lru_cache
from pathlib import Path

import yaml

# Root inside docker / project – adjust if needed
CONFIG_DIR = (
    Path(__file__).resolve().parent.parent.parent / "config" / "country_profiles"
)

_FALLBACK_STUB = {
    "currency": "USD",
    "mandatory_categories": [
        "housing",
        "utilities",
        "healthcare",
        "debts",
        "insurance",
    ],
    "seasonal_factors": {"winter": {}, "summer": {}},
    "classes": {
        "middle": {
            "housing": 0.33,
            "transport": 0.17,
            "food": 0.18,
            "savings": 0.10,
            "healthcare": 0.08,
            "entertainment": 0.07,
            "miscellaneous": 0.07,
        }
    },
}


def _load_yaml(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.error("Budget config: failed to read %s – %s", path, e)
        return {}


@lru_cache(maxsize=32)
def get_profile(country_code: str):
    """Return profile dict for given ISO‑2 country code ("US", "GB" ...)."""
    code = country_code.upper()
    path = CONFIG_DIR / f"{code}.yaml"
    if not path.exists():
        path = CONFIG_DIR / "DEFAULT.yaml"
    data = _load_yaml(path)
    if not data:
        return _FALLBACK_STUB
    # minimal validation
    if "classes" not in data:
        data["classes"] = _FALLBACK_STUB["classes"]
    if "mandatory_categories" not in data:
        data["mandatory_categories"] = _FALLBACK_STUB["mandatory_categories"]
    if "seasonal_factors" not in data:
        data["seasonal_factors"] = _FALLBACK_STUB["seasonal_factors"]
    return data


def current_season(date: datetime.date = None):
    d = date or datetime.date.today()
    return (
        "winter"
        if d.month in (12, 1, 2)
        else "summer" if d.month in (6, 7, 8) else "neutral"
    )


def get_class_split(country_code: str, class_key: str, date: datetime.date = None):
    prof = get_profile(country_code)
    split = prof["classes"].get(class_key)
    if not split:
        # fall to middle or first class
        split = prof["classes"].get("middle") or next(iter(prof["classes"].values()))
    season = current_season(date)
    factors = prof["seasonal_factors"].get(season, {})
    # apply seasonal multiplier
    return {cat: share * factors.get(cat, 1.0) for cat, share in split.items()}

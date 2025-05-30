import os
import yaml
import datetime
import logging
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent / "country_profiles"

_FALLBACK_STUB = {
    "currency": "USD",
    "mandatory_categories": ["housing", "utilities", "healthcare", "debts", "insurance"],
    "seasonal_factors": {
        "winter": {},
        "summer": {}
    },
    "class_thresholds": {
        "low": 2000,
        "middle": 5000,
        "high": 10000
    },
    "default_behavior": "balanced",
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
    }
}

def _load_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.error("Failed to load YAML %s: %s", path, e)
        return {}

@lru_cache(maxsize=32)
def get_profile(country_code: str) -> dict:
    code = country_code.upper()
    path = CONFIG_DIR / f"{code}.yaml"
    if not path.exists():
        path = CONFIG_DIR / "DEFAULT.yaml"
    data = _load_yaml(path)
    if not data:
        return _FALLBACK_STUB.copy()

    data.setdefault("classes", _FALLBACK_STUB["classes"])
    data.setdefault("mandatory_categories", _FALLBACK_STUB["mandatory_categories"])
    data.setdefault("seasonal_factors", _FALLBACK_STUB["seasonal_factors"])
    data.setdefault("class_thresholds", _FALLBACK_STUB["class_thresholds"])
    data.setdefault("default_behavior", _FALLBACK_STUB["default_behavior"])
    data.setdefault("currency", _FALLBACK_STUB["currency"])

    return data

def current_season(date: datetime.date = None) -> str:
    d = date or datetime.date.today()
    if d.month in (12, 1, 2):
        return "winter"
    if d.month in (6, 7, 8):
        return "summer"
    return "neutral"

def get_class_split(country_code: str, class_key: str, date: datetime.date = None) -> dict:
    profile = get_profile(country_code)
    split = profile["classes"].get(class_key)
    if not split:
        split = profile["classes"].get("middle") or next(iter(profile["classes"].values()))
    season = current_season(date)
    factors = profile["seasonal_factors"].get(season, {})
    return {cat: round(share * factors.get(cat, 1.0), 4) for cat, share in split.items()}

def _load_all_profiles() -> dict:
    profiles = {}
    if not CONFIG_DIR.exists() or not CONFIG_DIR.is_dir():
        raise RuntimeError(f"Profile directory {CONFIG_DIR} is missing or not a directory.")

    for yaml_file in CONFIG_DIR.glob("*.yaml"):
        country_code = yaml_file.stem.upper()
        data = _load_yaml(yaml_file)

        if not data:
            logging.warning(f"Skipping empty or invalid profile: {yaml_file}")
            continue

        # Apply fallback defaults
        data.setdefault("classes", _FALLBACK_STUB["classes"])
        data.setdefault("mandatory_categories", _FALLBACK_STUB["mandatory_categories"])
        data.setdefault("seasonal_factors", _FALLBACK_STUB["seasonal_factors"])
        data.setdefault("class_thresholds", _FALLBACK_STUB["class_thresholds"])
        data.setdefault("default_behavior", _FALLBACK_STUB["default_behavior"])
        data.setdefault("currency", _FALLBACK_STUB["currency"])

        profiles[country_code] = data

    if not profiles:
        raise RuntimeError(f"No valid country profiles found in {CONFIG_DIR}")

    return profiles

# Глобально доступный словарь всех профилей
COUNTRY_PROFILES = _load_all_profiles()

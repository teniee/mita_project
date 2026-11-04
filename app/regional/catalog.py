"""What MITA ingests, from where, and what each value means.

Every dataset, code and unit here was verified against the provider's live
API on 2026-11-04 (docs/chatgpt-app/personalization-2.8.md §6) — none is
guessed:

* Eurostat ``prc_hicp_minr`` — HICP, ECOICOP ver.2 (dimension ``coicop18``,
  i.e. COICOP 2018), unit ``RCH_A`` (annual rate of change). The older
  ``prc_hicp_manr`` stops at 2025-12 and is not used.
* Eurostat ``prc_ppp_ind`` — price level indices ``PLI_EU27_2020``
  (EU27_2020 = 100) by COICOP 1999 analytical category (``ppp_cat``).
* Eurostat ``hbs_str_t211`` — household budget survey, structure of
  consumption expenditure, per mille, COICOP 1999 (latest wave 2020).
* World Bank ``FP.CPI.TOTL.ZG`` — inflation, consumer prices (annual %), all
  items, every country.
* OECD ``DSD_PRICES@DF_PRICES_ALL`` — CPI growth over one year (``GY``),
  COICOP 1999 expenditure codes (``CP11: Restaurants and hotels``).

Eurostat data may be reused commercially only for EU, EFTA and EU candidate
countries (Eurostat copyright notice: data for other countries, e.g. the USA,
"may not be reused for commercial purposes"), so Eurostat is queried only for
``EUROSTAT_COUNTRIES``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

EUROSTAT = "eurostat"
WORLD_BANK = "worldbank"
OECD = "oecd"

COICOP_2018 = "COICOP_2018"
COICOP_1999 = "COICOP_1999"

# Countries whose Eurostat data MITA may reuse commercially (ISO 3166-1):
# EU27, EFTA, and the EU candidate countries.
EU27 = (
    "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO "
    "SE SI SK"
).split()
EFTA = ["CH", "IS", "LI", "NO"]
EU_CANDIDATES = ["AL", "BA", "GE", "MD", "ME", "MK", "RS", "TR", "UA"]
EUROSTAT_COUNTRIES: Tuple[str, ...] = tuple(sorted(EU27 + EFTA + EU_CANDIDATES))
# Eurostat's own geography codes where they differ from ISO 3166-1.
EUROSTAT_GEO = {"GR": "EL"}
EUROSTAT_ISO = {v: k for k, v in EUROSTAT_GEO.items()}

# OECD reference areas (ISO 3166-1 alpha-3): the 38 members and the EU
# countries in accession talks that the prices dataset covers.
OECD_AREAS: Dict[str, str] = {
    "AU": "AUS", "AT": "AUT", "BE": "BEL", "CA": "CAN", "CL": "CHL",
    "CO": "COL", "CR": "CRI", "CZ": "CZE", "DK": "DNK", "EE": "EST",
    "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC", "HU": "HUN",
    "IS": "ISL", "IE": "IRL", "IL": "ISR", "IT": "ITA", "JP": "JPN",
    "KR": "KOR", "LV": "LVA", "LT": "LTU", "LU": "LUX", "MX": "MEX",
    "NL": "NLD", "NZ": "NZL", "NO": "NOR", "PL": "POL", "PT": "PRT",
    "SK": "SVK", "SI": "SVN", "ES": "ESP", "SE": "SWE", "CH": "CHE",
    "TR": "TUR", "GB": "GBR", "US": "USA", "BG": "BGR", "HR": "HRV",
    "RO": "ROU",
}  # fmt: skip
OECD_ISO = {v: k for k, v in OECD_AREAS.items()}

LICENSE_EUROSTAT = "Eurostat: reuse authorised, source acknowledged"
LICENSE_WORLD_BANK = "World Bank: CC BY 4.0"
# oecd.org refused automated reads of its terms on 2026-11-04: the licence is
# recorded as unconfirmed until the owner confirms it (personalization-2.8 §6).
LICENSE_OECD = "OECD: terms to be confirmed by the owner"

# Categories MITA shows, by classification: (code, label as the provider
# names it). Top-level only — enough to set a budget line in context.
HICP_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("TOTAL", "All items"),
    ("CP01", "Food and non-alcoholic beverages"),
    ("CP03", "Clothing and footwear"),
    ("CP04", "Housing, water, electricity, gas and other fuels"),
    ("CP07", "Transport"),
    ("CP09", "Recreation, sport and culture"),
    ("CP11", "Restaurants and accommodation services"),
)
OECD_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("_T", "All items"),
    ("CP01", "Food and non-alcoholic beverages"),
    ("CP03", "Clothing and footwear"),
    ("CP04", "Housing, water, electricity, gas and other fuels"),
    ("CP07", "Transport"),
    ("CP09", "Recreation and culture"),
    ("CP11", "Restaurants and hotels"),
)
PLI_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("A01", "Actual individual consumption"),
    ("A0101", "Food and non-alcoholic beverages"),
    ("A0103", "Clothing and footwear"),
    ("A0104", "Housing, water, electricity, gas and other fuels"),
    ("A0107", "Transport"),
    ("A0111", "Restaurants and hotels"),
)
HBS_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("CP01", "Food and non-alcoholic beverages"),
    ("CP03", "Clothing and footwear"),
    ("CP04", "Housing, water, electricity, gas and other fuels"),
    ("CP07", "Transport"),
    ("CP09", "Recreation and culture"),
    ("CP11", "Restaurants and hotels"),
)

# MITA's own indicator codes.
INFLATION = "consumer_price_inflation"
INFLATION_ANNUAL = "consumer_price_inflation_annual"
PRICE_LEVEL = "price_level_index"
SPENDING_SHARE = "household_spending_share"


@dataclass(frozen=True)
class Dataset:
    provider: str
    dataset: str
    indicator: str
    unit_kind: str
    unit: str
    base_period: Optional[str]
    classification: Optional[str]
    period_type: str
    # A value older than this (from the start of its period) is stale.
    max_age_days: int
    license: str
    label: str  # what it measures, in plain words
    limitation: str  # what it is not
    categories: Tuple[Tuple[str, str], ...] = ()


HICP = Dataset(
    provider=EUROSTAT,
    dataset="prc_hicp_minr",
    indicator=INFLATION,
    unit_kind="percent_change",
    unit="annual rate of change (%)",
    base_period=None,
    classification=COICOP_2018,
    period_type="month",
    max_age_days=100,
    license=LICENSE_EUROSTAT,
    label="Consumer price inflation (HICP), change over 12 months",
    limitation=(
        "A national average change in consumer prices: not a price at any shop, "
        "not a city figure and not the user's own cost."
    ),
    categories=HICP_CATEGORIES,
)
PLI = Dataset(
    provider=EUROSTAT,
    dataset="prc_ppp_ind",
    indicator=PRICE_LEVEL,
    unit_kind="price_level_index",
    unit="price level index (EU27_2020 = 100)",
    base_period="EU27_2020=100",
    classification=COICOP_1999,
    period_type="year",
    max_age_days=900,
    license=LICENSE_EUROSTAT,
    label="Price level compared with the EU average (purchasing power parities)",
    limitation=(
        "A country-wide comparison with the EU average (100), from purchasing "
        "power parities: not a price, not a city figure, published with a delay."
    ),
    categories=PLI_CATEGORIES,
)
HBS = Dataset(
    provider=EUROSTAT,
    dataset="hbs_str_t211",
    indicator=SPENDING_SHARE,
    unit_kind="per_mille",
    unit="per mille of household consumption expenditure",
    base_period=None,
    classification=COICOP_1999,
    period_type="year",
    # The survey runs every five or six years; its age is always shown.
    max_age_days=365 * 7,
    license=LICENSE_EUROSTAT,
    label="Share of household spending (household budget survey)",
    limitation=(
        "How households in the country divided their spending in the survey "
        "year, on average: not a recommendation and not the user's own shares."
    ),
    categories=HBS_CATEGORIES,
)
WB_INFLATION = Dataset(
    provider=WORLD_BANK,
    dataset="FP.CPI.TOTL.ZG",
    indicator=INFLATION_ANNUAL,
    unit_kind="percent_change",
    unit="annual % (inflation, consumer prices)",
    base_period=None,
    classification=None,
    period_type="year",
    max_age_days=900,
    license=LICENSE_WORLD_BANK,
    label="Consumer price inflation over a calendar year (World Bank)",
    limitation="A national, all-items yearly figure; not a price and not a forecast.",
)
OECD_CPI = Dataset(
    provider=OECD,
    dataset="OECD.SDD.TPS:DSD_PRICES@DF_PRICES_ALL(1.0)",
    indicator=INFLATION,
    unit_kind="percent_change",
    unit="growth rate over 1 year (% per annum), CPI",
    base_period=None,
    classification=COICOP_1999,
    period_type="month",
    max_age_days=100,
    license=LICENSE_OECD,
    label="Consumer price inflation (CPI), change over 12 months",
    limitation=(
        "A national average change in consumer prices: not a price at any shop, "
        "not a city figure and not the user's own cost."
    ),
    categories=OECD_CATEGORIES,
)

DATASETS: Tuple[Dataset, ...] = (HICP, PLI, HBS, WB_INFLATION, OECD_CPI)

# Which provider answers an indicator for a country first: the harmonised
# EU measure where it may be used, then the OECD's.
PROVIDER_PRIORITY: Dict[str, Tuple[str, ...]] = {
    INFLATION: (EUROSTAT, OECD),
    INFLATION_ANNUAL: (WORLD_BANK,),
    PRICE_LEVEL: (EUROSTAT,),
    SPENDING_SHARE: (EUROSTAT,),
}

ATTRIBUTION = {
    EUROSTAT: "Source: Eurostat",
    WORLD_BANK: "Source: World Bank, World Development Indicators (CC BY 4.0)",
    OECD: "Source: OECD",
}


def dataset_of(provider: str, dataset: str) -> Optional[Dataset]:
    return next(
        (d for d in DATASETS if d.provider == provider and d.dataset == dataset), None
    )


# MITA's plain category keys for asking and grouping, per provider code.
CATEGORY_KEYS: Dict[Optional[str], str] = {
    None: "all_items",
    "TOTAL": "all_items",
    "_T": "all_items",
    "A01": "all_items",
    "CP01": "food",
    "A0101": "food",
    "CP03": "clothing",
    "A0103": "clothing",
    "CP04": "housing",
    "A0104": "housing",
    "CP07": "transport",
    "A0107": "transport",
    "CP09": "recreation",
    "CP11": "restaurants",
    "A0111": "restaurants",
}
TOPICS: Dict[str, Tuple[str, ...]] = {
    "inflation": (INFLATION, INFLATION_ANNUAL),
    "price_levels": (PRICE_LEVEL,),
    "household_spending": (SPENDING_SHARE,),
}

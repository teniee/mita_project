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
* Eurostat ``hbs_exp_t111`` — household budget survey, mean consumption
  expenditure per adult equivalent (units ``EUR_AE`` and ``NAC_AE``: euro and
  national currency; verified 2026-11-09, waves 2015 and 2020).
* Eurostat ``prc_hicp_aind`` — HICP annual average index (``INX_A_AVG``,
  2015 = 100), COICOP 1999 (``coicop``); the series ends with 2025 (the
  COICOP 1999 HICP was replaced by ECOICOP ver.2 in 2026).
* Eurostat ``hbs_exp_t123b`` — percentage of households with expenditure
  greater than zero, by COICOP 1999 code (``PC_HH``; waves 2015 and 2020).
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
from decimal import Decimal
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
    ("CP045", "Electricity, gas and other fuels"),
    ("CP07", "Transport"),
    ("CP0722", "Fuels and lubricants for personal transport equipment"),
    ("CP09", "Recreation and culture"),
    ("CP11", "Restaurants and hotels"),
)

# MITA's own indicator codes.
ENERGY_PRICE = "household_energy_price"
INFLATION = "consumer_price_inflation"
INFLATION_ANNUAL = "consumer_price_inflation_annual"
PRICE_LEVEL = "price_level_index"
SPENDING_SHARE = "household_spending_share"
# Inputs of the spending references (app/regional/reference.py), never shown
# on their own: an amount per adult equivalent and an annual price index.
HOUSEHOLD_EXPENDITURE = "household_expenditure_per_adult_equivalent"
PRICE_INDEX_ANNUAL = "consumer_price_index_annual_average"
HOUSEHOLDS_BUYING = "households_with_expenditure"

# A cell's currency taken from its unit code (Eurostat ``EUR_AE`` → EUR,
# ``NAC_AE`` → the country's national currency in that year): never guessed —
# a unit or a country-year not listed here is rejected.
CURRENCY_FROM_UNIT = "from_unit"


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
    # For an amount of money: its currency (asked for explicitly; a cell in
    # another currency is rejected, never converted) and plausible range.
    currency: Optional[str] = None
    value_range: Optional[Tuple[Decimal, Decimal]] = None
    # The first period to ask for, for a dataset whose latest values are
    # older than a few years (a survey wave, a discontinued index).
    since: Optional[str] = None


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
    since="2015",
)
HBS_EXPENDITURE = Dataset(
    provider=EUROSTAT,
    dataset="hbs_exp_t111",
    indicator=HOUSEHOLD_EXPENDITURE,
    unit_kind="currency_amount",
    unit=(
        "mean consumption expenditure per adult equivalent per year (modified "
        "OECD scale), all households"
    ),
    base_period=None,
    classification=None,
    period_type="year",
    max_age_days=365 * 7,
    license=LICENSE_EUROSTAT,
    label="Average household spending per adult equivalent (household budget survey)",
    limitation=(
        "A national average over every kind of household in the survey year: "
        "not a city figure, not today's prices and not the user's own spending."
    ),
    currency=CURRENCY_FROM_UNIT,
    since="2015",
)
HICP_ANNUAL_INDEX = Dataset(
    provider=EUROSTAT,
    dataset="prc_hicp_aind",
    indicator=PRICE_INDEX_ANNUAL,
    unit_kind="index",
    unit="HICP, annual average index (2015 = 100)",
    base_period="2015=100",
    classification=COICOP_1999,
    period_type="year",
    max_age_days=900,
    license=LICENSE_EUROSTAT,
    label="Consumer prices, annual average index (HICP, COICOP 1999)",
    limitation=(
        "How prices of a kind of spending changed between years, nationally: "
        "not a price and not a city figure."
    ),
    categories=(
        ("CP01", "Food and non-alcoholic beverages"),
        ("CP03", "Clothing and footwear"),
        ("CP045", "Electricity, gas and other fuels"),
        ("CP0722", "Fuels and lubricants for personal transport equipment"),
    ),
    since="2015",
)
HBS_BUYING = Dataset(
    provider=EUROSTAT,
    dataset="hbs_exp_t123b",
    indicator=HOUSEHOLDS_BUYING,
    # A percentage of households (0-100): the schema's "ratio" kind.
    unit_kind="ratio",
    unit="% of households with expenditure greater than zero (household budget survey)",
    base_period=None,
    classification=COICOP_1999,
    period_type="year",
    max_age_days=365 * 7,
    license=LICENSE_EUROSTAT,
    label="Households that spent anything on it (household budget survey)",
    limitation=(
        "Measured over the survey's recording period, so households that buy "
        "rarely can be missed: not how many own a car or eat out."
    ),
    categories=(("CP0722", "Fuels and lubricants for personal transport equipment"),),
    value_range=(Decimal("0"), Decimal("100")),
    since="2015",
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

# Average prices households actually pay (Eurostat, half-yearly, verified
# 2026-11-04: latest 2026-S1, updated 2026-10-19): a real unit price, not an
# index — Milestone 3's official "service price". In EUR only: the national
# currency column changed meaning for BG in 2026 (BGN -> EUR).
ELECTRICITY = Dataset(
    provider=EUROSTAT,
    dataset="nrg_pc_204",
    indicator=ENERGY_PRICE,
    unit_kind="currency_amount",
    unit=(
        "EUR per kWh, all taxes and levies included, households using 2,500 to "
        "4,999 kWh a year (band DC)"
    ),
    base_period=None,
    classification=None,
    period_type="half_year",
    max_age_days=400,
    license=LICENSE_EUROSTAT,
    label="Average electricity price paid by households",
    limitation=(
        "A national average per kWh for a typical household band, taxes "
        "included: not the user's tariff or bill, not a city figure."
    ),
    categories=(("E7000", "Electricity"),),
    currency="EUR",
    value_range=(Decimal("0.001"), Decimal("5")),
)
GAS = Dataset(
    provider=EUROSTAT,
    dataset="nrg_pc_202",
    indicator=ENERGY_PRICE,
    unit_kind="currency_amount",
    unit=(
        "EUR per kWh (gross calorific value), all taxes and levies included, "
        "households using 20 to 199 GJ a year (band D2)"
    ),
    base_period=None,
    classification=None,
    period_type="half_year",
    max_age_days=400,
    license=LICENSE_EUROSTAT,
    label="Average natural gas price paid by households",
    limitation=(
        "A national average per kWh for a typical household band, taxes "
        "included: not the user's tariff or bill, not a city figure."
    ),
    categories=(("G3000", "Natural gas"),),
    currency="EUR",
    value_range=(Decimal("0.001"), Decimal("5")),
)

DATASETS: Tuple[Dataset, ...] = (
    HICP,
    PLI,
    HBS,
    WB_INFLATION,
    OECD_CPI,
    ELECTRICITY,
    GAS,
    HBS_EXPENDITURE,
    HICP_ANNUAL_INDEX,
    HBS_BUYING,
)

# Which provider answers an indicator for a country first: the harmonised
# EU measure where it may be used, then the OECD's.
PROVIDER_PRIORITY: Dict[str, Tuple[str, ...]] = {
    ENERGY_PRICE: (EUROSTAT,),
    INFLATION: (EUROSTAT, OECD),
    INFLATION_ANNUAL: (WORLD_BANK,),
    PRICE_LEVEL: (EUROSTAT,),
    SPENDING_SHARE: (EUROSTAT,),
    HOUSEHOLD_EXPENDITURE: (EUROSTAT,),
    PRICE_INDEX_ANNUAL: (EUROSTAT,),
    HOUSEHOLDS_BUYING: (EUROSTAT,),
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
    "CP045": "household_energy",
    "CP07": "transport",
    "A0107": "transport",
    "CP0722": "fuel",
    "CP09": "recreation",
    "CP11": "restaurants",
    "A0111": "restaurants",
    "E7000": "electricity",
    "G3000": "gas",
}
TOPICS: Dict[str, Tuple[str, ...]] = {
    "inflation": (INFLATION, INFLATION_ANNUAL),
    "price_levels": (PRICE_LEVEL,),
    "household_spending": (SPENDING_SHARE,),
    "prices": (ENERGY_PRICE,),
}
# What get_regional_context shows when no topic is asked: every topic's
# indicators — never the reference inputs (an annual index, a yearly amount
# per adult equivalent, a share of households buying), which mean little on
# their own.
SHOWN_INDICATORS: Tuple[str, ...] = tuple(
    dict.fromkeys(i for indicators in TOPICS.values() for i in indicators)
)

# The national currency (ISO 4217) by country and the year it took effect:
# the euro area with each member's adoption year, and every other country
# Eurostat data may be used for. A country-year not covered is None.
EURO_ADOPTION: Dict[str, int] = {
    "AT": 1999, "BE": 1999, "DE": 1999, "ES": 1999, "FI": 1999, "FR": 1999,
    "IE": 1999, "IT": 1999, "LU": 1999, "NL": 1999, "PT": 1999, "GR": 2001,
    "SI": 2007, "CY": 2008, "MT": 2008, "SK": 2009, "EE": 2011, "LV": 2014,
    "LT": 2015, "HR": 2023, "BG": 2026,
    # Montenegro uses the euro without being a member.
    "ME": 2002,
}  # fmt: skip
CURRENCY_BEFORE_EURO: Dict[str, str] = {"HR": "HRK", "BG": "BGN"}
NON_EURO_CURRENCY: Dict[str, str] = {
    "CZ": "CZK", "DK": "DKK", "HU": "HUF", "PL": "PLN", "RO": "RON",
    "SE": "SEK", "CH": "CHF", "IS": "ISK", "LI": "CHF", "NO": "NOK",
    "AL": "ALL", "BA": "BAM", "GE": "GEL", "MD": "MDL", "MK": "MKD",
    "RS": "RSD", "TR": "TRY", "UA": "UAH",
}  # fmt: skip


def national_currency(country: str, year: int) -> Optional[str]:
    """The currency a country's statistics were in that year, or None when
    MITA does not know it (never a guess)."""
    if country in NON_EURO_CURRENCY:
        return NON_EURO_CURRENCY[country]
    adopted = EURO_ADOPTION.get(country)
    if adopted is None:
        return None
    if year >= adopted:
        return "EUR"
    return CURRENCY_BEFORE_EURO.get(country)


def currency_of_unit(unit_code: str, country: str, year: int) -> Optional[str]:
    """``EUR_AE`` → EUR; ``NAC_AE`` → the national currency that year."""
    if unit_code.startswith("EUR_"):
        return "EUR"
    if unit_code.startswith("NAC_"):
        return national_currency(country, year)
    return None

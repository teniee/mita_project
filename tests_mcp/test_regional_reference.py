"""Spending references from official statistics (owner brief 2026-11-09).

Pure: the engine (``app/regional/reference.py``) on the REAL Eurostat
responses recorded on 2026-11-09 (``tests_mcp/fixtures/regional``:
hbs_exp_t111, hbs_str_t211 detail, prc_hicp_aind, hbs_exp_t123b for BG, DE,
EE, HR, PT, RO, SE, TR). Every expected figure can be checked by hand:

    Bulgaria, food at home, one adult, a month at 2025 prices
      = 4,775 EUR (2020, per adult equivalent) × 246 / 1000
        × (180.75 / 116.26 = 1.554705) ÷ 12 = 152.19 → 152
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.regional import catalog, reference
from app.regional.observations import RejectedValue, build
from app.regional.providers import eurostat

FIXTURES = Path(__file__).parent / "fixtures" / "regional"
TODAY = date(2026, 11, 9)
INPUTS = (
    (catalog.HBS_EXPENDITURE, "eurostat_hbs_exp_t111.json"),
    (catalog.HBS, "eurostat_hbs_str_t211_detail.json"),
    (catalog.HICP_ANNUAL_INDEX, "eurostat_prc_hicp_aind.json"),
    (catalog.HBS_BUYING, "eurostat_hbs_exp_t123b.json"),
)


def rows():
    found = []
    for spec, name in INPUTS:
        parsed, rejected = eurostat.parse(
            spec, json.loads((FIXTURES / name).read_text()), name
        )
        assert rejected == 0
        found += parsed
    return found


ROWS = rows()


def refs(country, currency, household=None, today=TODAY):
    return reference.references(
        ROWS,
        country=country,
        currency=currency,
        household_size=household,
        today=today,
    )


def test_bulgaria_one_adult_by_hand():
    found = refs("BG", "EUR", 1)
    food = found["food"]
    assert food.status == "available"
    assert (food.yearly_per_adult, food.share_per_mille) == (D("4775"), D("246"))
    assert food.price_factor == D("1.554705")  # 180.75 / 116.26
    assert (food.survey_year, food.price_year) == (2020, 2025)
    exact = D("4775") * D("246") / 1000 * D("1.554705") / 12
    assert food.per_adult_exact == exact.quantize(D("0.01"))  # 152.19
    assert food.per_adult == D("152")
    assert (food.household_low, food.household_high) == (D("152"), D("152"))
    assert food.confidence == "low"
    assert {k: v.per_adult for k, v in found.items()} == {
        "food": D("152"),
        "clothing": D("13"),  # 4,775 × 30‰ × 1.117164 ÷ 12
        "household_energy": D("52"),  # 4,775 × 92‰ × 1.414579 ÷ 12
        "fuel": D("42"),  # 4,775 × 40‰ × 1.320004 ÷ 12 ÷ 50 %
    }


def test_fuel_is_for_households_that_buy_it():
    fuel = refs("BG", "EUR", 1)["fuel"]
    # 50 % of Bulgarian households bought fuel in the 2020 survey: the
    # all-household average (21.01) is for them only, assumed average size.
    assert fuel.buying_percent == D("50")
    assert fuel.per_adult_exact == D("42.02")
    germany = refs("DE", "EUR", 1)["fuel"]
    assert (germany.buying_percent, germany.per_adult) == (D("79"), D("117"))


def test_household_size_matters_but_not_linearly():
    """The survey's own scale: 1 first adult, 0.5 each other person aged 14+,
    0.3 each child under 14. Ages unknown → a range, never ×n."""
    assert reference.household_scale(1) == (D("1.0"), D("1.0"))
    assert reference.household_scale(2) == (D("1.3"), D("1.5"))
    assert reference.household_scale(4) == (D("1.9"), D("2.5"))
    two = refs("BG", "EUR", 2)["food"]
    assert (two.household_low, two.household_high) == (D("198"), D("228"))
    four = refs("BG", "EUR", 4)["food"]
    assert (four.household_low, four.household_high) == (D("289"), D("380"))
    assert four.household_high < 4 * four.per_adult  # never linear
    unknown = refs("BG", "EUR", None)["food"]
    assert (unknown.per_adult, unknown.household_low) == (D("152"), None)


def test_currency_rules_never_convert():
    # Bulgaria's currency is the euro since 2026: a budget in leva gets no
    # figure, though Eurostat publishes BGN — MITA does not convert.
    assert refs("BG", "BGN", 1)["food"].reason == "currency_mismatch"
    # Romania's figures are in lei: a budget in lei gets them...
    assert refs("RO", "RON", 1)["food"].per_adult == D("817")
    # ...a budget in euro does not, although Eurostat has an EUR column at
    # 2020 exchange rates (lei prices moved since; carrying it is wrong).
    assert refs("RO", "EUR", 1)["food"].reason == "currency_mismatch"
    # Croatia joined the euro in 2023: Eurostat's euro figure is used.
    assert refs("HR", "EUR", 1)["food"].per_adult == D("219")


def test_countries_without_a_licensed_survey():
    for country, currency in (("US", "USD"), ("GB", "GBP"), ("JP", "JPY")):
        found = refs(country, currency, 1)
        assert {r.reason for r in found.values()} == {"not_covered"}
        assert all(r.per_adult is None for r in found.values())
    assert {r.reason for r in refs(None, "EUR").values()} == {"no_country"}


def test_insufficient_data_is_never_filled_in():
    # Sweden has no 2020 wave; 2015 is too old to carry forward.
    assert {r.reason for r in refs("SE", "SEK", 1).values()} == {"survey_too_old"}
    # Turkey: food prices ×8.0 since 2020 — the 2020 quantities are no basis.
    turkey = refs("TR", "TRY", 1)
    assert turkey["food"].reason == "prices_changed_too_much"
    assert turkey["food"].price_factor == D("8.010038")
    # Estonia: energy prices ×2.33 → no energy figure; food is fine.
    estonia = refs("EE", "EUR", 1)
    assert estonia["household_energy"].reason == "prices_changed_too_much"
    assert estonia["food"].per_adult == D("242")
    # Portugal and Romania publish no energy or fuel share for 2020.
    assert refs("PT", "EUR", 1)["household_energy"].reason == "share_missing"
    assert refs("RO", "RON", 1)["fuel"].reason == "share_missing"
    # Prices too old to be "recent": the 2025 index in mid-2028.
    later = refs("BG", "EUR", 1, today=date(2028, 7, 1))
    assert {r.reason for r in later.values()} == {"prices_too_old"}
    for found in (refs("SE", "SEK"), turkey, estonia):
        assert all(
            r.per_adult is None for r in found.values() if r.status != "available"
        )


def test_a_low_reliability_input_gives_no_figure():
    flagged = [
        (
            type(r)(**{**r.__dict__, "quality_flags": ("low_reliability",)})
            if r.dataset == "hbs_str_t211" and r.category == "CP01"
            else r
        )
        for r in ROWS
    ]
    found = reference.references(
        flagged, country="BG", currency="EUR", household_size=1, today=TODAY
    )
    assert found["food"].reason == "low_reliability"
    assert found["clothing"].status == "available"


def test_expenditure_cells_carry_their_own_currency():
    parsed, _ = eurostat.parse(
        catalog.HBS_EXPENDITURE,
        json.loads((FIXTURES / "eurostat_hbs_exp_t111.json").read_text()),
        "t111",
    )
    currency = {(r.series_key, r.period): r.currency for r in parsed}
    assert currency[("A.EUR_AE.BG", "2020")] == "EUR"
    assert currency[("A.NAC_AE.BG", "2020")] == "BGN"  # before the euro
    assert currency[("A.NAC_AE.HR", "2020")] == "HRK"
    assert currency[("A.NAC_AE.EE", "2015")] == "EUR"  # euro since 2011
    assert currency[("A.NAC_AE.RO", "2020")] == "RON"
    assert currency[("A.NAC_AE.SE", "2015")] == "SEK"
    assert all(r.unit_kind == "currency_amount" for r in parsed)
    # A national-currency cell MITA cannot name is rejected, never guessed.
    with pytest.raises(RejectedValue):
        build(
            catalog.HBS_EXPENDITURE,
            series_key="A.NAC_AE.XX",
            category=None,
            category_label=None,
            geo_code="XX",
            period="2020",
            value="1000",
            provider_status=None,
            published_at=None,
            source_url="x",
            currency=catalog.currency_of_unit("NAC_AE", "XX", 2020),
        )


def test_the_inputs_are_never_shown_as_statistics():
    for hidden in (
        catalog.HOUSEHOLD_EXPENDITURE,
        catalog.PRICE_INDEX_ANNUAL,
        catalog.HOUSEHOLDS_BUYING,
    ):
        assert hidden not in catalog.SHOWN_INDICATORS
    assert catalog.SPENDING_SHARE in catalog.SHOWN_INDICATORS


def test_national_currency_by_year():
    assert catalog.national_currency("BG", 2025) == "BGN"
    assert catalog.national_currency("BG", 2026) == "EUR"
    assert catalog.national_currency("HR", 2022) == "HRK"
    assert catalog.national_currency("HR", 2023) == "EUR"
    assert catalog.national_currency("DE", 2020) == "EUR"
    assert catalog.national_currency("PL", 2026) == "PLN"
    assert catalog.national_currency("US", 2026) is None  # not a Eurostat country
    for country in catalog.EUROSTAT_COUNTRIES:
        assert catalog.national_currency(country, 2026) is not None


def test_requests_ask_for_exactly_what_is_used():
    url = eurostat.request_url(catalog.HBS_EXPENDITURE, ["BG"], "2015")
    assert "unit=EUR_AE&unit=NAC_AE" in url and "coicop" not in url
    url = eurostat.request_url(catalog.HICP_ANNUAL_INDEX, ["BG"], "2015")
    assert "unit=INX_A_AVG" in url and "coicop=CP0722" in url
    url = eurostat.request_url(catalog.HBS_BUYING, ["BG"], "2015")
    assert "unit=PC_HH" in url and "coicop=CP0722" in url

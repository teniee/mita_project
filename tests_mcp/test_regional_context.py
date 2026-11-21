"""get_regional_context (2.8, Milestone 2) through the real MCP tools.

A user in Bulgaria and a user in the United States get statistics for their
own country — with source, period, unit and limitation —, Eurostat never for
the US (its licence), stale figures marked stale, nothing without a
confirmed country or with the switch off, an honest "unavailable" for a
country MITA has no figures for. The observations are the REAL provider
responses of tests_mcp/fixtures/regional, stored through the ingestion upsert;
no network is used.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models.regional import RegionalIngestionRun
from app.regional import catalog
from app.regional.ingest import upsert
from app.regional.providers import eurostat, oecd, worldbank
from tests_mcp.conftest import structured

FIXTURES = Path(__file__).parent / "fixtures" / "regional"
RETRIEVED = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)
NOON = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)


def observations():
    found = []
    for spec, name in (
        (catalog.HICP, "eurostat_prc_hicp_minr.json"),
        (catalog.PLI, "eurostat_prc_ppp_ind.json"),
        (catalog.HBS, "eurostat_hbs_str_t211.json"),
    ):
        rows, _ = eurostat.parse(spec, json.loads((FIXTURES / name).read_text()), name)
        found += rows
    rows, _ = worldbank.parse(
        catalog.WB_INFLATION,
        json.loads((FIXTURES / "worldbank_fp_cpi_totl_zg.json").read_text()),
        "wb",
    )
    found += rows
    rows, _ = oecd.parse(
        catalog.OECD_CPI, (FIXTURES / "oecd_prices.csv").read_text(), "oecd"
    )
    found += rows
    for spec, name in (
        (catalog.ELECTRICITY, "eurostat_nrg_pc_204.json"),
        (catalog.GAS, "eurostat_nrg_pc_202.json"),
    ):
        rows, _ = eurostat.parse(spec, json.loads((FIXTURES / name).read_text()), name)
        found += rows
    return found


async def store(connection):
    def go(c):
        s = Session(bind=c, expire_on_commit=False)
        run_id = uuid.uuid4()
        s.add(
            RegionalIngestionRun(
                id=run_id,
                provider="eurostat",
                dataset="fixtures",
                started_at=RETRIEVED,
                status="succeeded",
            )
        )
        s.flush()
        upsert(s, observations(), run_id, RETRIEVED)
        s.flush()

    await connection.run_sync(go)


async def person(mcp, seed, country=None):
    m = mcp.at(NOON)
    user = await seed.user(currency="EUR", tz="Europe/Sofia", country="ZZ")
    token = m.token(user)
    if country:
        structured(
            await m.call(token, "update_financial_profile", {"country": country})
        )
    return m, token


async def context(m, token, **arguments):
    return structured(await m.call(token, "get_regional_context", arguments))


def index(result):
    return {(s["indicator"], s["category"]): s for s in result["statistics"]}


async def test_a_user_in_bulgaria_gets_bulgarian_statistics(mcp, seed, connection):
    await store(connection)
    m, token = await person(mcp, seed, "BG")
    result = await context(m, token)
    assert result["status"] == "available"
    assert (result["country"], result["country_name"]) == ("BG", "Bulgaria")
    stats = index(result)
    inflation = stats[("consumer_price_inflation", "all_items")]
    # Eurostat's harmonised figure (fresh, 2026-10) is chosen over the OECD's
    # (2025-12, stale) for an EU country.
    assert inflation["provider"] == "eurostat"
    assert (inflation["period"], inflation["value"]) == ("2026-10", "6")
    assert inflation["display"] == "6.0 % over 12 months"
    assert inflation["quality_flags"] == ["estimated"]  # Eurostat's flash
    assert inflation["stale"] is False
    assert inflation["source"] == "Source: Eurostat (prc_hicp_minr)"
    assert inflation["geographic_scope"] == "country"
    assert "not a price at any shop" in inflation["limitation"]
    assert inflation["retrieved_at"].startswith("2026-11-04T09:00")
    # Food: the latest category value is September (October not published).
    food = stats[("consumer_price_inflation", "food")]
    assert (food["period"], food["value"], food["provider"]) == (
        "2026-09",
        "1.6",
        "eurostat",
    )
    # How households spend (survey 2020): a share, shown as a percentage.
    share = stats[("household_spending_share", "food")]
    assert (share["period"], share["value"], share["display"]) == (
        "2020",
        "246",
        "24.6 % of household spending",
    )
    assert share["unit_kind"] == "per_mille"
    # Price levels against the EU average: an index, not a price.
    level = stats[("price_level_index", "food")]
    assert level["unit_kind"] == "price_level_index"
    assert level["base_period"] == "EU27_2020=100"
    assert level["display"].endswith("(EU average = 100)")
    # Yearly inflation from the World Bank, with its licence.
    yearly = stats[("consumer_price_inflation_annual", "all_items")]
    assert (yearly["period"], yearly["license"]) == ("2025", "World Bank: CC BY 4.0")
    assert any("never change the user's budget" in n for n in result["notes"])


async def test_a_user_in_the_us_gets_oecd_and_world_bank_never_eurostat(
    mcp, seed, connection
):
    await store(connection)
    m, token = await person(mcp, seed, "US")
    result = await context(m, token)
    assert result["status"] == "available"
    assert {s["provider"] for s in result["statistics"]} == {"oecd", "worldbank"}
    stats = index(result)
    total = stats[("consumer_price_inflation", "all_items")]
    assert (total["period"], total["stale"], total["provider"]) == (
        "2026-09",
        False,
        "oecd",
    )
    # The OECD's US transport series ended in 2024: shown, marked stale.
    transport = stats[("consumer_price_inflation", "transport")]
    assert (transport["period"], transport["stale"]) == ("2024-12", True)
    assert any("stale" in n for n in result["notes"])
    assert stats[("consumer_price_inflation_annual", "all_items")]["period"] == "2024"


async def test_filters_narrow_the_answer(mcp, seed, connection):
    await store(connection)
    m, token = await person(mcp, seed, "BG")
    food = await context(m, token, category="food")
    assert {s["category"] for s in food["statistics"]} == {"food"}
    inflation = await context(m, token, topic="inflation", category="food")
    assert {s["indicator"] for s in inflation["statistics"]} == {
        "consumer_price_inflation"
    }
    bad = await m.call(token, "get_regional_context", {"topic": "rent"})
    assert bad.is_error


async def test_no_country_turned_off_and_no_data(mcp, seed, connection):
    await store(connection)
    m, token = await person(mcp, seed)
    result = await context(m, token)
    assert (result["status"], result["statistics"]) == ("no_country", [])
    m, token = await person(mcp, seed, "BG")
    structured(
        await m.call(token, "update_financial_profile", {"regional_comparisons": False})
    )
    result = await context(m, token)
    assert (result["status"], result["statistics"]) == ("turned_off", [])
    m, token = await person(mcp, seed, "JP")  # nothing ingested for Japan here
    result = await context(m, token)
    assert (result["status"], result["statistics"]) == ("unavailable", [])
    assert any("never estimate" in n for n in result["notes"])


async def test_statistics_never_change_a_budget(mcp, seed, connection):
    """The preview reads no statistic: the same draft with and without them."""
    m, token = await person(mcp, seed, "BG")
    structured(
        await m.call(
            token,
            "update_financial_profile",
            {"monthly_net_income": 1500, "currency": "EUR", "timezone": "Europe/Sofia"},
        )
    )
    before = structured(await m.call(token, "preview_monthly_budget", {}))
    await store(connection)
    after = structured(await m.call(token, "preview_monthly_budget", {}))

    def amounts(draft):
        return [(a["category"], a["amount"]) for a in draft["category_allocations"]]

    assert amounts(after) == amounts(before)
    assert after["unallocated"] == before["unallocated"]
    assert after["plan_total"] == before["plan_total"]
    # Only the comparisons are new.
    assert before["regional"] is None and after["regional"]["country"] == "BG"


# --- 2.8 M4: statistics and history next to budget lines, comparison only ----------


async def budget_user(mcp, seed, *, country="BG"):
    m = mcp.at(NOON)
    user = await seed.user(currency="EUR", tz="Europe/Sofia", country="ZZ")
    token = m.token(user)
    structured(
        await m.call(
            token,
            "update_financial_profile",
            {
                "monthly_net_income": 1500,
                "currency": "EUR",
                "timezone": "Europe/Sofia",
                "country": country,
            },
        )
    )
    return user, m, token


def line(draft, code):
    return next(a for a in draft["category_allocations"] if a["category"] == code)


async def test_preview_lines_carry_national_comparisons(mcp, seed, connection):
    await store(connection)
    _user, m, token = await budget_user(mcp, seed)
    draft = structured(
        await m.call(
            token,
            "preview_monthly_budget",
            {
                "budget_lines": [
                    {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}
                ]
            },
        )
    )
    groceries = line(draft, "groceries")["regional_comparison"]
    assert groceries == {
        "category": "food",
        "category_label": "Food and non-alcoholic beverages",
        "display": "1.6 % over 12 months",
        "period": "2026-09",
        "stale": False,
        "estimated": False,
        "geographic_scope": "country",
        "source": "Source: Eurostat (prc_hicp_minr)",
        "limitation": catalog.HICP.limitation,
    }
    # The user's Fuel line is compared through the MITA line it replaces.
    fuel = line(draft, "my:Fuel")["regional_comparison"]
    assert (fuel["category"], fuel["display"]) == ("transport", "16.4 % over 12 months")
    # No restaurants figure was ingested in these fixtures: none is shown.
    assert line(draft, "dining out")["regional_comparison"] is None
    # MITA's own public-transport line gets the same transport figure.
    assert line(draft, "transport public")["regional_comparison"]["category"] == (
        "transport"
    )
    assert draft["regional"]["country"] == "BG"
    assert draft["regional"]["statistics_shown"] == 3
    # A comparison never set an amount: Fuel stays exactly 200.00.
    assert line(draft, "my:Fuel")["amount"] == "200.00"


async def test_switched_off_or_no_country_means_no_comparison(mcp, seed, connection):
    await store(connection)
    _user, m, token = await budget_user(mcp, seed)
    structured(
        await m.call(token, "update_financial_profile", {"regional_comparisons": False})
    )
    draft = structured(await m.call(token, "preview_monthly_budget", {}))
    assert draft["regional"] is None
    assert all(a["regional_comparison"] is None for a in draft["category_allocations"])


async def test_a_reviewed_draft_saves_after_statistics_arrive(mcp, seed, connection):
    """The digest covers allocations and layout only: statistics ingested
    between the preview and the yes cannot invalidate (or change) the plan."""
    _user, m, token = await budget_user(mcp, seed)
    draft = structured(await m.call(token, "preview_monthly_budget", {}))
    assert draft["regional"] is None  # nothing ingested yet
    await store(connection)
    saved = structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
        )
    )
    assert saved["status"] == "saved"
    assert saved["plan_total"] == draft["plan_total"]


async def test_recorded_history_is_shown_on_its_line(mcp, seed):
    """Three complete months of groceries (Aug–Oct 2026): 300, 330, 360 →
    330.00 a month on the groceries line; gas expenses on MITA's Fuel line."""
    user, m, token = await budget_user(mcp, seed)
    for month, amount in ((8, "300.00"), (9, "330.00"), (10, "360.00")):
        await seed.txn(
            user,
            amount,
            "groceries",
            datetime(2026, month, 12, 9, 0, tzinfo=timezone.utc),
        )
        await seed.txn(
            user, "45.00", "gas", datetime(2026, month, 20, 9, 0, tzinfo=timezone.utc)
        )
    draft = structured(await m.call(token, "preview_monthly_budget", {}))
    assert draft["history"]["months_used"] == 3
    assert line(draft, "groceries")["recorded_average"] == "330.00"
    assert line(draft, "transport gas")["recorded_average"] == "45.00"
    assert line(draft, "clothing")["recorded_average"] is None  # nothing recorded
    # MITA's amount is still MITA's: history is shown, never applied.
    assert line(draft, "groceries")["source"] == "calculated_by_mita"


async def test_official_prices_households_pay(mcp, seed, connection):
    """Milestone 3's official service price: what households in the user's
    country pay per kWh, with its currency, band and period — for the US
    none (Eurostat's licence), and never a shop price for anyone."""
    await store(connection)
    m, token = await person(mcp, seed, "BG")
    result = await context(m, token, topic="prices")
    stats = index(result)
    power = stats[("household_energy_price", "electricity")]
    assert (power["value"], power["currency"], power["period"]) == (
        "0.1341",
        "EUR",
        "2026-S1",
    )
    assert power["display"] == "0.1341 EUR per kWh, taxes included, national average"
    assert power["unit_kind"] == "currency_amount" and power["stale"] is False
    assert "band DC" in power["unit"]
    assert "not the user's tariff or bill" in power["limitation"]
    gas = stats[("household_energy_price", "gas")]
    assert (gas["value"], gas["period"]) == ("0.0654", "2026-S1")
    m, token = await person(mcp, seed, "US")
    us = await context(m, token, topic="prices")
    assert (us["status"], us["statistics"]) == ("unavailable", [])

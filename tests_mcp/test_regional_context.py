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
    return found + rows


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
    assert after["category_allocations"] == before["category_allocations"]
    assert after["unallocated"] == before["unallocated"]

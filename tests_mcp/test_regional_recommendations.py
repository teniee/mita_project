"""Regional recommendations through the real MCP tools (owner brief
2026-11-09, scenarios A–E; F is in test_local_prices.py).

The statistics are the REAL Eurostat and World Bank responses of
``tests_mcp/fixtures/regional``, stored through the ingestion upsert; every
person is fictional; no network. Each line's recommendation follows a fixed
order — the user's own amount, their recorded history, a stated purchase
pattern, a verified local price (MITA has none), official statistics, then
MITA's rules — and NEVER changes the plan: the same preview with
statistics on or off has the same amounts, and a saved plan is the
previewed one.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.regional import RegionalIngestionRun
from app.mcp.tools.budget import INCOME_BANDS_NOTE
from app.regional import catalog
from app.regional.ingest import upsert
from app.regional.providers import eurostat, worldbank
from tests_mcp.conftest import structured

FIXTURES = Path(__file__).parent / "fixtures" / "regional"
RETRIEVED = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
NOON = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
SOURCES = (
    (catalog.HICP, "eurostat_prc_hicp_minr.json"),
    (catalog.HBS_EXPENDITURE, "eurostat_hbs_exp_t111.json"),
    (catalog.HBS, "eurostat_hbs_str_t211_detail.json"),
    (catalog.HICP_ANNUAL_INDEX, "eurostat_prc_hicp_aind.json"),
    (catalog.HBS_BUYING, "eurostat_hbs_exp_t123b.json"),
)


def observations():
    found = []
    for spec, name in SOURCES:
        rows, rejected = eurostat.parse(
            spec, json.loads((FIXTURES / name).read_text()), name
        )
        assert rejected == 0
        found += rows
    rows, _ = worldbank.parse(
        catalog.WB_INFLATION,
        json.loads((FIXTURES / "worldbank_fp_cpi_totl_zg.json").read_text()),
        "wb",
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


async def call(m, token, tool, arguments=None, meta=None):
    return structured(await m.call(token, tool, arguments or {}, meta=meta))


async def person(mcp, seed, *, country, currency, income, household=1, tz=None):
    m = mcp.at(NOON)
    user = await seed.user(currency=currency, tz="UTC", country="ZZ")
    token = m.token(user)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": income,
            "currency": currency,
            "timezone": tz
            or ("Europe/Sofia" if country == "BG" else "America/New_York"),
            "household_size": household,
            "country": country,
        },
    )
    return user, m, token


def lines(draft):
    return {a["category"]: a for a in draft["category_allocations"]}


def amounts(draft):
    return [(a["category"], a["amount"]) for a in draft["category_allocations"]]


async def plan_totals(connection, user):
    result = await connection.execute(
        text(
            "SELECT category, SUM(planned_amount) FROM daily_plan "
            "WHERE user_id = :u GROUP BY category"
        ),
        {"u": user.id},
    )
    return {c: format(a, "f") for c, a in result.all()}


# --- A: Bulgaria €1,000 vs the United States -----------------------------------


async def test_a_bulgaria_1000_eur_gets_national_references_in_euro(
    mcp, seed, connection
):
    await store(connection)
    _user, m, token = await person(mcp, seed, country="BG", currency="EUR", income=1000)
    draft = await call(m, token, "preview_monthly_budget")
    by_line = lines(draft)
    groceries = by_line["groceries"]
    # MITA's own default (13 % food share, 60 % of it groceries) — unchanged.
    assert groceries["amount"] == "78.00"
    rec = groceries["recommendation"]
    assert (rec["basis"], rec["amount"], rec["differs_from_plan"]) == (
        "regional_statistics",
        "152.00",
        True,
    )
    assert rec["confirmed_by_user"] is False
    ref = rec["regional_reference"]
    assert ref["status"] == "available"
    assert (ref["currency"], ref["per_adult_monthly"]) == ("EUR", "152.00")
    assert (ref["survey_year"], ref["price_year"], ref["confidence"]) == (
        2020,
        2025,
        "low",
    )
    assert ref["inputs"] == {
        "yearly_per_adult": "4775",
        "share_per_mille": "246",
        "price_factor": "1.554705",
        "buying_percent": None,
    }
    assert ref["households"] == "all_households"
    assert ref["geographic_scope"] == "country"
    assert "not a city figure" in ref["limitation"]
    # Fuel: for the households that buy it (50 % in the survey).
    fuel = by_line["transport gas"]["recommendation"]
    assert (fuel["basis"], fuel["amount"]) == ("regional_statistics", "42.00")
    assert fuel["regional_reference"]["households"] == "households_that_buy_it"
    assert fuel["regional_reference"]["inputs"]["buying_percent"] == "50"
    # Eating out mixes people who never do with those who do: no figure.
    dining = by_line["dining out"]["recommendation"]
    assert (dining["basis"], dining["regional_reference"]) == ("mita_default", None)
    assert dining["regional_reason"] == "participation_varies"
    summary = draft["recommendations"]
    assert (summary["country"], summary["currency"], summary["household_size"]) == (
        "BG",
        "EUR",
        1,
    )
    assert summary["regional_status"] == "available"
    assert summary["verified_local_prices"] == "none"
    assert summary["precedence"][0] == "obligation"
    # MITA's own bands are not purchasing-power aware, and the preview says so.
    assert INCOME_BANDS_NOTE in draft["assumptions"]


async def test_a_the_us_has_no_reference_and_no_exchange_rate_is_used(
    mcp, seed, connection
):
    """$1,080 is €1,000 at an exchange rate THIS TEST assumes (1.08 USD per
    EUR); MITA uses no exchange rate anywhere. The US gets MITA's US rules
    and no household-spending reference (Eurostat's licence excludes the US;
    no US baseline is verified)."""
    await store(connection)
    for income, groceries in ((1000, "90.00"), (1080, "97.20")):
        _user, m, token = await person(
            mcp, seed, country="US", currency="USD", income=income
        )
        draft = await call(m, token, "preview_monthly_budget")
        line = lines(draft)["groceries"]
        assert line["amount"] == groceries  # 15 % food share at the US "low" tier
        rec = line["recommendation"]
        assert rec["basis"] == "mita_default"
        assert rec["regional_reference"]["status"] == "insufficient_data"
        assert rec["regional_reference"]["reason"] == "not_covered"
        assert rec["regional_reference"]["per_adult_monthly"] is None
        assert draft["recommendations"]["regional_status"] == "unavailable"
        assert INCOME_BANDS_NOTE not in draft["assumptions"]  # US rules, in USD
        assert "EUR" not in json.dumps(draft["recommendations"])


# --- B: Varna and Sofia are the same country to MITA ----------------------------


async def test_b_varna_and_sofia_get_the_same_country_figures(mcp, seed, connection):
    await store(connection)
    results = []
    for city in ("Varna", "Sofia"):
        _user, m, token = await person(
            mcp, seed, country="BG", currency="EUR", income=1500
        )
        hint = {"openai/userLocation": {"country": "BG", "city": city}}
        draft = await call(m, token, "preview_monthly_budget", meta=hint)
        context = await call(
            m, token, "get_regional_context", {"topic": "household_spending"}, hint
        )
        results.append((city, draft, context))
    (_, varna, varna_ctx), (_, sofia, sofia_ctx) = results

    def recommendations(draft):
        return {k: v["recommendation"] for k, v in lines(draft).items()}

    assert recommendations(varna) == recommendations(sofia)
    assert varna_ctx["spending_references"] == sofia_ctx["spending_references"]
    for _city, draft, context in results:
        blob = json.dumps([draft, context])
        assert "Varna" not in blob and "Sofia" not in blob
        assert {r["geographic_scope"] for r in context["spending_references"]} == {
            "country"
        }


# --- C: no car — no fuel line; transit and taxis are the user's own -------------


async def test_c_no_car_means_no_fuel_envelope(mcp, seed, connection):
    await store(connection)
    _user, m, token = await person(mcp, seed, country="BG", currency="EUR", income=1500)
    await call(
        m,
        token,
        "save_spending_patterns",
        {"patterns": [{"line": "transport gas", "kind": "not_applicable"}]},
    )
    await call(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "everyday_spending", "answer": "described"}]},
    )
    draft = await call(
        m,
        token,
        "preview_monthly_budget",
        {
            "budget_lines": [
                {
                    "label": "Public transport",
                    "amount": 26,
                    "replaces": ["transport public"],
                },
                {"label": "Taxi", "amount": 30},
            ]
        },
    )
    by_line = lines(draft)
    assert "transport gas" not in by_line
    assert all(
        (a["recommendation"]["regional_reference"] or {}).get("category") != "fuel"
        for a in draft["category_allocations"]
    )
    transit = by_line["my:Public transport"]
    assert transit["amount"] == "26.00"
    assert transit["recommendation"]["basis"] == "user_amount"
    assert transit["recommendation"]["regional_reason"] == "category_mismatch"
    taxi = by_line["my:Taxi"]
    assert (taxi["amount"], taxi["recommendation"]["basis"]) == ("30.00", "user_amount")
    assert taxi["recommendation"]["regional_reason"] == "no_statistic_for_line"


# --- D: the user's Fuel €200 stays; the reference is only a reference -----------


async def test_d_the_users_fuel_is_kept_and_the_reference_is_beside_it(
    mcp, seed, connection
):
    await store(connection)
    user, m, token = await person(mcp, seed, country="BG", currency="EUR", income=1500)
    own = {
        "budget_lines": [
            {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}
        ]
    }
    with_statistics = await call(m, token, "preview_monthly_budget", own)
    fuel = lines(with_statistics)["my:Fuel"]
    assert fuel["amount"] == "200.00"
    rec = fuel["recommendation"]
    assert (rec["basis"], rec["amount"], rec["differs_from_plan"]) == (
        "user_amount",
        "200.00",
        False,
    )
    assert rec["confirmed_by_user"] is True
    assert rec["regional_reference"]["per_adult_monthly"] == "42.00"
    # The same preview with statistics off: the same plan, to the cent.
    await call(m, token, "update_financial_profile", {"regional_comparisons": False})
    without = await call(m, token, "preview_monthly_budget", own)
    assert amounts(without) == amounts(with_statistics)
    assert without["plan_total"] == with_statistics["plan_total"]
    assert without["unallocated"] == with_statistics["unallocated"]
    assert lines(without)["my:Fuel"]["recommendation"]["regional_reference"] is None
    assert without["recommendations"]["regional_status"] == "turned_off"
    # Saving the statistics-on preview stores exactly its amounts.
    await call(m, token, "update_financial_profile", {"regional_comparisons": True})
    again = await call(m, token, "preview_monthly_budget", own)
    saved = await call(
        m, token, "save_monthly_budget", {"draft_token": again["draft_token"]}
    )
    assert saved["status"] == "saved"
    stored = await plan_totals(connection, user)
    assert stored["my:Fuel"] == "200.00"
    for category, amount in amounts(again):
        assert stored[category] == amount


# --- E: the user's history is not the national average -------------------------


async def test_e_history_comes_before_statistics_and_replaces_nothing(
    mcp, seed, connection
):
    await store(connection)
    user, m, token = await person(mcp, seed, country="BG", currency="EUR", income=1500)
    for month, amount in ((8, "300.00"), (9, "310.00"), (10, "320.00")):
        await seed.txn(
            user,
            amount,
            "groceries",
            datetime(2026, month, 12, 9, 0, tzinfo=timezone.utc),
        )
    draft = await call(m, token, "preview_monthly_budget")
    groceries = lines(draft)["groceries"]
    plan_amount = groceries["amount"]
    assert groceries["recorded_average"] == "310.00"
    rec = groceries["recommendation"]
    assert (rec["basis"], rec["amount"]) == ("history", "310.00")
    assert rec["regional_reference"]["per_adult_monthly"] == "152.00"
    assert rec["amount"] != rec["regional_reference"]["per_adult_monthly"]
    # Nothing replaced: the plan keeps MITA's amount until the user sets one.
    assert plan_amount == "117.00"  # 1,500 × 13 % × 60 %
    assert rec["differs_from_plan"] is True
    # The user's own amount outranks both their history and the statistics.
    own = await call(
        m,
        token,
        "preview_monthly_budget",
        {
            "budget_lines": [
                {"label": "Groceries", "amount": 250, "replaces": ["groceries"]}
            ]
        },
    )
    mine = lines(own)["my:Groceries"]
    assert mine["amount"] == "250.00"
    assert (mine["recommendation"]["basis"], mine["recommendation"]["amount"]) == (
        "user_amount",
        "250.00",
    )


async def test_a_household_of_four_gets_a_range_not_four_times(mcp, seed, connection):
    await store(connection)
    _user, m, token = await person(
        mcp, seed, country="BG", currency="EUR", income=3000, household=4
    )
    draft = await call(m, token, "preview_monthly_budget")
    rec = lines(draft)["groceries"]["recommendation"]
    assert rec["basis"] == "regional_statistics"
    assert (rec["amount"], rec["low"], rec["high"]) == (None, "289.00", "380.00")
    ref = rec["regional_reference"]
    assert (ref["household_size"], ref["per_adult_monthly"]) == (4, "152.00")
    assert (ref["household_monthly_low"], ref["household_monthly_high"]) == (
        "289.00",
        "380.00",
    )


async def test_get_regional_context_lists_the_references(mcp, seed, connection):
    await store(connection)
    _user, m, token = await person(
        mcp, seed, country="BG", currency="EUR", income=1500, household=2
    )
    result = await call(
        m, token, "get_regional_context", {"topic": "household_spending"}
    )
    refs = {r["category"]: r for r in result["spending_references"]}
    assert set(refs) == {"food", "clothing", "household_energy", "fuel"}
    assert (
        refs["food"]["household_monthly_low"],
        refs["food"]["household_monthly_high"],
    ) == (
        "198.00",
        "228.00",
    )
    assert any("never present one as the user's cost" in n for n in result["notes"])
    # The inputs are never listed as statistics of their own.
    indicators = {s["indicator"] for s in result["statistics"]}
    assert indicators == {"household_spending_share"}
    only_food = await call(
        m,
        token,
        "get_regional_context",
        {"topic": "household_spending", "category": "food"},
    )
    assert [r["category"] for r in only_food["spending_references"]] == ["food"]
    inflation = await call(m, token, "get_regional_context", {"topic": "inflation"})
    assert inflation["spending_references"] == []


async def test_a_currency_the_country_does_not_use_gets_no_figure(
    mcp, seed, connection
):
    await store(connection)
    _user, m, token = await person(mcp, seed, country="BG", currency="USD", income=1500)
    draft = await call(m, token, "preview_monthly_budget")
    ref = lines(draft)["groceries"]["recommendation"]["regional_reference"]
    assert (ref["status"], ref["reason"]) == ("insufficient_data", "currency_mismatch")
    assert lines(draft)["groceries"]["recommendation"]["basis"] == "mita_default"

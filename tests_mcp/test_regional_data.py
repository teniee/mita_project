"""MITA's regional reference data (2.8, Milestone 2): official statistics,
normalized with units and provenance, ingested idempotently.

The parsers run on REAL responses recorded from the providers on 2026-11-04
(``tests_mcp/fixtures/regional``; the requests are in each test) — never
invented figures. Network is never used here: the fetcher is driven by a
replaying client.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.regional import RegionalIngestionRun, RegionalObservation
from app.regional import catalog
from app.regional.http import Fetcher, ProviderError
from app.regional.ingest import run_dataset, upsert
from app.regional.observations import RejectedValue, build, is_stale
from app.regional.providers import eurostat, oecd, worldbank

FIXTURES = Path(__file__).parent / "fixtures" / "regional"
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
D = Decimal


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def by(observations, **match):
    return [
        o for o in observations if all(getattr(o, k) == v for k, v in match.items())
    ]


# --- parsers on real responses -------------------------------------------------------


def test_eurostat_hicp_ecoicop_v2():
    """GET .../prc_hicp_minr?format=JSON&lang=EN&freq=M&unit=RCH_A&coicop18=TOTAL
    &coicop18=CP01&coicop18=CP07&geo=BG&geo=EL&sinceTimePeriod=2026-08"""
    found, rejected = eurostat.parse(
        catalog.HICP, load("eurostat_prc_hicp_minr.json"), "https://example/hicp"
    )
    assert rejected == 0
    bg_total = by(found, geo_code="BG", category="TOTAL")
    assert [(o.period, o.value, o.quality_flags) for o in bg_total] == [
        ("2026-08", D("5.000000"), ()),
        ("2026-09", D("5.600000"), ()),
        ("2026-10", D("6.000000"), ("estimated",)),  # Eurostat's flash: 'e'
    ]
    first = bg_total[0]
    assert (first.unit_kind, first.classification, first.period_type) == (
        "percent_change",
        "COICOP_2018",
        "month",
    )
    assert first.series_key == "M.RCH_A.TOTAL.BG"
    assert first.published_at == datetime.fromisoformat("2026-11-04T11:00:00+01:00")
    assert first.license.startswith("Eurostat")
    # Greece is "EL" at Eurostat and GR in MITA.
    assert {o.geo_code for o in found} == {"BG", "GR"}
    # October has no category values yet: those cells are absent, never zero.
    assert by(found, geo_code="BG", category="CP01", period="2026-10") == []
    assert len(found) == 14


def test_eurostat_price_levels_and_household_shares():
    """prc_ppp_ind (PLI_EU27_2020; A01, A0101, A0111; BG, DE; since 2023) and
    hbs_str_t211 (per mille; CP01, CP04, CP07, CP11; BG; since 2015)."""
    pli, rejected = eurostat.parse(
        catalog.PLI, load("eurostat_prc_ppp_ind.json"), "https://example/pli"
    )
    assert rejected == 0
    food_bg = by(pli, geo_code="BG", category="A0101")
    assert food_bg and all(o.unit_kind == "price_level_index" for o in food_bg)
    assert food_bg[0].base_period == "EU27_2020=100"
    assert food_bg[0].classification == "COICOP_1999"
    assert all(D("0") < o.value < D("1000") for o in pli)
    shares, rejected = eurostat.parse(
        catalog.HBS, load("eurostat_hbs_str_t211.json"), "https://example/hbs"
    )
    assert rejected == 0
    food_2020 = by(shares, geo_code="BG", category="CP01", period="2020")
    assert [(o.value, o.unit_kind) for o in food_2020] == [
        (D("246.000000"), "per_mille")
    ]


def test_world_bank_inflation_drops_aggregates():
    """GET /v2/country/BG;US;EMU/indicator/FP.CPI.TOTL.ZG?mrnev=2: the euro
    area aggregate (EMU) is not a country and is dropped."""
    found, rejected = worldbank.parse(
        catalog.WB_INFLATION,
        load("worldbank_fp_cpi_totl_zg.json"),
        "https://example/wb",
    )
    assert rejected == 0
    assert {o.geo_code for o in found} == {"BG", "US"}
    bg = by(found, geo_code="BG", period="2025")
    assert [o.value for o in bg] == [D("4.580844")]
    assert bg[0].license == "World Bank: CC BY 4.0"
    assert bg[0].published_at == datetime(2026, 10, 8, tzinfo=timezone.utc)


def test_oecd_cpi_coicop_1999_and_stale_series():
    """OECD prices, USA+BGR, _T+CP01+CP07, GY, last 2 observations."""
    found, rejected = oecd.parse(
        catalog.OECD_CPI,
        (FIXTURES / "oecd_prices.csv").read_text(),
        "https://example/oecd",
    )
    assert rejected == 0
    assert {o.geo_code for o in found} == {"US", "BG"}
    us_transport = by(found, geo_code="US", category="CP07")
    assert {o.period for o in us_transport} == {"2024-11", "2024-12"}
    # A monthly series that ended in 2024 is stale today, and must say so.
    latest = max(us_transport, key=lambda o: o.period_start)
    assert is_stale(catalog.OECD_CPI, latest.period_start, NOW.date())
    us_total = max(by(found, geo_code="US", category="_T"), key=lambda o: o.period)
    assert not is_stale(catalog.OECD_CPI, us_total.period_start, NOW.date())
    assert us_total.classification == "COICOP_1999"


def test_eurostat_is_never_asked_for_a_country_its_licence_excludes():
    url = eurostat.request_url(catalog.HICP, ["BG", "US", "GR"], "2026-01")
    assert "geo=BG" in url and "geo=EL" in url and "geo=US" not in url
    with pytest.raises(ValueError):
        eurostat.request_url(catalog.HICP, ["US", "JP"], "2026-01")


def test_values_are_checked_never_invented():
    common = dict(
        series_key="k",
        category="TOTAL",
        category_label=None,
        geo_code="BG",
        provider_status=None,
        published_at=None,
        source_url="https://example",
    )
    for bad in (None, "", "n/a", "NaN", "Infinity"):
        with pytest.raises(RejectedValue):
            build(catalog.HICP, period="2026-10", value=bad, **common)
    with pytest.raises(RejectedValue):  # prices cannot fall by more than all
        build(catalog.HICP, period="2026-10", value="-120", **common)
    with pytest.raises(RejectedValue):  # a share is at most 1000 per mille
        build(catalog.HBS, period="2020", value="1200", **common)
    with pytest.raises(RejectedValue):  # a yearly figure in a monthly dataset
        build(catalog.HICP, period="2025", value="3.1", **common)
    extreme = build(catalog.WB_INFLATION, period="2024", value="219.9", **common)
    assert extreme.quality_flags == ("extreme_value",)  # kept, flagged


# --- the fetcher: retries, backoff, no retry on a client error -----------------------


def replay(responses):
    """An httpx2 client that answers from a list (status, body)."""
    calls = []

    def handler(request):
        calls.append(str(request.url))
        status, body = responses[min(len(calls) - 1, len(responses) - 1)]
        return httpx2.Response(status, text=body, headers={"Retry-After": "1"})

    return httpx2.Client(transport=httpx2.MockTransport(handler)), calls


def test_the_fetcher_retries_then_gives_up_cleanly():
    sleeps = []
    client, calls = replay([(503, "busy"), (200, "{}")])
    fetcher = Fetcher(client=client, sleep=sleeps.append, clock=lambda: 0.0)
    assert fetcher.get("eurostat", "https://example/a").status_code == 200
    assert len(calls) == 2 and sleeps  # waited before the retry
    client, calls = replay([(404, "no such dataset")])
    fetcher = Fetcher(client=client, sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(ProviderError):
        fetcher.get("eurostat", "https://example/b")
    assert len(calls) == 1  # a client error is not retried
    client, calls = replay([(503, "busy")])
    fetcher = Fetcher(client=client, sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(ProviderError):
        fetcher.get("oecd", "https://example/c")
    assert len(calls) == 4  # bounded


# --- ingestion: idempotent upsert, revisions, failures keep the last values ----------


async def run_sync(connection, fn):
    """``fn`` with a sync Session on the test's connection, inside its
    rolled-back transaction (the ingestion job is synchronous)."""
    return await connection.run_sync(
        lambda c: fn(Session(bind=c, expire_on_commit=False))
    )


async def test_upsert_is_idempotent_and_flags_revisions(connection):
    found, _ = eurostat.parse(
        catalog.HICP, load("eurostat_prc_hicp_minr.json"), "https://example/hicp"
    )
    run_id = uuid.uuid4()

    def first(s):
        s.add(
            RegionalIngestionRun(
                id=run_id,
                provider="eurostat",
                dataset="prc_hicp_minr",
                started_at=NOW,
                status="running",
            )
        )
        s.flush()
        counts = upsert(s, found, run_id, NOW)
        s.flush()
        return counts

    assert await run_sync(connection, first) == {
        "inserted": 14,
        "updated": 0,
        "unchanged": 0,
    }

    def again(s):
        counts = upsert(s, found, run_id, NOW)
        s.flush()
        return counts

    assert await run_sync(connection, again) == {
        "inserted": 0,
        "updated": 0,
        "unchanged": 14,
    }

    # Eurostat revises September's figure: updated, flagged.
    from dataclasses import replace

    revised = [
        (
            replace(o, value=D("5.700000"))
            if (o.geo_code, o.category, o.period) == ("BG", "TOTAL", "2026-09")
            else o
        )
        for o in found
    ]

    def revise(s):
        counts = upsert(s, revised, run_id, NOW)
        s.flush()
        row = s.scalar(
            select(RegionalObservation).where(
                RegionalObservation.series_key == "M.RCH_A.TOTAL.BG",
                RegionalObservation.period == "2026-09",
            )
        )
        return counts, row.value, row.quality_flags

    counts, value, flags = await run_sync(connection, revise)
    assert counts == {"inserted": 0, "updated": 1, "unchanged": 13}
    assert value == D("5.700000") and flags == ["revised"]


async def test_a_re_denominated_level_is_flagged_as_a_break(connection):
    """BGN → EUR divides a level by 1.95583 (a 48.9 % move): a break, not a
    revision to trust silently."""
    shares, _ = eurostat.parse(
        catalog.HBS, load("eurostat_hbs_str_t211.json"), "https://example/hbs"
    )
    run_id = uuid.uuid4()
    from dataclasses import replace

    def go(s):
        s.add(
            RegionalIngestionRun(
                id=run_id,
                provider="eurostat",
                dataset="hbs_str_t211",
                started_at=NOW,
                status="running",
            )
        )
        s.flush()
        upsert(s, shares, run_id, NOW)
        converted = [
            replace(o, value=(o.value / D("1.95583")).quantize(D("0.000001")))
            for o in shares
        ]
        upsert(s, converted, run_id, NOW)
        s.flush()
        return {
            tuple(r.quality_flags)
            for r in s.scalars(
                select(RegionalObservation).where(
                    RegionalObservation.dataset == "hbs_str_t211"
                )
            )
        }

    assert await run_sync(connection, go) == {("break_suspected", "revised")}


async def test_a_failed_provider_leaves_stored_values_untouched(connection):
    found, _ = worldbank.parse(
        catalog.WB_INFLATION,
        load("worldbank_fp_cpi_totl_zg.json"),
        "https://example/wb",
    )

    def seed(s):
        run_id = uuid.uuid4()
        s.add(
            RegionalIngestionRun(
                id=run_id,
                provider="worldbank",
                dataset="FP.CPI.TOTL.ZG",
                started_at=NOW,
                status="succeeded",
            )
        )
        s.flush()
        upsert(s, found, run_id, NOW)
        s.flush()

    await run_sync(connection, seed)
    client, calls = replay([(503, "down")])
    fetcher = Fetcher(client=client, sleep=lambda s: None, clock=lambda: 0.0)

    def failing(s):
        result = run_dataset(
            lambda: _NestedSession(s), fetcher, catalog.WB_INFLATION, now=NOW
        )
        stored = s.scalars(
            select(RegionalObservation.value).where(
                RegionalObservation.dataset == "FP.CPI.TOTL.ZG"
            )
        ).all()
        run = s.scalar(
            select(RegionalIngestionRun)
            .where(RegionalIngestionRun.dataset == "FP.CPI.TOTL.ZG")
            .order_by(
                RegionalIngestionRun.started_at.desc(), RegionalIngestionRun.status
            )
            .limit(1)
        )
        return result, sorted(stored), run.status

    result, stored, _status = await run_sync(connection, failing)
    assert result.status == "failed" and result.error_class == "ProviderError"
    assert result.requests == 4
    assert stored == sorted(o.value for o in found)  # the last good values


class _NestedSession:
    """``with session_factory() as s`` on one shared Session: commits become
    flushes, so the test's outer transaction still rolls everything back."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, obj):
        self.session.add(obj)

    def get(self, *args):
        return self.session.get(*args)

    def scalars(self, *args):
        return self.session.scalars(*args)

    def commit(self):
        self.session.flush()


def test_the_regional_tables_hold_no_user_column():
    for model in (RegionalObservation, RegionalIngestionRun):
        columns = {c.name for c in model.__table__.columns}
        assert not {c for c in columns if "user" in c or "email" in c}, columns


async def test_the_schema_refuses_an_amount_without_its_currency(connection):
    from sqlalchemy.exc import IntegrityError

    nested = await connection.begin_nested()
    with pytest.raises(IntegrityError):
        await connection.execute(
            text(
                "INSERT INTO regional_observations (provider, dataset, series_key, "
                "indicator, geo_level, geo_code, period, period_type, period_start, "
                "value, unit_kind, unit, retrieved_at, source_url, transformation, "
                "license) VALUES ('oecd', 'd', 's', 'i', 'country', 'US', '2026', "
                "'year', '2026-01-01', 1, 'currency_amount', 'x', now(), 'u', "
                "'none', 'l')"
            )
        )
    await nested.rollback()


def test_since_period_bounds_the_request():
    from app.regional.ingest import since_period

    assert since_period(catalog.HICP, date(2026, 11, 4)) == "2025-09"
    assert since_period(catalog.PLI, date(2026, 11, 4)) == "2022"
    assert since_period(catalog.HBS, date(2026, 11, 4)) == "2015"

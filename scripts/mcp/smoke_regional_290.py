#!/usr/bin/env python3
"""MITA 2.9 smoke test (regional recommendations) against a RUNNING MCP
service.

    python scripts/mcp/smoke_regional_290.py --base-url https://<staging-host> \\
        [--database-url postgresql://...]   # clean-up of the accounts it creates

Through the public endpoints, with NEW fictional accounts (never the owner's).
Run it after the ingestion job filled the target with this release's
Eurostat inputs:

* ``/health`` reports 2.9.0, the same 26 tools are published, and no tool
  takes a city, an address or coordinates;
* a person in Bulgaria on €1,000 (household of one) gets MITA's own
  groceries line unchanged and, beside it, the national reference: about 152
  a month, in EUR, low confidence, 2020 survey at 2025 prices, with its
  inputs. Fuel is for households that buy it. Dining out has no figure and
  says why;
* the user's own Fuel €200 stays 200.00, its reference only beside it;
  turning statistics off gives the same plan to the cent; the saved plan is
  the previewed one;
* a household of four gets a range, never four times one adult;
* a person in the United States gets no reference ("not_covered"), never a
  converted one; a dollar budget in Bulgaria gets none either;
* the preview says MITA has no verified local price; the Varna and Sofia
  hints change nothing and appear nowhere.

Prints PASS/FAIL names only (no tokens, codes, passwords). Refuses
production hosts (scripts/_target_guard.py). With --database-url it deletes
every account it created with ``e2e_v2.cleanup``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import uuid
from pathlib import Path
from typing import Optional

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402
from e2e_v2 import PASSED, Session, check, cleanup, connect  # noqa: E402

VERSION = "2.9.0"


def hint(city: str) -> dict:
    return {"country": "BG", "city": city, "timezone": "Europe/Sofia"}


async def call(s: Session, tool: str, args=None, *, location=None, ok: bool = True):
    meta = {"openai/session": s.conversation}
    if location is not None:
        meta["openai/userLocation"] = location
    result = await s._client.call_tool(tool, args or {}, meta=meta)
    if ok:
        check(f"{tool} succeeds", not result.is_error, str(result.content)[:300])
        return result.structured_content
    return result


def lines(draft) -> dict:
    return {a["category"]: a for a in draft["category_allocations"]}


def amounts(draft):
    return [(a["category"], a["amount"]) for a in draft["category_allocations"]]


async def profile(s: Session, country: str, currency: str, income, household=1):
    await call(
        s,
        "update_financial_profile",
        {
            "monthly_net_income": income,
            "currency": currency,
            "timezone": "Europe/Sofia" if country == "BG" else "America/New_York",
            "household_size": household,
            "country": country,
        },
    )


async def bulgaria(s: Session):
    await profile(s, "BG", "EUR", 1000)
    draft = await call(s, "preview_monthly_budget", location=hint("Varna"))
    by_line = lines(draft)
    groceries = by_line.get("groceries") or {}
    rec = groceries.get("recommendation") or {}
    ref = rec.get("regional_reference") or {}
    check(
        "Bulgaria €1,000: MITA's groceries line is unchanged (78.00)",
        groceries.get("amount") == "78.00",
        str(groceries.get("amount")),
    )
    check(
        "the national reference beside it: 152 a month for one adult, in EUR",
        rec.get("basis") == "regional_statistics"
        and rec.get("amount") == "152.00"
        and ref.get("currency") == "EUR"
        and ref.get("per_adult_monthly") == "152.00",
        json.dumps(rec)[:300],
    )
    check(
        "with its method, inputs, years and low confidence",
        ref.get("confidence") == "low"
        and (ref.get("survey_year"), ref.get("price_year")) == (2020, 2025)
        and (ref.get("inputs") or {}).get("yearly_per_adult") == "4775"
        and ref.get("geographic_scope") == "country"
        and ref.get("source", "").startswith("Source: Eurostat"),
    )
    fuel = (by_line.get("transport gas") or {}).get("recommendation") or {}
    check(
        "fuel: for households that buy it",
        (fuel.get("regional_reference") or {}).get("households")
        == "households_that_buy_it",
    )
    dining = (by_line.get("dining out") or {}).get("recommendation") or {}
    check(
        "dining out: no figure, and why",
        dining.get("regional_reference") is None
        and dining.get("regional_reason") == "participation_varies",
    )
    summary = draft.get("recommendations") or {}
    check(
        "MITA says it has no verified local price",
        summary.get("verified_local_prices") == "none",
    )
    check(
        "the city hint appears nowhere", "Varna" not in json.dumps(draft), "Varna found"
    )
    sofia = await call(s, "preview_monthly_budget", location=hint("Sofia"))
    check(
        "Varna and Sofia give the same recommendations",
        {k: v["recommendation"] for k, v in lines(sofia).items()}
        == {k: v["recommendation"] for k, v in by_line.items()},
    )

    own = {
        "budget_lines": [
            {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}
        ]
    }
    with_stats = await call(s, "preview_monthly_budget", own)
    mine = lines(with_stats).get("my:Fuel") or {}
    check(
        "the user's Fuel €200 stays exactly, the reference only beside it",
        mine.get("amount") == "200.00"
        and (mine.get("recommendation") or {}).get("basis") == "user_amount",
    )
    await call(s, "update_financial_profile", {"regional_comparisons": False})
    without = await call(s, "preview_monthly_budget", own)
    check(
        "statistics off: the same plan to the cent",
        amounts(without) == amounts(with_stats)
        and without["plan_total"] == with_stats["plan_total"],
    )
    await call(s, "update_financial_profile", {"regional_comparisons": True})
    again = await call(s, "preview_monthly_budget", own)
    saved = await call(s, "save_monthly_budget", {"draft_token": again["draft_token"]})
    check("the reviewed plan saves", saved.get("status") == "saved")
    context = await call(s, "get_regional_context", {"topic": "household_spending"})
    categories = {r["category"] for r in context.get("spending_references") or []}
    check(
        "get_regional_context lists the four references",
        categories == {"food", "clothing", "household_energy", "fuel"},
        str(sorted(categories)),
    )
    check(
        "the inputs are never listed as statistics",
        {x["indicator"] for x in context["statistics"]} == {"household_spending_share"},
    )


async def family(s: Session):
    await profile(s, "BG", "EUR", 3000, household=4)
    draft = await call(s, "preview_monthly_budget")
    rec = (lines(draft).get("groceries") or {}).get("recommendation") or {}
    check(
        "a household of four: a range (289–380), never four times one adult",
        (rec.get("amount"), rec.get("low"), rec.get("high"))
        == (None, "289.00", "380.00"),
        json.dumps(rec)[:200],
    )
    await call(s, "update_financial_profile", {"currency": "USD"})
    dollars = await call(s, "preview_monthly_budget")
    ref = ((lines(dollars).get("groceries") or {}).get("recommendation") or {}).get(
        "regional_reference"
    ) or {}
    check(
        "a dollar budget in Bulgaria: no figure, never converted",
        ref.get("reason") == "currency_mismatch"
        and ref.get("per_adult_monthly") is None,
    )


async def united_states(s: Session):
    await profile(s, "US", "USD", 1000)
    draft = await call(s, "preview_monthly_budget")
    rec = (lines(draft).get("groceries") or {}).get("recommendation") or {}
    ref = rec.get("regional_reference") or {}
    check(
        "the US: MITA's own line, no household-spending reference",
        rec.get("basis") == "mita_default" and ref.get("reason") == "not_covered",
        json.dumps(rec)[:200],
    )


async def run(base: str, database_url: Optional[str]) -> None:
    emails = [f"rg290-{uuid.uuid4().hex[:10]}@example.test" for _ in range(3)]
    password = "S290-" + secrets.token_urlsafe(14) + "!"
    try:
        async with httpx2.AsyncClient(timeout=30) as http:
            health = (await http.get(f"{base}/health")).json()
        check(
            f"/health reports {VERSION}", health.get("version") == VERSION, str(health)
        )
        for index, (email, scenario) in enumerate(
            zip(emails, (bulgaria, family, united_states))
        ):
            grant = await connect(base, email, password, register=True)
            async with Session(base, grant["access"], f"smoke-290-{index}") as s:
                if index == 0:
                    listed = (await s._client.list_tools()).tools
                    check("26 tools are published", len(listed) == 26, str(len(listed)))
                    fields = {
                        name
                        for tool in listed
                        for name in (tool.input_schema.get("properties") or {})
                    }
                    check(
                        "no tool takes a city, address or coordinates",
                        not fields
                        & {"city", "address", "latitude", "longitude", "location"},
                    )
                await scenario(s)
    finally:
        if database_url:
            for email in emails:
                cleanup(database_url, email)
    print(f"{len(PASSED)} checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url")
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp smoke 2.9.0")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(run(base, args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())

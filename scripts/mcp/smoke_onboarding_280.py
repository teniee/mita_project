#!/usr/bin/env python3
"""MITA 2.8 smoke test (personalized onboarding) against a RUNNING MCP service.

    python scripts/mcp/smoke_onboarding_280.py --base-url https://<staging-host> \\
        [--database-url postgresql://...]   # clean-up of the accounts it creates

Through the public endpoints, with two NEW fictional accounts (never the
owner's), so a missing 0043 grant (``mcp_setup_answers``, ``users.country``)
or a broken migration shows up before a person sees it:

* ``/health`` reports 2.8.0; the published tools are the 25 of 2.7.0, and
  ``update_financial_profile`` takes a country but no city, address or
  coordinates;
* ChatGPT's approximate location (``openai/userLocation``) is only a
  suggestion: nothing is stored by reading, the confirmed country is stored
  with its source, a "skip" clears it;
* a commuter in Sofia (no car, rent) and a family in Varna (car, mortgage,
  variable income) get different budgets: no fuel line for the first, no rent
  for either, the lines they never mentioned listed with MITA's suggestion,
  every euro accounted for, a month at the minimum income shown;
* a preview saves nothing; a save needs the draft; setup survives a new
  connection; the other account sees none of it;
* ``get_regional_context`` (0044): Bulgarian statistics from Eurostat for a
  user in Bulgaria, OECD and World Bank — never Eurostat — for one in the
  United States, every figure with its source and period; nothing without a
  country. ``--expect-statistics`` requires figures (run it after the
  ingestion job filled the target).

Prints PASS/FAIL names only (no tokens, codes, passwords). Refuses
production hosts (scripts/_target_guard.py). With --database-url it deletes
both accounts with ``e2e_v2.cleanup``.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Optional

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402
from e2e_v2 import PASSED, Session, check, cleanup, connect  # noqa: E402

D = Decimal
VERSION = "2.8.0"
SOFIA = {
    "city": "Sofia",
    "region": "Sofia City",
    "country": "BG",
    "timezone": "Europe/Sofia",
    "latitude": "42.6977",
    "longitude": "23.3219",
}


def key() -> str:
    return uuid.uuid4().hex


async def call(s: Session, tool: str, args=None, *, hint=None, ok: bool = True):
    """A tool call with ChatGPT's request _meta (and, when given, the coarse
    location hint ChatGPT may send)."""
    meta = {"openai/session": s.conversation}
    if hint is not None:
        meta["openai/userLocation"] = hint
    result = await s._client.call_tool(tool, args or {}, meta=meta)
    if ok:
        check(f"{tool} succeeds", not result.is_error, str(result.content)[:300])
        return result.structured_content
    return result


async def recurring(s: Session, name, amount, category, day):
    saved = await call(
        s,
        "add_recurring_expense",
        {
            "name": name,
            "amount": amount,
            "category": category,
            "recurrence": "monthly",
            "day_of_month": day,
            "idempotency_key": key(),
        },
    )
    check(f"{name} saved", saved["status"] == "created")


def accounted(draft) -> bool:
    total = (
        D(draft["fixed_obligations_total"])
        + D(draft["savings_allocation"])
        + sum(D(x["amount"]) for x in draft["category_allocations"])
        + D(draft["unallocated"])
    )
    return total == D(draft["stated_monthly_income"])


async def commuter(s: Session):
    """Sofia, no car, takes the bus, rents."""
    status = await call(s, "get_setup_status", hint=SOFIA)
    check(
        "a new account: not started, ChatGPT's country only as a suggestion",
        status["onboarding"]["stage"] == "not_started"
        and status["region"]["country"] is None
        and (status["region"]["suggestion"] or {}).get("country") == "BG",
        str(status["region"]),
    )
    check(
        "nothing but the country leaves the hint",
        not any(x in repr(status) for x in ("42.69", "23.32", "Sofia City")),
    )
    result = await call(
        s,
        "update_financial_profile",
        {
            "monthly_net_income": 1500,
            "currency": "EUR",
            "timezone": "Europe/Sofia",
            "household_size": 1,
            "monthly_savings_target": 100,
            "country": "BG",
            "income_regularity": "regular",
            "pay_frequency": "monthly",
            "pay_days": [25],
        },
        hint=SOFIA,
    )
    check(
        "the confirmed country is stored with its source",
        result["region"]["country"] == "BG"
        and result["region"]["source"] == "chatgpt_location_confirmed",
        str(result["region"]),
    )
    await recurring(s, "Rent", 600, "rent", 1)
    await recurring(s, "Phone", 15, "utilities", 20)
    await call(
        s,
        "save_spending_patterns",
        {
            "patterns": [
                {
                    "line": "Groceries",
                    "kind": "planned",
                    "frequency": "weekly",
                    "weekdays": ["saturday"],
                },
                {"line": "dining out", "kind": "flexible"},
            ]
        },
    )
    before = await call(
        s,
        "preview_monthly_budget",
        {"budget_lines": [{"label": "Groceries", "amount": 250}]},
    )
    check(
        "before 'that is everything': MITA's lines are suggestions",
        before["personalization"]["level"] == "preliminary"
        and any(
            x["line_status"] == "mita_suggested" for x in before["category_allocations"]
        ),
    )
    result = await call(
        s,
        "update_financial_profile",
        {"setup_answers": [{"topic": "everyday_spending", "answer": "described"}]},
    )
    check(
        "setup answers are stored (mcp_setup_answers grant)",
        result["onboarding"]["stage"] == "ready_for_personalized_budget",
        result["onboarding"]["stage"],
    )
    return [
        {"label": "Groceries", "amount": 250, "replaces": ["groceries"]},
        {"label": "Public transport", "amount": 26, "replaces": ["transport public"]},
    ]


async def family(s: Session):
    """Varna, drives, mortgage, family of three, income that varies."""
    await call(
        s,
        "update_financial_profile",
        {
            "monthly_net_income": 3000,
            "currency": "EUR",
            "timezone": "Europe/Sofia",
            "household_size": 3,
            "monthly_savings_target": 300,
            "country": "BG",
            "income_regularity": "variable",
            "minimum_monthly_income": 2400,
        },
    )
    await recurring(s, "Mortgage", 450, "mortgage", 5)
    await recurring(s, "Electricity and water", 120, "utilities", 15)
    await call(
        s,
        "save_spending_patterns",
        {
            "patterns": [
                {"line": "Fuel", "kind": "planned", "frequency": "weekly"},
                {"line": "clothing", "kind": "flexible"},
                {"line": "transport public", "kind": "not_applicable"},
            ]
        },
    )
    await call(
        s,
        "update_financial_profile",
        {"setup_answers": [{"topic": "everyday_spending", "answer": "described"}]},
    )
    return [
        {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]},
        {"label": "Groceries", "amount": 500, "replaces": ["groceries"]},
        {"label": "Kids activities", "amount": 80},
    ]


async def regional(s: Session, country: str, expect: bool):
    result = await call(s, "get_regional_context")
    stats = result["statistics"]
    if not expect and result["status"] == "unavailable":
        check(f"{country}: no figures yet, said honestly", stats == [])
        return
    check(
        f"{country}: official statistics for the user's country",
        result["status"] == "available" and result["country"] == country and stats,
        result["status"],
    )
    providers = {x["provider"] for x in stats}
    if country == "US":
        check("never Eurostat for the US (its licence)", "eurostat" not in providers)
    else:
        check("Eurostat for an EU country", "eurostat" in providers, str(providers))
        prices = await call(s, "get_regional_context", {"topic": "prices"})
        power = [x for x in prices["statistics"] if x["category"] == "electricity"]
        check(
            f"{country}: the electricity price households pay, in EUR per kWh",
            len(power) == 1
            and power[0]["currency"] == "EUR"
            and power[0]["unit_kind"] == "currency_amount"
            and "per kWh" in power[0]["unit"],
            str(power)[:200],
        )
    check(
        "every figure has its source, period, unit and limitation",
        all(
            x["source"]
            and x["period"]
            and x["unit"]
            and x["limitation"]
            and x["source_url"].startswith("https://")
            for x in stats
        ),
    )


async def run(base: str, database_url: Optional[str], expect: bool = False) -> None:
    emails = [f"ob280-{uuid.uuid4().hex[:10]}@example.test" for _ in range(2)]
    password = "S280-" + secrets.token_urlsafe(14) + "!"
    try:
        async with httpx2.AsyncClient(timeout=30) as http:
            health = (await http.get(f"{base}/health")).json()
        check(
            f"/health reports {VERSION}", health.get("version") == VERSION, str(health)
        )

        first = await connect(base, emails[0], password, register=True)
        async with Session(base, first["access"], "smoke-280-1") as a:
            listed = (await a._client.list_tools()).tools
            check("26 tools are published", len(listed) == 26, str(len(listed)))
            profile_tool = next(
                t for t in listed if t.name == "update_financial_profile"
            )
            fields = set(profile_tool.input_schema["properties"])
            check(
                "a country, never a city, address or coordinates",
                "country" in fields
                and not fields
                & {"city", "address", "latitude", "longitude", "location", "region"},
                str(sorted(fields)),
            )
            a_lines = await commuter(a)
            a_draft = await call(a, "preview_monthly_budget", {"budget_lines": a_lines})
            a_codes = {x["category"] for x in a_draft["category_allocations"]}
            check(
                "the commuter's budget is personalized, every euro accounted for",
                a_draft["personalization"]["level"] == "personalized"
                and accounted(a_draft),
            )
            check(
                "no fuel line for someone without a car; it is listed as a question",
                "transport gas" not in a_codes
                and "transport gas" in {x["category"] for x in a_draft["not_included"]},
                str(sorted(a_codes)),
            )
            calendar = await call(a, "get_calendar_month")
            check(
                "a preview saved nothing",
                calendar["plan_status"] == "not_generated",
                calendar["plan_status"],
            )
            saved = await call(
                a, "save_monthly_budget", {"draft_token": a_draft["draft_token"]}
            )
            check(
                "the reviewed plan is saved after the yes", saved["status"] == "saved"
            )
            await regional(a, "BG", expect)

        again = await connect(base, emails[0], password, register=False)
        async with Session(base, again["access"], "smoke-280-1b") as a2:
            status = await call(a2, "get_setup_status", hint=SOFIA)
            check(
                "a new connection: a returning user, never asked again",
                status["onboarding"]["stage"] == "established"
                and status["onboarding"]["next_questions"] == []
                and status["region"]["country"] == "BG",
                status["onboarding"]["stage"],
            )

        second = await connect(base, emails[1], password, register=True)
        async with Session(base, second["access"], "smoke-280-2") as b:
            theirs = await call(b, "get_setup_status")
            check(
                "the other account sees none of the first one's setup",
                theirs["onboarding"]["stage"] == "not_started"
                and theirs["region"]["country"] is None,
            )
            b_lines = await family(b)
            b_draft = await call(b, "preview_monthly_budget", {"budget_lines": b_lines})
            b_codes = {x["category"] for x in b_draft["category_allocations"]}
            check(
                "two people, two budgets",
                b_codes != a_codes and b_draft["plan_total"] != a_draft["plan_total"],
                f"{sorted(a_codes)} vs {sorted(b_codes)}",
            )
            check(
                "no rent for a family that pays a mortgage",
                "rent" not in b_codes
                and {o["category"] for o in b_draft["fixed_obligations"]}
                == {"mortgage", "utilities"},
            )
            vi = b_draft["variable_income"] or {}
            check(
                "income that varies: a month at the minimum is shown",
                vi.get("minimum_monthly_income") == "2400.00"
                and vi.get("planned_on") == "3000.00",
                str(vi),
            )
            check(
                "fuel about once a week: dates proposed, and said so",
                all(
                    p["proposed"]
                    for x in b_draft["category_allocations"]
                    if x["category"] == "my:Fuel"
                    for p in x["purchases"]
                ),
            )
            skipped = await call(
                b,
                "update_financial_profile",
                {"setup_answers": [{"topic": "region", "answer": "skipped"}]},
            )
            check(
                "'I prefer not to say' clears the country (users.country grant)",
                skipped["region"]["country"] is None,
            )
            refused = await call(
                b, "update_financial_profile", {"city": "Varna"}, ok=False
            )
            check("a city argument is refused", refused.is_error)
            await call(b, "update_financial_profile", {"country": "US"})
            await regional(b, "US", expect)
            await call(
                b,
                "update_financial_profile",
                {"setup_answers": [{"topic": "region", "answer": "skipped"}]},
            )
            none = await call(b, "get_regional_context")
            check(
                "no country, no statistics",
                none["status"] == "no_country" and none["statistics"] == [],
            )
    finally:
        if database_url:
            for email in emails:
                cleanup(database_url, email)
    print(f"{len(PASSED)} checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url")
    parser.add_argument(
        "--expect-statistics",
        action="store_true",
        help="require regional figures (after the ingestion job ran)",
    )
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp smoke 2.8.0")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(run(base, args.database_url, args.expect_statistics))
    return 0


if __name__ == "__main__":
    sys.exit(main())

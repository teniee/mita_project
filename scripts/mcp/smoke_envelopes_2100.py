#!/usr/bin/env python3
"""MITA 2.10.0 smoke test against a RUNNING MCP service, over real HTTP.

    python scripts/mcp/smoke_envelopes_2100.py --base-url https://<staging-host> \\
        [--database-url postgresql://...]   # clean-up of the account it creates

A budget is not a schedule (docs/chatgpt-app/flexible-envelopes-calendar.md):
through the public endpoints, with ONE new fictional account, the brief's
month in the current month — income 1,985, savings 500, a car loan of 270 on
the 15th, a laptop loan of 70 on the 25th, own lines Groceries 320, Car
maintenance 200, Entertainment 100, Restaurants 100, Coffee 45, and 380 left
unallocated:

* ``/health`` reports 2.10.0; ``show_financial_calendar`` points at the v4
  component and the served component is this checkout's file;
* with nothing said about when the user buys, every line is a flexible
  budget and is on NO date: no planned purchase, nothing scheduled but the
  loans, every date ahead ``free``, and the component's month payload
  (version 2) carries no flexible line on any date;
* a real 40.00 restaurant expense is on its date only, leaves 60.00 and a
  daily guidance, and is not over;
* "a coffee every day" then IS a schedule: one purchase a date, adding up to
  45.00 exactly, the same in the data and in the component's payload;
* the user's amounts, the savings and the unallocated 380.00 are unchanged
  throughout.

Prints PASS/FAIL names only (no tokens, codes, passwords). Refuses
production hosts (scripts/_target_guard.py). With --database-url it deletes
the account with ``e2e_v2.cleanup``; without it the account stays (name it
in staging.md → "Left on staging").
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import secrets
import sys
import uuid
from calendar import monthrange
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402
from e2e_v2 import PASSED, Session, check, cleanup, connect  # noqa: E402

VERSION = "2.10.0"
COMPONENT = "ui://mita/financial-calendar-v4.html"
COMPONENT_FILE = (
    Path(__file__).resolve().parents[2] / "app/mcp/ui/financial_calendar.html"
)
D = Decimal
ZERO = D("0.00")
LINES = [
    {"label": "Groceries", "amount": 320},
    {"label": "Car maintenance", "amount": 200},
    {"label": "Entertainment", "amount": 100},
    {"label": "Restaurants", "amount": 100},
    {"label": "Coffee", "amount": 45},
]
OWN = {f"my:{line['label']}": D(str(line["amount"])) for line in LINES}
COFFEE = "my:Coffee"
RESTAURANTS = "my:Restaurants"


def key() -> str:
    return uuid.uuid4().hex


async def month(s: Session):
    """The current month as data and as the component gets it."""
    result = await s.call("get_calendar_month", ok=False)
    check("get_calendar_month succeeds", not result.is_error, str(result.content)[:300])
    payload = (result.meta or {}).get("mita/calendar") or {}
    return result.structured_content, payload


def lines_of(cal: dict) -> dict:
    return {c["category"]: c for c in cal["categories"]}


def day_lines(payload: dict) -> dict:
    """``{date: {line: (scheduled, spent)}}`` of the component's payload."""
    return {
        iso: {entry[0]: (entry[1], entry[2]) for entry in entries}
        for iso, entries in (payload.get("day_lines") or {}).items()
    }


async def run(base: str, database_url: Optional[str]) -> None:
    email = f"cal210-{uuid.uuid4().hex[:10]}@example.test"
    password = "S210-" + secrets.token_urlsafe(14) + "!"
    try:
        async with httpx2.AsyncClient(base_url=base, timeout=30) as http:
            health = (await http.get("/health")).json()
        check(
            f"/health reports {VERSION}", health.get("version") == VERSION, str(health)
        )
        tokens = await connect(base, email, password, register=True)
        async with Session(base, tokens["access"], "smoke-2100") as s:
            listed = await s._client.list_tools()
            tools = {t.name: t for t in listed.tools}
            meta = tools["show_financial_calendar"].meta or {}
            check(
                "show_financial_calendar points at the v4 component",
                (meta.get("ui") or {}).get("resourceUri") == COMPONENT
                and meta.get("openai/outputTemplate") == COMPONENT,
                str(meta)[:200],
            )
            served = await s._client.read_resource(COMPONENT)
            html = served.contents[0].text
            check(
                "the served component is this checkout's file",
                hashlib.sha256(html.encode()).hexdigest()
                == hashlib.sha256(COMPONENT_FILE.read_bytes()).hexdigest(),
            )
            check(
                "the component draws no daily guide and takes payload version 2",
                "≈" not in html and "var PAYLOAD_VERSION = 2;" in html,
            )
            description = tools["get_calendar_month"].description or ""
            check(
                "the data tool says a flexible budget is on no date",
                "A flexible budget is a monthly limit with no dates" in description
                and "the flexible budgets' daily share" not in description,
            )

            await s.call(
                "update_financial_profile",
                {
                    "monthly_net_income": 1985,
                    "currency": "EUR",
                    "timezone": "Europe/Sofia",
                    "household_size": 1,
                    "monthly_savings_target": 500,
                    "setup_answers": [
                        {"topic": "everyday_spending", "answer": "described"}
                    ],
                },
            )
            for name, amount, category, day in (
                ("Car loan", 270, "transportation", 15),
                ("Laptop loan", 70, "other", 25),
            ):
                saved = await s.call(
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
            status = await s.call("get_setup_status")
            year, mon = map(int, status["current_month"].split("-"))
            days_in_month = monthrange(year, mon)[1]

            # --- 1. nothing said about when: monthly limits, on no date -----
            draft = await s.call(
                "preview_monthly_budget",
                {"month": status["current_month"], "budget_lines": LINES},
            )
            own = {
                a["category"]: a
                for a in draft["category_allocations"]
                if a["category"] in OWN
            }
            check(
                "the user's five amounts are kept exactly, as flexible budgets",
                {k: D(v["amount"]) for k, v in own.items()} == OWN
                and all(v["spending_type"] == "flexible" for v in own.values()),
                str({k: (v["amount"], v["spending_type"]) for k, v in own.items()}),
            )
            check(
                "380.00 stays unallocated; savings 500.00",
                draft["unallocated"] == "380.00"
                and draft["savings_allocation"] == "500.00",
                f"{draft['unallocated']} {draft['savings_allocation']}",
            )
            saved = await s.call(
                "save_monthly_budget", {"draft_token": draft["draft_token"]}
            )
            check("the budget is saved", saved["status"] == "saved")

            cal, payload = await month(s)
            today = cal["today"]
            lines = lines_of(cal)
            by_date = day_lines(payload)
            check(
                "the component payload is version 2",
                payload.get("version") == 2 and payload.get("month") == cal,
                str(payload.get("version")),
            )
            check(
                "each budget shows its month: amount, spent 0.00, all of it left",
                all(
                    (D(lines[k]["planned"]), lines[k]["spent"]) == (amount, "0.00")
                    and D(lines[k]["remaining"]) == amount
                    and lines[k]["spending_type"] == "flexible"
                    and lines[k]["purchases"] == []
                    for k, amount in OWN.items()
                ),
            )
            check(
                "no flexible budget is on any date the component draws",
                not any(k in entries for entries in by_date.values() for k in OWN),
                str(sorted({k for e in by_date.values() for k in e if k in OWN})),
            )
            check(
                "no planned purchase on any date",
                all(d["purchases"] == [] for d in cal["days"]),
            )
            scheduled = {
                d["date"]: D(d["planned_scheduled"])
                for d in cal["days"]
                if D(d["planned_scheduled"]) > 0
            }
            check(
                "only the two loans are scheduled: 270.00 on the 15th, 70.00 on the 25th",
                {iso[-2:]: amount for iso, amount in scheduled.items()}
                == {"15": D("270.00"), "25": D("70.00")},
                str(scheduled),
            )
            ahead = [d for d in cal["days"] if d["day_kind"] == "future"]
            check(
                "every date ahead is free: a monthly budget plans no date",
                all(d["state"] == "free" for d in ahead),
                str({d["date"]: d["state"] for d in ahead if d["state"] != "free"}),
            )
            check(
                "the stored rows are bookkeeping: scheduled + flexible share",
                all(
                    D(d["planned"])
                    == D(d["planned_scheduled"]) + D(d["planned_flexible"])
                    for d in cal["days"]
                )
                and sum(D(d["planned_flexible"]) for d in cal["days"])
                == sum(OWN.values(), ZERO),
            )
            summary = cal["summary"]
            check(
                "scheduled ahead counts the loans only; the budgets are flexible_left",
                D(summary["scheduled_after_today"])
                == sum((D(d["planned_scheduled"]) for d in ahead), ZERO)
                and D(summary["flexible_left"]) == sum(OWN.values(), ZERO),
                f"{summary['scheduled_after_today']} {summary['flexible_left']}",
            )
            check(
                "the plan leaves 380.00 with no line",
                D("1985.00") - D(summary["total_planned"]) == D("380.00")
                and summary["savings_set_aside"] == "500.00",
                summary["total_planned"],
            )

            # --- 2. a real expense: on its date, once ------------------------
            spent = await s.call(
                "add_transaction",
                {
                    "amount": "40.00",
                    "budget_line": "Restaurants",
                    "idempotency_key": key(),
                },
            )
            check("the restaurant expense is recorded", spent["status"] == "recorded")
            cal, payload = await month(s)
            lines = lines_of(cal)
            by_date = day_lines(payload)
            restaurants = lines[RESTAURANTS]
            days_left = sum(1 for d in cal["days"] if d["date"] >= today)
            guidance = (D("60.00") / days_left).quantize(D("0.01"), ROUND_HALF_UP)
            check(
                "40.00 of 100.00 spent, 60.00 left, guidance = 60.00 / days left",
                (restaurants["spent"], restaurants["remaining"]) == ("40.00", "60.00")
                and D(restaurants["left_per_day"]) == guidance,
                f"{restaurants['remaining']} {restaurants['left_per_day']} {guidance}",
            )
            check(
                "the expense is on today only, with nothing scheduled beside it",
                by_date.get(today, {}).get(RESTAURANTS) == ("0.00", "40.00")
                and not any(
                    RESTAURANTS in entries
                    for iso, entries in by_date.items()
                    if iso != today
                ),
            )
            day = next(d for d in cal["days"] if d["date"] == today)
            check(
                "spending inside a monthly limit is not over, and not 'within' a plan",
                day["state"] == "unplanned" and day["everyday_left"] is None,
                f"{day['state']} {day['everyday_left']}",
            )
            check(
                "the month's spending is that one expense",
                cal["summary"]["total_spent"] == "40.00"
                and sum(D(d["spent"]) for d in cal["days"] if d["spent"]) == D("40.00"),
            )

            # --- 3. "a coffee every day" is a schedule -------------------------
            draft = await s.call(
                "preview_monthly_budget",
                {
                    "month": status["current_month"],
                    "budget_lines": LINES,
                    "spending_patterns": [
                        {
                            "line": "Coffee",
                            "kind": "planned",
                            "frequency": "daily",
                            "typical_amount": "1.50",
                        }
                    ],
                },
            )
            check(
                "still 380.00 unallocated with the pattern",
                draft["unallocated"] == "380.00",
                draft["unallocated"],
            )
            await s.call("save_monthly_budget", {"draft_token": draft["draft_token"]})
            cal, payload = await month(s)
            lines = lines_of(cal)
            by_date = day_lines(payload)
            coffee = lines[COFFEE]
            check(
                "coffee is a planned purchase on every date, 45.00 exactly",
                coffee["spending_type"] == "planned"
                and coffee["pattern"] == "every day"
                and len(coffee["purchases"]) == days_in_month
                and sum(D(p["planned"]) for p in coffee["purchases"]) == D("45.00"),
                f"{coffee['spending_type']} {len(coffee['purchases'])}",
            )
            check(
                "one coffee a date, the same amount in the data and the payload",
                all(
                    [p["category"] for p in d["purchases"]] == [COFFEE]
                    and by_date[d["date"]][COFFEE][0] == d["purchases"][0]["planned"]
                    and D(d["planned_scheduled_everyday"])
                    == D(d["purchases"][0]["planned"])
                    for d in cal["days"]
                ),
            )
            check(
                "the other budgets are still on no date beside it",
                not any(
                    k in entries and D(entries[k][0]) > 0
                    for entries in by_date.values()
                    for k in OWN
                    if k != COFFEE
                )
                and lines[RESTAURANTS]["remaining"] == "60.00",
            )
            check(
                "all categories on a date = the lines one by one",
                all(
                    sum(
                        (
                            D(s_)
                            for k, (s_, _spent) in by_date.get(d["date"], {}).items()
                            if lines[k]["group"] != "set_aside"
                        ),
                        ZERO,
                    )
                    == D(d["planned_scheduled"])
                    for d in cal["days"]
                ),
            )

            shown = await s.call(
                "show_financial_calendar", {"category": "Restaurants"}, ok=False
            )
            text = shown.content[0].text if shown.content else ""
            check(
                "the calendar opens filtered, and its text names no per-date share",
                not shown.is_error
                and shown.structured_content["category"] == RESTAURANTS
                and "monthly limits with no dates" in text
                and (shown.meta or {}).get("mita/calendar") == payload,
                text[:200],
            )
    finally:
        if database_url:
            cleanup(database_url, email)
    print(f"{len(PASSED)} checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp smoke 2.10.0").rstrip(
            "/"
        )
    except ProductionTargetError as exc:
        print(f"REFUSED  {exc}")
        return 2
    asyncio.run(run(base, args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())

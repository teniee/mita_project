#!/usr/bin/env python3
"""MITA 2.7.0 smoke test against a RUNNING MCP service, over real HTTP.

    python scripts/mcp/smoke_behavioral_270.py --base-url https://<staging-host> \\
        [--database-url postgresql://...]   # clean-up of the accounts it creates

What `e2e_v2.py` does not reach: the 2.7.0 writes and reads, each through
the public endpoints with a NEW fictional account (and a second one for
isolation), so a missing grant on `obligation_payments` / `spending_patterns`
or a broken migration shows up here before a person sees it.

* the owner's month, fictional copy: income 2,000, savings 500, phone 30 on
  the 10th, car loan 270 on the 15th, laptop loan 70 on the 25th, own lines;
* planned purchases on real dates (groceries every Wednesday), proposed dates
  ("about once a week" with no day named), a MITA line left out and the
  money it freed, conserved to the cent;
* `save_spending_patterns`: insert, unchanged, update;
* a purchase in a bill's category is NOT a payment (reserve stays 370.00);
  an expense linked to the phone pays it; linking, relinking and unlinking an
  expense (`update_transaction(obligation_ref=…)`);
* flexible budgets: a daily guide, the pace flags, calendar = forecast;
* the calendar component (v4 since 2.10.0) is the one the tool points at and is served;
* another account cannot use this account's payment reference.

Prints PASS/FAIL names only (no tokens, codes, passwords). Refuses
production hosts (scripts/_target_guard.py). With --database-url it deletes
both accounts with `e2e_v2.cleanup`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import secrets
import sys
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402
from e2e_v2 import PASSED, Session, check, cleanup, connect  # noqa: E402

COMPONENT = "ui://mita/financial-calendar-v4.html"
COMPONENT_FILE = (
    Path(__file__).resolve().parents[2] / "app/mcp/ui/financial_calendar.html"
)
D = Decimal


def key() -> str:
    return uuid.uuid4().hex


def by(items, field, value):
    return next((i for i in items if i.get(field) == value), None)


async def owner_like_month(s: Session):
    await s.call(
        "update_financial_profile",
        {
            "monthly_net_income": 2000,
            "currency": "EUR",
            "timezone": "Europe/Sofia",
            "household_size": 1,
            "monthly_savings_target": 500,
        },
    )
    for name, amount, category, day in (
        ("Phone", 30, "utilities", 10),
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


async def run(base: str, database_url: Optional[str]) -> None:
    emails = [f"ab270-{uuid.uuid4().hex[:10]}@example.test" for _ in range(2)]
    password = "S270-" + secrets.token_urlsafe(14) + "!"
    try:
        first = await connect(base, emails[0], password, register=True)
        async with Session(base, first["access"], "smoke-270-1") as s:
            listed = await s._client.list_tools()
            names = sorted(t.name for t in listed.tools)
            check(
                "save_spending_patterns is published", "save_spending_patterns" in names
            )
            show = next(t for t in listed.tools if t.name == "show_financial_calendar")
            meta = show.meta or {}
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

            await owner_like_month(s)
            status = await s.call("get_setup_status")
            year, month = map(int, status["current_month"].split("-"))
            last = monthrange(year, month)[1]
            days = [date(year, month, d) for d in range(1, last + 1)]
            wednesdays = [d.isoformat() for d in days if d.weekday() == 2]
            proposed = [d.isoformat() for d in days if d.day % 7 == 4]

            lines = [
                {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]},
                {"label": "Cigarettes", "amount": 200},
                {"label": "Coffee and walks", "amount": 100},
                {"label": "Groceries", "amount": 200, "replaces": ["groceries"]},
            ]
            patterns = [
                {
                    "line": "Groceries",
                    "kind": "planned",
                    "frequency": "weekly",
                    "weekdays": ["wednesday"],
                },
                {
                    "line": "Fuel",
                    "kind": "planned",
                    "frequency": "weekly",
                    "typical_amount": "50",
                },
                {"line": "Medical insurance", "kind": "not_applicable"},
            ]
            draft = await s.call(
                "preview_monthly_budget",
                {"budget_lines": lines, "spending_patterns": patterns},
            )
            alloc = {a["category"]: a for a in draft["category_allocations"]}
            groceries, fuel = alloc["my:Groceries"], alloc["my:Fuel"]
            check(
                "groceries: one purchase each Wednesday, the line exact",
                [p["date"] for p in groceries["purchases"]] == wednesdays
                and sum(D(p["amount"]) for p in groceries["purchases"]) == D("200.00")
                and not any(p["proposed"] for p in groceries["purchases"]),
            )
            check(
                "fuel 'about once a week': dates proposed by MITA and labelled",
                [p["date"] for p in fuel["purchases"]] == proposed
                and all(p["proposed"] for p in fuel["purchases"])
                and fuel["purchase_dates_stated"] is False
                and sum(D(p["amount"]) for p in fuel["purchases"]) == D("200.00"),
            )
            freed = draft["freed_money"]
            check(
                "medical insurance left out; the freed money shown and conserved",
                any(
                    x["category"] == "insurance medical"
                    for x in draft["not_applicable_lines"]
                )
                and "insurance medical" not in alloc
                and freed is not None
                and sum(D(x["amount"]) for x in freed["to_other_lines"])
                + D(freed["unallocated"])
                == D(freed["total"]),
            )
            saved = await s.call(
                "save_monthly_budget", {"draft_token": draft["draft_token"]}
            )
            check("the reviewed month saved", saved["status"] == "saved")

            first_save = await s.call(
                "save_spending_patterns",
                {"patterns": [{"line": "Coffee and walks", "kind": "flexible"}]},
            )
            again = await s.call(
                "save_spending_patterns",
                {"patterns": [{"line": "Coffee and walks", "kind": "flexible"}]},
            )
            moved = await s.call(
                "save_spending_patterns",
                {
                    "patterns": [
                        {
                            "line": "Groceries",
                            "kind": "planned",
                            "frequency": "weekly",
                            "weekdays": ["thursday"],
                        }
                    ]
                },
            )
            check(
                "patterns: inserted, unchanged, updated (the saved month untouched)",
                first_save["status"] == "saved"
                and again["status"] == "unchanged"
                and moved["status"] == "saved",
                f"{first_save['status']}/{again['status']}/{moved['status']}",
            )

            async def reserve() -> str:
                forecast = await s.call("get_budget_forecast")
                return forecast["commitments_reserved"]

            check("all three bills held", await reserve() == "370.00")
            part = await s.call(
                "add_transaction",
                {
                    "amount": "60.00",
                    "category": "transportation",
                    "merchant": "Car parts",
                    "idempotency_key": key(),
                },
            )
            part_ref = part["transactions"][0]["ref"]
            check("a car part does not pay the car loan", await reserve() == "370.00")
            refs = {
                i["merchant"]: i["obligation_ref"]
                for i in (await s.call("get_recurring_expenses"))["scheduled_recurring"]
            }
            await s.call(
                "add_transaction",
                {
                    "amount": "30.00",
                    "category": "utilities",
                    "obligation_ref": refs["Phone"],
                    "idempotency_key": key(),
                },
            )
            check(
                "the linked phone payment pays the phone", await reserve() == "340.00"
            )
            await s.call(
                "update_transaction",
                {"ref": part_ref, "obligation_ref": refs["Car loan"]},
            )
            check("linking an expense pays that due date", await reserve() == "280.00")
            await s.call(
                "update_transaction",
                {"ref": part_ref, "obligation_ref": refs["Laptop loan"]},
            )
            bills = {
                b["name"]: b for b in (await s.call("get_calendar_month"))["bills"]
            }
            check(
                "relinking moves the payment to the other bill",
                await reserve() == "280.00"  # car 270 + laptop 70 − 60
                and bills["Laptop loan"]["paid"] == "60.00"
                and bills["Car loan"]["paid"] == "0.00",
            )
            await s.call(
                "update_transaction",
                {"ref": part_ref, "obligation_ref": refs["Phone"]},
            )
            check(
                "a due date is paid at most its amount (the phone was paid)",
                await reserve() == "340.00",
            )
            await s.call("update_transaction", {"ref": part_ref, "obligation_ref": ""})
            check(
                "unlinking returns it to ordinary spending", await reserve() == "340.00"
            )

            await s.call(
                "add_transaction",
                {
                    "amount": "90.00",
                    "budget_line": "Cigarettes",
                    "idempotency_key": key(),
                },
            )
            cal = await s.call("get_calendar_month")
            forecast = await s.call("get_budget_forecast")
            cig = by(cal["categories"], "category", "my:Cigarettes")
            check(
                "flexible budgets: a daily guide, cigarettes flagged by pace",
                cal["summary"]["flexible_per_day"] is not None
                and cig["spending_type"] == "flexible"
                and cig["pace_status"] in ("faster_than_pace", "on_pace")
                and cig["remaining"] == "110.00",
                str(cig and cig.get("pace_status")),
            )
            check(
                "calendar = forecast (reserve, daily figure)",
                cal["summary"]["commitments_reserved"]
                == forecast["commitments_reserved"]
                and cal["summary"]["average_per_day"] == forecast["safe_daily_limit"],
            )
            bills = {b["name"]: b for b in cal["bills"]}
            # A bill saved after its day of the month is listed from its next
            # due date on (the calendar never shows a bill before the date it
            # was scheduled for): run after the 10th, the phone is not among
            # this month's bills, and its payment is what the reserve above
            # proved (340.00). The loans' checks need a run on or before the
            # 15th.
            phone = bills.get("Phone")
            check(
                "the phone bill is recorded as paid, the loans are not",
                (phone is None or phone["state"] == "paid")
                and bills["Car loan"]["state"] != "paid"
                and bills["Laptop loan"]["state"] != "paid",
                str({n: b["state"] for n, b in bills.items()}),
            )

        second = await connect(base, emails[1], password, register=True)
        async with Session(base, second["access"], "smoke-270-2") as other:
            stolen = await other.call(
                "add_transaction",
                {
                    "amount": "30.00",
                    "obligation_ref": refs["Phone"],
                    "idempotency_key": key(),
                },
                ok=False,
            )
            check(
                "another account cannot use this account's payment reference",
                stolen.is_error,
            )
            empty = await other.call("get_calendar_month")
            check(
                "another account sees no plan of this one",
                empty["plan_status"] == "not_generated"
                and not empty["bills"]
                and empty["summary"]["total_spent"] == "0.00",
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
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp smoke 2.7.0")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(run(base, args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())

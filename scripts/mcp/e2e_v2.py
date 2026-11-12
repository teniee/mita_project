#!/usr/bin/env python3
"""Free-v1 acceptance conversation against a RUNNING MCP service, over real HTTP.

    python scripts/mcp/e2e_v2.py --base-url https://<staging-host> \\
        [--database-url postgresql://...]   # analytics audit + cleanup

Plays the master plan's core flow as ChatGPT would, through the public
endpoints only: creates a NEW account on the OAuth sign-up page, completes
the profile, saves rent, previews a budget (and checks nothing was saved),
saves the reviewed draft, records single and batch expenses (and a retry),
records three past months, reconnects as a brand-new connection and checks
everything persisted, asks the six-month grocery question, creates a goal,
sends feedback, and runs negative checks (smuggled identity, forged ref,
tampered draft, read-only grant cannot write, no money-movement tool).

With --database-url it also audits analytics (linked events present, no
amounts/merchants/feedback text in them) and deletes the account it created
(everything cascades). Never prints tokens, codes or the password.
Refuses production hosts (scripts/_target_guard.py).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import calendar
import hashlib
import re
import secrets
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402

from app.mcp.auth.scopes import SUPPORTED_SCOPES  # noqa: E402
from app.mcp.tools import PUBLISHED_TOOLS  # noqa: E402

REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
PASSED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASSED.append(name)
        print(f"PASS  {name}")
        return
    print(f"FAIL  {name}  {detail[:300]}")
    raise SystemExit(1)


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.decode().rstrip("=")


async def connect(
    base: str, email: str, password: str, *, register: bool, scopes=SUPPORTED_SCOPES
) -> Dict[str, str]:
    """A brand-new ChatGPT-style connection: DCR, authorize, sign in or sign up, token."""
    async with httpx2.AsyncClient(
        base_url=base, follow_redirects=False, timeout=30
    ) as http:
        reg = await http.post(
            "/register",
            json={
                "redirect_uris": [REDIRECT],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "client_name": "ChatGPT",
            },
        )
        check("client registration", reg.status_code == 201, reg.text)
        client_id = reg.json()["client_id"]
        verifier, challenge = pkce()
        auth = await http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "v2-state",
                "scope": " ".join(scopes),
                "resource": f"{base}/mcp",
            },
        )
        check("authorize → consent page", auth.status_code == 302, auth.text)
        login_url = auth.headers["location"] + ("&mode=register" if register else "")
        page = await http.get(login_url)
        check("consent page served", page.status_code == 200, str(page.status_code))
        if register:
            check(
                "sign-up form offered",
                'name="password_confirm"' in page.text
                and "Create account" in page.text,
            )
        cookie = re.search(
            r"(__Host-mita_oauth_csrf=[^;]+)", page.headers["set-cookie"]
        ).group(1)
        csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', page.text).group(1)
        req = parse_qs(urlparse(login_url).query)["req"][0]
        form = {
            "req": req,
            "csrf": csrf,
            "email": email,
            "password": password,
            "usage_stats": "1",
        }
        form["action"] = "register" if register else "allow"
        if register:
            form["password_confirm"] = password
        done = await http.post("/oauth/login", data=form, headers={"cookie": cookie})
        check(
            (
                "account created and code issued"
                if register
                else "signed in and code issued"
            ),
            done.status_code == 302 and done.headers["location"].startswith(REDIRECT),
            f"HTTP {done.status_code}",
        )
        query = parse_qs(urlparse(done.headers["location"]).query)
        check(
            "the pending authorization continued (state)",
            query.get("state") == ["v2-state"],
        )
        token = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": query["code"][0],
                "redirect_uri": REDIRECT,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": f"{base}/mcp",
            },
        )
        check("code exchange", token.status_code == 200, f"HTTP {token.status_code}")
        body = token.json()
        return {
            "client_id": client_id,
            "access": body["access_token"],
            "refresh": body["refresh_token"],
            "scope": body.get("scope", ""),
        }


class Session:
    """One MCP client session, like one ChatGPT conversation."""

    def __init__(self, base: str, token: str, conversation: str):
        self.base, self.token, self.conversation = base, token, conversation

    async def __aenter__(self):
        self._http = httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {self.token}"}, timeout=60
        )
        self._client = Client(
            streamable_http_client(f"{self.base}/mcp", http_client=self._http)
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self._client.__aexit__(*exc)
        await self._http.aclose()

    async def call(self, tool: str, args: Optional[dict] = None, *, ok: bool = True):
        result = await self._client.call_tool(
            tool, args or {}, meta={"openai/session": self.conversation}
        )
        if ok:
            check(f"{tool} succeeds", not result.is_error, str(result.content)[:300])
            return result.structured_content
        return result

    async def tools(self):
        return sorted(t.name for t in (await self._client.list_tools()).tools)


def months_back(today: date, back: int) -> date:
    index = today.year * 12 + today.month - 1 - back
    return date(index // 12, index % 12 + 1, 10)


async def run(base: str, database_url: Optional[str]) -> None:
    email = f"v2e2e_{uuid.uuid4().hex[:10]}@example.test"
    password = "V2-" + secrets.token_urlsafe(14) + "!"
    async with httpx2.AsyncClient(base_url=base, timeout=30) as http:
        health = await http.get("/health")
        check(
            "/health",
            health.status_code == 200 and health.json()["status"] == "ok",
            health.text,
        )
        prm = (await http.get("/.well-known/oauth-protected-resource/mcp")).json()
        check(
            "metadata lists the write scopes",
            set(SUPPORTED_SCOPES) <= set(prm["scopes_supported"]),
        )

    first = await connect(base, email, password, register=True)
    check(
        "grant carries every scope",
        set(first["scope"].split()) == set(SUPPORTED_SCOPES),
    )
    try:
        async with Session(base, first["access"], "v2-conversation-1") as s:
            check(
                "tools/list is exactly the published set",
                await s.tools() == sorted(PUBLISHED_TOOLS),
            )
            check(
                "no money-movement tool exists",
                not any(
                    w in t
                    for t in await s.tools()
                    for w in ("transfer", "pay", "trade")
                ),
            )
            status = await s.call("get_setup_status")
            check(
                "new account: nothing known yet",
                status["profile_complete"] is False
                and len(status["missing_fields"]) == 5,
            )
            today = date.fromisoformat(status["current_month"] + "-01")
            profile = await s.call(
                "update_financial_profile",
                {
                    "monthly_net_income": 2500,
                    "currency": "EUR",
                    "timezone": "Europe/Sofia",
                    "household_size": 2,
                    "monthly_savings_target": 400,
                },
            )
            check("profile saved and complete", profile["profile_complete"] is True)
            check(
                "asks about regular payments before a first budget",
                profile["suggested_next_step"] == "ask_about_obligations",
            )
            rent = await s.call(
                "add_recurring_expense",
                {
                    "name": "Rent",
                    "amount": 700,
                    "category": "rent",
                    "recurrence": "monthly",
                    "day_of_month": 1,
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check(
                "rent saved", rent["status"] == "created" and rent["amount"] == "700.00"
            )
            preview = await s.call("preview_monthly_budget")
            check(
                "preview is a preview",
                preview["status"] == "preview"
                and preview["fixed_obligations_total"] == "700.00",
            )
            before = await s.call("get_budget_status")
            check("the preview saved nothing", before["plan_status"] == "not_generated")
            saved = await s.call(
                "save_monthly_budget", {"draft_token": preview["draft_token"]}
            )
            check(
                "reviewed plan saved",
                saved["status"] == "saved"
                and saved["plan_total"] == preview["plan_total"],
            )
            after = await s.call("get_budget_status")
            check(
                "saved plan equals the preview total",
                after["total_planned"] == preview["plan_total"],
            )
            # F-11: a budget line the user names and sets is kept exactly.
            mine = await s.call(
                "preview_monthly_budget",
                {"budget_lines": [{"label": "Cigarettes", "amount": "40.00"}]},
            )
            set_lines = {
                a["category"]: (a["amount"], a["source"])
                for a in mine["category_allocations"]
            }
            check(
                "own budget line previewed as set by the user",
                set_lines.get("my:Cigarettes") == ("40.00", "set_by_you"),
            )
            kept = await s.call(
                "save_monthly_budget", {"draft_token": mine["draft_token"]}
            )
            check(
                "own budget line saved",
                [(a["category"], a["amount"]) for a in kept["set_by_you"]]
                == [("my:Cigarettes", "40.00")],
            )
            smoked = await s.call(
                "add_transaction",
                {
                    "amount": "7.00",
                    "budget_line": "Cigarettes",
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check(
                "expense recorded against the user's line",
                smoked["transactions"][0]["category"] == "my:Cigarettes",
            )
            lines = {
                c["category"]: c
                for c in (await s.call("get_budget_status"))["categories"]
            }
            check(
                "status shows the user's line",
                lines["my:Cigarettes"]["planned"] == "40.00"
                and lines["my:Cigarettes"]["spent"] == "7.00"
                and lines["my:Cigarettes"]["source"] == "set_by_you",
            )
            key = uuid.uuid4().hex
            one = await s.call(
                "add_transaction",
                {
                    "amount": "36.80",
                    "category": "groceries",
                    "merchant": "Lidl",
                    "idempotency_key": key,
                },
            )
            check("expense recorded", one["status"] == "recorded")
            retry = await s.call(
                "add_transaction",
                {
                    "amount": "36.80",
                    "category": "groceries",
                    "merchant": "Lidl",
                    "idempotency_key": key,
                },
            )
            check("retry did not duplicate", retry["status"] == "already_recorded")
            batch = await s.call(
                "add_transactions",
                {
                    "expenses": [
                        {"amount": 8, "category": "dining", "merchant": "Coffee"},
                        {"amount": 55, "category": "gas"},
                    ],
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check(
                "batch recorded",
                batch["count"] == 2 and batch["month_to_date_spent"] == "106.80",
            )
            lines = (await s.call("get_budget_status"))["categories"]
            labels = [c["category_label"] for c in lines]
            fuel = [c for c in lines if c["category_label"] == "Fuel"]
            check(
                "one budget line per category name (fuel combined)",
                len(labels) == len(set(labels))
                and len(fuel) == 1
                and "gas" in fuel[0]["category_codes"]
                and fuel[0]["spent"] == "55.00",
                str(labels),
            )
            for back, amount in ((3, "300.00"), (2, "320.00"), (1, "360.00")):
                await s.call(
                    "add_transaction",
                    {
                        "amount": amount,
                        "category": "groceries",
                        "date": months_back(today, back).isoformat(),
                        "idempotency_key": uuid.uuid4().hex,
                    },
                )
            # Negative checks
            smuggled = await s.call(
                "add_transaction",
                {
                    "amount": 1,
                    "category": "dining",
                    "idempotency_key": uuid.uuid4().hex,
                    "user_id": str(uuid.uuid4()),
                },
                ok=False,
            )
            check("smuggled user_id is rejected", smuggled.is_error)
            forged = await s.call(
                "update_transaction", {"ref": "tx_" + "A" * 43, "amount": 1}, ok=False
            )
            check("forged ref is refused", forged.is_error)
            tampered = await s.call(
                "save_monthly_budget",
                {"draft_token": preview["draft_token"][:-3] + "AAA"},
                ok=False,
            )
            check("tampered draft is refused", tampered.is_error)

        # A completely new connection, as after deleting the ChatGPT conversation.
        second = await connect(base, email, password, register=False)
        async with Session(base, second["access"], "v2-conversation-2") as s:
            summary = await s.call("get_financial_summary")
            check(
                "persisted: month spending",
                summary["spent_total"] == "106.80",  # incl. the €7 on the user's line
                summary["spent_total"],
            )
            check("persisted: saved plan", summary["plan_status"] == "generated")
            setup = await s.call("get_setup_status")
            check(
                "persisted: setup complete",
                setup["profile_complete"] and setup["monthly_plan_exists"],
            )
            history = await s.call("get_spending_history", {"category": "groceries"})
            totals = [m["total_spent"] for m in history["months"][-4:]]
            check(
                "six-month grocery history",
                totals == ["300.00", "320.00", "360.00", "36.80"],
                str(totals),
            )
            check(
                "trend uses three complete months", history["trend"]["status"] == "ok"
            )
            target = months_back(today, -8)
            last_day = date(
                target.year,
                target.month,
                calendar.monthrange(target.year, target.month)[1],
            )
            goal = await s.call(
                "create_savings_goal",
                {
                    "title": "Emergency fund — София",
                    "target_amount": 5000,
                    "target_date": last_day.isoformat(),
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check("goal title kept exactly", goal["title"] == "Emergency fund — София")
            undated = await s.call(
                "create_savings_goal",
                {
                    "title": "Holiday",
                    "target_amount": 1000,
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check(
                "an undated goal says nothing is set aside and it cannot be changed",
                undated["reserved_in_budget_plan"] is False
                and any("cannot be changed" in n for n in undated["notes"]),
            )
            anna = await s.call("list_transactions", {"merchant": "Anna"})
            check(
                "a name filter searches only the user's own expenses",
                anna["matching_count"] == 0
                and any("own recorded expenses" in n for n in anna["notes"]),
            )
            sent = await s.call(
                "submit_feedback",
                {
                    "type": "confusing",
                    "feature_area": "transactions",
                    "message": "Transaction categorization is confusing.",
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
            check("feedback sent", sent["status"] == "sent")

        readonly = await connect(
            base,
            email,
            password,
            register=False,
            scopes=("profile:read", "finance:read"),
        )
        async with Session(base, readonly["access"], "v2-conversation-3") as s:
            denied = await s.call(
                "add_transaction",
                {
                    "amount": 1,
                    "category": "dining",
                    "idempotency_key": uuid.uuid4().hex,
                },
                ok=False,
            )
            check(
                "read-only grant cannot write",
                denied.is_error
                and (denied.structured_content or {}).get("error", {}).get("category")
                == "forbidden",
            )

        if database_url:
            audit(database_url, email)
    finally:
        if database_url:
            cleanup(database_url, email)
        else:
            print(
                f"NOTE  created staging account {email} was not deleted (no --database-url)"
            )
    print(f"e2e v2 complete: {len(PASSED)} checks passed")


def _pg(url: str):
    import psycopg2

    return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))


def audit(url: str, email: str) -> None:
    expected = {
        "account_created",
        "oauth_connected",
        "financial_profile_created",
        "recurring_expense_created",
        "budget_previewed",
        "budget_saved",
        "onboarding_completed",
        "transaction_created",
        "transaction_batch_created",
        "savings_goal_created",
        "feedback_submitted",
        "tool_call_succeeded",
        "tool_call_failed",
    }
    names, rows = set(), []
    for _ in range(20):  # the production sink writes in the background
        with _pg(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT e.event_name, e.properties::text, coalesce(e.session_key,''), "
                "coalesce(e.locale,''), coalesce(e.intent_code,'') FROM analytics.events e "
                "JOIN analytics_identities i ON i.user_key = e.user_key "
                "JOIN users u ON u.id = i.user_id WHERE u.email = %s",
                (email,),
            )
            rows = cur.fetchall()
        names = {r[0] for r in rows}
        if expected <= names:
            break
        time.sleep(1)
    check(
        "analytics: lifecycle events recorded (pseudonymous)",
        expected <= names,
        str(sorted(expected - names)),
    )
    flat = " ".join(" ".join(r) for r in rows)
    for value in ("36.80", "Lidl", "categorization", email, "v2-conversation"):
        check(f"analytics holds no '{value[:12]}'", value not in flat)
    with _pg(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT f.message FROM product_feedback f JOIN users u ON u.id = f.user_id WHERE u.email = %s",
            (email,),
        )
        check(
            "feedback stored with the user's words",
            cur.fetchone()[0] == "Transaction categorization is confusing.",
        )


def cleanup(url: str, email: str) -> None:
    with _pg(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
            cur.execute(
                "DELETE FROM mcp_oauth_clients WHERE client_id IN ("
                "SELECT client_id FROM mcp_oauth_refresh_tokens WHERE user_id = %s)",
                (user_id,),
            )
            for statement in (
                "DELETE FROM transactions WHERE user_id = %s",
                "DELETE FROM daily_plan WHERE user_id = %s",
                "DELETE FROM redistribution_events WHERE user_id = %s",
                "DELETE FROM scheduled_expenses WHERE user_id = %s",
                "DELETE FROM goals WHERE user_id = %s",
            ):
                cur.execute(statement, (user_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    print("cleanup: the test account and its data were deleted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url")
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp e2e_v2")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(run(base, args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())

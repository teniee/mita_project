#!/usr/bin/env python3
"""End-to-end check of a RUNNING MCP service over real HTTP.

    # phase 1: full OAuth flow + all tools; saves the refresh token
    python scripts/mcp/e2e_http.py --base-url http://localhost:8080 \\
        --database-url postgresql://... --state /tmp/e2e.json --phase first

    # restart the service, then:
    python scripts/mcp/e2e_http.py ... --phase after-restart --log-file service.log

Creates ONE disposable user directly in the given database (so it needs no
REST API), refuses production hosts via scripts/_target_guard.py, and deletes
the user (and, by cascade, its OAuth rows) at the end of the second phase.

The consent page cookie is __Host- (Secure); over plain-HTTP local runs the
script carries it by hand, which the server does not distinguish.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import secrets
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx2
import psycopg2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402

from app.core.password_security import hash_password_sync  # noqa: E402

REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
TOOLS = [
    ("get_profile", {}),
    ("get_financial_summary", {}),
    ("list_transactions", {}),
    ("get_spending_breakdown", {}),
    ("get_budget_status", {}),
    ("get_budget_forecast", {}),
    ("get_recurring_expenses", {}),
    ("get_goals", {"status": "all"}),
]


def check(name: str, ok: bool, detail: str = "") -> None:
    """Details are printed only on failure, and never token/code bodies."""
    if ok:
        print(f"PASS  {name}")
        return
    print(f"FAIL  {name}  {detail[:300]}")
    raise SystemExit(1)


def pg(dsn: str):
    return psycopg2.connect(dsn.replace("postgresql+asyncpg://", "postgresql://"))


async def call_tools(base: str, token: str) -> dict:
    results = {}
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}, timeout=30
    ) as http:
        async with Client(
            streamable_http_client(f"{base}/mcp", http_client=http)
        ) as client:
            listed = sorted(t.name for t in (await client.list_tools()).tools)
            check(
                "tools/list returns the 8 read-only tools",
                listed == sorted(n for n, _ in TOOLS),
                str(listed),
            )
            for name, args in TOOLS:
                result = await client.call_tool(name, args)
                check(
                    f"tool {name}",
                    not result.is_error,
                    "" if not result.is_error else str(result.content),
                )
                results[name] = result.structured_content
    return results


async def first_phase(args, base: str) -> None:
    password = "E2e-" + secrets.token_urlsafe(12)
    email = f"e2e_{uuid.uuid4().hex[:10]}@example.test"
    user_id = uuid.uuid4()
    with pg(args.database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, email, password_hash, timezone, currency, monthly_income, "
            "has_onboarded, token_version, failed_login_attempts, email_verified, "
            "notifications_enabled, dark_mode_enabled, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'Europe/Sofia', 'EUR', 3200, true, 1, 0, false, true, false, now(), now())",
            (str(user_id), email, hash_password_sync(password)),
        )
        cur.execute(
            "INSERT INTO transactions (id, user_id, category, amount, currency, merchant, "
            "is_recurring, spent_at, created_at, updated_at) "
            "VALUES (%s, %s, 'groceries', 42.17, 'EUR', 'E2E Market', false, now(), now(), now())",
            (str(uuid.uuid4()), str(user_id)),
        )

    async with httpx2.AsyncClient(
        base_url=base, follow_redirects=False, timeout=30
    ) as http:
        health = await http.get("/health")
        check(
            "/health",
            health.status_code == 200 and health.json()["status"] == "ok",
            health.text,
        )
        prm = (await http.get("/.well-known/oauth-protected-resource/mcp")).json()
        check(
            "protected-resource metadata",
            prm["resource"] == f"{base}/mcp",
            json.dumps(prm),
        )
        asm = (await http.get("/.well-known/oauth-authorization-server")).json()
        check(
            "AS metadata advertises S256 only",
            asm["code_challenge_methods_supported"] == ["S256"],
        )
        unauth = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"accept": "application/json, text/event-stream"},
        )
        check("unauthenticated /mcp is 401", unauth.status_code == 401)
        check(
            "WWW-Authenticate points at metadata",
            "resource_metadata=" in unauth.headers.get("www-authenticate", ""),
        )

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
        check("dynamic client registration", reg.status_code == 201, reg.text)
        client_id = reg.json()["client_id"]
        evil = await http.post(
            "/register", json={"redirect_uris": ["https://evil.example/cb"]}
        )
        check("foreign redirect refused at registration", evil.status_code == 400)

        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        auth = await http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "e2e-state",
                "scope": "profile:read finance:read",
                "resource": f"{base}/mcp",
            },
        )
        check(
            "/authorize redirects to consent page", auth.status_code == 302, auth.text
        )
        login_url = auth.headers["location"]
        page = await http.get(login_url)
        cookie = re.search(
            r"(__Host-mita_oauth_csrf=[^;]+)", page.headers["set-cookie"]
        ).group(1)
        csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', page.text).group(1)
        req = parse_qs(urlparse(login_url).query)["req"][0]
        done = await http.post(
            "/oauth/login",
            data={
                "req": req,
                "csrf": csrf,
                "email": email,
                "password": password,
                "action": "allow",
            },
            headers={"cookie": cookie},
        )
        check(
            "consent issues a code to the registered redirect",
            done.status_code == 302 and done.headers["location"].startswith(REDIRECT),
            str(done.status_code),
        )
        query = parse_qs(urlparse(done.headers["location"]).query)
        check("state round-trips", query.get("state") == ["e2e-state"])
        code = query["code"][0]

        tokens = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": f"{base}/mcp",
            },
        )
        check(
            "code exchange with PKCE",
            tokens.status_code == 200,
            f"HTTP {tokens.status_code}",
        )
        tokens = tokens.json()
        replay = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        check("code replay refused", replay.status_code == 400)

    results = await call_tools(base, tokens["access_token"])
    check(
        "ledger figure is exact",
        results["list_transactions"]["matching_total"] == "42.17",
        results["list_transactions"]["matching_total"],
    )

    Path(args.state).write_text(
        json.dumps(
            {
                "client_id": client_id,
                "refresh_token": tokens["refresh_token"],
                "user_id": str(user_id),
                "secrets": [
                    code,
                    verifier,
                    tokens["access_token"],
                    tokens["refresh_token"],
                    password,
                    email,
                ],
            }
        )
    )
    print("phase 1 complete")


async def second_phase(args, base: str) -> None:
    state = json.loads(Path(args.state).read_text())
    try:
        async with httpx2.AsyncClient(base_url=base, timeout=30) as http:
            check(
                "/health after restart", (await http.get("/health")).status_code == 200
            )
            rotated = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": state["refresh_token"],
                    "client_id": state["client_id"],
                },
            )
            check(
                "refresh token survives restart",
                rotated.status_code == 200,
                f"HTTP {rotated.status_code}",
            )
            rotated = rotated.json()
            reuse = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": state["refresh_token"],
                    "client_id": state["client_id"],
                },
            )
            check("rotated refresh token is refused", reuse.status_code == 400)
        await call_tools(base, rotated["access_token"])
        state["secrets"] += [rotated["access_token"], rotated["refresh_token"]]
        # Persist the complete list so a later scan (e.g. `docker logs`) checks
        # the rotated tokens too.
        Path(args.state).write_text(json.dumps(state))

        # Revocation: a password change (by any path) must end MCP access.
        with pg(args.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (
                    hash_password_sync("Rotated-" + secrets.token_urlsafe(12)),
                    state["user_id"],
                ),
            )
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {rotated['access_token']}"}, timeout=30
        ) as http:
            async with Client(
                streamable_http_client(f"{base}/mcp", http_client=http)
            ) as client:
                result = await client.call_tool("get_profile", {})
        check(
            "password change revokes the live access token",
            result.is_error
            and (result.structured_content or {}).get("error", {}).get("category")
            == "auth",
        )
        async with httpx2.AsyncClient(base_url=base, timeout=30) as http:
            after = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": rotated["refresh_token"],
                    "client_id": state["client_id"],
                },
            )
        check("password change revokes the refresh token", after.status_code == 400)
        if args.log_file:
            logs = Path(args.log_file).read_text(errors="replace")
            leaked = [i for i, s in enumerate(state["secrets"]) if s and s in logs]
            check(
                "logs contain no codes, tokens, passwords or e-mails",
                not leaked,
                f"leaked items: {leaked}",
            )
            check("logs contain no amounts", "42.17" not in logs)
            # app.core.logging_config prints two plain-text lines at import,
            # before configure_logging() takes over; nothing else may.
            stray = [
                line
                for line in logs.splitlines()
                if line.strip()
                and not line.startswith("{")
                and "app.core.logging_config: Log" not in line
                and "app.core.logging_config: Logging configured" not in line
            ]
            check(
                "logs are JSON lines (besides two known startup lines)",
                not stray,
                str(len(stray)),
            )
    finally:
        with pg(args.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM transactions WHERE user_id = %s", (state["user_id"],)
            )
            cur.execute(
                "DELETE FROM mcp_oauth_clients WHERE client_id = %s",
                (state["client_id"],),
            )
            cur.execute("DELETE FROM users WHERE id = %s", (state["user_id"],))
    print("phase 2 complete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--phase", choices=["first", "after-restart"], required=True)
    parser.add_argument("--log-file")
    args = parser.parse_args()
    try:
        base = assert_writable_target(args.base_url, purpose="mcp e2e_http")
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(
        first_phase(args, base) if args.phase == "first" else second_phase(args, base)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

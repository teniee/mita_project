#!/usr/bin/env python3
"""Fail-closed checks against a deployed (non-production) MCP service.

    python scripts/mcp/staging_failure_modes.py --base-url https://<staging> \\
        --database-url postgresql://<staging db>

Creates one temporary fake user (deleted at the end), never prints tokens,
codes or passwords, refuses production hosts. Light on the target: about
fifty requests in total.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import re
import secrets
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _target_guard import ProductionTargetError, assert_writable_target  # noqa: E402
from e2e_http import REDIRECT, check, pg  # noqa: E402

from app.core.password_security import hash_password_sync  # noqa: E402


def pkce():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


async def login(http, base, client_id, challenge, email, password, scope):
    auth = await http.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "s",
            "scope": scope,
            "resource": f"{base}/mcp",
        },
    )
    page = await http.get(auth.headers["location"])
    cookie = re.search(
        r"(__Host-mita_oauth_csrf=[^;]+)", page.headers["set-cookie"]
    ).group(1)
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', page.text).group(1)
    req = parse_qs(urlparse(auth.headers["location"]).query)["req"][0]
    return await http.post(
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


async def run(base: str, dsn: str) -> None:
    email = f"fail_{uuid.uuid4().hex[:10]}@example.test"
    password = "Fail-" + secrets.token_urlsafe(12)
    user_id = uuid.uuid4()
    client_id = None
    with pg(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, email, password_hash, timezone, currency, monthly_income, "
            "has_onboarded, token_version, failed_login_attempts, email_verified, "
            "notifications_enabled, dark_mode_enabled, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'UTC', 'EUR', 1000, true, 1, 0, false, true, false, now(), now())",
            (str(user_id), email, hash_password_sync(password)),
        )
    try:
        async with httpx2.AsyncClient(
            base_url=base, follow_redirects=False, timeout=30
        ) as http:
            r = await http.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={
                    "accept": "application/json, text/event-stream",
                    "authorization": "Bearer not-a-real-token",
                },
            )
            check("invalid bearer -> 401", r.status_code == 401)

            for uri in (
                "https://evil.example/cb",
                "https://chatgpt.com/connector/oauth/x?next=https://evil.example",
                "https://chatgpt.com/connector_platform_oauth_redirect/../x",
            ):
                r = await http.post("/register", json={"redirect_uris": [uri]})
                check(
                    f"register refuses redirect {urlparse(uri).netloc}{urlparse(uri).path[:20]}…",
                    r.status_code == 400,
                )

            r = await http.post(
                "/register",
                json={
                    "redirect_uris": [REDIRECT],
                    "token_endpoint_auth_method": "none",
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                },
            )
            check("register legitimate client", r.status_code == 201)
            client_id = r.json()["client_id"]

            r = await http.get(
                "/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": "https://chatgpt.com/connector/oauth/other",
                    "code_challenge": pkce()[1],
                    "code_challenge_method": "S256",
                    "state": "s",
                },
            )
            check(
                "authorize with unregistered redirect -> 400, no redirect",
                r.status_code == 400 and "location" not in r.headers,
            )

            r = await http.get(
                "/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": REDIRECT,
                    "state": "s",
                },
            )
            check(
                "authorize without PKCE never reaches consent",
                "/oauth/login" not in r.headers.get("location", ""),
            )

            verifier, challenge = pkce()
            bad = await login(
                http,
                base,
                client_id,
                challenge,
                email,
                "wrong-password-123",
                "profile:read finance:read",
            )
            check(
                "wrong password -> generic failure, no code",
                bad.status_code == 400
                and "location" not in bad.headers
                and "Sign-in failed" in bad.text,
            )

            done = await login(
                http, base, client_id, challenge, email, password, "profile:read"
            )
            code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
            r = await http.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "bogus-" + secrets.token_urlsafe(8),
                    "redirect_uri": REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            check(
                "bad authorization code -> 400 invalid_grant",
                r.status_code == 400 and r.json()["error"] == "invalid_grant",
            )
            r = await http.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT,
                    "client_id": client_id,
                    "code_verifier": secrets.token_urlsafe(48),
                },
            )
            check("wrong PKCE verifier -> 400", r.status_code == 400)
            tokens = (
                await http.post(
                    "/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": REDIRECT,
                        "client_id": client_id,
                        "code_verifier": verifier,
                    },
                )
            ).json()
            check("profile-only grant issued", tokens.get("scope") == "profile:read")
            r = await http.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT,
                    "client_id": client_id,
                    "code_verifier": verifier,
                },
            )
            check("replayed code -> 400", r.status_code == 400)

            r = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "client_id": client_id,
                    "scope": "profile:read finance:read",
                },
            )
            check(
                "refresh cannot widen scope -> 400 invalid_scope",
                r.status_code == 400 and r.json()["error"] == "invalid_scope",
            )
            rotated = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "client_id": client_id,
                },
            )
            check("refresh rotates", rotated.status_code == 200)
            r = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "client_id": client_id,
                },
            )
            check("replayed refresh token -> 400", r.status_code == 400)
            r = await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": rotated.json()["refresh_token"],
                    "client_id": client_id,
                },
            )
            check("replay revoked the whole family -> 400", r.status_code == 400)

        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
            timeout=30,
        ) as h2:
            async with Client(
                streamable_http_client(f"{base}/mcp", http_client=h2)
            ) as client:
                ok = await client.call_tool("get_profile", {})
                check("profile scope works for get_profile", not ok.is_error)
                denied = await client.call_tool("list_transactions", {})
                check(
                    "profile-only token on a finance tool -> forbidden",
                    denied.is_error
                    and denied.structured_content["error"]["category"] == "forbidden",
                )
                bad_args = await client.call_tool(
                    "get_profile", {"user_id": str(uuid.uuid4())}
                )
                check(
                    "smuggled user_id cannot change identity",
                    bad_args.is_error
                    or (bad_args.structured_content or {}).get("id")
                    == ok.structured_content["id"],
                )
                malformed = await client.call_tool(
                    "get_goals", {"status": "everything"}
                )
                check("malformed tool argument -> error", malformed.is_error)
                names = sorted(t.name for t in (await client.list_tools()).tools)
                check("exactly 8 tools, all read-only", len(names) == 8)

        async with httpx2.AsyncClient(base_url=base, timeout=30) as http:
            statuses = [(await http.get("/authorize")).status_code for _ in range(31)]
            check(
                "/authorize rate limit engages (429)",
                429 in statuses,
                str(sorted(set(statuses))),
            )
    finally:
        with pg(dsn) as conn, conn.cursor() as cur:
            if client_id:
                cur.execute(
                    "DELETE FROM mcp_oauth_clients WHERE client_id = %s", (client_id,)
                )
            cur.execute("DELETE FROM users WHERE id = %s", (str(user_id),))
    print("failure modes complete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    try:
        base = assert_writable_target(
            args.base_url, purpose="mcp staging_failure_modes"
        )
    except ProductionTargetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    asyncio.run(run(base, args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())

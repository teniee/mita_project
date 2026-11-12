"""Adversarial tests for the built-in OAuth 2.1 authorization server.

Each test states the attack and asserts the server fails closed. Written
against the implementation as reviewed in docs/chatgpt-app/oauth-security-audit.md.
"""

import asyncio
import base64
import json
import logging
import secrets
import time
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx2
import jwt
import pytest
from sqlalchemy import text

from app.mcp.config import McpConfigError
from app.mcp.ratelimit import UNUSABLE_CLIENT_ADDRESS, client_address
from tests_mcp.conftest import PASSWORD, PUBLIC_URL, make_settings, started, structured
from tests_mcp.test_oauth_flow import (
    REDIRECT,
    RESOURCE,
    authorize,
    consent,
    csrf_from,
    exchange,
    full_login,
    pkce,
    refresh,
    register,
)

LEGIT_DYNAMIC = "https://chatgpt.com/connector/oauth/AbC_123-x"

# ---------------------------------------------------------------------------
# Redirect URI attacks
# ---------------------------------------------------------------------------

MALICIOUS_REDIRECTS = [
    # different scheme / host / port
    "http://chatgpt.com/connector/oauth/abc",
    "https://evil.example/connector/oauth/abc",
    "https://chatgpt.co/connector/oauth/abc",
    "https://chatgpt.com.evil.example/connector/oauth/abc",
    "https://evilchatgpt.com/connector/oauth/abc",
    "https://chatgpt.com:8443/connector/oauth/abc",
    "https://sub.chatgpt.com/connector/oauth/abc",
    # userinfo tricks
    "https://evil.example@chatgpt.com/connector/oauth/abc",
    "https://chatgpt.com@evil.example/connector/oauth/abc",
    # path tricks under the right host
    "https://chatgpt.com/connector/oauth/",
    "https://chatgpt.com/connector/oauth/abc/extra",
    "https://chatgpt.com/connector/oauth/../../redirect",
    "https://chatgpt.com/connector/oauth/%2e%2e%2f%2e%2e%2fredirect",
    "https://chatgpt.com/connector/oauth/abc%2Fx",
    "https://chatgpt.com/connector_platform_oauth_redirectX",
    "https://chatgpt.com/connector_platform_oauth_redirect/",
    "https://chatgpt.com/connector_platform_oauth_redirect/../evil",
    "https://chatgpt.com/CONNECTOR/oauth/abc",
    # query / fragment (open-redirect chaining)
    "https://chatgpt.com/connector_platform_oauth_redirect?next=https://evil.example",
    "https://chatgpt.com/connector/oauth/abc?redirect=https://evil.example",
    "https://chatgpt.com/connector/oauth/abc#https://evil.example",
    # localhost substitution
    "http://localhost/callback",
    "https://localhost/connector/oauth/abc",
    "http://127.0.0.1:8080/connector/oauth/abc",
    # non-http schemes
    "javascript:alert(1)",
    "chatgpt://connector/oauth/abc",
]


@pytest.mark.parametrize("uri", MALICIOUS_REDIRECTS)
async def test_registration_rejects_malicious_redirect(mcp, uri):
    async with mcp.http() as http:
        response = await register(http, redirect_uris=[uri])
    assert response.status_code == 400, (uri, response.text)


@pytest.mark.parametrize("uri", [REDIRECT, LEGIT_DYNAMIC])
async def test_registration_accepts_exact_chatgpt_redirects(mcp, uri):
    async with mcp.http() as http:
        assert (await register(http, redirect_uris=[uri])).status_code == 201


@pytest.mark.parametrize(
    "variant",
    [
        LEGIT_DYNAMIC + "x",
        LEGIT_DYNAMIC + "/",
        LEGIT_DYNAMIC + "?a=b",
        LEGIT_DYNAMIC + "#f",
        LEGIT_DYNAMIC.replace("https", "http"),
        "https://chatgpt.com/connector/oauth/other",
    ],
)
async def test_authorize_requires_the_exact_registered_redirect(mcp, variant):
    async with mcp.http() as http:
        client_id = (await register(http, redirect_uris=[LEGIT_DYNAMIC])).json()[
            "client_id"
        ]
        _, challenge = pkce()
        response = await http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": variant,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "s",
            },
        )
    # Never redirect to an unvalidated URI.
    assert response.status_code == 400, variant
    assert "location" not in response.headers


# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------


async def test_pkce_is_mandatory(mcp):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        response = await http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "state": "s",
            },
        )
    query = parse_qs(urlparse(response.headers.get("location", "")).query)
    assert "code" not in query and not response.headers.get("location", "").startswith(
        f"{PUBLIC_URL}/oauth/login"
    )


@pytest.mark.parametrize(
    "challenge", ["a", "short-challenge", "x" * 42, "!" * 43, "x" * 129]
)
async def test_malformed_code_challenge_is_refused(mcp, challenge):
    """A challenge that is not a base64url SHA-256 digest (43 chars) is refused."""
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        response = await authorize(http, client_id, challenge)
    location = response.headers.get("location", "")
    assert not location.startswith(f"{PUBLIC_URL}/oauth/login"), challenge


async def test_token_without_verifier_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, _, code, _ = await full_login(http, user)
        response = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
            },
        )
    assert response.status_code == 400 and response.json()["error"] == "invalid_request"


async def test_verifier_from_another_flow_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier_a, code_a, _ = await full_login(http, user)
        _, verifier_b, code_b, _ = await full_login(http, user)
        crossed = await exchange(http, client_id, code_a, verifier_b)
        assert crossed.status_code == 400 and crossed.json()["error"] in (
            "invalid_grant",
            "invalid_client",
        )
        assert (await exchange(http, client_id, code_a, verifier_a)).status_code == 200


# ---------------------------------------------------------------------------
# Authorization codes
# ---------------------------------------------------------------------------


async def test_code_expires(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        provider = http.mita_service.provider
        real_clock = provider.clock
        provider.clock = lambda: real_clock() - timedelta(
            minutes=10
        )  # issued 10 min ago
        client_id, verifier, code, _ = await full_login(http, user)
        provider.clock = real_clock
        response = await exchange(http, client_id, code, verifier)
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_code_is_bound_to_its_client(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        _, verifier, code, _ = await full_login(http, user)
        other_client = (await register(http)).json()["client_id"]
        response = await exchange(http, other_client, code, verifier)
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_code_is_bound_to_its_redirect_uri(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (
            await register(http, redirect_uris=[REDIRECT, LEGIT_DYNAMIC])
        ).json()["client_id"]
        verifier, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        _, done = await consent(http, login_url, user.email, PASSWORD)
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        response = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LEGIT_DYNAMIC,
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
    assert response.status_code == 400


async def test_token_request_for_another_resource_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        response = await http.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": "https://api.example.test/",
            },
        )
    assert response.status_code == 400 and response.json()["error"] == "invalid_target"


async def test_code_of_user_a_yields_only_user_a(mcp, seed):
    a = await seed.user(name="Alice A")
    await seed.user(name="Bob B")
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, a)
        token = (await exchange(http, client_id, code, verifier)).json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] == str(a.id)
    assert structured(await mcp.call(token, "get_profile"))["name"] == "Alice A"


async def test_failed_exchange_does_not_leave_code_reusable_by_others(
    mcp, seed, connection
):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        assert (await exchange(http, client_id, code, verifier)).status_code == 200
    left = await connection.scalar(
        text("SELECT count(*) FROM mcp_oauth_authorization_codes")
    )
    assert left == 0


# ---------------------------------------------------------------------------
# CSRF / state
# ---------------------------------------------------------------------------


async def test_csrf_token_from_another_browser_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as victim, mcp.http() as attacker:
        client_id = (await register(victim)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(victim, client_id, challenge)).headers["location"]
        req = parse_qs(urlparse(login_url).query)["req"][0]
        await victim.get(login_url)  # victim's cookie
        attacker_page = await attacker.get(login_url)  # attacker's own cookie + token
        response = await victim.post(
            "/oauth/login",
            data={
                "req": req,
                "csrf": csrf_from(attacker_page.text),
                "email": user.email,
                "password": PASSWORD,
                "action": "allow",
            },
        )
    assert response.status_code == 400 and "location" not in response.headers


async def test_get_cannot_complete_consent(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        response = await http.get(
            login_url + f"&email={user.email}&password={PASSWORD}&action=allow"
        )
    assert response.status_code == 200 and "location" not in response.headers


async def test_expired_pending_request_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        page = await http.get(login_url)
        codec = http.mita_service.provider.pending
        codec._clock = lambda: time.time() + 3600
        req = parse_qs(urlparse(login_url).query)["req"][0]
        response = await http.post(
            "/oauth/login",
            data={
                "req": req,
                "csrf": csrf_from(page.text),
                "email": user.email,
                "password": PASSWORD,
                "action": "allow",
            },
        )
    assert response.status_code == 400 and "expired" in response.text


async def test_state_cannot_be_substituted(mcp):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (
            await authorize(http, client_id, challenge, state="victim-state")
        ).headers["location"]
        req = parse_qs(urlparse(login_url).query)["req"][0]
        raw, sig = req.rsplit(".", 1)
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        payload["state"] = "attacker-state"
        forged = (
            base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode()
            .rstrip("=")
        )
        page = await http.get("/oauth/login", params={"req": f"{forged}.{sig}"})
    assert page.status_code == 400


# ---------------------------------------------------------------------------
# Access tokens at the resource server
# ---------------------------------------------------------------------------


def _claims(user, **overrides):
    now = int(time.time())
    claims = {
        "iss": PUBLIC_URL,
        "sub": str(user.id),
        "aud": RESOURCE,
        "iat": now,
        "nbf": now,
        "exp": now + 600,
        "jti": uuid.uuid4().hex,
        "client_id": "c",
        "scope": "profile:read finance:read",
        "tv": 1,
    }
    claims.update(overrides)
    return claims


def _sign(mcp, claims, headers=None):
    keys = mcp.service.keys
    return jwt.encode(
        claims,
        keys.private_key,
        algorithm="RS256",
        headers=headers or {"kid": keys.kid, "typ": "at+jwt"},
    )


async def _status(mcp, token):
    async with mcp.http(token) as http:
        response = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    return response.status_code


async def test_access_token_attacks_fail_closed(mcp, seed):
    user = await seed.user()
    keys = mcp.service.keys
    now = int(time.time())
    attacks = {
        "nbf in future": _sign(mcp, _claims(user, nbf=now + 3600, iat=now)),
        "iat in future": _sign(mcp, _claims(user, iat=now + 3600, nbf=now)),
        "no exp": _sign(mcp, {k: v for k, v in _claims(user).items() if k != "exp"}),
        "no aud": _sign(mcp, {k: v for k, v in _claims(user).items() if k != "aud"}),
        "aud list without resource": _sign(
            mcp, _claims(user, aud=["https://x.example/mcp"])
        ),
        "unknown kid": _sign(mcp, _claims(user), {"kid": "nope", "typ": "at+jwt"}),
        "no kid": _sign(mcp, _claims(user), {"typ": "at+jwt"}),
        "id-token typ": _sign(mcp, _claims(user), {"kid": keys.kid, "typ": "JWT"}),
        "alg none": jwt.encode(
            _claims(user),
            None,
            algorithm="none",
            headers={"kid": keys.kid, "typ": "at+jwt"},
        ),
        "empty": "",
        "refresh-token shaped": secrets.token_urlsafe(48),
    }
    for name, token in attacks.items():
        assert await _status(mcp, token) == 401, name


async def test_refresh_token_and_code_are_not_access_tokens(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
    assert await _status(mcp, tokens["refresh_token"]) == 401
    assert await _status(mcp, code) == 401


async def test_unknown_subject_is_auth_error(mcp, seed):
    ghost = type("U", (), {"id": uuid.uuid4()})()
    result = await mcp.call(_sign(mcp, _claims(ghost)), "list_transactions")
    assert result.is_error and result.structured_content["error"]["category"] == "auth"


# The reverse boundary (an MCP token at the mobile API) is tested in the API's
# own environment: app/tests/test_mcp_token_boundary.py.


# ---------------------------------------------------------------------------
# Scope escalation
# ---------------------------------------------------------------------------


async def test_authorize_with_unregistered_scope_is_refused(mcp):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        response = await authorize(
            http, client_id, challenge, scope="finance:read admin:system"
        )
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query.get("error") == ["invalid_scope"]


async def test_refresh_cannot_widen_scope(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http, scope="profile:read")).json()["client_id"]
        verifier, challenge = pkce()
        login_url = (
            await authorize(http, client_id, challenge, scope="profile:read")
        ).headers["location"]
        _, done = await consent(http, login_url, user.email, PASSWORD)
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        tokens = (await exchange(http, client_id, code, verifier)).json()
        assert tokens["scope"] == "profile:read"
        widened = await http.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
                "scope": "profile:read finance:read",
            },
        )
    assert widened.status_code == 400 and widened.json()["error"] == "invalid_scope"
    result = await mcp.call(tokens["access_token"], "get_budget_status")
    assert (
        result.is_error
        and result.structured_content["error"]["category"] == "forbidden"
    )


async def test_narrowed_refresh_stays_narrow(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        narrow = (
            await http.post(
                "/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "client_id": client_id,
                    "scope": "profile:read",
                },
            )
        ).json()
        assert narrow["scope"] == "profile:read"
        back = await http.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": narrow["refresh_token"],
                "client_id": client_id,
                "scope": "finance:read",
            },
        )
    assert back.status_code == 400 and back.json()["error"] == "invalid_scope"


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------


async def test_refresh_token_of_another_client_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        other = (await register(http)).json()["client_id"]
        response = await refresh(http, other, tokens["refresh_token"])
        assert response.status_code == 400
        # The rightful client still can (a foreign presentation is not reuse).
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 200


async def test_expired_refresh_token_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        provider = http.mita_service.provider
        real_clock = provider.clock
        client_id, verifier, code, _ = await full_login(http, user)
        provider.clock = lambda: real_clock() - timedelta(days=31)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        provider.clock = real_clock
        response = await refresh(http, client_id, tokens["refresh_token"])
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_refreshed_access_token_keeps_resource_binding(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        response = await http.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
                "resource": "https://api.example.test/",
            },
        )
    assert response.status_code == 400 and response.json()["error"] == "invalid_target"


# ---------------------------------------------------------------------------
# Revocation: password change / session version / deletion
# ---------------------------------------------------------------------------


async def test_any_password_change_ends_chatgpt_access(mcp, seed):
    """Every password-changing path must end ChatGPT access — including
    /reset-password, whose token_version bump is best-effort (fail-open)."""
    from app.core.password_security import hash_password_sync

    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        assert not (await mcp.call(tokens["access_token"], "get_profile")).is_error
        await seed.connection.execute(
            text("UPDATE users SET password_hash = :h WHERE id = :id"),
            {"h": hash_password_sync("A-New-Password-2026!"), "id": user.id},
        )
        result = await mcp.call(tokens["access_token"], "get_profile")
        assert (
            result.is_error and result.structured_content["error"]["category"] == "auth"
        )
        response = await refresh(http, client_id, tokens["refresh_token"])
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_token_version_bump_ends_access_and_refresh(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        await seed.bump_token_version(user)
        assert (await mcp.call(tokens["access_token"], "get_profile")).is_error
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 400


async def test_account_deletion_ends_access_and_refresh(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        await seed.delete_user(user)
        assert (await mcp.call(tokens["access_token"], "get_profile")).is_error
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 400


async def test_revoking_refresh_token_does_not_kill_live_access_token(mcp, seed):
    """Documented limit: /revoke ends renewal; the current JWT works until it
    expires (<= MCP_ACCESS_TOKEN_TTL_SECONDS)."""
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        await http.post(
            "/revoke",
            data={
                "token": tokens["refresh_token"],
                "client_id": client_id,
                "client_secret": "",
            },
        )
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 400
    assert not (await mcp.call(tokens["access_token"], "get_profile")).is_error


# ---------------------------------------------------------------------------
# Dynamic client registration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"grant_types": ["authorization_code", "password"]},
        {"grant_types": ["authorization_code", "client_credentials"]},
        {"grant_types": ["authorization_code", "implicit"]},
        {
            "grant_types": [
                "authorization_code",
                "urn:ietf:params:oauth:grant-type:device_code",
            ]
        },
        {"response_types": ["code", "token"]},
        {"response_types": ["token"]},
        {"token_endpoint_auth_method": "private_key_jwt"},
        {"token_endpoint_auth_method": "client_secret_jwt"},
        {"jwks_uri": "https://evil.example/jwks"},
        {"jwks": {"keys": []}},
        {"client_name": "x" * 101},
        {"client_uri": "https://evil.example/" + "a" * 5000},
        {"contacts": ["a@b.c"] * 500},
    ],
)
async def test_registration_rejects_unneeded_or_dangerous_metadata(mcp, extra):
    async with mcp.http() as http:
        response = await register(http, **extra)
    assert response.status_code == 400, (extra, response.text)


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"{",
        b"[]",
        b'{"redirect_uris": "https://chatgpt.com/connector_platform_oauth_redirect"}',
    ],
)
async def test_registration_rejects_malformed_json(mcp, body):
    async with mcp.http() as http:
        response = await http.post(
            "/register", content=body, headers={"content-type": "application/json"}
        )
    assert response.status_code == 400


async def test_registration_is_rate_limited(make_service):
    from tests_mcp.conftest import Harness, make_settings

    harness = Harness(make_service, make_settings(oauth_requests_per_minute=5))
    async with harness.http() as http:
        codes = [(await register(http)).status_code for _ in range(7)]
    assert codes[:5] == [201] * 5 and codes[5:] == [429, 429]


# ---------------------------------------------------------------------------
# Consent page: enumeration, lockout, logging
# ---------------------------------------------------------------------------


async def test_unknown_email_costs_a_password_check(mcp, monkeypatch):
    """Timing: an unknown e-mail must not answer faster than a wrong password."""
    import app.services.credential_verification as cv

    calls = []
    real = cv.verify_password_async

    async def counting(password, hashed):
        calls.append(hashed)
        return await real(password, hashed)

    monkeypatch.setattr(cv, "verify_password_async", counting)
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        await consent(http, login_url, "nobody-here@example.test", PASSWORD)
    assert len(calls) == 1


async def test_lockout_does_not_reveal_that_an_account_exists(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        for _ in range(6):
            _, locked = await consent(http, login_url, user.email, "wrong-password")
        for _ in range(6):
            _, unknown = await consent(
                http, login_url, "ghost@example.test", "wrong-password"
            )

    def error_of(page):
        return page.text.split('role="alert">')[1].split("</p>")[0]

    assert error_of(locked) == error_of(unknown)


async def test_consent_page_rate_limit(make_service, seed):
    from tests_mcp.conftest import Harness, make_settings

    harness = Harness(make_service, make_settings(login_attempts_per_minute=2))
    user = await seed.user()
    async with harness.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        statuses = [
            (await consent(http, login_url, user.email, "wrong"))[1].status_code
            for _ in range(3)
        ]
    assert statuses == [400, 400, 429]


async def test_oauth_flow_logs_no_secrets(mcp, seed, caplog):
    from app.mcp.observability import JsonFormatter

    user = await seed.user()
    caplog.set_level(logging.DEBUG)
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        rotated = (await refresh(http, client_id, tokens["refresh_token"])).json()
        await consent(
            http,
            (await authorize(http, client_id, pkce()[1])).headers["location"],
            user.email,
            "wrong-pw-123",
        )
    rendered = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    for secret in (
        code,
        verifier,
        tokens["access_token"],
        tokens["refresh_token"],
        rotated["refresh_token"],
        PASSWORD,
        "wrong-pw-123",
        user.email,
    ):
        assert secret not in rendered


# ---------------------------------------------------------------------------
# Per-IP limits: which address a request counts against
# ---------------------------------------------------------------------------
#
# What Railway's HTTP edge delivered on staging (2026-10-28, a temporary
# header-shape probe in the staging project and region; no address printed):
# exactly one X-Real-IP, the client's address, whatever the client had sent
# under that name (forged, repeated, comma-separated, IPv6); X-Forwarded-For
# rebuilt as "<client>, <edge address>" with the edge address rotating over at
# least four values; a TCP peer that changed from request to request. The
# limits counted by the last X-Forwarded-For hop, so one client got a new
# bucket for most requests and /authorize never answered 429 there.

CLIENT_A, CLIENT_B = "198.51.100.7", "198.51.100.8"  # two real clients
EDGE_HOPS = ("192.0.2.11", "192.0.2.12", "192.0.2.13", "192.0.2.14")
FORGED = "203.0.113.66"  # what a caller writes to pick a bucket


class RailwayEdge:
    """Railway's HTTP edge as observed: X-Real-IP and X-Forwarded-For are
    replaced whatever the client sent, X-Forwarded-For is "<client>, <edge
    hop>" with the hop rotating, X-Forwarded-Proto is https, and the TCP peer
    is an internal address that changes per request. Other headers (Forwarded,
    True-Client-IP...) pass through as the client wrote them."""

    REPLACED = {b"x-real-ip", b"x-forwarded-for", b"x-forwarded-proto"}

    def __init__(self, app, client: str) -> None:
        self.app, self.client, self.requests = app, client, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            self.requests += 1
            n = self.requests
            hop = EDGE_HOPS[n % len(EDGE_HOPS)]
            scope = dict(
                scope,
                headers=[(k, v) for k, v in scope["headers"] if k not in self.REPLACED]
                + [
                    (b"x-real-ip", self.client.encode()),
                    (b"x-forwarded-for", f"{self.client}, {hop}".encode()),
                    (b"x-forwarded-proto", b"https"),
                ],
                client=(f"100.64.{n % 200}.{n % 7 + 1}", 30000 + n),
            )
        await self.app(scope, receive, send)


@asynccontextmanager
async def one_service(make_service, settings):
    """A fresh service (fresh limiters) and ``connect``: ``connect(ip)`` opens a
    client arriving through RailwayEdge as the real client ``ip``,
    ``connect(peer=...)`` one connecting directly from that TCP address."""
    service = make_service(settings)
    async with started(service), AsyncExitStack() as stack:

        async def connect(ip=None, *, peer="127.0.0.1"):
            app = RailwayEdge(service.app, ip) if ip else service.app
            return await stack.enter_async_context(
                httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app, client=(peer, 50000)),
                    base_url=PUBLIC_URL,
                    follow_redirects=False,
                )
            )

        yield connect


def test_one_client_keeps_one_address_while_the_edge_hop_changes():
    keys, last_hops = set(), set()
    for n in range(8):
        forwarded = f"{CLIENT_A}, {EDGE_HOPS[n % len(EDGE_HOPS)]}"
        headers = [
            (b"x-real-ip", CLIENT_A.encode()),
            (b"x-forwarded-for", forwarded.encode()),
        ]
        keys.add(client_address(headers, f"100.64.0.{n + 1}", "x-real-ip"))
        last_hops.add(forwarded.split(",")[-1].strip())
    assert keys == {CLIENT_A}
    # The old key, the last X-Forwarded-For hop: four buckets for one client.
    assert len(last_hops) == 4


async def test_authorize_answers_429_on_request_31_behind_railway(make_service):
    settings = make_settings()
    assert settings.oauth_requests_per_minute == 30  # the configured limit
    async with one_service(make_service, settings) as connect:
        a = await connect(CLIENT_A)
        statuses = [(await a.get("/authorize")).status_code for _ in range(31)]
        other = await connect(CLIENT_B)
        fresh = (await other.get("/authorize")).status_code
    assert statuses == [400] * 30 + [429]
    assert fresh == 400


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/authorize"),
        ("POST", "/register"),
        ("POST", "/token"),
        ("POST", "/revoke"),
    ],
)
async def test_every_oauth_endpoint_counts_the_client_not_the_edge_hop(
    make_service, method, path
):
    async with one_service(
        make_service, make_settings(oauth_requests_per_minute=2)
    ) as connect:
        a, b = await connect(CLIENT_A), await connect(CLIENT_B)
        statuses = [(await a.request(method, path)).status_code for _ in range(3)]
        other = (await b.request(method, path)).status_code
    assert 429 not in statuses[:2] and statuses[2] == 429, statuses
    assert other != 429


async def test_forged_forwarding_headers_do_not_leave_the_bucket(make_service):
    async with one_service(
        make_service, make_settings(oauth_requests_per_minute=3)
    ) as connect:
        a = await connect(CLIENT_A)
        allowed = [(await a.get("/authorize")).status_code for _ in range(3)]
        forged = [
            (await a.get("/authorize", headers=headers)).status_code
            for headers in (
                {"X-Real-IP": FORGED},
                {"X-Forwarded-For": f"{FORGED}, {FORGED}"},
                {"Forwarded": f"for={FORGED}", "True-Client-IP": FORGED},
            )
        ]
    assert allowed == [400, 400, 400]
    assert forged == [429, 429, 429]


@pytest.mark.parametrize(
    "variants",
    [
        # a second X-Real-IP line, with a new value every time
        [
            [
                (b"x-real-ip", f"203.0.113.{i}".encode()),
                (b"x-real-ip", CLIENT_A.encode()),
            ]
            for i in range(4)
        ],
        # not one IP address
        [
            [(b"x-real-ip", value)]
            for value in (
                b"203.0.113.5:443",
                b"203.0.113.5, 203.0.113.6",
                b"not-an-address",
                b"[2001:db8::1]",
            )
        ],
    ],
    ids=["repeated", "malformed"],
)
async def test_an_unusable_client_address_header_cannot_pick_a_bucket(
    make_service, variants
):
    """A header Railway's edge never sends (it reached the app another way):
    every such request shares one bucket, whatever the value or the peer."""
    async with one_service(
        make_service, make_settings(oauth_requests_per_minute=3)
    ) as connect:
        statuses = []
        for i, headers in enumerate(variants):
            direct = await connect(peer=f"127.0.0.{i + 1}")
            statuses.append(
                (await direct.get("/authorize", headers=headers)).status_code
            )
    assert statuses == [400, 400, 400, 429]
    assert client_address(variants[0], "127.0.0.1", "x-real-ip") == (
        UNUSABLE_CLIENT_ADDRESS
    )


async def test_direct_requests_count_by_their_connection(make_service):
    """No X-Real-IP: not through the edge (a local run, a test, the private
    network). The TCP peer counts; forwarded headers never do."""
    async with one_service(
        make_service, make_settings(oauth_requests_per_minute=3)
    ) as connect:
        local = await connect(peer="127.0.0.1")
        statuses = [
            (
                await local.get(
                    "/authorize",
                    headers={
                        "X-Forwarded-For": f"203.0.113.{i}",
                        "Forwarded": f"for=203.0.113.{i}",
                    },
                )
            ).status_code
            for i in range(4)
        ]
        other = await connect(peer="127.0.0.2")
        fresh = (await other.get("/authorize")).status_code
    assert statuses == [400, 400, 400, 429]
    assert fresh == 400


async def test_x_real_ip_is_ignored_when_no_header_is_trusted(make_service):
    """MCP_CLIENT_IP_HEADER= (the service reached directly): nothing the
    client writes can choose its bucket."""
    settings = make_settings(oauth_requests_per_minute=3, client_ip_header="")
    async with one_service(make_service, settings) as connect:
        direct = await connect(peer="127.0.0.1")
        statuses = [
            (
                await direct.get("/authorize", headers={"X-Real-IP": f"203.0.113.{i}"})
            ).status_code
            for i in range(4)
        ]
    assert statuses == [400, 400, 400, 429]


@pytest.mark.parametrize(
    "value,key",
    [
        ("198.51.100.7", "198.51.100.7"),
        (" 198.51.100.7 ", "198.51.100.7"),
        ("2001:DB8::1", "2001:db8::1"),
        ("2001:db8:0:0:0:0:0:1", "2001:db8::1"),
        ("::ffff:198.51.100.7", "198.51.100.7"),
    ],
)
def test_one_address_has_one_key_however_it_is_written(value, key):
    assert (
        client_address([(b"x-real-ip", value.encode())], "100.64.0.1", "x-real-ip")
        == key
    )
    assert client_address([], value.strip(), "x-real-ip") == key


def test_no_header_and_no_peer_is_one_bucket():
    assert client_address([], None, "x-real-ip") == "unknown"


def test_the_client_address_header_is_configured_safely(monkeypatch):
    from app.mcp.config import load_settings
    from tests_mcp.test_secret_separation import _env_for

    _env_for(monkeypatch, "staging")
    monkeypatch.delenv("MCP_CLIENT_IP_HEADER", raising=False)
    monkeypatch.delenv("RAILWAY_TCP_PROXY_PORT", raising=False)
    assert load_settings().client_ip_header == "x-real-ip"
    monkeypatch.setenv("MCP_CLIENT_IP_HEADER", "")
    assert load_settings().client_ip_header == ""
    for chain in ("X-Forwarded-For", "forwarded", "x real ip"):
        monkeypatch.setenv("MCP_CLIENT_IP_HEADER", chain)
        with pytest.raises(McpConfigError, match="MCP_CLIENT_IP_HEADER"):
            load_settings()
    # A Railway TCP proxy reaches the service without the HTTP edge: there the
    # caller could write X-Real-IP itself, so the service refuses to start.
    monkeypatch.delenv("MCP_CLIENT_IP_HEADER")
    monkeypatch.setenv("RAILWAY_TCP_PROXY_PORT", "15140")
    with pytest.raises(McpConfigError, match="TCP proxy"):
        load_settings()


async def test_served_app_limits_by_the_tcp_peer_and_keeps_https(make_service):
    """The container's own server options, over real TCP. uvicorn must not
    replace the client with an X-Forwarded-For entry (proxy_headers with
    forwarded_allow_ips="*" did, for any caller, which would let a request
    without X-Real-IP choose its bucket), and redirects behind Railway's TLS
    must stay https."""
    import uvicorn

    from app.mcp.__main__ import ForwardedProto, serve_options

    async def serve(**overrides):
        service = make_service(make_settings(oauth_requests_per_minute=3))
        options = {**serve_options(0), "host": "127.0.0.1", **overrides}
        server = uvicorn.Server(uvicorn.Config(ForwardedProto(service.app), **options))
        task = asyncio.create_task(server.serve())
        while not server.started:
            assert not task.done()
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        try:
            async with httpx2.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
                statuses = [
                    (
                        await http.get(
                            "/authorize",
                            headers={"X-Forwarded-For": f"203.0.113.{i}"},
                        )
                    ).status_code
                    for i in range(4)
                ]
                behind_tls = await http.get(
                    "/authorize/", headers={"X-Forwarded-Proto": "https"}
                )
                plain = await http.get("/authorize/")
        finally:
            server.should_exit = True
            await task
        return statuses, behind_tls, plain

    statuses, behind_tls, plain = await serve()
    assert statuses == [400, 400, 400, 429]
    assert behind_tls.status_code == 307
    assert behind_tls.headers["location"].startswith("https://127.0.0.1:")
    assert plain.headers["location"].startswith("http://127.0.0.1:")
    # The options this replaced: every forged X-Forwarded-For was a new client.
    old, _, _ = await serve(proxy_headers=True, forwarded_allow_ips="*")
    assert 429 not in old


async def test_sign_in_limit_counts_the_client_behind_railway(make_service, seed):
    user = await seed.user()
    async with one_service(
        make_service, make_settings(login_attempts_per_minute=2)
    ) as connect:
        a, b = await connect(CLIENT_A), await connect(CLIENT_B)
        client_id = (await register(a)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(a, client_id, challenge)).headers["location"]
        statuses = [
            (await consent(a, login_url, user.email, "wrong"))[1].status_code
            for _ in range(3)
        ]
        _, other = await consent(b, login_url, user.email, "wrong")
    assert statuses == [400, 400, 429]
    assert other.status_code == 400


async def test_sign_up_limit_counts_the_client_behind_railway(make_service, connection):
    from tests_mcp.test_registration import _login_url, _sign_up

    async with one_service(
        make_service, make_settings(registrations_per_hour=2)
    ) as connect:
        a, b = await connect(CLIENT_A), await connect(CLIENT_B)
        statuses = []
        for i in range(3):
            _, _, login_url = await _login_url(a)
            _, response = await _sign_up(a, login_url, f"edge{i}@example.test")
            statuses.append(response.status_code)
        _, _, login_url = await _login_url(b)
        _, other = await _sign_up(b, login_url, "edge-other@example.test")
    assert statuses == [302, 302, 429]
    assert other.status_code == 302


async def test_lockout_counts_the_account_across_client_addresses(
    make_service, seed, connection
):
    """Five wrong passwords from five addresses still lock the account: the
    lockout is per account, in the database, not per address."""
    user = await seed.user()
    async with one_service(make_service, make_settings()) as connect:
        clients = [await connect(f"198.51.100.{20 + i}") for i in range(6)]
        client_id = (await register(clients[0])).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(clients[0], client_id, challenge)).headers[
            "location"
        ]
        for http in clients[:5]:
            _, response = await consent(http, login_url, user.email, "wrong-password")
            assert response.status_code == 400
        _, last = await consent(clients[5], login_url, user.email, PASSWORD)
    assert last.status_code == 400 and "Sign-in failed" in last.text
    row = (
        await connection.execute(
            text(
                "SELECT failed_login_attempts, account_locked_until IS NOT NULL "
                "FROM users WHERE id = :id"
            ),
            {"id": user.id},
        )
    ).one()
    assert row == (5, True)


async def test_connecting_through_railway_works_below_the_limits(make_service, seed):
    user = await seed.user()
    async with one_service(make_service, make_settings()) as connect:
        a = await connect(CLIENT_A)
        client_id, verifier, code, _ = await full_login(a, user)
        tokens = await exchange(a, client_id, code, verifier)
    assert tokens.status_code == 200
    assert tokens.json()["token_type"].lower() == "bearer"

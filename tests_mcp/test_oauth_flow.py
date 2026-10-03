"""The built-in authorization server, end to end, as ChatGPT drives it."""

import base64
import hashlib
import re
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text

from tests_mcp.conftest import PASSWORD, PUBLIC_URL, structured

REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
RESOURCE = f"{PUBLIC_URL}/mcp"


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


async def register(http, redirect_uris=(REDIRECT,), **extra):
    return await http.post(
        "/register",
        json={
            "redirect_uris": list(redirect_uris),
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "ChatGPT",
            **extra,
        },
    )


async def authorize(
    http,
    client_id,
    challenge,
    *,
    resource=RESOURCE,
    state="st-1",
    scope="profile:read finance:read",
):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": scope,
    }
    if resource is not None:
        params["resource"] = resource
    return await http.get("/authorize", params=params)


def csrf_from(html: str) -> str:
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


async def consent(http, login_url, email, password, action="allow"):
    page = await http.get(login_url)
    assert page.status_code == 200, page.text
    req = parse_qs(urlparse(login_url).query)["req"][0]
    return page, await http.post(
        "/oauth/login",
        data={
            "req": req,
            "csrf": csrf_from(page.text),
            "email": email,
            "password": password,
            "action": action,
        },
    )


async def full_login(http, user, *, challenge=None):
    verifier, challenge_ = pkce()
    challenge = challenge or challenge_
    client_id = (await register(http)).json()["client_id"]
    redirect = await authorize(http, client_id, challenge)
    assert redirect.status_code == 302, redirect.text
    _, done = await consent(http, redirect.headers["location"], user.email, PASSWORD)
    assert done.status_code == 302, done.text
    location = urlparse(done.headers["location"])
    query = parse_qs(location.query)
    return client_id, verifier, query["code"][0], query


async def exchange(http, client_id, code, verifier):
    return await http.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )


async def refresh(http, client_id, refresh_token):
    return await http.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )


async def test_metadata_documents(mcp):
    async with mcp.http() as http:
        prm = (await http.get("/.well-known/oauth-protected-resource/mcp")).json()
        assert prm["resource"] == RESOURCE
        assert prm["authorization_servers"] == [PUBLIC_URL]
        assert prm["scopes_supported"] == ["profile:read", "finance:read"]
        asm = (await http.get("/.well-known/oauth-authorization-server")).json()
        assert asm["issuer"] == PUBLIC_URL
        assert asm["code_challenge_methods_supported"] == ["S256"]
        assert asm["registration_endpoint"] == f"{PUBLIC_URL}/register"
        assert set(asm["scopes_supported"]) == {"profile:read", "finance:read"}
        assert "authorization_code" in asm["grant_types_supported"]
        jwks = (await http.get("/.well-known/jwks.json")).json()
        assert jwks["keys"][0]["alg"] == "RS256" and "d" not in jwks["keys"][0]


async def test_full_flow_then_tool_call(mcp, seed):
    user = await seed.user(name="Flow User")
    async with mcp.http() as http:
        client_id, verifier, code, query = await full_login(http, user)
        assert query["state"] == ["st-1"]
        tokens = await exchange(http, client_id, code, verifier)
        assert tokens.status_code == 200, tokens.text
        body = tokens.json()
        assert body["token_type"].lower() == "bearer"
        assert body["scope"] == "profile:read finance:read"
        assert 0 < body["expires_in"] <= 900
        assert tokens.headers["cache-control"] == "no-store"
    profile = structured(await mcp.call(body["access_token"], "get_profile"))
    assert profile["name"] == "Flow User"


async def test_code_is_single_use(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        assert (await exchange(http, client_id, code, verifier)).status_code == 200
        replay = await exchange(http, client_id, code, verifier)
        assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant"


async def test_wrong_pkce_verifier_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, _, code, _ = await full_login(http, user)
        bad = await exchange(http, client_id, code, secrets.token_urlsafe(48))
        assert bad.status_code == 400 and bad.json()["error"] == "invalid_grant"


async def test_plain_pkce_method_is_refused(mcp, seed):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        response = await http.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "code_challenge": "abc",
                "code_challenge_method": "plain",
                "state": "s",
            },
        )
        assert response.status_code in (302, 400)
        assert "code" not in parse_qs(
            urlparse(response.headers.get("location", "")).query
        )


async def test_registration_rejects_non_chatgpt_redirects(mcp):
    async with mcp.http() as http:
        for uri in (
            "https://evil.example/cb",
            "https://chatgpt.com.evil.example/cb",
            "http://chatgpt.com/connector/oauth/x",
        ):
            response = await register(http, redirect_uris=[uri])
            assert (
                response.status_code == 400
                and response.json()["error"] == "invalid_redirect_uri"
            ), uri
        ok = await register(
            http, redirect_uris=["https://chatgpt.com/connector/oauth/abc123"]
        )
        assert ok.status_code == 201


async def test_registration_rejects_unsupported_scopes(mcp):
    async with mcp.http() as http:
        response = await register(http, scope="finance:read write:transactions")
        assert response.status_code == 400


async def test_foreign_resource_is_refused(mcp):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        response = await authorize(
            http, client_id, challenge, resource="https://api.example.test/"
        )
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["error"] == ["invalid_target"] and "code" not in query


async def test_missing_resource_defaults_to_this_server(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        verifier, challenge = pkce()
        redirect = await authorize(http, client_id, challenge, resource=None)
        _, done = await consent(
            http, redirect.headers["location"], user.email, PASSWORD
        )
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        token = (await exchange(http, client_id, code, verifier)).json()["access_token"]
    assert not (await mcp.call(token, "get_profile")).is_error


async def test_consent_page_is_hardened(mcp):
    async with mcp.http() as http:
        client_id = (
            await register(http, client_name="<script>alert(1)</script>")
        ).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        page = await http.get(login_url)
    assert (
        "<script>alert(1)</script>" not in page.text and "&lt;script&gt;" in page.text
    )
    csp = page.headers["content-security-policy"]
    assert (
        "frame-ancestors 'none'" in csp
        and "script-src" not in csp
        and "default-src 'none'" in csp
    )
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["cache-control"] == "no-store"
    cookie = page.headers["set-cookie"]
    assert cookie.startswith("__Host-") and "Secure" in cookie and "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "read-only" in page.text.lower() and "chatgpt.com" in page.text


async def test_post_without_csrf_cookie_is_refused(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        page = await http.get(login_url)
        req = parse_qs(urlparse(login_url).query)["req"][0]
        http.cookies.clear()
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
    assert response.status_code == 400 and "location" not in response.headers


async def test_tampered_pending_request_is_refused(mcp):
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        req = parse_qs(urlparse(login_url).query)["req"][0]
        raw, sig = req.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).replace(
            b"chatgpt.com", b"evil.examp"
        )
        forged = base64.urlsafe_b64encode(payload).decode().rstrip("=") + "." + sig
        page = await http.get("/oauth/login", params={"req": forged})
    assert page.status_code == 400 and "expired" in page.text


async def test_deny_returns_access_denied(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (
            await authorize(http, client_id, challenge, state="keep-me")
        ).headers["location"]
        _, response = await consent(http, login_url, user.email, "", action="deny")
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query == {"error": ["access_denied"], "state": ["keep-me"]}


async def test_wrong_password_and_shared_lockout(mcp, seed, connection):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        for attempt in range(5):
            _, response = await consent(http, login_url, user.email, "wrong-password")
            assert response.status_code == 400 and "location" not in response.headers
        # Locked now even with the right password — the same counter the
        # mobile login uses. The message is the generic one (no enumeration).
        _, response = await consent(http, login_url, user.email, PASSWORD)
        assert response.status_code == 400 and "location" not in response.headers
        assert "Sign-in failed" in response.text
    row = (
        await connection.execute(
            text(
                "SELECT failed_login_attempts, account_locked_until IS NOT NULL FROM users WHERE id = :id"
            ),
            {"id": user.id},
        )
    ).one()
    assert row == (5, True)


async def test_unknown_email_and_wrong_password_look_the_same(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id = (await register(http)).json()["client_id"]
        _, challenge = pkce()
        login_url = (await authorize(http, client_id, challenge)).headers["location"]
        _, unknown = await consent(http, login_url, "nobody@example.test", PASSWORD)
        _, wrong = await consent(http, login_url, user.email, "nope-nope-nope")
    assert "Sign-in failed" in unknown.text and "Sign-in failed" in wrong.text


async def test_refresh_rotation_and_reuse_detection(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        first = (await exchange(http, client_id, code, verifier)).json()
        second = await refresh(http, client_id, first["refresh_token"])
        assert second.status_code == 200, second.text
        second = second.json()
        assert second["refresh_token"] != first["refresh_token"]
        # The rotated token comes back: someone has a copy → the whole family dies.
        reuse = await refresh(http, client_id, first["refresh_token"])
        assert reuse.status_code == 400 and reuse.json()["error"] == "invalid_grant"
        after = await refresh(http, client_id, second["refresh_token"])
        assert after.status_code == 400
    assert not (
        await mcp.call(second["access_token"], "get_profile")
    ).is_error  # ≤15 min access remains


async def test_refresh_bound_to_mita_session(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        await seed.bump_token_version(user)  # logout-all / password reset in the app
        response = await refresh(http, client_id, tokens["refresh_token"])
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_code_issued_before_logout_all_cannot_be_exchanged(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        await seed.bump_token_version(user)
        response = await exchange(http, client_id, code, verifier)
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_revocation_endpoint(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        # mcp 2.2.0's RevocationRequest declares `client_secret: str | None`
        # without a default, so even a public client must send the field.
        revoked = await http.post(
            "/revoke",
            data={
                "token": tokens["refresh_token"],
                "client_id": client_id,
                "client_secret": "",
            },
        )
        assert revoked.status_code == 200
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 400


async def test_secrets_are_stored_hashed(mcp, seed, connection):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        code_rows = (
            (
                await connection.execute(
                    text("SELECT code_hash FROM mcp_oauth_authorization_codes")
                )
            )
            .scalars()
            .all()
        )
        assert (
            code not in code_rows
            and hashlib.sha256(code.encode()).hexdigest() in code_rows
        )
        tokens = (await exchange(http, client_id, code, verifier)).json()
    stored = (
        (
            await connection.execute(
                text("SELECT token_hash FROM mcp_oauth_refresh_tokens")
            )
        )
        .scalars()
        .all()
    )
    assert tokens["refresh_token"] not in stored
    assert hashlib.sha256(tokens["refresh_token"].encode()).hexdigest() in stored


async def test_account_deletion_cascades_oauth_rows(mcp, seed, connection):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        await exchange(http, client_id, code, verifier)
    await seed.delete_user(user)
    left = await connection.scalar(
        text("SELECT count(*) FROM mcp_oauth_refresh_tokens WHERE user_id = :u"),
        {"u": user.id},
    )
    assert left == 0


@pytest.mark.parametrize("hops,expected", [(1, "203.0.113.9"), (0, "testclient")])
def test_client_ip_respects_trusted_proxy_hops(hops, expected):
    from starlette.requests import Request

    from app.mcp.auth.login import client_ip

    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"198.51.100.1, 203.0.113.9")],
        "client": ("testclient", 1234),
    }
    assert client_ip(Request(scope), hops) == expected

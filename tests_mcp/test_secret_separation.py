"""MCP_GRANT_FINGERPRINT_SECRET alone binds grants; the CSRF secret does not.

Rotating the grant secret revokes every existing ChatGPT grant (emergency
kill switch). Rotating the login CSRF secret only invalidates open consent
pages and pending authorization links — it must not be what revocation
depends on, and it must not revoke grants by accident.
"""

import pytest

from app.mcp.config import McpConfigError, validate_settings
from tests_mcp.conftest import Harness, make_settings, structured
from tests_mcp.test_oauth_flow import exchange, full_login, refresh


async def _grant(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
    return client_id, tokens


async def test_rotating_grant_secret_revokes_access_and_refresh(
    make_service, mcp, seed
):
    client_id, tokens = await _grant(mcp, seed)
    rotated = Harness(make_service, make_settings(grant_fingerprint_secret="h" * 48))
    result = await rotated.call(tokens["access_token"], "get_profile")
    assert result.is_error and result.structured_content["error"]["category"] == "auth"
    async with rotated.http() as http:
        response = await refresh(http, client_id, tokens["refresh_token"])
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_rotating_csrf_secret_keeps_existing_grants(make_service, mcp, seed):
    client_id, tokens = await _grant(mcp, seed)
    rotated = Harness(make_service, make_settings(login_csrf_secret="d" * 48))
    assert structured(await rotated.call(tokens["access_token"], "get_profile"))["id"]
    async with rotated.http() as http:
        response = await refresh(http, client_id, tokens["refresh_token"])
    assert response.status_code == 200


async def test_password_change_still_revokes_with_separate_secret(mcp, seed):
    from sqlalchemy import text

    from app.core.password_security import hash_password_sync

    user = await seed.user()
    async with mcp.http() as http:
        client_id, verifier, code, _ = await full_login(http, user)
        tokens = (await exchange(http, client_id, code, verifier)).json()
        await seed.connection.execute(
            text("UPDATE users SET password_hash = :h WHERE id = :id"),
            {"h": hash_password_sync("Another-Password-2026!"), "id": user.id},
        )
        assert (
            await refresh(http, client_id, tokens["refresh_token"])
        ).status_code == 400
    assert (await mcp.call(tokens["access_token"], "get_profile")).is_error


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"grant_fingerprint_secret": ""}, "MCP_GRANT_FINGERPRINT_SECRET"),
        ({"grant_fingerprint_secret": "short"}, "MCP_GRANT_FINGERPRINT_SECRET"),
        ({"login_csrf_secret": "short"}, "MCP_LOGIN_CSRF_SECRET"),
        (
            {"grant_fingerprint_secret": "s" * 40, "login_csrf_secret": "s" * 40},
            "independently generated",
        ),
    ],
)
def test_config_requires_two_independent_strong_secrets(overrides, message):
    with pytest.raises(McpConfigError, match=message):
        validate_settings(make_settings(**overrides))


def test_staging_is_as_strict_as_production(monkeypatch):
    from app.mcp.config import load_settings

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://mcp-staging.example.test")
    monkeypatch.setenv("MCP_OAUTH_PRIVATE_KEY", make_settings().private_key_pem)
    monkeypatch.setenv("MCP_LOGIN_CSRF_SECRET", "c" * 48)
    monkeypatch.setenv("MCP_GRANT_FINGERPRINT_SECRET", "g" * 48)
    with pytest.raises(McpConfigError, match="https"):
        load_settings()
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp-staging.example.test")
    settings = load_settings()
    assert settings.is_production
    from app.mcp.server import _transport_security

    hosts = _transport_security(settings).allowed_hosts
    assert hosts == ["mcp-staging.example.test"]

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
        ({"data_secret": ""}, "MCP_DATA_SECRET"),
        ({"analytics_secret": "short"}, "MCP_ANALYTICS_SECRET"),
        (
            {"data_secret": "s" * 40, "analytics_secret": "s" * 40},
            "independently generated",
        ),
        ({"data_secret": "g" * 48}, "independently generated"),
    ],
)
def test_config_requires_independent_strong_secrets(overrides, message):
    with pytest.raises(McpConfigError, match=message):
        validate_settings(make_settings(**overrides))


def _env_for(monkeypatch, environment: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.test")
    monkeypatch.setenv("MCP_OAUTH_PRIVATE_KEY", make_settings().private_key_pem)
    monkeypatch.setenv("MCP_LOGIN_CSRF_SECRET", "c" * 48)
    monkeypatch.setenv("MCP_GRANT_FINGERPRINT_SECRET", "g" * 48)
    monkeypatch.setenv("MCP_DATA_SECRET", "d" * 48)
    monkeypatch.setenv("MCP_ANALYTICS_SECRET", "a" * 48)
    monkeypatch.setenv("JWT_SECRET", "j" * 48)
    monkeypatch.setenv("SECRET_KEY", "k" * 48)


def test_production_refuses_to_start_without_a_widget_domain(monkeypatch):
    """OpenAI accepts a plugin with UI only with a dedicated component origin
    (_meta.ui.domain): the service that is submitted never runs without one."""
    from app.mcp.config import load_settings

    _env_for(monkeypatch, "production")
    monkeypatch.delenv("MCP_WIDGET_DOMAIN", raising=False)
    with pytest.raises(McpConfigError, match="MCP_WIDGET_DOMAIN"):
        load_settings()
    monkeypatch.setenv("MCP_WIDGET_DOMAIN", "https://mcp.example.test/")
    assert load_settings().widget_domain == "https://mcp.example.test"
    monkeypatch.setenv("MCP_WIDGET_DOMAIN", "https://mcp.example.test/ui")
    with pytest.raises(McpConfigError, match="origin"):
        load_settings()


def test_staging_may_run_without_a_widget_domain(monkeypatch):
    from app.mcp.config import load_settings

    _env_for(monkeypatch, "staging")
    monkeypatch.delenv("MCP_WIDGET_DOMAIN", raising=False)
    assert load_settings().widget_domain == ""


def test_staging_is_as_strict_as_production(monkeypatch):
    from app.mcp.config import load_settings

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://mcp-staging.example.test")
    monkeypatch.setenv("MCP_OAUTH_PRIVATE_KEY", make_settings().private_key_pem)
    monkeypatch.setenv("MCP_LOGIN_CSRF_SECRET", "c" * 48)
    monkeypatch.setenv("MCP_GRANT_FINGERPRINT_SECRET", "g" * 48)
    monkeypatch.setenv("MCP_DATA_SECRET", "d" * 48)
    monkeypatch.setenv("MCP_ANALYTICS_SECRET", "a" * 48)
    with pytest.raises(McpConfigError, match="https"):
        load_settings()
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp-staging.example.test")
    settings = load_settings()
    assert settings.is_production
    from app.mcp.server import _transport_security

    hosts = _transport_security(settings).allowed_hosts
    assert hosts == ["mcp-staging.example.test"]

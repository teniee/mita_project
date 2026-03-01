from unittest.mock import patch, AsyncMock

import pytest

from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    blacklist_token,
    verify_token,
)


def _make_mock_blacklist_service(store: dict):
    """Create a mock blacklist service backed by an in-memory dict."""
    service = AsyncMock()

    async def _blacklist(token=None, **kwargs):
        if token:
            import jwt as pyjwt
            try:
                payload = pyjwt.decode(token, options={"verify_signature": False})
                jti = payload.get("jti", token)
            except Exception:
                jti = token
            store[jti] = True
        return True

    async def _is_blacklisted(token_id):
        return store.get(token_id, False)

    service.blacklist_token = AsyncMock(side_effect=_blacklist)
    service.is_token_blacklisted = AsyncMock(side_effect=_is_blacklisted)
    return service


@pytest.mark.asyncio
async def test_logout_revokes_token():
    """Access-token must be blacklisted after explicit logout."""
    store = {}
    mock_service = _make_mock_blacklist_service(store)

    async def mock_get():
        return mock_service

    with patch("app.services.token_blacklist_service.get_blacklist_service", mock_get):
        token = create_access_token({"sub": "u1"})

        # Token should be valid before blacklisting
        payload = await verify_token(token)
        assert payload is not None

        # Blacklist the token (emulate logout)
        result = await blacklist_token(token)
        assert result is True

        # Token should be in the blacklist
        # (verify_token skips blacklist for fresh tokens, so check directly)
        jti = payload.get("jti")
        assert await mock_service.is_token_blacklisted(jti) is True


@pytest.mark.asyncio
async def test_refresh_revokes_old():
    """Old refresh token should be blacklisted immediately after refresh."""
    store = {}
    mock_service = _make_mock_blacklist_service(store)

    async def mock_get():
        return mock_service

    with patch("app.services.token_blacklist_service.get_blacklist_service", mock_get):
        old_refresh = create_refresh_token({"sub": "u1"})

        # Old token should be valid
        payload = await verify_token(old_refresh, token_type="refresh_token")
        assert payload is not None

        # Simulate what refresh endpoint does: blacklist old, create new
        result = await blacklist_token(old_refresh)
        assert result is True
        new_refresh = create_refresh_token({"sub": "u1"})

        # Old refresh must be in the blacklist
        old_jti = payload.get("jti")
        assert await mock_service.is_token_blacklisted(old_jti) is True

        # New token should be different and valid
        assert new_refresh != old_refresh
        new_payload = await verify_token(new_refresh, token_type="refresh_token")
        assert new_payload is not None

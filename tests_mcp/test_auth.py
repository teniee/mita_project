"""Resource-server authentication: every way a token can be wrong."""

import time
import uuid

import jwt

from app.mcp.auth.keys import generate_private_key_pem
from tests_mcp.conftest import PUBLIC_URL, forge_token, make_settings, structured

RESOURCE = f"{PUBLIC_URL}/mcp"
METADATA = f"{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp"


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
        "client_id": "test-client",
        "scope": "profile:read finance:read",
        "tv": 1,
    }
    claims.update(overrides)
    return claims


def _signed(mcp, claims):
    """A token signed with the REAL key and kid, so only the claim under test is wrong."""
    keys = mcp.service.keys
    return jwt.encode(
        claims,
        keys.private_key,
        algorithm="RS256",
        headers={"kid": keys.kid, "typ": "at+jwt"},
    )


INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "1"},
    },
}
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


async def _post(mcp, token):
    async with mcp.http(token) as http:
        return await http.post("/mcp", json=INIT, headers=HEADERS)


async def test_no_token_is_401_with_resource_metadata(mcp):
    response = await _post(mcp, None)
    assert response.status_code == 401
    www = response.headers["www-authenticate"]
    assert www.startswith("Bearer ")
    assert f'resource_metadata="{METADATA}"' in www


async def test_garbage_token_is_401(mcp):
    assert (await _post(mcp, "not-a-jwt")).status_code == 401


async def test_expired_token_is_401(mcp, seed):
    user = await seed.user()
    past = int(time.time()) - 3600
    token = _signed(mcp, _claims(user, iat=past - 600, nbf=past - 600, exp=past))
    assert (await _post(mcp, token)).status_code == 401


async def test_wrong_issuer_is_401(mcp, seed):
    user = await seed.user()
    assert (
        await _post(mcp, _signed(mcp, _claims(user, iss="https://evil.example")))
    ).status_code == 401


async def test_wrong_audience_is_401(mcp, seed):
    user = await seed.user()
    # A token minted for another resource (e.g. the MITA mobile API) must not work here.
    for aud in (
        "mita-finance-app",
        "https://mcp.example.test/other",
        "https://other.example/mcp",
    ):
        assert (
            await _post(mcp, _signed(mcp, _claims(user, aud=aud)))
        ).status_code == 401, aud


async def test_token_signed_by_another_key_is_401(mcp, seed):
    user = await seed.user()
    foreign = generate_private_key_pem(2048)
    token = forge_token(_claims(user), key_pem=foreign, kid=mcp.service.keys.kid)
    assert (await _post(mcp, token)).status_code == 401


async def test_hs256_token_is_401(mcp, seed):
    """Algorithm confusion: an HS256 token keyed with the public key must fail."""
    user = await seed.user()
    token = jwt.encode(
        _claims(user),
        "secret",
        algorithm="HS256",
        headers={"kid": mcp.service.keys.kid, "typ": "at+jwt"},
    )
    assert (await _post(mcp, token)).status_code == 401


async def test_mita_mobile_app_token_is_401(mcp, seed):
    """The mobile app's HS256 JWT (iss=mita-finance-api) never authenticates here."""
    user = await seed.user()
    mobile = jwt.encode(
        {
            "sub": str(user.id),
            "iss": "mita-finance-api",
            "aud": "mita-finance-app",
            "exp": int(time.time()) + 600,
            "token_type": "access_token",
            "scope": "read:profile",
        },
        "test_jwt_secret_key_min_32_chars_long_for_testing",
        algorithm="HS256",
    )
    assert (await _post(mcp, mobile)).status_code == 401


async def test_token_without_user_subject_is_401(mcp, seed):
    user = await seed.user()
    assert (
        await _post(mcp, _signed(mcp, _claims(user, sub="not-a-uuid")))
    ).status_code == 401


async def test_valid_token_succeeds(mcp, seed):
    user = await seed.user()
    data = structured(await mcp.call(mcp.token(user), "get_profile"))
    assert data["timezone"] == "UTC"


async def test_missing_scope_is_forbidden_with_reauth_hint(mcp, seed):
    user = await seed.user()
    token = mcp.token(user, scopes=["profile:read"])
    result = await mcp.call(token, "list_transactions")
    assert result.is_error
    assert result.structured_content["error"]["category"] == "forbidden"
    www = (result.meta or {})["mcp/www_authenticate"][0]
    assert 'error="insufficient_scope"' in www and 'scope="finance:read"' in www
    # …while the scope it does have still works.
    assert not (await mcp.call(token, "get_profile")).is_error


async def test_unknown_scopes_in_token_are_ignored(mcp, seed):
    user = await seed.user()
    token = _signed(mcp, _claims(user, scope="admin:system write:transactions"))
    result = await mcp.call(token, "list_transactions")
    assert (
        result.is_error
        and result.structured_content["error"]["category"] == "forbidden"
    )


async def test_logout_all_revokes_chatgpt_access(mcp, seed):
    """MITA bumps users.token_version on logout-all / password reset."""
    user = await seed.user()
    token = mcp.token(user)
    assert not (await mcp.call(token, "get_profile")).is_error
    await seed.bump_token_version(user)
    result = await mcp.call(token, "get_profile")
    assert result.is_error
    assert result.structured_content["error"]["category"] == "auth"
    assert 'error="invalid_token"' in result.meta["mcp/www_authenticate"][0]


async def test_deleted_account_is_auth_error_not_empty_data(mcp, seed):
    user = await seed.user()
    token = mcp.token(user)
    await seed.delete_user(user)
    result = await mcp.call(token, "get_budget_status")
    assert result.is_error and result.structured_content["error"]["category"] == "auth"


async def test_external_mode_rejects_unknown_issuer_tokens(make_service, seed):
    """Resource-server-only mode verifies an external IdP's JWKS; our own
    builtin-issued tokens (different issuer) are refused there."""
    from tests_mcp.conftest import Harness

    builtin = Harness(make_service, make_settings())
    user = await seed.user()
    token = builtin.token(user)

    class StubJwks:
        def get_signing_key_from_jwt(self, _token):
            raise jwt.PyJWKClientError("unreachable")

    from app.mcp.auth.tokens import JwtTokenVerifier

    settings = make_settings(
        auth_mode="external",
        external_issuer="https://idp.example.test/",
        external_jwks_url="https://idp.example.test/.well-known/jwks.json",
    )
    verifier = JwtTokenVerifier(settings, jwks_client=StubJwks())
    assert await verifier.verify_token(token) is None


async def test_external_mode_accepts_idp_token_with_user_claim(seed):
    """Auth0/Stytch-style token: issuer + JWKS + a claim carrying the MITA user id."""
    from cryptography.hazmat.primitives import serialization

    from app.mcp.auth.tokens import JwtTokenVerifier

    pem = generate_private_key_pem(2048)
    private = serialization.load_pem_private_key(pem.encode(), password=None)

    class StubJwks:
        def get_signing_key_from_jwt(self, _token):
            return type("K", (), {"key": private.public_key()})()

    settings = make_settings(
        auth_mode="external",
        external_issuer="https://idp.example.test/",
        external_jwks_url="https://idp.example.test/.well-known/jwks.json",
        external_user_claim="https://mitafinance.com/user_id",
    )
    verifier = JwtTokenVerifier(settings, jwks_client=StubJwks())
    user = await seed.user()
    now = int(time.time())
    claims = {
        "iss": "https://idp.example.test/",
        "sub": "auth0|abc",
        "aud": [RESOURCE, "https://idp.example.test/userinfo"],
        "iat": now,
        "exp": now + 600,
        "azp": "chatgpt-client",
        "permissions": ["finance:read", "write:transactions"],
        "https://mitafinance.com/user_id": str(user.id),
    }
    token = jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "k1"})
    access = await verifier.verify_token(token)
    assert access is not None
    assert access.subject == str(user.id)
    assert access.scopes == ["finance:read"]  # unknown permissions dropped
    assert access.client_id == "chatgpt-client"

    claims.pop("https://mitafinance.com/user_id")
    assert (
        await verifier.verify_token(
            jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "k1"})
        )
        is None
    )

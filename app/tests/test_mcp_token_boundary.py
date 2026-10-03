"""Trust boundary: tokens shaped for the ChatGPT MCP resource never
authenticate against the mobile API (iss=mita-finance-api, aud=mita-finance-app).

The MCP service issues RS256 tokens with iss=<MCP_PUBLIC_URL> and
aud=<MCP_PUBLIC_URL>/mcp (app/mcp/auth/tokens.py). Even a token signed with the
API's own HS256 secret is refused when it carries the MCP issuer/audience.
"""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services.auth_jwt_service import verify_token

MCP = "https://mcp.example.test"


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": MCP,
        "sub": str(uuid.uuid4()),
        "aud": f"{MCP}/mcp",
        "iat": now,
        "nbf": now,
        "exp": now + 600,
        "jti": uuid.uuid4().hex,
        "client_id": "chatgpt",
        "scope": "profile:read finance:read",
        "tv": 1,
        "token_type": "access_token",
    }
    claims.update(overrides)
    return claims


@pytest.mark.asyncio
async def test_rs256_mcp_access_token_is_rejected_by_mobile_api():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    token = jwt.encode(_claims(), pem, algorithm="RS256", headers={"typ": "at+jwt"})
    assert await verify_token(token, token_type="access_token") is None


@pytest.mark.asyncio
async def test_mcp_audience_is_rejected_even_with_the_api_secret():
    secret = settings.JWT_SECRET or settings.SECRET_KEY
    for claims in (_claims(), _claims(iss="mita-finance-api")):
        token = jwt.encode(claims, secret, algorithm="HS256")
        assert await verify_token(token, token_type="access_token") is None

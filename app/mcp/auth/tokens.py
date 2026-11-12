"""Access-token issuing and verification (RFC 9068 JWT profile, RS256).

The resource-server half (``JwtTokenVerifier``) does not care who issued the
token: in ``external`` mode it verifies an external IdP's tokens through its
JWKS with the same audience and scope rules.
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.mcp.auth.fingerprint import CREDENTIAL_CLAIM
from app.mcp.auth.keys import SigningKeys
from app.mcp.auth.scopes import SUPPORTED_SCOPES
from app.mcp.config import McpSettings
from app.mcp.observability import metrics

logger = logging.getLogger(__name__)

ACCESS_TOKEN_TYP = "at+jwt"
CLOCK_SKEW_SECONDS = 30
TOKEN_VERSION_CLAIM = "tv"


def issue_access_token(
    keys: SigningKeys,
    settings: McpSettings,
    *,
    user_id: UUID,
    client_id: str,
    scopes: Iterable[str],
    token_version: int,
    credential_fingerprint: str,
    now: Optional[int] = None,
) -> tuple[str, int]:
    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + settings.access_token_ttl_seconds
    claims = {
        "iss": settings.issuer_url,
        "sub": str(user_id),
        "aud": settings.resource_url,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),
        "client_id": client_id,
        "scope": " ".join(s for s in scopes if s in SUPPORTED_SCOPES),
        TOKEN_VERSION_CLAIM: token_version,
        CREDENTIAL_CLAIM: credential_fingerprint,
    }
    token = jwt.encode(
        claims,
        keys.private_key,
        algorithm="RS256",
        headers={"kid": keys.kid, "typ": ACCESS_TOKEN_TYP},
    )
    return token, expires_at


def _scopes_from(claims: Dict[str, Any]) -> List[str]:
    raw = claims.get("scope")
    if isinstance(raw, str):
        values = raw.split()
    elif isinstance(claims.get("scp"), list):
        values = [str(v) for v in claims["scp"]]
    elif isinstance(claims.get("permissions"), list):  # Auth0 RBAC
        values = [str(v) for v in claims["permissions"]]
    else:
        values = []
    # Anything outside our two read scopes is ignored, whatever the IdP put in.
    return [s for s in values if s in SUPPORTED_SCOPES]


class JwtTokenVerifier(TokenVerifier):
    """Validates signature, ``iss``, ``aud`` (= this MCP resource), ``exp``,
    ``nbf`` and the presence of a MITA user id. Returns ``None`` on any failure;
    the SDK middleware turns that into ``401`` + ``WWW-Authenticate``."""

    def __init__(
        self,
        settings: McpSettings,
        *,
        keys: Optional[SigningKeys] = None,
        jwks_client: Optional[jwt.PyJWKClient] = None,
    ):
        self._settings = settings
        self._keys = keys
        self._jwks_client = jwks_client
        if settings.auth_mode == "builtin" and keys is None:
            raise ValueError("builtin auth mode needs signing keys")
        if settings.auth_mode == "external" and jwks_client is None:
            self._jwks_client = jwt.PyJWKClient(
                settings.external_jwks_url, cache_keys=True, lifespan=3600, timeout=5
            )

    def _key_for(self, token: str):
        if self._settings.auth_mode == "builtin":
            header = jwt.get_unverified_header(token)
            if header.get("typ") != ACCESS_TOKEN_TYP:
                raise jwt.InvalidTokenError("unexpected token type")
            key = self._keys.verification_keys.get(header.get("kid", ""))
            if key is None:
                raise jwt.InvalidTokenError("unknown key id")
            return key, ["RS256"]
        return self._jwks_client.get_signing_key_from_jwt(token).key, ["RS256", "ES256"]

    def decode(self, token: str) -> Dict[str, Any]:
        key, algorithms = self._key_for(token)
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=self._settings.resource_url,
            issuer=self._settings.issuer_url,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )

    def _subject(self, claims: Dict[str, Any]) -> Optional[str]:
        raw = (
            claims.get("sub")
            if self._settings.auth_mode == "builtin"
            else claims.get(self._settings.external_user_claim)
        )
        try:
            return str(UUID(str(raw)))
        except (TypeError, ValueError):
            return None

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        try:
            claims = self.decode(token)
        except jwt.ExpiredSignatureError:
            metrics.auth_failure("expired")
            return None
        except (jwt.InvalidAudienceError, jwt.InvalidIssuerError) as exc:
            metrics.auth_failure(
                "audience" if isinstance(exc, jwt.InvalidAudienceError) else "issuer"
            )
            return None
        except jwt.PyJWKClientError:
            metrics.auth_failure("jwks_unavailable")
            logger.warning("mcp.auth jwks fetch failed")
            return None
        except jwt.InvalidTokenError:
            metrics.auth_failure("invalid")
            return None

        subject = self._subject(claims)
        if subject is None:
            metrics.auth_failure("no_subject")
            return None
        token_version = claims.get(TOKEN_VERSION_CLAIM)
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or claims.get("azp") or "unknown"),
            scopes=_scopes_from(claims),
            expires_at=int(claims["exp"]),
            resource=self._settings.resource_url,
            subject=subject,
            claims={
                "iss": claims["iss"],
                TOKEN_VERSION_CLAIM: (
                    token_version if isinstance(token_version, int) else None
                ),
                CREDENTIAL_CLAIM: (
                    claims.get(CREDENTIAL_CLAIM)
                    if isinstance(claims.get(CREDENTIAL_CLAIM), str)
                    else None
                ),
            },
        )

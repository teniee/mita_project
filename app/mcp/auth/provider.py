"""MITA's OAuth authorization-server provider for the official MCP SDK.

The SDK handlers own the protocol: metadata, request parsing, redirect-URI
matching, PKCE S256 verification, code expiry, client authentication. This
provider owns storage, policy and identity:

* DCR accepts only ChatGPT's redirect URIs (``MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES``);
* every authorization is bound to this server's resource (RFC 8707);
* codes are single use (atomic delete-on-exchange), stored as SHA-256 digests;
* refresh tokens rotate; presenting a rotated token revokes its whole family;
* every grant is bound to ``users.token_version`` AND to an HMAC fingerprint
  of the password hash: a password change by any path, a token-version bump
  (admin revoke, /change-password) or account deletion ends ChatGPT access.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
from urllib.parse import urlencode, urlparse
from uuid import UUID

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import delete, update

from app.db.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthRefreshToken,
    User,
)
from app.mcp.auth.fingerprint import (
    credential_fingerprint,
    fingerprint_key,
    same_fingerprint,
)
from app.mcp.auth.keys import SigningKeys
from app.mcp.auth.redirects import redirect_uri_allowed
from app.mcp.auth.scopes import SUPPORTED_SCOPES
from app.mcp.auth.tokens import JwtTokenVerifier, issue_access_token
from app.mcp.config import McpSettings
from app.mcp.db import SessionScope
from app.mcp.observability import subject_hash

logger = logging.getLogger("app.mcp.oauth")

MAX_REDIRECT_URIS = 5
MAX_CLIENT_NAME = 100
MAX_CLIENT_METADATA_BYTES = 4096
ALLOWED_GRANT_TYPES = {"authorization_code", "refresh_token"}
ALLOWED_AUTH_METHODS = {"none", "client_secret_post", "client_secret_basic"}
# RFC 7636: S256 challenge = BASE64URL(SHA256(verifier)) = 43 characters.
PKCE_S256_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}")
LOGIN_PATH = "/oauth/login"


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def same_resource(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (
        pa.scheme.lower() == pb.scheme.lower()
        and pa.netloc.lower() == pb.netloc.lower()
        and pa.path.rstrip("/") == pb.path.rstrip("/")
        and not pa.query
        and not pa.fragment
    )


class MitaAuthorizationCode(AuthorizationCode):
    user_id: UUID
    token_version: int
    credential_fingerprint: str


class MitaRefreshToken(RefreshToken):
    family_id: UUID
    user_id: UUID
    token_version: int
    credential_fingerprint: str


# ---------------------------------------------------------------------------
# Pending authorization requests: signed, short-lived, stateless
# ---------------------------------------------------------------------------


class PendingRequestCodec:
    """Carries a validated /authorize request to the login page without a
    database row. HMAC-SHA256 over the JSON payload; expires after
    ``pending_authorization_ttl_seconds``."""

    def __init__(
        self, secret: str, ttl_seconds: int, clock: Callable[[], float] = time.time
    ):
        self._key = hashlib.sha256(b"mita-mcp-pending:" + secret.encode()).digest()
        self._ttl = ttl_seconds
        self._clock = clock

    def encode(self, payload: dict) -> str:
        body = dict(payload, exp=int(self._clock()) + self._ttl)
        raw = (
            base64.urlsafe_b64encode(
                json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode()
            .rstrip("=")
        )
        sig = hmac.new(self._key, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def decode(self, blob: str) -> Optional[dict]:
        try:
            raw, sig = blob.rsplit(".", 1)
        except (ValueError, AttributeError):
            return None
        expected = hmac.new(self._key, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("exp", 0) < self._clock():
            return None
        return payload


class MitaAuthorizationProvider(
    OAuthAuthorizationServerProvider[
        MitaAuthorizationCode, MitaRefreshToken, AccessToken
    ]
):
    def __init__(
        self,
        settings: McpSettings,
        keys: SigningKeys,
        verifier: JwtTokenVerifier,
        write_scope: SessionScope,
        pending: PendingRequestCodec,
        clock: Callable[[], datetime] = _utcnow,
    ):
        self.settings = settings
        self.keys = keys
        self.verifier = verifier
        self.write_scope = write_scope
        self.pending = pending
        self.clock = clock
        self._fingerprint_key = fingerprint_key(settings.grant_fingerprint_secret)

    def fingerprint(self, user: User) -> str:
        return credential_fingerprint(self._fingerprint_key, user.password_hash)

    def _grant_still_valid(
        self, user: Optional[User], token_version: int, fingerprint: str
    ) -> bool:
        return (
            user is not None
            and int(user.token_version or 1) == token_version
            and same_fingerprint(self.fingerprint(user), fingerprint)
        )

    # --- clients (RFC 7591) ---------------------------------------------

    def redirect_uri_allowed(self, uri: str) -> bool:
        return redirect_uri_allowed(uri, self.settings.allowed_redirect_prefixes)

    @staticmethod
    def _enforce_minimal_client(client_info: OAuthClientInformationFull) -> None:
        """Accept only what ChatGPT needs: code + refresh grants, the code
        response type, no client-supplied keys, bounded metadata."""
        problems = []
        if set(client_info.grant_types) - ALLOWED_GRANT_TYPES:
            problems.append(
                "grant_types may only be authorization_code and refresh_token"
            )
        if list(client_info.response_types) != ["code"]:
            problems.append("response_types must be exactly ['code']")
        if client_info.token_endpoint_auth_method not in ALLOWED_AUTH_METHODS:
            problems.append("unsupported token_endpoint_auth_method")
        if client_info.jwks is not None or client_info.jwks_uri is not None:
            problems.append("jwks/jwks_uri are not accepted")
        if client_info.client_name and len(client_info.client_name) > MAX_CLIENT_NAME:
            problems.append("client_name is too long")
        size = len(client_info.model_dump_json(exclude_none=True))
        if size > MAX_CLIENT_METADATA_BYTES:
            problems.append("client metadata is too large")
        if problems:
            raise RegistrationError("invalid_client_metadata", "; ".join(problems))

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        async with self.write_scope() as session:
            row = await session.get(McpOAuthClient, client_id)
            if row is None:
                return None
            return OAuthClientInformationFull.model_validate(row.client_info)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        uris = [str(u) for u in (client_info.redirect_uris or [])]
        if not uris or len(uris) > MAX_REDIRECT_URIS:
            raise RegistrationError(
                "invalid_redirect_uri",
                f"Register between 1 and {MAX_REDIRECT_URIS} redirect URIs.",
            )
        rejected = [u for u in uris if not self.redirect_uri_allowed(u)]
        if rejected:
            logger.warning(
                "oauth register rejected redirect",
                extra={"event": "oauth_register_rejected"},
            )
            raise RegistrationError(
                "invalid_redirect_uri",
                "This authorization server only accepts ChatGPT connector redirect URIs.",
            )
        self._enforce_minimal_client(client_info)
        async with self.write_scope() as session:
            session.add(
                McpOAuthClient(
                    client_id=client_info.client_id,
                    client_info=client_info.model_dump(mode="json", exclude_none=True),
                )
            )
        logger.info(
            "oauth client registered",
            extra={"event": "oauth_client_registered", "client": client_info.client_id},
        )

    # --- authorization ---------------------------------------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        resource = params.resource or self.settings.resource_url
        if not same_resource(resource, self.settings.resource_url):
            raise AuthorizeError(
                "invalid_target", "Unknown resource for this authorization server."
            )
        if not self.redirect_uri_allowed(str(params.redirect_uri)):
            raise AuthorizeError("invalid_request", "Redirect URI is not allowed.")
        if not PKCE_S256_CHALLENGE.fullmatch(params.code_challenge or ""):
            raise AuthorizeError(
                "invalid_request", "code_challenge must be an S256 PKCE challenge."
            )
        requested = params.scopes or (
            client.scope.split() if client.scope else list(SUPPORTED_SCOPES)
        )
        scopes = [s for s in requested if s in SUPPORTED_SCOPES]
        if not scopes:
            raise AuthorizeError("invalid_scope", "No supported scope requested.")
        blob = self.pending.encode(
            {
                "client_id": client.client_id,
                "redirect_uri": str(params.redirect_uri),
                "explicit": params.redirect_uri_provided_explicitly,
                "code_challenge": params.code_challenge,
                "state": params.state,
                "scopes": scopes,
                "resource": self.settings.resource_url,
            }
        )
        return f"{self.settings.public_url}{LOGIN_PATH}?{urlencode({'req': blob})}"

    async def create_authorization_code(self, pending: dict, user: User) -> str:
        """Called by the consent page after MITA credentials were verified."""
        code = secrets.token_urlsafe(32)  # 256 bits
        async with self.write_scope() as session:
            session.add(
                McpOAuthAuthorizationCode(
                    code_hash=token_digest(code),
                    client_id=pending["client_id"],
                    user_id=user.id,
                    scopes=" ".join(pending["scopes"]),
                    code_challenge=pending["code_challenge"],
                    redirect_uri=pending["redirect_uri"],
                    redirect_uri_provided_explicitly=bool(pending["explicit"]),
                    resource=pending["resource"],
                    token_version=int(user.token_version or 1),
                    credential_fingerprint=self.fingerprint(user),
                    expires_at=self.clock()
                    + timedelta(seconds=self.settings.authorization_code_ttl_seconds),
                )
            )
        logger.info(
            "oauth code issued",
            extra={
                "event": "oauth_code_issued",
                "client": pending["client_id"],
                "subject_hash": subject_hash(user.id),
            },
        )
        return code

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[MitaAuthorizationCode]:
        async with self.write_scope() as session:
            row = await session.get(
                McpOAuthAuthorizationCode, token_digest(authorization_code)
            )
            if row is None or row.client_id != client.client_id:
                return None
            return MitaAuthorizationCode(
                code=authorization_code,
                scopes=row.scopes.split(),
                expires_at=row.expires_at.timestamp(),
                client_id=row.client_id,
                code_challenge=row.code_challenge,
                redirect_uri=row.redirect_uri,
                redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
                resource=row.resource,
                subject=str(row.user_id),
                user_id=row.user_id,
                token_version=row.token_version,
                credential_fingerprint=row.credential_fingerprint,
            )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: MitaAuthorizationCode,
    ) -> OAuthToken:
        failure: Optional[TokenError] = None
        async with self.write_scope() as session:
            # Single use: whoever deletes the row wins; a replay finds nothing.
            # The delete commits even when the exchange is then refused.
            deleted = await session.execute(
                delete(McpOAuthAuthorizationCode)
                .where(
                    McpOAuthAuthorizationCode.code_hash
                    == token_digest(authorization_code.code)
                )
                .returning(McpOAuthAuthorizationCode.code_hash)
            )
            user = await session.get(User, authorization_code.user_id)
            if deleted.first() is None:
                failure = TokenError(
                    "invalid_grant", "authorization code was already used"
                )
            elif not same_resource(
                authorization_code.resource or "", self.settings.resource_url
            ):
                failure = TokenError(
                    "invalid_target",
                    "authorization code was issued for another resource",
                )
            elif not self._grant_still_valid(
                user,
                authorization_code.token_version,
                authorization_code.credential_fingerprint,
            ):
                failure = TokenError(
                    "invalid_grant", "the MITA session behind this code has ended"
                )
            else:
                return await self._issue_tokens(
                    session,
                    client_id=client.client_id,
                    user_id=user.id,
                    scopes=authorization_code.scopes,
                    token_version=authorization_code.token_version,
                    credential_fingerprint=authorization_code.credential_fingerprint,
                    family_id=uuid.uuid4(),
                )
        raise failure

    # --- tokens ----------------------------------------------------------

    async def _issue_tokens(
        self,
        session,
        *,
        client_id: str,
        user_id: UUID,
        scopes: List[str],
        token_version: int,
        credential_fingerprint: str,
        family_id: UUID,
    ) -> OAuthToken:
        now = self.clock()
        access, expires_at = issue_access_token(
            self.keys,
            self.settings,
            user_id=user_id,
            client_id=client_id,
            scopes=scopes,
            token_version=token_version,
            credential_fingerprint=credential_fingerprint,
            now=int(now.timestamp()),
        )
        refresh = secrets.token_urlsafe(48)
        session.add(
            McpOAuthRefreshToken(
                token_hash=token_digest(refresh),
                family_id=family_id,
                client_id=client_id,
                user_id=user_id,
                scopes=" ".join(scopes),
                resource=self.settings.resource_url,
                token_version=token_version,
                credential_fingerprint=credential_fingerprint,
                expires_at=now
                + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
            )
        )
        await session.execute(
            update(McpOAuthClient)
            .where(McpOAuthClient.client_id == client_id)
            .values(last_used_at=now)
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=expires_at - int(now.timestamp()),
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    async def _revoke_family(self, session, family_id: UUID) -> None:
        await session.execute(
            update(McpOAuthRefreshToken)
            .where(
                McpOAuthRefreshToken.family_id == family_id,
                McpOAuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=self.clock())
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[MitaRefreshToken]:
        async with self.write_scope() as session:
            row = await session.get(McpOAuthRefreshToken, token_digest(refresh_token))
            if (
                row is None
                or row.client_id != client.client_id
                or row.revoked_at is not None
            ):
                return None
            if row.rotated_at is not None:
                # A rotated token came back: someone holds a copy. End the family.
                await self._revoke_family(session, row.family_id)
                logger.warning(
                    "refresh token reuse",
                    extra={
                        "event": "oauth_refresh_reuse",
                        "client": row.client_id,
                        "subject_hash": subject_hash(row.user_id),
                    },
                )
                return None
            return MitaRefreshToken(
                token=refresh_token,
                client_id=row.client_id,
                scopes=row.scopes.split(),
                expires_at=int(row.expires_at.timestamp()),
                resource=row.resource,
                subject=str(row.user_id),
                family_id=row.family_id,
                user_id=row.user_id,
                token_version=row.token_version,
                credential_fingerprint=row.credential_fingerprint,
            )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: MitaRefreshToken,
        scopes: List[str],
    ) -> OAuthToken:
        failure: Optional[TokenError] = None
        async with self.write_scope() as session:
            rotated = await session.execute(
                update(McpOAuthRefreshToken)
                .where(
                    McpOAuthRefreshToken.token_hash
                    == token_digest(refresh_token.token),
                    McpOAuthRefreshToken.rotated_at.is_(None),
                    McpOAuthRefreshToken.revoked_at.is_(None),
                )
                .values(rotated_at=self.clock())
                .returning(McpOAuthRefreshToken.token_hash)
            )
            user = await session.get(User, refresh_token.user_id)
            if rotated.first() is None:
                # Lost a race with another exchange of the same token: treat as reuse.
                await self._revoke_family(session, refresh_token.family_id)
                failure = TokenError(
                    "invalid_grant", "refresh token is no longer valid"
                )
            elif not self._grant_still_valid(
                user, refresh_token.token_version, refresh_token.credential_fingerprint
            ):
                await self._revoke_family(session, refresh_token.family_id)
                failure = TokenError(
                    "invalid_grant", "the MITA session behind this token has ended"
                )
            else:
                return await self._issue_tokens(
                    session,
                    client_id=client.client_id,
                    user_id=user.id,
                    scopes=[s for s in scopes if s in SUPPORTED_SCOPES],
                    token_version=refresh_token.token_version,
                    credential_fingerprint=refresh_token.credential_fingerprint,
                    family_id=refresh_token.family_id,
                )
        # The revocation above is committed before the refusal is returned.
        raise failure

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        return await self.verifier.verify_token(token)

    async def revoke_token(self, token: AccessToken | MitaRefreshToken) -> None:
        async with self.write_scope() as session:
            if isinstance(token, MitaRefreshToken):
                await self._revoke_family(session, token.family_id)
                return
            # An access token is a stateless JWT (≤ MCP_ACCESS_TOKEN_TTL_SECONDS);
            # revoke every refresh token this client holds for the user so the
            # connection cannot be renewed.
            if token.subject:
                await session.execute(
                    update(McpOAuthRefreshToken)
                    .where(
                        McpOAuthRefreshToken.user_id == UUID(token.subject),
                        McpOAuthRefreshToken.client_id == token.client_id,
                        McpOAuthRefreshToken.revoked_at.is_(None),
                    )
                    .values(revoked_at=self.clock())
                )

    async def purge_expired(self) -> int:
        """Housekeeping: drop expired codes and long-dead refresh tokens."""
        now = self.clock()
        async with self.write_scope() as session:
            codes = await session.execute(
                delete(McpOAuthAuthorizationCode).where(
                    McpOAuthAuthorizationCode.expires_at < now
                )
            )
            tokens = await session.execute(
                delete(McpOAuthRefreshToken).where(
                    McpOAuthRefreshToken.expires_at < now - timedelta(days=7)
                )
            )
            return (codes.rowcount or 0) + (tokens.rowcount or 0)

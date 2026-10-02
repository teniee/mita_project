"""Storage for the ChatGPT app's OAuth authorization server (app/mcp/auth).

Written only by the OAuth endpoints of the MCP service; never by a tool.
Authorization codes and refresh tokens are stored as SHA-256 digests — the
plaintext exists only in the response that hands it to the client.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class McpOAuthClient(Base):
    """A client registered through RFC 7591 dynamic client registration."""

    __tablename__ = "mcp_oauth_clients"

    client_id = Column(String(64), primary_key=True)
    # OAuthClientInformationFull as JSON (redirect URIs, auth method, scope,
    # client name, and — for confidential clients — the client secret the SDK
    # compares at the token endpoint).
    client_info = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class McpOAuthAuthorizationCode(Base):
    __tablename__ = "mcp_oauth_authorization_codes"

    code_hash = Column(String(64), primary_key=True)
    client_id = Column(
        String(64),
        ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scopes = Column(Text, nullable=False)
    code_challenge = Column(String(128), nullable=False)
    redirect_uri = Column(Text, nullable=False)
    redirect_uri_provided_explicitly = Column(Boolean, nullable=False)
    resource = Column(Text, nullable=False)
    token_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class McpOAuthRefreshToken(Base):
    __tablename__ = "mcp_oauth_refresh_tokens"

    token_hash = Column(String(64), primary_key=True)
    # All tokens descending from one authorization share a family; reuse of a
    # rotated token revokes the family (RFC 6819 §5.2.2.3 / OAuth 2.1 §4.3.1).
    family_id = Column(
        UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4
    )
    client_id = Column(
        String(64),
        ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scopes = Column(Text, nullable=False)
    resource = Column(Text, nullable=False)
    token_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    rotated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

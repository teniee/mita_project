"""Per-user state of the ChatGPT app (MCP service) — migrations 0038 and 0039.

Written only by MCP tools and the ChatGPT consent page. Income, currency,
timezone and monthly savings remain canonical on ``users``; these tables hold
only what ``users`` cannot express.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class McpUserProfile(Base):
    """Setup state for one user.

    ``*_confirmed_at`` records that the user stated the value (in ChatGPT, or
    by completing onboarding in the app — see ``app.mcp.queries.setup``): the
    ``users`` column defaults (USD, UTC, 0) are not choices.
    ``usage_analytics_enabled`` is the user's answer on the MITA consent page
    or through ``set_usage_analytics``; with no row, nothing is linked to them.
    """

    __tablename__ = "mcp_user_profiles"
    __table_args__ = (
        CheckConstraint(
            "household_size IS NULL OR household_size BETWEEN 1 AND 20",
            name="ck_mcp_user_profiles_household_size",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    household_size = Column(SmallInteger, nullable=True)
    income_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    currency_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    timezone_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    savings_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    usage_analytics_enabled = Column(Boolean, nullable=False, default=False)
    usage_analytics_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class McpIdempotencyKey(Base):
    """A completed create operation, keyed by a digest of the client's key.

    Stores digests and the created rows' ids only — never amounts, merchants
    or any other value the user entered.
    """

    __tablename__ = "mcp_idempotency_keys"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scope_hash = Column(String(64), primary_key=True)
    operation = Column(String(40), nullable=False)
    request_hash = Column(String(64), nullable=False)
    resource_ids = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class ProductFeedback(Base):
    """Feedback a user explicitly chose to send to the MITA team (0039).

    Keyed by user id so it is deleted with the account. ``status``, ``theme``
    and ``internal_notes`` are the team's triage fields, never shown to users.
    """

    __tablename__ = "product_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    type = Column(String(20), nullable=False)
    feature_area = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    rating = Column(SmallInteger, nullable=True)
    status = Column(String(16), nullable=False, default="new")
    source = Column(String(16), nullable=False, default="chatgpt")
    theme = Column(String(64), nullable=True)
    internal_notes = Column(Text, nullable=True)


class AnalyticsIdentity(Base):
    """User id -> pseudonymous analytics key. Deleting the row (account
    deletion, or the user turning usage statistics off) cascades to every
    event linked to the key (0039)."""

    __tablename__ = "analytics_identities"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user_key = Column(String(32), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

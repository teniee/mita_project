"""Per-user state of the ChatGPT app (MCP service) — migrations 0038–0043.

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
    Numeric,
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

    Since 0043 (personalized onboarding, all stated by the user): the country
    itself stays on ``users.country``; ``country_confirmed_at`` and
    ``country_source`` record that the user confirmed it (``stated``, or
    ``chatgpt_location_confirmed`` when it is the country of ChatGPT's
    approximate location). ``regional_context_enabled`` is the user's switch
    for regional statistics. The income schedule: ``income_regularity``,
    ``pay_frequency``, ``pay_days`` and, for variable income only,
    ``minimum_monthly_income``. No city, address or coordinates.
    """

    __tablename__ = "mcp_user_profiles"
    __table_args__ = (
        CheckConstraint(
            "household_size IS NULL OR household_size BETWEEN 1 AND 20",
            name="ck_mcp_user_profiles_household_size",
        ),
        CheckConstraint(
            "country_source IS NULL OR country_source IN "
            "('stated', 'chatgpt_location_confirmed')",
            name="ck_mcp_user_profiles_country_source",
        ),
        CheckConstraint(
            "(country_source IS NULL) = (country_confirmed_at IS NULL)",
            name="ck_mcp_user_profiles_country_confirmed",
        ),
        CheckConstraint(
            "income_regularity IS NULL OR income_regularity IN ('regular', 'variable')",
            name="ck_mcp_user_profiles_income_regularity",
        ),
        CheckConstraint(
            "pay_frequency IS NULL OR pay_frequency IN "
            "('monthly', 'twice_monthly', 'every_two_weeks', 'weekly', 'irregular')",
            name="ck_mcp_user_profiles_pay_frequency",
        ),
        CheckConstraint(
            "minimum_monthly_income IS NULL OR (minimum_monthly_income >= 0 "
            "AND income_regularity IS NOT NULL AND income_regularity = 'variable')",
            name="ck_mcp_user_profiles_minimum_income",
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
    country_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    country_source = Column(String(32), nullable=True)
    regional_context_enabled = Column(Boolean, nullable=False, default=True)
    income_regularity = Column(String(16), nullable=True)
    pay_frequency = Column(String(20), nullable=True)
    pay_days = Column(JSONB, nullable=False, default=list)
    minimum_monthly_income = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class McpSetupAnswer(Base):
    """An answer to one of MITA's setup questions that no other table holds
    (migration 0043): "I have no regular payments" (``regular_payments`` =
    ``none``), "that is what I regularly spend on" (``everyday_spending`` =
    ``described``), or the user's choice to skip a question (``skipped``).
    No row means never answered — never "none". Cascades with the user."""

    __tablename__ = "mcp_setup_answers"
    __table_args__ = (
        CheckConstraint(
            "topic IN ('regular_payments', 'everyday_spending', "
            "'irregular_expenses', 'income_schedule', 'region')",
            name="ck_mcp_setup_answers_topic",
        ),
        CheckConstraint(
            "answer IN ('none', 'described', 'skipped')",
            name="ck_mcp_setup_answers_answer",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic = Column(String(32), primary_key=True)
    answer = Column(String(16), nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=False, default=_now)


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


class McpBudgetLine(Base):
    """A budget line the user named and set in ChatGPT (F-11, migration 0040).

    The line's amounts live in ``daily_plan`` under ``line_key``
    (``"my:<label>"``) like any other plan line, and expenses recorded against
    it carry the same key (``app/services/core/engine/user_budget_lines.py``).
    This row keeps only what rebuilding a month later must know: which of
    MITA's own lines the user's line takes the place of (``replaces``, engine
    line codes chosen in the conversation), so MITA never budgets the same
    spending twice. Cascades with the user.
    """

    __tablename__ = "mcp_budget_lines"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    line_key = Column(String(50), primary_key=True)
    replaces = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

"""Personalized onboarding: confirmed country, income schedule, setup answers.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-04

Additive only: nullable or defaulted columns on ``mcp_user_profiles`` and one
new table; no existing row changes (docs/chatgpt-app/personalization-2.8.md).

``mcp_user_profiles`` gains what the user stated about their income and
where they live, never inferred:

* ``country_confirmed_at`` / ``country_source`` — the country itself stays on
  ``users.country`` (ISO 3166-1 alpha-2; ChatGPT sign-up stores ``ZZ``);
  these record that the user confirmed it, and whether they confirmed the
  country of ChatGPT's approximate location (``chatgpt_location_confirmed``)
  or named another one (``stated``). No city, address or coordinates are
  stored;
* ``regional_context_enabled`` — the user's switch for regional statistics;
* ``income_regularity`` (regular | variable), ``pay_frequency``,
  ``pay_days`` (days of the month), ``minimum_monthly_income`` (variable
  income only).

``mcp_setup_answers`` keeps answers no other table can hold, one row per
user and topic: "no regular payments" (``regular_payments = none``), "that is
what I spend on" (``everyday_spending = described``), "skip this"
(``skipped``). A missing row means the question was never answered — never
"none".

Written by the MCP service (``update_financial_profile``). The MCP role needs
``GRANT UPDATE (country, region) ON users`` and ``GRANT SELECT, INSERT,
UPDATE, DELETE ON mcp_setup_answers`` (scripts/mcp/mcp_service_role.sql).

Downgrade drops the new table and columns: previews fall back to 2.7.0
behaviour (every MITA line suggested, no personalization).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

PROFILE_CHECKS = (
    (
        "ck_mcp_user_profiles_country_source",
        "country_source IS NULL OR country_source IN "
        "('stated', 'chatgpt_location_confirmed')",
    ),
    (
        "ck_mcp_user_profiles_country_confirmed",
        "(country_source IS NULL) = (country_confirmed_at IS NULL)",
    ),
    (
        "ck_mcp_user_profiles_income_regularity",
        "income_regularity IS NULL OR income_regularity IN ('regular', 'variable')",
    ),
    (
        "ck_mcp_user_profiles_pay_frequency",
        "pay_frequency IS NULL OR pay_frequency IN "
        "('monthly', 'twice_monthly', 'every_two_weeks', 'weekly', 'irregular')",
    ),
    (
        "ck_mcp_user_profiles_minimum_income",
        # IS NOT NULL first: a CHECK passes when its expression is NULL, so
        # "NULL = 'variable'" alone would let a minimum through without it.
        "minimum_monthly_income IS NULL OR (minimum_monthly_income >= 0 "
        "AND income_regularity IS NOT NULL AND income_regularity = 'variable')",
    ),
)


def upgrade():
    op.add_column(
        "mcp_user_profiles",
        sa.Column("country_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column("country_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column(
            "regional_context_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column("income_regularity", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column("pay_frequency", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column(
            "pay_days",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "mcp_user_profiles",
        sa.Column("minimum_monthly_income", sa.Numeric(12, 2), nullable=True),
    )
    for name, condition in PROFILE_CHECKS:
        op.create_check_constraint(name, "mcp_user_profiles", condition)

    op.create_table(
        "mcp_setup_answers",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("topic", sa.String(length=32), primary_key=True),
        sa.Column("answer", sa.String(length=16), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "topic IN ('regular_payments', 'everyday_spending', "
            "'irregular_expenses', 'income_schedule', 'region')",
            name="ck_mcp_setup_answers_topic",
        ),
        sa.CheckConstraint(
            "answer IN ('none', 'described', 'skipped')",
            name="ck_mcp_setup_answers_answer",
        ),
    )


def downgrade():
    op.drop_table("mcp_setup_answers")
    for name, _condition in reversed(PROFILE_CHECKS):
        op.drop_constraint(name, "mcp_user_profiles", type_="check")
    for column in (
        "minimum_monthly_income",
        "pay_days",
        "pay_frequency",
        "income_regularity",
        "regional_context_enabled",
        "country_source",
        "country_confirmed_at",
    ):
        op.drop_column("mcp_user_profiles", column)

"""add installments module

Revision ID: 0015_add_installments_module
Revises: f8e0108e3527
Create Date: 2025-11-14 00:00:00.000000

Smart Installment Payment Management Module
Based on BNPL research and US financial best practices
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0015_add_installments_module"
down_revision = "f8e0108e3527"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_financial_profiles table
    op.create_table(
        "user_financial_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Income and balance (in USD)
        sa.Column("monthly_income", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_balance", sa.Numeric(precision=12, scale=2), nullable=False),
        # Demographics
        sa.Column("age_group", sa.String(length=10), nullable=False, server_default="25-34"),
        # Existing obligations
        sa.Column("credit_card_debt", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("credit_card_payment", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("other_loans_payment", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("rent_payment", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("subscriptions_payment", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        # Future plans
        sa.Column("planning_mortgage", sa.Boolean(), nullable=False, server_default="false"),
        # Metadata
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id")
    )
    op.create_index("ix_user_financial_profiles_user_id", "user_financial_profiles", ["user_id"])

    # Create installments table
    op.create_table(
        "installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Installment details
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="other"),
        # Financial details (USD)
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
        # Payment schedule
        sa.Column("total_payments", sa.Integer(), nullable=False),
        sa.Column("payments_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_frequency", sa.String(length=20), nullable=False, server_default="monthly"),
        # Dates
        sa.Column("first_payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_payment_date", sa.DateTime(timezone=True), nullable=False),
        # Status
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        # Metadata
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")
    )
    op.create_index("ix_installments_user_id", "installments", ["user_id"])
    op.create_index("ix_installments_created_at", "installments", ["created_at"])

    # Create installment_calculations table
    op.create_table(
        "installment_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installment_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Purchase details
        sa.Column("purchase_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        # Payment structure
        sa.Column("num_payments", sa.Integer(), nullable=False),
        sa.Column("interest_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_interest", sa.Numeric(precision=12, scale=2), nullable=False),
        # Risk assessment
        sa.Column("risk_level", sa.String(length=10), nullable=False),
        # Financial metrics
        sa.Column("dti_ratio", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("payment_to_income_ratio", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(precision=12, scale=2), nullable=False),
        # Risk factors (JSON)
        sa.Column("risk_factors", sa.Text(), nullable=True),
        # User decision
        sa.Column("user_proceeded", sa.Boolean(), nullable=False, server_default="false"),
        # Metadata
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installment_id"], ["installments.id"], ondelete="SET NULL")
    )
    op.create_index("ix_installment_calculations_user_id", "installment_calculations", ["user_id"])
    op.create_index("ix_installment_calculations_installment_id", "installment_calculations", ["installment_id"])
    op.create_index("ix_installment_calculations_calculated_at", "installment_calculations", ["calculated_at"])

    # Create installment_achievements table
    op.create_table(
        "installment_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Achievement tracking
        sa.Column("installments_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calculations_performed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calculations_declined", sa.Integer(), nullable=False, server_default="0"),
        # Streak tracking
        sa.Column("days_without_new_installment", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_days_streak", sa.Integer(), nullable=False, server_default="0"),
        # Financial discipline
        sa.Column("interest_saved", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("achievement_level", sa.String(length=20), nullable=False, server_default="beginner"),
        # Metadata
        sa.Column("last_calculation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")
    )
    op.create_index("ix_installment_achievements_user_id", "installment_achievements", ["user_id"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index("ix_installment_achievements_user_id", "installment_achievements")
    op.drop_table("installment_achievements")

    op.drop_index("ix_installment_calculations_calculated_at", "installment_calculations")
    op.drop_index("ix_installment_calculations_installment_id", "installment_calculations")
    op.drop_index("ix_installment_calculations_user_id", "installment_calculations")
    op.drop_table("installment_calculations")

    op.drop_index("ix_installments_created_at", "installments")
    op.drop_index("ix_installments_user_id", "installments")
    op.drop_table("installments")

    op.drop_index("ix_user_financial_profiles_user_id", "user_financial_profiles")
    op.drop_table("user_financial_profiles")

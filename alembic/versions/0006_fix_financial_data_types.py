"""fix critical financial data types for compliance

Revision ID: 0006_fix_financial_data_types
Revises: 0005_push_tokens
Create Date: 2025-08-11

CRITICAL: This migration fixes financial data integrity issues:
1. Converts Float to Numeric(precision=12, scale=2) for expenses.amount
2. Adds proper precision to existing Numeric columns
3. Adds foreign key constraints for data integrity
4. Ensures all monetary values use appropriate decimal precision

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_fix_financial_data_types"
down_revision = "0005_push_tokens"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    """True if `name` exists in the current database."""
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    """
    Apply financial data-type fixes with proper error handling.

    HISTORICAL NOTE: this migration was authored against an older schema state
    in which `expenses`, `goals`, `user_answers` and `user_profiles` already
    existed. In the current linear chain those tables are created later
    (0016_sync_models et al.), so on a fresh database none of them exist yet
    when this revision runs. Every operation is therefore guarded by an
    existence check: on a clean database the whole migration is a safe no-op
    (the tables are later created with types that match the ORM models), while
    on any legacy database that did have these tables the fixes still apply.
    Without these guards `alembic upgrade head` crashes from empty
    ("relation expenses does not exist"), breaking every fresh deploy / DR.
    """
    # ---- expenses ---------------------------------------------------------
    if _has_table("expenses"):
        op.execute("CREATE TEMP TABLE expenses_backup AS SELECT * FROM expenses")

        op.alter_column(
            "expenses",
            "amount",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=False,
            comment="Fixed: Float to Numeric(12,2) for financial precision",
        )
        op.alter_column(
            "expenses",
            "user_id",
            existing_type=sa.String(),
            type_=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
            postgresql_using="user_id::uuid",
        )
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.create_foreign_key(
                "fk_expenses_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )

    # ---- goals ------------------------------------------------------------
    if _has_table("goals"):
        op.alter_column(
            "goals",
            "target_amount",
            existing_type=sa.Numeric(),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=False,
            comment="Added precision(12,2) for financial accuracy",
        )
        op.alter_column(
            "goals",
            "saved_amount",
            existing_type=sa.Numeric(),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=False,
            comment="Added precision(12,2) for financial accuracy",
        )
        with op.batch_alter_table("goals") as batch_op:
            batch_op.create_foreign_key(
                "fk_goals_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )

    # ---- users ------------------------------------------------------------
    if _has_column("users", "annual_income"):
        op.alter_column(
            "users",
            "annual_income",
            existing_type=sa.Numeric(),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=True,
            comment="Added precision(12,2) for financial accuracy",
        )

    # ---- user_answers -----------------------------------------------------
    if _has_table("user_answers"):
        op.alter_column(
            "user_answers",
            "user_id",
            existing_type=sa.String(),
            type_=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
            postgresql_using="user_id::uuid",
        )
        with op.batch_alter_table("user_answers") as batch_op:
            batch_op.create_foreign_key(
                "fk_user_answers_user_id",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    # ---- user_profiles ----------------------------------------------------
    if _has_table("user_profiles"):
        op.alter_column(
            "user_profiles",
            "user_id",
            existing_type=sa.String(),
            type_=postgresql.UUID(as_uuid=True),
            existing_nullable=False,
            postgresql_using="user_id::uuid",
        )
        with op.batch_alter_table("user_profiles") as batch_op:
            batch_op.create_foreign_key(
                "fk_user_profiles_user_id",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    # ---- indexes ----------------------------------------------------------
    if _has_table("expenses") and _has_column("expenses", "date"):
        op.create_index(
            "ix_expenses_user_id_date", "expenses", ["user_id", "date"], unique=False
        )
    if _has_table("transactions") and _has_column("transactions", "spent_at"):
        op.create_index(
            "ix_transactions_user_id_spent_at",
            "transactions",
            ["user_id", "spent_at"],
            unique=False,
        )

    # ---- data-integrity validation (only if expenses was migrated) --------
    if _has_table("expenses"):
        op.execute(
            """
            DO $$
            BEGIN
                IF (SELECT COUNT(*) FROM expenses) != (SELECT COUNT(*) FROM expenses_backup) THEN
                    RAISE EXCEPTION 'Data loss detected in expenses migration';
                END IF;

                IF EXISTS (SELECT 1 FROM expenses WHERE amount < 0) THEN
                    RAISE WARNING 'Negative amounts found in expenses table';
                END IF;

                IF EXISTS (SELECT 1 FROM expenses e LEFT JOIN users u ON e.user_id = u.id WHERE u.id IS NULL) THEN
                    RAISE EXCEPTION 'Orphaned records found in expenses table';
                END IF;
            END $$;
        """
        )


def downgrade() -> None:
    """
    Reverse financial data type fixes (guarded — only touches tables that
    exist, mirroring the guarded upgrade above).
    WARNING: This may result in precision loss for financial data.
    """
    if _has_table("transactions"):
        op.drop_index("ix_transactions_user_id_spent_at", table_name="transactions")
    if _has_table("expenses"):
        op.drop_index("ix_expenses_user_id_date", table_name="expenses")

    if _has_table("user_profiles"):
        with op.batch_alter_table("user_profiles") as batch_op:
            batch_op.drop_constraint("fk_user_profiles_user_id", type_="foreignkey")
        op.alter_column(
            "user_profiles",
            "user_id",
            existing_type=postgresql.UUID(as_uuid=True),
            type_=sa.String(),
            existing_nullable=False,
        )

    if _has_table("user_answers"):
        with op.batch_alter_table("user_answers") as batch_op:
            batch_op.drop_constraint("fk_user_answers_user_id", type_="foreignkey")
        op.alter_column(
            "user_answers",
            "user_id",
            existing_type=postgresql.UUID(as_uuid=True),
            type_=sa.String(),
            existing_nullable=False,
        )

    if _has_column("users", "annual_income"):
        op.alter_column(
            "users",
            "annual_income",
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Numeric(),
            existing_nullable=True,
        )

    if _has_table("goals"):
        with op.batch_alter_table("goals") as batch_op:
            batch_op.drop_constraint("fk_goals_user_id", type_="foreignkey")
        op.alter_column(
            "goals",
            "saved_amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Numeric(),
            existing_nullable=False,
        )
        op.alter_column(
            "goals",
            "target_amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Numeric(),
            existing_nullable=False,
        )

    if _has_table("expenses"):
        with op.batch_alter_table("expenses") as batch_op:
            batch_op.drop_constraint("fk_expenses_user_id", type_="foreignkey")
        op.alter_column(
            "expenses",
            "user_id",
            existing_type=postgresql.UUID(as_uuid=True),
            type_=sa.String(),
            existing_nullable=False,
        )
        # WARNING: Converting back to Float loses financial precision
        op.alter_column(
            "expenses",
            "amount",
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Float(),
            existing_nullable=False,
        )

"""IAP webhook security: store-side purchase identity + processed-event log.

- subscriptions.original_transaction_id / product_id / environment let the
  backend match store server notifications to a user through the purchase
  identity (Apple originalTransactionId, Google purchaseToken) instead of
  trusting a client-supplied user_id.
- iap_events records every processed notification; (provider, event_id) is
  unique, giving idempotency and replay protection.

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subscriptions",
        sa.Column("original_transaction_id", sa.String(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("product_id", sa.String(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "environment",
            sa.String(),
            nullable=False,
            server_default="production",
        ),
    )
    op.create_index(
        "ix_subscriptions_original_transaction_id",
        "subscriptions",
        ["original_transaction_id"],
    )

    op.create_table(
        "iap_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("transaction_key", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=False, server_default="processed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "provider", "event_id", name="uq_iap_events_provider_event"
        ),
    )
    op.create_index("ix_iap_events_transaction_key", "iap_events", ["transaction_key"])


def downgrade():
    op.drop_index("ix_iap_events_transaction_key", table_name="iap_events")
    op.drop_table("iap_events")
    op.drop_index(
        "ix_subscriptions_original_transaction_id", table_name="subscriptions"
    )
    op.drop_column("subscriptions", "environment")
    op.drop_column("subscriptions", "product_id")
    op.drop_column("subscriptions", "original_transaction_id")

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    platform = Column(String, nullable=False)
    plan = Column(String, default="standard")
    receipt = Column(JSONB, nullable=False)
    status = Column(String, default="active")
    # Store-side identity of the purchase: Apple originalTransactionId or
    # Google purchaseToken. Server notifications are matched to a user
    # through this key — never through client-supplied user ids.
    original_transaction_id = Column(String, nullable=True, index=True)
    product_id = Column(String, nullable=True)
    environment = Column(String, nullable=False, server_default="production")
    starts_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # NOTE: there is deliberately no `deleted_at` mapping here. Migration 0022
    # adds subscriptions.deleted_at conditionally, but it was added to 0022
    # *after* production had already stamped past 0022, so the live table never
    # got the column. Every `db.query(Subscription)` therefore emitted
    # `SELECT ... deleted_at` and 500'd on production (UndefinedColumn) across
    # /iap/status and the three /users/{id}/premium-* routes. Nothing filters or
    # writes the column, so the ORM must not reference it. If subscription
    # soft-delete is ever needed, re-add the mapping *and* a migration that
    # guarantees the column exists on production in the same window.

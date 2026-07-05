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
    # Soft-delete column added by migration 0018; kept on the model so the
    # ORM matches the migrated schema.
    deleted_at = Column(DateTime(timezone=True), nullable=True)

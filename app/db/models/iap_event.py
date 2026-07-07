import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class IAPEvent(Base):
    """Processed store server notifications (Apple/Google).

    The (provider, event_id) uniqueness gives webhook idempotency and
    replay protection: a notification that was already recorded is never
    applied a second time.
    """

    __tablename__ = "iap_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String, nullable=False)  # "apple" | "google"
    event_id = Column(String, nullable=False)  # notificationUUID / messageId
    event_type = Column(String, nullable=True)
    transaction_key = Column(String, nullable=True, index=True)
    result = Column(String, nullable=False, default="processed")
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_iap_events_provider_event"),
    )

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class ScheduledExpense(Base):
    """
    A future expense the user knows about in advance — insurance, rent, etc.

    Lifecycle:
        pending   → MITA shows it in forecast, reduces safe_daily_limit
        processed → cron created a real Transaction on scheduled_date
        cancelled → user removed it before it fired
        failed    → cron tried to process but something broke
    """

    __tablename__ = "scheduled_expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category = Column(String(100), nullable=False, index=True)
    amount = Column(Numeric(precision=12, scale=2), nullable=False)
    description = Column(String(500), nullable=True)
    merchant = Column(String(200), nullable=True)

    # The date the expense is expected to occur
    scheduled_date = Column(Date, nullable=False, index=True)

    # Recurrence: None/"once", "weekly", "monthly"
    recurrence = Column(String(20), nullable=True, default=None)

    # Status lifecycle
    status = Column(String(20), nullable=False, default="pending", index=True)

    # Tracking
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # FK to the Transaction that was created when this expense fired
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None, index=True)

    # Relationships
    user = relationship("User", backref="scheduled_expenses")
    transaction = relationship("Transaction", foreign_keys=[transaction_id])

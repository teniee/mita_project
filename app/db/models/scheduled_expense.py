import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class ScheduledExpense(Base):
    """
    A future expense the user knows about in advance — insurance, rent, etc.

    Lifecycle:
        pending   → MITA shows it in forecast, reduces safe_daily_limit
        processed → cron created a real Transaction on scheduled_date (app
                    rows only; or the user had already recorded the payment
                    by linking an expense to it — then no second one)
        cancelled → user removed it before it fired
        failed    → cron tried to process but something broke

    A row saved in ChatGPT (``origin = "chatgpt"``) stays pending: it is paid
    only by an expense the user links to it, never by the processor.
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

    # For a monthly payment: the day of the month the user asked for (1-31),
    # kept apart from scheduled_date, which is clamped to its month ("the
    # 31st" saved in November is due on the 30th, then on 31 December). NULL
    # when it was not kept (rows before migration 0045): the date's own day is
    # used, never a guessed one (monthly_obligations.due_dates_in_month).
    day_of_month = Column(SmallInteger, nullable=True)

    # Where the row was made (migration 0045): "app" — an instruction the
    # daily processor turns into a transaction on its date
    # (cron_task_scheduled_expenses), written only by the app's create route;
    # "chatgpt" — an obligation saved in ChatGPT, paid only when the user
    # links an expense to it (obligation_payments); "unknown" — no source
    # recorded (older rows, or a writer that does not say). Only "app" rows
    # are ever processed or pushed, so the default is the safe one.
    origin = Column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )

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

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    # Relationships
    user = relationship("User", backref="scheduled_expenses")
    transaction = relationship("Transaction", foreign_keys=[transaction_id])

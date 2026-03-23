import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class IgnoredAlert(Base):
    """
    Persistent store for budget alerts the user chose to ignore.

    Replaces the in-memory _ignored_alerts list in cron_task_followup_reminder.py.
    Survives Railway restarts and container re-deploys.

    Written by:  record_ignored_alert()  (via POST /budget/alert/ignored)
    Read by:     run_followup_reminders()  (daily cron at 09:05 UTC)
    """
    __tablename__ = "ignored_alerts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    category = Column(String(100), nullable=False)
    overspend_amount = Column(Numeric(12, 2), nullable=False)
    goal_title = Column(String(255), nullable=True)
    alert_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    reminded = Column(Boolean, nullable=False, default=False)
    reminded_at = Column(DateTime(timezone=True), nullable=True)

import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import Column, DateTime, Date, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class RedistributionEvent(Base):
    """
    Persistent audit log for every budget redistribution transfer.

    Replaces the in-memory _audit_log dict in redistribution_audit_log.py.
    Survives Railway restarts and container re-deploys.

    Written by:  realtime_rebalancer.rebalance_after_overspend()
                 budget_redistributor.redistribute_budget_for_user()
    Read by:     GET /budget/redistribution_history
    """
    __tablename__ = "redistribution_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_category = Column(String(100), nullable=False)
    to_category = Column(String(100), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    # 'realtime_rebalance' | 'budget_redistribution'
    reason = Column(String(50), nullable=False)
    # The specific day from which budget was taken (nullable for bulk ops)
    from_day = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class DailyPlan(Base):
    __tablename__ = "daily_plan"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # Category and budget tracking columns
    category = Column(String(100), nullable=True, index=True)  # Spending category
    planned_amount = Column(Numeric(12, 2), nullable=True, default=Decimal("0.00"))  # Budgeted amount
    spent_amount = Column(Numeric(12, 2), nullable=True, default=Decimal("0.00"))  # Actual spent
    daily_budget = Column(Numeric(12, 2), nullable=True)  # Total daily budget limit
    status = Column(String(20), nullable=True, default="green")  # green/yellow/red status

    # JSONB for additional metadata and backward compatibility
    plan_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

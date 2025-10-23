import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Numeric, String, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base


class Goal(Base):
    """
    Budgeting Goal Model - MODULE 5

    Represents a financial goal that users can track and work towards.
    Supports categorization, progress tracking, and deadlines.
    """
    __tablename__ = "goals"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Goal details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)  # Savings, Travel, Emergency, etc.

    # Financial tracking
    target_amount = Column(Numeric(precision=10, scale=2), nullable=False)
    saved_amount = Column(Numeric(precision=10, scale=2), nullable=False, default=0)
    monthly_contribution = Column(Numeric(precision=10, scale=2), nullable=True)  # Recommended monthly amount

    # Status and progress
    status = Column(String(20), nullable=False, default='active', index=True)  # active, completed, paused, cancelled
    progress = Column(Numeric(precision=5, scale=2), nullable=False, default=0)  # Percentage 0-100

    # Dates
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Priority for UI ordering
    priority = Column(String(10), nullable=True, default='medium')  # high, medium, low

    @hybrid_property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining amount to reach goal"""
        return max(Decimal(str(self.target_amount)) - Decimal(str(self.saved_amount)), Decimal('0'))

    @hybrid_property
    def is_completed(self) -> bool:
        """Check if goal is completed"""
        return self.status == 'completed' or self.progress >= 100

    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if goal is past target date"""
        if not self.target_date:
            return False
        return self.target_date < datetime.utcnow().date() and not self.is_completed

    def update_progress(self):
        """Calculate and update progress percentage"""
        if self.target_amount > 0:
            self.progress = min(
                (Decimal(str(self.saved_amount)) / Decimal(str(self.target_amount)) * 100),
                Decimal('100')
            )

            # Auto-complete if target reached
            if self.progress >= 100 and self.status == 'active':
                self.status = 'completed'
                self.completed_at = datetime.utcnow()
        else:
            self.progress = 0

        self.last_updated = datetime.utcnow()

    def add_savings(self, amount: Decimal):
        """Add amount to saved_amount and update progress"""
        self.saved_amount = Decimal(str(self.saved_amount)) + Decimal(str(amount))
        self.update_progress()

    def __repr__(self):
        return f"<Goal(id={self.id}, title='{self.title}', progress={self.progress}%, status='{self.status}')>"

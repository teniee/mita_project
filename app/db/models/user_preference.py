import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Boolean
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class UserPreference(Base):
    """
    Model for storing user preferences and settings
    """
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Behavioral analysis preferences
    auto_insights = Column(Boolean, default=True)
    anomaly_detection = Column(Boolean, default=True)
    predictive_alerts = Column(Boolean, default=True)
    peer_comparison = Column(Boolean, default=False)

    # Notification preferences
    anomaly_alerts = Column(Boolean, default=True)
    pattern_insights = Column(Boolean, default=True)
    weekly_summary = Column(Boolean, default=True)
    spending_warnings = Column(Boolean, default=True)

    # Budget automation preferences
    auto_adapt_enabled = Column(Boolean, default=True)
    redistribution_enabled = Column(Boolean, default=True)
    ai_suggestions_enabled = Column(Boolean, default=True)
    notification_threshold = Column(JSON, default=lambda: {"value": 0.8})  # Budget % threshold for notifications

    # Budget mode
    budget_mode = Column(String(20), default="flexible")  # flexible, strict, goal-oriented

    # Other preferences (stored as JSON for flexibility)
    additional_preferences = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

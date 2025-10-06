import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Boolean
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class FeatureUsageLog(Base):
    """
    Model for tracking feature usage analytics
    """
    __tablename__ = "feature_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    feature = Column(String(100), nullable=False, index=True)
    screen = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=True)

    # Context and metadata
    extra_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved keyword)

    # Session tracking
    session_id = Column(String(100), nullable=True, index=True)

    # Device info
    platform = Column(String(20), nullable=True)  # ios, android, web
    app_version = Column(String(20), nullable=True)

    # Timestamps
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class FeatureAccessLog(Base):
    """
    Model for tracking premium feature access attempts (for conversion tracking)
    """
    __tablename__ = "feature_access_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    feature = Column(String(100), nullable=False, index=True)
    has_access = Column(Boolean, default=False, nullable=False)
    is_premium_feature = Column(Boolean, default=False, nullable=False)

    # Conversion tracking
    converted_to_premium = Column(Boolean, default=False)
    converted_at = Column(DateTime(timezone=True), nullable=True)

    # Context
    screen = Column(String(100), nullable=True)
    extra_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved keyword)

    # Timestamps
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class PaywallImpressionLog(Base):
    """
    Model for tracking paywall impressions (for conversion funnel analysis)
    """
    __tablename__ = "paywall_impression_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    screen = Column(String(100), nullable=False, index=True)
    feature = Column(String(100), nullable=True)

    # Conversion tracking
    resulted_in_purchase = Column(Boolean, default=False)
    purchase_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Context
    impression_context = Column(String(200), nullable=True)  # what triggered the paywall
    extra_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved keyword)

    # Timestamps
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

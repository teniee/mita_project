import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)

    # Position in queue (assigned at signup, 1-based)
    position = Column(Integer, nullable=False)

    # Referral mechanics
    ref_code = Column(String(12), nullable=False, unique=True, index=True)
    referred_by_code = Column(String(12), nullable=True)
    referral_count = Column(Integer, default=0, nullable=False)

    # Boost: each referral moves user up by REFERRAL_BOOST spots
    position_boost = Column(Integer, default=0, nullable=False)

    # Email confirmed
    confirmed = Column(Boolean, default=False, nullable=False)
    confirm_token = Column(String(64), nullable=True, unique=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    country = Column(String(2), default="US")
    annual_income = Column(Numeric, default=0)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    timezone = Column(String, default="UTC")
    token_version = Column(Integer, default=1, nullable=False)
    
    # Password reset fields
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    password_reset_attempts = Column(Integer, default=0, nullable=False)
    
    # Email verification fields
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Additional fields for budget tracking
    monthly_income = Column(Numeric, default=0)

    # Relationships
    ai_snapshots = relationship("AIAnalysisSnapshot", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    challenge_participations = relationship("ChallengeParticipation", back_populates="user")

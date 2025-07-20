import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Numeric, String
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
    timezone = Column(String, default="UTC")
    ai_snapshots = relationship("AIAnalysisSnapshot", back_populates="user")

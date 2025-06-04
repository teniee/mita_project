
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    country = Column(String(2), default="US")
    annual_income = Column(Numeric, default=0)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

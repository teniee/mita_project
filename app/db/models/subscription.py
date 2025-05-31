
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    platform = Column(String, nullable=False)
    receipt = Column(JSONB, nullable=False)
    status = Column(String, default="active")
    current_period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

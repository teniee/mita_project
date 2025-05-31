
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base

class DailyPlan(Base):
    __tablename__ = "daily_plan"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    plan_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

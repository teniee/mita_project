import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String, nullable=False)
    target_amount = Column(Numeric, nullable=False)
    saved_amount = Column(Numeric, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class BudgetAdvice(Base):
    __tablename__ = "budget_advice"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    type = Column(String, nullable=False)
    text = Column(String, nullable=False)

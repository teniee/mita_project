import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base

class AIAdviceTemplate(Base):
    __tablename__ = "ai_advice_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False, index=True)
    text = Column(String, nullable=False)


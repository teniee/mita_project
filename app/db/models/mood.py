import uuid

from sqlalchemy import Column, Date, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Mood(Base):
    __tablename__ = "moods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    mood = Column(String, nullable=False)

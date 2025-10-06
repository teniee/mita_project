import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Habit(Base):
    __tablename__ = "habits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class HabitCompletion(Base):
    """
    Model for tracking habit completions
    """
    __tablename__ = "habit_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    habit_id = Column(UUID(as_uuid=True), ForeignKey("habits.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Completion data
    completed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

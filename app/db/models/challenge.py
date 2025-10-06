import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Challenge(Base):
    """
    Model for available challenges (savings streaks, category restrictions, etc.)
    """
    __tablename__ = "challenges"

    id = Column(String, primary_key=True)  # e.g., "savings_streak_7"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # streak, category_restriction, category_reduction
    duration_days = Column(Integer, nullable=False)
    reward_points = Column(Integer, default=0)
    difficulty = Column(String(20), nullable=False)  # easy, medium, hard
    start_month = Column(String(7), nullable=False)  # "2025-01"
    end_month = Column(String(7), nullable=False)  # "2025-12"
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    participations = relationship("ChallengeParticipation", back_populates="challenge")


class ChallengeParticipation(Base):
    """
    Model for user participation in challenges
    """
    __tablename__ = "challenge_participations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    challenge_id = Column(String, ForeignKey("challenges.id"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)  # "2025-10"
    status = Column(String(20), default="active")  # active, completed, failed, abandoned
    progress_percentage = Column(Integer, default=0)
    days_completed = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    challenge = relationship("Challenge", back_populates="participations")
    user = relationship("User", back_populates="challenge_participations")

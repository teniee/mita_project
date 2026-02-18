from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class HabitIn(BaseModel):
    title: str
    description: Optional[str] = None
    target_frequency: Optional[str] = "daily"  # daily, weekly, monthly


class HabitUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_frequency: Optional[str] = None


class HabitOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    target_frequency: str
    created_at: datetime
    current_streak: int = 0
    longest_streak: int = 0
    completion_rate: float = 0.0
    completed_dates: List[str] = []

    class Config:
        from_attributes = True

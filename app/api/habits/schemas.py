from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class HabitIn(BaseModel):
    title: str
    description: Optional[str] = None


class HabitUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class HabitOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

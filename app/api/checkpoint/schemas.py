from typing import Dict, List

from pydantic import BaseModel


class CheckpointInput(BaseModel):
    calendar: List[Dict]
    income: float
    day: int


class CheckpointOut(BaseModel):
    available_today: float

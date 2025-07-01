
from pydantic import BaseModel
from typing import List, Dict

class CheckpointInput(BaseModel):
    calendar: List[Dict]
    income: float
    day: int

class CheckpointOut(BaseModel):
    available_today: float

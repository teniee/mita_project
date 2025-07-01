
from pydantic import BaseModel
from typing import List

class GoalState(BaseModel):
    user_id: str
    region: str = "US-CA"
    cohort: str = "unknown"
    behavior: str = "neutral"
    income: float
    fixed_expenses: float
    goal: float
    saved: float

class GoalProgressInput(BaseModel):
    calendar: List[dict]
    target: float

class ProgressRequest(BaseModel):
    user_id: str
    year: int
    month: int
    locale: str = "en_US"

class ProgressOut(BaseModel):
    progress_pct: float
    target: float
    saved: float
    remaining: float

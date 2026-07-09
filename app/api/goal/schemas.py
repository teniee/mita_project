from typing import List, Optional

from pydantic import BaseModel


class GoalState(BaseModel):
    # Deprecated: identity is taken from the session; if sent it must match.
    user_id: Optional[str] = None
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
    # Deprecated: identity is taken from the session; if sent it must match.
    user_id: Optional[str] = None
    year: int
    month: int
    locale: str = "en_US"


class ProgressOut(BaseModel):
    progress_pct: float
    target: float
    saved: float
    remaining: float

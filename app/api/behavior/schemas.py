from typing import Dict

from pydantic import BaseModel


class BehaviorPayload(BaseModel):
    year: int
    month: int
    profile: Dict
    mood_log: Dict
    challenge_log: Dict
    calendar_log: Dict

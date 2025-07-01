from pydantic import BaseModel
from typing import List, Dict



class ChallengeFullCheckRequest(BaseModel):
    calendar: List[dict]
    today_date: str
    challenge_log: Dict

class ChallengeResult(BaseModel):
    passed: bool
    message: str
    updated_log: Dict


class StreakChallengeRequest(BaseModel):
    calendar: List[dict]
    user_id: str
    log_data: Dict

class StreakChallengeResult(BaseModel):
    streak_active: bool
    updated_log: Dict

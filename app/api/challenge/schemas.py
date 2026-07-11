from typing import Dict, List, Optional

from pydantic import BaseModel


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
    # Identity is session-bound; if a client still sends user_id it must
    # match the authenticated user (403 otherwise).
    user_id: Optional[str] = None
    log_data: Dict


class StreakChallengeResult(BaseModel):
    streak_active: bool
    updated_log: Dict

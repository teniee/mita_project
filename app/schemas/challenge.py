from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChallengeEligibilityRequest(BaseModel):
    """
    Request payload sent by the client to ask whether the user is allowed
    to join challenges in the given month.
    """
    user_id: str
    current_month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",          # example: "2025-05"
        description="Target month in the format YYYY-MM.",
    )


class ChallengeBrief(BaseModel):
    """
    A minimal representation of a challenge that can be shown in a list
    of available challenges.
    """
    challenge_id: str
    name: str
    description: str


class ChallengeEligibilityResponse(BaseModel):
    """
    Response returned by the API. It tells the client whether the user
    is eligible and, if so, which challenges can be joined.
    """
    user_id: str
    current_month: str
    eligible: bool
    reason: Optional[str] = None          # filled if eligible == False
    available_challenges: List[ChallengeBrief] = []

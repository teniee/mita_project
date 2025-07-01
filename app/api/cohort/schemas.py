
from pydantic import BaseModel
from typing import Dict

class ProfileRequest(BaseModel):
    user_id: str
    profile: Dict

class DriftRequest(BaseModel):
    user_id: str

class CohortOut(BaseModel):
    cohort: str

class DriftOut(BaseModel):
    drift: Dict

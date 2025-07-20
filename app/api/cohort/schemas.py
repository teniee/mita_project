
from pydantic import BaseModel
from typing import Dict

class ProfileRequest(BaseModel):
    profile: Dict

class DriftRequest(BaseModel):
    pass

class CohortOut(BaseModel):
    cohort: str

class DriftOut(BaseModel):
    drift: Dict

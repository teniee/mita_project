from typing import Dict

from pydantic import BaseModel


class ProfileRequest(BaseModel):
    profile: Dict


class DriftRequest(BaseModel):
    pass


class CohortOut(BaseModel):
    cohort: str


class DriftOut(BaseModel):
    drift: Dict

from typing import List, Optional

from pydantic import BaseModel


class AnomalyDetectionRequest(BaseModel):
    user_id: str
    start_date: str
    end_date: str


class MonthlyAggregationRequest(BaseModel):
    user_id: str
    month: str
    year: int


class ProgressRequest(BaseModel):
    user_id: str
    period: str  # e.g., 'weekly', 'monthly'


class DailyCheckpointRequest(BaseModel):
    user_id: str
    date: str

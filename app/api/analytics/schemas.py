
from pydantic import BaseModel
from typing import List, Dict
from datetime import date

class CalendarPayload(BaseModel):
    calendar: List[dict]

class AnomalyResult(BaseModel):
    anomalies: List[dict]

class AggregateResult(BaseModel):
    aggregation: Dict[str, float]

class MonthlyAnalyticsOut(BaseModel):
    categories: Dict[str, float]

class TrendOut(BaseModel):
    trend: List[dict]

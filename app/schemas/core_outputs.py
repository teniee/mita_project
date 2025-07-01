
from pydantic import BaseModel
from typing import List
from datetime import datetime

class TransactionOut(BaseModel):
    id: str
    category: str
    amount: float
    currency: str = "USD"
    spent_at: datetime

class AnalyticsCategory(BaseModel):
    name: str
    amount: float
    percentage: float

class TrendPoint(BaseModel):
    date: str
    amount: float

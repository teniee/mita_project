from datetime import datetime
from typing import List

from pydantic import BaseModel


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

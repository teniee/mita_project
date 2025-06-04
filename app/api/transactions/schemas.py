
from pydantic import BaseModel
from datetime import datetime
from typing import List

class TxnIn(BaseModel):
    category: str
    amount: float
    currency: str = "USD"
    spent_at: datetime = datetime.utcnow()

class TxnOut(BaseModel):
    id: str
    category: str
    amount: float
    currency: str
    spent_at: datetime

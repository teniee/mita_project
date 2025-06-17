from datetime import datetime

from pydantic import BaseModel


class TxnIn(BaseModel):
    category: str
    amount: float
    spent_at: datetime = datetime.utcnow()


class TxnOut(BaseModel):
    id: str
    category: str
    amount: float
    currency: str
    spent_at: datetime

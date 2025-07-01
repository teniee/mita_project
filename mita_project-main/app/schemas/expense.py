from pydantic import BaseModel
from typing import List
from datetime import date


class ExpenseEntry(BaseModel):
    user_id: str
    action: str
    amount: float
    date: str


class ExpenseHistoryRequest(BaseModel):
    user_id: str


class ExpenseOut(BaseModel):
    user_id: str
    action: str
    amount: float
    date: date


class ExpenseHistoryOut(BaseModel):
    expenses: List[ExpenseOut]

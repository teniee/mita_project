
from pydantic import BaseModel

class InstallmentEvalRequest(BaseModel):
    user_id: str
    profile: dict
    goal: float
    income: float
    fixed_expenses: float

class InstallmentEvalResult(BaseModel):
    approved: bool
    limit: float
    message: str

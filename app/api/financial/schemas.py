from pydantic import BaseModel


class InstallmentEvalRequest(BaseModel):
    price: float
    months: int


class InstallmentEvalResult(BaseModel):
    can_afford: bool
    monthly_payment: float
    reason: str

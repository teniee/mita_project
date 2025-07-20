from typing import Any, Dict

from pydantic import BaseModel


class BudgetRequest(BaseModel):
    user_answers: Dict[str, Any]
    year: int
    month: int

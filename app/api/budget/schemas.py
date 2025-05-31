from pydantic import BaseModel
from typing import Dict, Any

class BudgetRequest(BaseModel):
    user_answers: Dict[str, Any]
    year: int
    month: int

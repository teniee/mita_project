from fastapi import APIRouter, HTTPException
from app.api.budget.schemas import BudgetRequest
from app.api.budget.services import generate_user_budget

router = APIRouter(prefix="/budget", tags=["budget"])


@router.post("/generate")
def generate_monthly_budget(request: BudgetRequest):
    try:
        return generate_user_budget(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


from fastapi import APIRouter
from app.api.financial.schemas import InstallmentEvalRequest, InstallmentEvalResult
from app.api.financial.services import evaluate_installment
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/financial", tags=["financial"])

@router.post("/installment-evaluate", response_model=InstallmentEvalResult)
async def installment_check(payload: InstallmentEvalRequest):
    result = evaluate_installment(payload.profile, payload.goal, payload.income, payload.fixed_expenses)
    return success_response(result)
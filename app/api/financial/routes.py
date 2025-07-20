from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.financial.schemas import InstallmentEvalRequest  # noqa: E501
from app.api.financial.schemas import InstallmentEvalResult
from app.api.financial.services import evaluate_installment
from app.core.session import get_db
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/financial", tags=["financial"])


@router.post("/installment-evaluate", response_model=InstallmentEvalResult)
async def installment_check(
    payload: InstallmentEvalRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    result = evaluate_installment(user.id, payload.price, payload.months, db)
    return success_response(result)

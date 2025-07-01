from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_premium_user
from app.core.session import get_db
from app.db.models import BudgetAdvice
from app.utils.response_wrapper import success_response
from .schemas import AdviceOut

router = APIRouter(prefix="", tags=["insights"])


@router.get("/", response_model=AdviceOut | None)
async def latest_insight(
    user=Depends(require_premium_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    advice = (
        db.query(BudgetAdvice)
        .filter(BudgetAdvice.user_id == user.id)
        .order_by(BudgetAdvice.date.desc())
        .first()
    )
    data = (
        AdviceOut.model_validate(advice).model_dump(mode="json") if advice else None
    )
    return success_response(data)


@router.get("/history", response_model=list[AdviceOut])
async def insight_history(
    user=Depends(require_premium_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    items = (
        db.query(BudgetAdvice)
        .filter(BudgetAdvice.user_id == user.id)
        .order_by(BudgetAdvice.date.desc())
        .all()
    )
    data = [AdviceOut.model_validate(it).model_dump(mode="json") for it in items]
    return success_response(data)

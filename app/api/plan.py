from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import DailyPlan
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/{year}/{month}")
def plan_month(
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    rows = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user.id,
            DailyPlan.date.between(
                date(year, month, 1),
                date(year, month, 28),
            ),
        )
        .all()
    )
    return success_response({row.date.day: row.plan_json for row in rows})

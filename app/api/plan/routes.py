from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import DailyPlan
from app.services.monthly_plan_service import ensure_month_plan_safe
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/{year}/{month}", response_model=dict)
def plan_month(
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    ensure_month_plan_safe(db, user.id, year, month)

    start = date(year, month, 1)
    # NOTE: this window has always stopped at the 28th, so days 29-31 are
    # invisible to this endpoint. Pre-existing and out of scope here; it does
    # not affect the 404-on-missing-month behavior this call fixes, since a
    # materialized month always has rows on or before the 28th.
    end = date(year, month, 28)
    rows = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user.id,
            DailyPlan.date.between(start, end),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return success_response({row.date.day: row.plan_json for row in rows})

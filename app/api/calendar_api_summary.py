from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from collections import defaultdict

from app.services.auth_dependency import get_current_user
from app.core.db import get_db
from app.db.models import DailyPlan
from app.db.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar-summary"])

@router.get("/summary/{year}/{month}")
def get_month_summary(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        start = date(year, month, 1)
        end = date(year + (month // 12), (month % 12) + 1, 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid year or month")

    entries = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id)
        .filter(DailyPlan.date >= start)
        .filter(DailyPlan.date < end)
        .all()
    )

    summary = defaultdict(lambda: {"planned": 0.0, "spent": 0.0, "difference": 0.0})
    for entry in entries:
        cat = entry.category
        summary[cat]["planned"] += float(entry.planned_amount)
        summary[cat]["spent"] += float(entry.spent_amount)
        summary[cat]["difference"] = round(
            summary[cat]["planned"] - summary[cat]["spent"], 2
        )

    # round all values
    for cat in summary:
        for key in summary[cat]:
            summary[cat][key] = round(summary[cat][key], 2)

    return dict(summary)

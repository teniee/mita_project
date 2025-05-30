from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import Dict

from app.services.auth_dependency import get_current_user
from app.db.models.user import User
from app.core.db import get_db
from app.db.models import DailyPlan

router = APIRouter(prefix="/calendar", tags=["calendar-extended"])

@router.delete("/{year}/{month}")
def delete_calendar_month(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        start = date(year, month, 1)
        end = date(year + (month // 12), ((month % 12) + 1), 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid year/month")

    deleted = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id)
        .filter(DailyPlan.date >= start)
        .filter(DailyPlan.date < end)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"status": "deleted", "records": deleted}

@router.get("/day/{day}")
def get_calendar_day(
    day: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Dict[str, float]]:
    entries = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user.id)
        .filter(DailyPlan.date == day)
        .all()
    )
    if not entries:
        raise HTTPException(status_code=404, detail="No entries found for this date")

    return {
        "date": day.isoformat(),
        "categories": {
            entry.category: {
                "planned": float(entry.planned_amount),
                "spent": float(entry.spent_amount),
            } for entry in entries
        }
    }

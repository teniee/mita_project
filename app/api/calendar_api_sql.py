from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import Dict

from app.services.auth_dependency import get_current_user # Fixed import
from app.db.models.user import User # Assuming User model is here
from app.core.db import get_db
from app.services.validation import validate_category, validate_amount
from app.services.calendar_service_real import fetch_calendar, update_day_entry

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.get("/{year}/{month}")
def get_calendar(year: int, month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Dict[str, Dict[str, float]]:
    return fetch_calendar(db, user.id, year, month)

@router.patch("/{day}")
def patch_calendar_day(day: date, updates: Dict[str, float], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for cat, amt in updates.items():
        validate_category(cat)
        validate_amount(amt)
    update_day_entry(db, user.id, day, updates)
    return {"status": "updated", "date": day.isoformat()}


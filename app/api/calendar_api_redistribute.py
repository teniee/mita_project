from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services.auth_dependency import get_current_user
from app.db.models.user import User
from app.core.db import get_db
from app.services.budget_redistributor import redistribute_budget_for_user

router = APIRouter(prefix="/calendar", tags=["calendar-redistribute"])

@router.post("/redistribute/{year}/{month}")
def redistribute_budget(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = redistribute_budget_for_user(db, user_id=user.id, year=year, month=month)
    return result

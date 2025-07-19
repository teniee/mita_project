from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.session import get_db

# assumes User is defined in models
from app.db.models.user import User
from app.services.auth_dependency import get_current_user

from app.api.budget.services import fetch_remaining_budget  # isort:skip
from app.api.budget.services import fetch_spent_by_category  # isort:skip


router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/spent")
async def spent(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Return spending amounts grouped by category."""

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    return fetch_spent_by_category(db, user.id, year, month)


@router.get("/remaining")
async def remaining(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Return the remaining budget for the month."""

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    return fetch_remaining_budget(db, user.id, year, month)

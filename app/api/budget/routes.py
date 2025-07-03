
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.budget.services import (
    fetch_remaining_budget,
    fetch_spent_by_category,
)
from app.core.session import get_db
# assumes User is defined in models
from app.db.models.user import User
from app.services.auth_dependency import get_current_user

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/spent")
async def spent(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return spending amounts grouped by category."""

    return fetch_spent_by_category(db, user.id, 2025, 5)


@router.get("/remaining")
async def remaining(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the remaining budget for the month."""

    return fetch_remaining_budget(db, user.id, 2025, 5)

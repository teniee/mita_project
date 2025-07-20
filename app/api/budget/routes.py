from datetime import datetime
from typing import Optional
import inspect

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.session import get_db

# assumes User is defined in models
from app.db.models.user import User
from app.api.dependencies import get_current_user

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
    if not isinstance(user, User):
        user = get_current_user()  # type: ignore
    if not isinstance(db, Session):
        db = next(get_db())  # type: ignore

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    result = fetch_spent_by_category(db, user.id, year, month)
    if inspect.isawaitable(result):
        result = await result
    return result


@router.get("/remaining")
async def remaining(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Return the remaining budget for the month."""
    if not isinstance(user, User):
        user = get_current_user()  # type: ignore
    if not isinstance(db, Session):
        db = next(get_db())  # type: ignore

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    result = fetch_remaining_budget(db, user.id, year, month)
    if inspect.isawaitable(result):
        result = await result
    return result

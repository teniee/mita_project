import inspect
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db

# assumes User is defined in models
from app.db.models.user import User
from app.utils.response_wrapper import success_response

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
    return success_response(result)


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
    return success_response(result)


@router.get("/suggestions")
async def get_budget_suggestions(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get AI-powered budget suggestions"""
    # Mock data for now - this would be replaced with actual AI analysis
    suggestions_data = {
        "suggestions": [
            {
                "id": 1,
                "text": "Consider reducing dining out expenses by 20% to meet your savings goal",
                "category": "dining",
                "potential_savings": 120.0,
                "difficulty": "easy"
            },
            {
                "id": 2, 
                "text": "You could save $45/month by switching to generic brands for groceries",
                "category": "groceries",
                "potential_savings": 45.0,
                "difficulty": "easy"
            }
        ],
        "total_potential_savings": 165.0,
        "priority_areas": ["dining", "groceries", "entertainment"]
    }
    return success_response(suggestions_data)


@router.get("/mode")
async def get_budget_mode(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get current budget mode setting"""
    # Mock data for now - this would be retrieved from user preferences
    return success_response("flexible")


@router.get("/redistribution_history")
async def get_redistribution_history(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get budget redistribution history"""
    # Mock data for now - this would be retrieved from database
    history_data = [
        {
            "id": 1,
            "from": "15",
            "to": "20", 
            "amount": 25.0,
            "date": "2025-01-28T10:30:00Z",
            "reason": "automatic_redistribution"
        },
        {
            "id": 2,
            "from": "12",
            "to": "18",
            "amount": 15.0, 
            "date": "2025-01-27T14:22:00Z",
            "reason": "overspending_adjustment"
        }
    ]
    return success_response(history_data)

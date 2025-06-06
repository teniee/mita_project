# flake8: noqa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.category_goal_service import (
    get_goal_progress,
    list_category_goals,
    set_category_goal,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/category-goal", tags=["category_goal"])


class GoalInput(BaseModel):
    user_id: str
    category: str
    year: int
    month: int
    amount: float


@router.post("/set")
async def set_goal(
    payload: GoalInput,
    db: Session = Depends(get_db),  # noqa: B008
):
    goal = set_category_goal(
        db,
        user_id=payload.user_id,
        category=payload.category,
        year=payload.year,
        month=payload.month,
        amount=payload.amount,
    )
    return success_response({"goal_id": str(goal.id)})


class GoalQuery(BaseModel):
    user_id: str
    year: int
    month: int


@router.post("/list")
async def list_goals(
    payload: GoalQuery,
    db: Session = Depends(get_db),  # noqa: B008
):
    goals = list_category_goals(
        db,
        payload.user_id,
        payload.year,
        payload.month,
    )
    data = [
        {
            "category": g.category,
            "amount": float(g.target_amount),
        }
        for g in goals
    ]
    return success_response({"goals": data})


class ProgressQuery(BaseModel):
    user_id: str
    category: str
    year: int
    month: int


@router.post("/progress")
async def goal_progress(
    payload: ProgressQuery,
    db: Session = Depends(get_db),  # noqa: B008
):
    result = get_goal_progress(
        db,
        payload.user_id,
        payload.category,
        payload.year,
        payload.month,
    )
    return success_response(result or {"status": "no_goal"})

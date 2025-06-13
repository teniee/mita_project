from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import Goal
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="", tags=["goals"])


class GoalIn(BaseModel):
    title: str
    target_amount: float


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    target_amount: Optional[float] = None


class GoalOut(BaseModel):
    id: UUID
    title: str
    target_amount: float
    saved_amount: float


@router.post("/", response_model=GoalOut)
def create_goal(
    data: GoalIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    goal = Goal(
        user_id=user.id,
        title=data.title,
        target_amount=data.target_amount,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return success_response(
        {
            "id": goal.id,
            "title": goal.title,
            "target_amount": float(goal.target_amount),
            "saved_amount": float(goal.saved_amount),
        }
    )


@router.get("/", response_model=List[GoalOut])
def list_goals(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    return success_response(
        [
            {
                "id": g.id,
                "title": g.title,
                "target_amount": float(g.target_amount),
                "saved_amount": float(g.saved_amount),
            }
            for g in goals
        ]
    )


@router.patch("/{goal_id}")
def update_goal(
    goal_id: UUID,
    data: GoalUpdate,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    goal = (
        db.query(Goal)
        .filter(
            Goal.id == goal_id,
            Goal.user_id == user.id,
        )
        .first()
    )
    if not goal:
        return success_response({"error": "not found"})
    if data.title is not None:
        goal.title = data.title
    if data.target_amount is not None:
        goal.target_amount = data.target_amount
    db.commit()
    return success_response({"status": "updated"})


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    goal = (
        db.query(Goal)
        .filter(
            Goal.id == goal_id,
            Goal.user_id == user.id,
        )
        .first()
    )
    if goal:
        db.delete(goal)
        db.commit()
    return success_response({"status": "deleted"})

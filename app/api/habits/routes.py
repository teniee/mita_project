from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import Habit
from app.utils.response_wrapper import success_response

from .schemas import HabitIn, HabitOut, HabitUpdate

router = APIRouter(prefix="", tags=["habits"])


@router.post("/", response_model=HabitOut)
def create_habit(
    data: HabitIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    habit = Habit(
        user_id=user.id,
        title=data.title,
        description=data.description,
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return success_response(
        {
            "id": habit.id,
            "title": habit.title,
            "description": habit.description,
            "created_at": habit.created_at,
        }
    )


@router.get("/", response_model=List[HabitOut])
def list_habits(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    habits = db.query(Habit).filter(Habit.user_id == user.id).all()
    return success_response(
        [
            {
                "id": h.id,
                "title": h.title,
                "description": h.description,
                "created_at": h.created_at,
            }
            for h in habits
        ]
    )


@router.patch("/{habit_id}")
def update_habit(
    habit_id: UUID,
    data: HabitUpdate,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    habit = (
        db.query(Habit)
        .filter(Habit.id == habit_id, Habit.user_id == user.id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="not found")
    if data.title is not None:
        habit.title = data.title
    if data.description is not None:
        habit.description = data.description
    db.commit()
    return success_response({"status": "updated"})


@router.delete("/{habit_id}")
def delete_habit(
    habit_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    habit = (
        db.query(Habit)
        .filter(Habit.id == habit_id, Habit.user_id == user.id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(habit)
    db.commit()
    return success_response({"status": "deleted"})

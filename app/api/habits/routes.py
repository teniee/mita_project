from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.base_crud import CRUDHelper
from app.api.dependencies import get_current_user
from app.core.db import get_db
from app.db.models import Habit, HabitCompletion
from app.utils.response_wrapper import success_response

from .schemas import HabitIn, HabitOut, HabitUpdate

router = APIRouter(prefix="/habits", tags=["habits"])


@router.post("/", response_model=HabitOut)
async def create_habit(
    data: HabitIn,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    habit = CRUDHelper.create_user_resource(
        db, Habit,
        {"title": data.title, "description": data.description},
        user.id
    )
    return success_response({
        "id": habit.id,
        "title": habit.title,
        "description": habit.description,
        "created_at": habit.created_at,
    })


@router.get("/", response_model=List[HabitOut])
async def list_habits(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    habits = CRUDHelper.get_user_resources(db, Habit, user.id)
    return success_response([
        {
            "id": h.id,
            "title": h.title,
            "description": h.description,
            "created_at": h.created_at,
        }
        for h in habits
    ])


@router.patch("/{habit_id}")
async def update_habit(
    habit_id: UUID,
    data: HabitUpdate,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    habit = CRUDHelper.get_user_resource_or_404(
        db, Habit, habit_id, user.id, "Habit not found"
    )
    CRUDHelper.update_resource(
        db, habit,
        {"title": data.title, "description": data.description}
    )
    return success_response({"status": "updated"})


@router.delete("/{habit_id}")
async def delete_habit(
    habit_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    CRUDHelper.delete_user_resource_or_404(
        db, Habit, habit_id, user.id, "Habit not found"
    )
    return success_response({"status": "deleted"})


# NEW ENDPOINTS for mobile app integration

@router.post("/{habit_id}/complete")
async def complete_habit(
    habit_id: UUID,
    date: str = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Mark habit as completed for a specific date"""
    from datetime import datetime

    habit = CRUDHelper.get_user_resource_or_404(
        db, Habit, habit_id, user.id, "Habit not found"
    )

    completion_date = datetime.fromisoformat(date.replace('Z', '+00:00')) if date else datetime.utcnow()

    # Check if already completed for this date
    result = await db.execute(
        select(HabitCompletion).filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.user_id == user.id,
            HabitCompletion.completed_at >= completion_date.replace(hour=0, minute=0, second=0),
            HabitCompletion.completed_at < completion_date.replace(hour=23, minute=59, second=59)
        )
    )
    existing = result.scalars().first()

    if existing:
        return success_response({
            "status": "already_completed",
            "habit_id": str(habit_id),
            "completed_at": existing.completed_at.isoformat()
        })

    # Create new completion record
    completion = HabitCompletion(
        habit_id=habit_id,
        user_id=user.id,
        completed_at=completion_date
    )
    db.add(completion)
    await db.commit()

    return success_response({
        "status": "completed",
        "habit_id": str(habit_id),
        "completed_at": completion_date.isoformat()
    })


@router.get("/{habit_id}/progress")
async def get_habit_progress(
    habit_id: UUID,
    start_date: str = None,
    end_date: str = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Get habit completion progress over time"""
    from datetime import datetime, timedelta

    habit = CRUDHelper.get_user_resource_or_404(
        db, Habit, habit_id, user.id, "Habit not found"
    )

    # Parse dates
    start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else datetime.utcnow() - timedelta(days=30)
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else datetime.utcnow()

    # Query completions
    result = await db.execute(
        select(HabitCompletion).filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.user_id == user.id,
            HabitCompletion.completed_at >= start,
            HabitCompletion.completed_at <= end
        )
    )
    completions = result.scalars().all()

    completion_dates = [c.completed_at.date().isoformat() for c in completions]
    total_days = (end - start).days + 1
    completion_rate = len(completions) / total_days if total_days > 0 else 0

    # Calculate streak
    current_streak = 0
    check_date = end.date()
    while check_date >= start.date():
        if check_date.isoformat() in completion_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return success_response({
        "habit_id": str(habit_id),
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "total_completions": len(completions),
        "completion_rate": round(completion_rate, 2),
        "current_streak": current_streak,
        "completion_dates": completion_dates
    })

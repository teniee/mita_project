from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db as get_db
from app.db.models import Habit, HabitCompletion
from app.utils.response_wrapper import success_response
from app.services.habit_service import get_habit_with_stats

from .schemas import HabitIn, HabitOut, HabitUpdate

router = APIRouter(prefix="/habits", tags=["habits"])


@router.post("/")
async def create_habit(
    data: HabitIn,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Create a new habit for the authenticated user"""
    habit = Habit(
        user_id=user.id,
        title=data.title,
        description=data.description,
        target_frequency=data.target_frequency or "daily"
    )
    db.add(habit)
    await db.commit()
    await db.refresh(habit)

    # Return complete habit data with statistics (will be empty for new habit)
    habit_data = await get_habit_with_stats(habit, user.id, db)
    return success_response(habit_data)


@router.get("/")
async def list_habits(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """List all habits for the authenticated user with complete statistics"""
    result = await db.execute(
        select(Habit).where(Habit.user_id == user.id)
    )
    habits = result.scalars().all()

    # Get complete habit data with statistics for each habit
    habits_with_stats = []
    for habit in habits:
        habit_data = await get_habit_with_stats(habit, user.id, db)
        habits_with_stats.append(habit_data)

    return success_response(habits_with_stats)


@router.patch("/{habit_id}")
async def update_habit(
    habit_id: UUID,
    data: HabitUpdate,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Update an existing habit"""
    result = await db.execute(
        select(Habit).where(
            and_(Habit.id == habit_id, Habit.user_id == user.id)
        )
    )
    habit = result.scalar_one_or_none()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    if data.title is not None:
        habit.title = data.title
    if data.description is not None:
        habit.description = data.description
    if data.target_frequency is not None:
        habit.target_frequency = data.target_frequency

    await db.commit()
    await db.refresh(habit)

    # Return updated habit with statistics
    habit_data = await get_habit_with_stats(habit, user.id, db)
    return success_response(habit_data)


@router.delete("/{habit_id}")
async def delete_habit(
    habit_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Delete a habit and all its completions"""
    result = await db.execute(
        select(Habit).where(
            and_(Habit.id == habit_id, Habit.user_id == user.id)
        )
    )
    habit = result.scalar_one_or_none()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    await db.delete(habit)
    await db.commit()
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
    # Verify habit exists and belongs to user
    result = await db.execute(
        select(Habit).where(
            and_(Habit.id == habit_id, Habit.user_id == user.id)
        )
    )
    habit = result.scalar_one_or_none()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

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


@router.delete("/{habit_id}/complete")
async def uncomplete_habit(
    habit_id: UUID,
    body: dict = Body(default={}),
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Remove the completion record for a habit on a given date (uncomplete)."""
    result = await db.execute(
        select(Habit).where(
            and_(Habit.id == habit_id, Habit.user_id == user.id)
        )
    )
    habit = result.scalar_one_or_none()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    date_str = body.get("date")
    if date_str:
        completion_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    else:
        completion_date = datetime.utcnow()

    result = await db.execute(
        select(HabitCompletion).filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.user_id == user.id,
            HabitCompletion.completed_at >= completion_date.replace(hour=0, minute=0, second=0),
            HabitCompletion.completed_at < completion_date.replace(hour=23, minute=59, second=59),
        )
    )
    existing = result.scalars().first()

    if not existing:
        return success_response({
            "status": "not_completed",
            "habit_id": str(habit_id),
        })

    await db.delete(existing)
    await db.commit()

    return success_response({
        "status": "uncompleted",
        "habit_id": str(habit_id),
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
    # Verify habit exists and belongs to user
    result = await db.execute(
        select(Habit).where(
            and_(Habit.id == habit_id, Habit.user_id == user.id)
        )
    )
    habit = result.scalar_one_or_none()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

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

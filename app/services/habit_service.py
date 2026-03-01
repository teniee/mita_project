"""
Service for calculating habit statistics and streaks
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Habit, HabitCompletion


async def calculate_habit_statistics(
    habit_id: UUID,
    user_id: UUID,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Calculate comprehensive statistics for a habit including:
    - current_streak: consecutive days from today backwards
    - longest_streak: longest consecutive streak ever
    - completion_rate: percentage of days completed in last 30 days
    - completed_dates: list of ISO date strings for last 30 days
    """
    # Query completions for the last 90 days to calculate streaks accurately
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)

    result = await db.execute(
        select(HabitCompletion)
        .filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.user_id == user_id,
            HabitCompletion.completed_at >= ninety_days_ago
        )
        .order_by(HabitCompletion.completed_at.desc())
    )
    all_completions = result.scalars().all()

    # Extract completed dates
    completion_dates_set = set(
        c.completed_at.date() for c in all_completions
    )

    # Calculate current streak (from today backwards)
    current_streak = 0
    check_date = datetime.utcnow().date()

    while check_date in completion_dates_set:
        current_streak += 1
        check_date -= timedelta(days=1)

    # Calculate longest streak
    longest_streak = 0
    current_temp_streak = 0

    if completion_dates_set:
        # Get sorted dates
        sorted_dates = sorted(completion_dates_set)

        for i, date in enumerate(sorted_dates):
            if i == 0:
                current_temp_streak = 1
            else:
                # Check if consecutive
                if (date - sorted_dates[i-1]).days == 1:
                    current_temp_streak += 1
                else:
                    longest_streak = max(longest_streak, current_temp_streak)
                    current_temp_streak = 1

        longest_streak = max(longest_streak, current_temp_streak)

    # Calculate completion rate for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_completions = [
        c for c in all_completions
        if c.completed_at >= thirty_days_ago
    ]

    completion_rate = (len(recent_completions) / 30.0) * 100.0

    # Get completed dates for last 30 days as ISO strings
    completed_dates = sorted([
        c.completed_at.date().isoformat()
        for c in recent_completions
    ])

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "completion_rate": round(completion_rate, 1),
        "completed_dates": completed_dates
    }


async def get_habit_with_stats(
    habit: Habit,
    user_id: UUID,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Get habit data with calculated statistics
    """
    stats = await calculate_habit_statistics(habit.id, user_id, db)

    return {
        "id": str(habit.id),
        "title": habit.title,
        "description": habit.description,
        "target_frequency": habit.target_frequency,
        "created_at": habit.created_at.isoformat() if habit.created_at else None,
        "current_streak": stats["current_streak"],
        "longest_streak": stats["longest_streak"],
        "completion_rate": stats["completion_rate"],
        "completed_dates": stats["completed_dates"]
    }

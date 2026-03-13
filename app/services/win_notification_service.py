"""
Win Notification Service
Sends positive motivational notifications when users are on track.
Based on behavioral economics: celebrate small wins (Thaler).
"""
from typing import Optional, Dict, List
from uuid import UUID
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Goal, User
from app.core.logging_config import get_logger

logger = get_logger(__name__)

STREAK_THRESHOLD = 7  # days of green status to trigger celebration


class WinNotificationService:
    def __init__(self, db: Session):
        self.db = db

    def check_streak_win(self, user_id: UUID, check_date: Optional[date] = None) -> Optional[Dict]:
        """
        Check if user has a spending streak (N consecutive green days).
        Returns win notification dict if streak found, None otherwise.

        A "green day" means spent_amount <= planned_amount for that day's total.
        """
        if check_date is None:
            check_date = date.today()

        # Check last STREAK_THRESHOLD days
        streak_days: List[date] = []
        for i in range(STREAK_THRESHOLD):
            day = check_date - timedelta(days=i)
            entries = (
                self.db.query(DailyPlan)
                .filter(DailyPlan.user_id == user_id)
                .filter(DailyPlan.date == day)
                .all()
            )
            if not entries:
                break  # Gap in data — streak broken

            day_planned = sum(float(e.planned_amount) for e in entries)
            day_spent = sum(float(e.spent_amount) for e in entries)

            if day_spent <= day_planned:
                streak_days.append(day)
            else:
                break  # Not green — streak broken

        if len(streak_days) < STREAK_THRESHOLD:
            return None

        # Calculate savings progress
        saved_amount = self._calculate_streak_savings(user_id, streak_days)

        # Get primary goal
        goal = self._get_primary_goal(user_id)

        win_message = f"You've been on budget for {len(streak_days)} days in a row!"
        if goal and saved_amount > 0:
            win_message += f" You're ${saved_amount:.2f} closer to [{goal.title}]!"

        return {
            "type": "streak_win",
            "streak_days": len(streak_days),
            "saved_amount": float(saved_amount),
            "goal_title": goal.title if goal else None,
            "message": win_message,
        }

    def _calculate_streak_savings(self, user_id: UUID, streak_days: List[date]) -> Decimal:
        """Sum of (planned - spent) across streak days."""
        total_saved = Decimal("0")
        for day in streak_days:
            entries = (
                self.db.query(DailyPlan)
                .filter(DailyPlan.user_id == user_id)
                .filter(DailyPlan.date == day)
                .all()
            )
            for e in entries:
                delta = Decimal(str(e.planned_amount)) - Decimal(str(e.spent_amount))
                if delta > 0:
                    total_saved += delta
        return total_saved

    def _get_primary_goal(self, user_id: UUID) -> Optional[object]:
        """Get user's highest-priority active goal."""
        return (
            self.db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.status == "active")
            .order_by(Goal.priority)
            .first()
        )


def get_win_notification_service(db: Session) -> WinNotificationService:
    return WinNotificationService(db)

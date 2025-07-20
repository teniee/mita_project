from decimal import Decimal
from typing import Dict

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.db.models.daily_plan import DailyPlan


class BudgetTracker:
    def __init__(self, db: Session, user_id: int, year: int, month: int):
        self.db = db
        self.user_id = user_id
        self.year = year
        self.month = month

    def get_spent(self) -> Dict[str, Decimal]:
        """Returns total spent amount per category for the month."""
        result = (
            self.db.query(DailyPlan.category, func.sum(DailyPlan.spent_amount))
            .filter(DailyPlan.user_id == self.user_id)
            .filter(extract("year", DailyPlan.date) == self.year)
            .filter(extract("month", DailyPlan.date) == self.month)
            .group_by(DailyPlan.category)
            .all()
        )

        return {category: amount or Decimal("0.00") for category, amount in result}

    def get_remaining_per_category(self) -> Dict[str, Decimal]:
        """Returns remaining budget per category: planned - spent."""
        result = (
            self.db.query(
                DailyPlan.category,
                func.sum(DailyPlan.planned_amount),
                func.sum(DailyPlan.spent_amount),
            )
            .filter(DailyPlan.user_id == self.user_id)
            .filter(extract("year", DailyPlan.date) == self.year)
            .filter(extract("month", DailyPlan.date) == self.month)
            .group_by(DailyPlan.category)
            .all()
        )

        remaining = {}
        for category, total_planned, total_spent in result:
            remaining[category] = (total_planned or Decimal("0.00")) - (
                total_spent or Decimal("0.00")
            )

        return remaining

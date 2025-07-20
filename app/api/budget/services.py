from sqlalchemy.orm import Session

from app.services.core.engine.budget_tracker import BudgetTracker


def fetch_spent_by_category(db: Session, user_id: int, year: int, month: int):
    tracker = BudgetTracker(db=db, user_id=user_id, year=year, month=month)
    return tracker.get_spent()


def fetch_remaining_budget(db: Session, user_id: int, year: int, month: int):
    tracker = BudgetTracker(db=db, user_id=user_id, year=year, month=month)
    return tracker.get_remaining_per_category()

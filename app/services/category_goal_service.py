from decimal import Decimal
from typing import List, Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.db.models import CategoryGoal, Transaction


def set_category_goal(
    db: Session,
    user_id: str,
    category: str,
    year: int,
    month: int,
    amount: float,
) -> CategoryGoal:
    obj = (
        db.query(CategoryGoal)
        .filter_by(user_id=user_id, category=category, year=year, month=month)
        .first()
    )
    if obj:
        obj.target_amount = Decimal(amount)
    else:
        obj = CategoryGoal(
            user_id=user_id,
            category=category,
            year=year,
            month=month,
            target_amount=Decimal(amount),
        )
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_category_goals(
    db: Session, user_id: str, year: int, month: int
) -> List[CategoryGoal]:
    return (
        db.query(CategoryGoal)
        .filter_by(user_id=user_id, year=year, month=month)
        .all()  # noqa: E501
    )


def get_goal_progress(
    db: Session,
    user_id: str,
    category: str,
    year: int,
    month: int,
) -> Optional[dict]:
    goal = (
        db.query(CategoryGoal)
        .filter_by(
            user_id=user_id,
            category=category,
            year=year,
            month=month,
        )
        .first()
    )
    if not goal:
        return None

    spent = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id
    ).filter(Transaction.category == category).filter(
        extract("year", Transaction.spent_at) == year
    ).filter(
        extract("month", Transaction.spent_at) == month
    ).scalar() or Decimal(
        "0"
    )

    spent_f = float(spent)
    target_f = float(goal.target_amount)
    pct = (spent_f / target_f * 100) if target_f else 0.0

    return {
        "category": category,
        "target": target_f,
        "spent": spent_f,
        "progress_pct": round(pct, 2),
        "remaining": max(target_f - spent_f, 0.0),
    }

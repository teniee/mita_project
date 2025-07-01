from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import Transaction
from app.schemas.core_outputs import AnalyticsCategory, TrendPoint

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/monthly/{user_id}", response_model=List[AnalyticsCategory])
# fmt: off
def get_monthly_analytics(
    user_id: str, db: Session = Depends(get_db)  # noqa: B008
):
    # fmt: on
    today = datetime.utcnow()
    month_start = datetime(today.year, today.month, 1)
    month_end = (
        datetime(today.year, today.month + 1, 1)
        if today.month < 12
        else datetime(today.year + 1, 1, 1)
    )

    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= month_start,
            Transaction.spent_at < month_end,
        )
        .all()
    )

    totals = {}
    for txn in txns:
        totals[txn.category] = totals.get(txn.category, 0) + txn.amount

    total_spent = sum(totals.values())
    return [
        AnalyticsCategory(
            name=k, amount=v, percentage=v / total_spent if total_spent else 0
        )
        for k, v in totals.items()
    ]


@router.get("/trend/{user_id}", response_model=List[TrendPoint])
def get_trend(user_id: str, db: Session = Depends(get_db)):  # noqa: B008
    txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()

    daily = {}
    for t in txns:
        key = t.spent_at.date().isoformat()
        daily[key] = daily.get(key, 0) + t.amount

    sorted_days = sorted(daily.items())
    return [{"date": d[0], "amount": d[1]} for d in sorted_days]

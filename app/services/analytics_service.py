from sqlalchemy import select, extract, func
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.db.models.transaction import Transaction
from app.services.core.analytics.monthly_aggregator import aggregate_monthly_data
from app.services.core.api.analytics_engine import detect_anomalies


def get_monthly_category_totals(user_id: str, db: Session):
    current_year = datetime.utcnow().year
    current_month = datetime.utcnow().month

    stmt = (
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("total")
        )
        .where(
            Transaction.user_id == user_id,
            extract("year", Transaction.spent_at) == current_year,
            extract("month", Transaction.spent_at) == current_month
        )
        .group_by(Transaction.category)
    )

    result = db.execute(stmt).all()

    return [{"category": row[0], "total": float(row[1])} for row in result]


def get_monthly_trend(user_id: str, db: Session):
    stmt = (
        select(
            func.to_char(Transaction.spent_at, "YYYY-MM").label("month"),
            func.sum(Transaction.amount).label("total")
        )
        .where(Transaction.user_id == user_id)
        .group_by("month")
        .order_by("month")
    )

    result = db.execute(stmt).all()

    return [{"month": row[0], "total": float(row[1])} for row in result]


def analyze_aggregate(calendar: List[dict]):
    current_month = datetime.utcnow().strftime("%Y-%m")
    return aggregate_monthly_data(calendar, current_month)


def analyze_anomalies(calendar: List[dict]):
    return detect_anomalies(calendar)

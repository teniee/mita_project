
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Transaction
from app.services.core.api.analytics_engine import aggregate_monthly_data, detect_anomalies

def get_monthly_category_totals(user_id: str, db: Session) -> dict:
    now = datetime.now()
    txns = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.timestamp >= datetime(now.year, now.month, 1),
        Transaction.timestamp < datetime(now.year + (now.month == 12), (now.month % 12) + 1, 1)
    ).all()
    totals = defaultdict(float)
    for txn in txns:
        totals[txn.category] += float(txn.amount)
    return dict(totals)

def get_monthly_trend(user_id: str, db: Session) -> list:
    now = datetime.now()
    txns = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.timestamp >= datetime(now.year, now.month, 1),
        Transaction.timestamp < datetime(now.year + (now.month == 12), (now.month % 12) + 1, 1)
    ).all()
    trend = defaultdict(float)
    for txn in txns:
        key = txn.timestamp.date().isoformat()
        trend[key] += float(txn.amount)
    return [{"date": k, "amount": round(v, 2)} for k, v in sorted(trend.items())]

def analyze_aggregate(calendar: list) -> dict:
    return {"aggregation": aggregate_monthly_data(calendar)}

def analyze_anomalies(calendar: list) -> dict:
    return {"anomalies": detect_anomalies(calendar)}

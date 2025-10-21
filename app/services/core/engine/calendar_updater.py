from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DailyPlan


def update_day_status(db: Session, user_id: UUID, day: date):
    days = db.query(DailyPlan).filter_by(user_id=user_id, date=day).all()
    if not days:
        return {"status": "no_plan", "date": day.isoformat()}

    total_planned = Decimal("0.00")
    total_spent = Decimal("0.00")

    for d in days:
        total_planned += d.planned_amount
        total_spent += d.spent_amount

    delta = total_spent - total_planned
    if delta <= Decimal("0.00"):
        status = "green"
    elif delta <= Decimal("10.00"):
        status = "yellow"
    else:
        status = "red"

    for d in days:
        d.status = status

    db.commit()
    return {"status": status, "overspent": float(delta), "date": day.isoformat()}

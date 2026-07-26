from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.date_utils import day_to_range
from app.db.models import DailyPlan


def calculate_day_status(total_planned: Decimal, total_spent: Decimal):
    """Return the shared status and delta for one day's plan rows."""
    delta = total_spent - total_planned

    # Dynamic yellow threshold: 5% of planned budget, bounded between $2 and $25
    yellow_threshold = max(
        Decimal("2.00"), min(Decimal("25.00"), total_planned * Decimal("0.05"))
    )

    if delta <= Decimal("0.00"):
        status = "green"
    elif delta <= yellow_threshold:
        status = "yellow"
    else:
        status = "red"
    return status, delta


def update_day_status(db: Session, user_id: UUID, day: date, *, commit: bool = True):
    day_start, day_end = day_to_range(day)
    days = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= day_start,
            DailyPlan.date <= day_end,
        )
        .all()
    )
    if not days:
        return {"status": "no_plan", "date": day.isoformat()}

    total_planned = Decimal("0.00")
    total_spent = Decimal("0.00")

    for d in days:
        total_planned += Decimal(d.planned_amount or 0)
        total_spent += Decimal(d.spent_amount or 0)

    status, delta = calculate_day_status(total_planned, total_spent)

    for d in days:
        d.status = status

    if commit:
        db.commit()
    else:
        db.flush()
    return {"status": status, "overspent": float(delta), "date": day.isoformat()}

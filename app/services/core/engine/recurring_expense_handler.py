from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import RecurringExpense


def inject_recurring_expenses(db: Session, user_id: int, calendar: list):
    """Insert recurring expenses into the calendar.

    ``calendar`` is a list of dictionaries with keys ``date`` and
    ``planned_budget`` among others.
    """
    recurring = db.query(RecurringExpense).filter_by(user_id=user_id).all()
    if not recurring:
        return calendar

    # Convert calendar to a dict keyed by date
    cal_dict = {d["date"]: d for d in calendar}

    for entry in recurring:
        current_date = entry.start_date
        while current_date <= entry.end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            if date_str in cal_dict:
                cal_dict[date_str]["planned_budget"][entry.category] = float(
                    Decimal(entry.amount).quantize(Decimal("0.01"))
                )
            if entry.frequency == "monthly":
                current_date = (
                    current_date.replace(day=1) + timedelta(days=32)
                ).replace(day=entry.start_date.day)
            elif entry.frequency == "weekly":
                current_date += timedelta(days=7)
            elif entry.frequency == "daily":
                current_date += timedelta(days=1)
            else:
                break  # unknown frequency

    return list(cal_dict.values())

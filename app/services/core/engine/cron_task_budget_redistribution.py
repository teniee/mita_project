from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db import get_db
from app.db.models import User
from app.services.budget_redistributor import redistribute_budget_for_user


def run_budget_redistribution_batch():
    """Run monthly redistribution for all active users."""
    db: Session = next(get_db())

    now = datetime.utcnow()
    # Redistribute for the previous month at the start of a new one
    year = now.year
    month = now.month - 1
    if month == 0:
        month = 12
        year -= 1

    users = db.query(User).all()
    for user in users:
        try:
            result = redistribute_budget_for_user(db, user.id, year, month)
            msg = (
                f"Redistribution for user {user.id} "
                f"{year}-{month:02d}: {result['status']}"
            )
            print(msg)
        except Exception as e:
            print(f"Redistribution failed for user {user.id}: {str(e)}")

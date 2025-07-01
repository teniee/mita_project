from datetime import datetime

from app.core.session import get_db
from app.db.models import User
from app.services.budget_redistributor import redistribute_budget_for_user


def run():
    db = next(get_db())
    today = datetime.utcnow().date()
    year, month = today.year, today.month
    users = db.query(User.id).all()
    for (uid,) in users:
        print(f"Redistributing {year}-{month:02d} for user {uid}")
        try:
            redistribute_budget_for_user(db, uid, year, month)
        except Exception as exc:
            print(f"Failed for {uid}: {exc}")


if __name__ == "__main__":
    run()

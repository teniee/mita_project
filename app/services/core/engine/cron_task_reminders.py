from datetime import datetime

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import User
from app.utils.email_utils import send_reminder_email


def run_daily_email_reminders() -> None:
    """Send a simple reminder email to all active users."""
    db: Session = next(get_db())
    today = datetime.utcnow().date().isoformat()

    users = db.query(User).filter(User.is_active.is_(True)).all()
    for user in users:
        try:
            body = f"Don't forget to log your expenses for {today}."
            send_reminder_email(user.email, "Mita Daily Reminder", body)
        except Exception as exc:  # pragma: no cover - ignore email failures
            print(f"Reminder email failed for {user.id}: {exc}")

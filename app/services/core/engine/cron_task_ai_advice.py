from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.db.models import BudgetAdvice, PushToken, User
from app.services.advisory_service import AdvisoryService
from app.services.push_service import send_push_notification


def run_ai_advice_batch() -> None:
    """Generate daily budget advice and push to active users."""
    db: Session = next(get_db())
    utc_now = datetime.utcnow()
    today = utc_now.date()

    users_q = db.query(User)
    if hasattr(User, "is_active"):
        users_q = users_q.filter(User.is_active.is_(True))
    users = users_q.all()
    for user in users:
        user_now = utc_now.astimezone(ZoneInfo(getattr(user, "timezone", "UTC")))
        if user_now.hour != 8:
            continue
        already = (
            db.query(BudgetAdvice)
            .filter(BudgetAdvice.user_id == user.id)
            .filter(func.date(BudgetAdvice.date) == today)
            .first()
        )
        if already:
            continue

        try:
            service = AdvisoryService(db)
            result = service.evaluate_user_risk(user.id)
            text = result.get("reason")
            if not text:
                continue

            token_record = (
                db.query(PushToken)
                .filter(PushToken.user_id == user.id)
                .order_by(PushToken.created_at.desc())
                .first()
            )
            token = token_record.token if token_record else None

            if token:
                send_push_notification(
                    user_id=user.id,
                    message=text,
                    token=token,
                )
        except Exception as e:
            print(f"AI advice failed for user {user.id}: {str(e)}")

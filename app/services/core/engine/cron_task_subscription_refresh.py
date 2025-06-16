from datetime import datetime

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import Subscription, User


def refresh_premium_status() -> None:
    """Disable premium when a subscription expires."""
    db: Session = next(get_db())
    now = datetime.utcnow()
    expired = (
        db.query(Subscription)
        .filter(
            Subscription.expires_at <= now,
            Subscription.status == "active",
        )
        .all()
    )
    for sub in expired:
        sub.status = "expired"
        user = db.query(User).filter(User.id == sub.user_id).first()
        if user and user.premium_until and user.premium_until <= now:
            user.is_premium = False
    db.commit()

from sqlalchemy.orm import Session

from app.db.models import NotificationLog


def log_notification(
    db: Session, *, user_id, channel: str, message: str, success: bool = True
) -> None:
    record = NotificationLog(
        user_id=user_id,
        channel=channel,
        message=message,
        success=success,
    )
    db.add(record)
    db.commit()

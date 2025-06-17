from sqlalchemy.orm import Session

from app.db.models import PushToken
from app.services.advisory_service import AdvisoryService
from app.services.push_service import send_push_notification


def evaluate_installment(
    user_id: str,
    price: float,
    months: int,
    db: Session,
) -> dict:
    """Evaluate affordability and notify if unsafe."""
    service = AdvisoryService(db)
    result = service.can_user_afford_installment(user_id, price, months)

    if not result.get("can_afford"):
        token_record = (
            db.query(PushToken)
            .filter(PushToken.user_id == user_id)
            .order_by(PushToken.created_at.desc())
            .first()
        )
        token = token_record.token if token_record else None
        if token:
            try:
                send_push_notification(
                    user_id=user_id,
                    message=result.get("reason", ""),
                    token=token,
                )
            except Exception:
                pass
    return result

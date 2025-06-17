from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import BudgetAdvice

# isort: off
from app.engine.financial.installment_evaluator import (
    can_user_afford_installment,  # noqa: E501
)
from app.engine.risk_predictor import evaluate_user_risk

# isort: on


class AdvisoryService:
    """Generate and store budget advice for users."""

    def __init__(self, db: Session):
        self.db = db

    def _store_advice(self, user_id: str, type_: str, text: str):
        advice = BudgetAdvice(
            user_id=user_id,
            date=datetime.utcnow(),
            type=type_,
            text=text,
        )
        self.db.add(advice)
        self.db.commit()
        self.db.refresh(advice)
        return advice

    def evaluate_user_risk(self, user_id: str) -> dict:
        result = evaluate_user_risk(user_id)
        self._store_advice(user_id, "risk", result.get("reason", ""))
        return result

    def can_user_afford_installment(
        self, user_id: str, price: float, months: int
    ) -> dict:
        result = can_user_afford_installment(user_id, price, months)
        if not result.get("can_afford"):
            self._store_advice(
                user_id,
                "installment",
                result.get("reason", ""),
            )
        return result

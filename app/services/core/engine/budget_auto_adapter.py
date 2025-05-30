
from decimal import Decimal
from sqlalchemy.orm import Session
from app.db.models import AIAnalysisSnapshot
from typing import Dict

def adapt_category_weights(user_id: int, default_weights: Dict[str, float], db: Session) -> Dict[str, float]:
    snapshot = (
        db.query(AIAnalysisSnapshot)
        .filter_by(user_id=user_id)
        .order_by(AIAnalysisSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        return default_weights

    risk = (snapshot.risk or "").lower()
    tags = snapshot.full_profile.get("behavior_tags", [])

    adjusted = default_weights.copy()

    if "emotional_spender" in tags:
        if "shopping" in adjusted:
            adjusted["shopping"] = max(adjusted["shopping"] - 0.05, 0.05)

    if "food_dominated" in tags:
        if "groceries" in adjusted:
            adjusted["groceries"] = adjusted.get("groceries", 0.1) + 0.05
        if "restaurants" in adjusted:
            adjusted["restaurants"] = adjusted.get("restaurants", 0.1) + 0.05

    if risk == "высокий":
        for cat in adjusted:
            adjusted[cat] = round(adjusted[cat] * 0.95, 3)
        adjusted["savings"] = adjusted.get("savings", 0.0) + 0.05

    # Нормализация
    total = sum(adjusted.values())
    if not (0.99 <= total <= 1.01):
        adjusted = {k: round(v / total, 4) for k, v in adjusted.items()}

    return adjusted

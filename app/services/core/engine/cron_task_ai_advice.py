
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.core.engine.ai_budget_analyst import generate_push_advice
from app.services.push_service import send_push_notification  # предполагаем, что такая есть
from app.db.models import User
from datetime import datetime

def run_ai_advice_batch():
    db: Session = next(get_db())
    now = datetime.utcnow()
    year = now.year
    month = now.month

    users = db.query(User).filter(User.is_active == True).all()
    for user in users:
        try:
            result = generate_push_advice(user.id, db, year, month)
            text = result.get("text")
            if text:
                send_push_notification(user_id=user.id, message=text)
        except Exception as e:
            print(f"AI advice failed for user {user.id}: {str(e)}")

from sqlalchemy.orm import Session
from app.db.models import UserAnswer, UserProfile, DailyPlan
from sqlalchemy import select
import json

class UserDataService:
    def save_onboarding_answer(self, user_id: int, key: str, value, db: Session):
        obj = db.query(UserAnswer).filter_by(user_id=user_id, question_key=key).first()
        if obj:
            obj.answer_json = json.dumps(value)
        else:
            obj = UserAnswer(user_id=user_id, question_key=key, answer_json=json.dumps(value))
            db.add(obj)
        db.commit()

    def get_onboarding_answers(self, user_id: int, db: Session) -> dict:
        answers = {}
        rows = db.query(UserAnswer).filter_by(user_id=user_id).all()
        for row in rows:
            try:
                answers[row.question_key] = json.loads(row.answer_json)
            except:
                answers[row.question_key] = row.answer_json
        return answers

    def save_user_financial_profile(self, user_id: int, profile: dict, db: Session):
        obj = db.query(UserProfile).filter_by(user_id=user_id).first()
        if obj:
            obj.data = profile
        else:
            obj = UserProfile(user_id=user_id, data=profile)
            db.add(obj)
        db.commit()

    def save_user_calendar(self, user_id: int, calendar: dict, db: Session):
        db.query(DailyPlan).filter_by(user_id=user_id).delete()
        for date_str, day_data in calendar.items():
            for category, amount in day_data.items():
                dp = DailyPlan(
                    user_id=user_id,
                    date=date_str,
                    category=category,
                    planned_amount=amount,
                    spent_amount=0
                )
                db.add(dp)
        db.commit()

    @staticmethod
    def get_user_financial_profile(user_id: str) -> dict:
        if user_id == "user_001":
            return {
                "monthly_income": 5000,
                "monthly_expenses": [1000, 1200, 1100, 1300],
                "savings_balance": 2000,
                "missed_payments": 0
            }
        elif user_id == "user_002":
            return {
                "monthly_income": 3000,
                "monthly_expenses": [900, 1000, 950, 970],
                "savings_balance": 1000,
                "missed_payments": 2
            }
        else:
            return None

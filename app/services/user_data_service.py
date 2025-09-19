import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DailyPlan, UserAnswer, UserProfile

logger = logging.getLogger(__name__)


class UserDataService:
    def save_onboarding_answer(self, user_id: int, key: str, value, db: Session):
        obj = db.query(UserAnswer).filter_by(user_id=user_id, question_key=key).first()
        if obj:
            obj.answer_json = json.dumps(value)
        else:
            obj = UserAnswer(
                user_id=user_id, question_key=key, answer_json=json.dumps(value)
            )
            db.add(obj)
        db.commit()

    def get_onboarding_answers(self, user_id: int, db: Session) -> dict:
        answers = {}
        rows = db.query(UserAnswer).filter_by(user_id=user_id).all()
        for row in rows:
            try:
                answers[row.question_key] = json.loads(row.answer_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse JSON for user {user_id}, question {row.question_key}: {str(e)}")
                answers[row.question_key] = row.answer_json
            except Exception as e:
                logger.error(f"Unexpected error parsing answer for user {user_id}, question {row.question_key}: {str(e)}")
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
                    spent_amount=0,
                )
                db.add(dp)
        db.commit()

    def get_user_financial_profile(self, user_id: int, db: Session) -> dict:
        """
        Get user financial profile from the database.
        Returns None if no profile exists.
        """
        try:
            profile = db.query(UserProfile).filter_by(user_id=user_id).first()
            if profile and profile.data:
                return profile.data
            return None
        except Exception as e:
            logger.error(f"Failed to get user financial profile for user {user_id}: {str(e)}")
            return None

import json
import os

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.budget_planner import generate_budget_from_answers
from app.services.calendar_service_real import save_calendar_for_user
from app.services.user_data_service import UserDataService

ONBOARDING_QUESTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "../config/onboarding_questions.json"
)

with open(ONBOARDING_QUESTIONS_PATH, "r", encoding="utf-8") as f:
    ONBOARDING_QUESTIONS = json.load(f)


class OnboardingEngine:
    def __init__(self, db: Session = None):
        self.user_service = UserDataService()
        self.db = db or next(get_db())

    def save_onboarding_step(self, user_id: int, step_key: str, answer):
        if step_key not in ONBOARDING_QUESTIONS:
            raise ValueError(f"Invalid onboarding step: {step_key}")

        self.user_service.save_onboarding_answer(user_id, step_key, answer, self.db)

        if self._is_onboarding_complete(user_id):
            self._finalize_user_profile(user_id)

    def get_onboarding_status(self, user_id: int):
        answers = self.user_service.get_onboarding_answers(user_id, self.db)
        missing_steps = [key for key in ONBOARDING_QUESTIONS if key not in answers]
        return {
            "completed": len(missing_steps) == 0,
            "missing_steps": missing_steps,
            "answers": answers,
        }

    def _is_onboarding_complete(self, user_id: int) -> bool:
        answers = self.user_service.get_onboarding_answers(user_id, self.db)
        return all(key in answers for key in ONBOARDING_QUESTIONS)

    def _finalize_user_profile(self, user_id: int):
        answers = self.user_service.get_onboarding_answers(user_id, self.db)

        try:
            # Generate a budget plan
            plan = generate_budget_from_answers(answers)
            config = {**answers, **plan, "user_id": user_id, "db": self.db}

            # Generate the calendar
            calendar = build_calendar(config)

            # Save calendar to the database
            save_calendar_for_user(self.db, user_id, calendar)

            # Save final financial profile
            self.user_service.save_user_financial_profile(user_id, plan, self.db)

        except Exception as e:
            # Log the error and re-raise
            print(
                f"[OnboardingEngine] Error finalizing profile for user {user_id}: {str(e)}"
            )
            raise

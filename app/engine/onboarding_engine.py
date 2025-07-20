import json
import os

from app.engine.calendar_engine import CalendarEngine
from app.services.budget_planner import generate_budget_from_answers
from app.services.user_data_service import UserDataService

ONBOARDING_QUESTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "../config/onboarding_questions.json"
)
with open(ONBOARDING_QUESTIONS_PATH, "r", encoding="utf-8") as f:
    ONBOARDING_QUESTIONS = json.load(f)


class OnboardingEngine:
    def __init__(self):
        self.user_service = UserDataService()

    def save_onboarding_step(self, user_id: str, step_key: str, answer):
        if step_key not in ONBOARDING_QUESTIONS:
            raise ValueError("Invalid onboarding step key")

        self.user_service.save_onboarding_answer(user_id, step_key, answer)

        if self._is_onboarding_complete(user_id):
            self._finalize_user_profile(user_id)

    def get_onboarding_status(self, user_id: str):
        answers = self.user_service.get_onboarding_answers(user_id)
        missing_steps = [key for key in ONBOARDING_QUESTIONS if key not in answers]

        return {
            "completed": len(missing_steps) == 0,
            "missing_steps": missing_steps,
            "answers": answers,
        }

    def _is_onboarding_complete(self, user_id: str) -> bool:
        answers = self.user_service.get_onboarding_answers(user_id)
        return all(key in answers for key in ONBOARDING_QUESTIONS)

    def _finalize_user_profile(self, user_id: str):
        answers = self.user_service.get_onboarding_answers(user_id)

        income = float(answers.get("monthly_income", 0))
        fixed_expenses = answers.get("fixed_expenses", {})
        categories = answers.get("spending_priorities", {})

        profile = {
            "monthly_income": income,
            "fixed_expenses": fixed_expenses,
            "spending_priorities": categories,
            "savings_balance": answers.get("savings", 0),
            "missed_payments": 0,
        }

        self.user_service.save_user_financial_profile(user_id, profile)

        # Generate initial calendar based on answers
        budget_plan = generate_budget_from_answers(answers)
        from app.services.budget_planner import generate_and_save_calendar

        generate_and_save_calendar(user_id, answers)
        calendar = CalendarEngine(
            income=income,
            fixed_expenses=fixed_expenses,
            flexible_categories=budget_plan,
        ).generate_calendar(year=2025, month=4)

        self.user_service.save_user_calendar(user_id, calendar)

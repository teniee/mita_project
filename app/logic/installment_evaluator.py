from sqlalchemy.orm import Session
from app.services.user_data_service import UserDataService


def can_user_afford_installment(user_id: int, price: float, months: int, db: Session) -> dict:
    user_data_service = UserDataService()
    profile = user_data_service.get_user_financial_profile(user_id, db)
    if not profile:
        return {"can_afford": False, "monthly_payment": 0, "reason": "User not found."}

    monthly_payment = round(price / months, 2)
    income = profile["monthly_income"]
    expenses = sum(profile["monthly_expenses"]) / len(profile["monthly_expenses"])
    free_money = income - expenses

    if free_money <= 0:
        return {
            "can_afford": False,
            "monthly_payment": monthly_payment,
            "reason": "No free money after expenses.",
        }

    if monthly_payment > 0.5 * free_money:
        return {
            "can_afford": False,
            "monthly_payment": monthly_payment,
            "reason": "Installment exceeds safe budget limits.",
        }

    return {
        "can_afford": True,
        "monthly_payment": monthly_payment,
        "reason": "You can afford this safely.",
    }

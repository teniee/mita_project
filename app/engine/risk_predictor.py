from app.services.user_data_service import UserDataService


def evaluate_user_risk(user_id: str) -> dict:
    profile = UserDataService.get_user_financial_profile(user_id)
    if not profile:
        return {"risk_level": "unknown", "reason": "User not found."}

    avg_expenses = sum(profile["monthly_expenses"]) / len(profile["monthly_expenses"])
    income = profile["monthly_income"]
    savings = profile["savings_balance"]
    missed_payments = profile["missed_payments"]

    if missed_payments > 1:
        return {
            "risk_level": "high",
            "reason": "User has a history of missed payments.",
        }
    if avg_expenses > income:
        return {"risk_level": "high", "reason": "Expenses exceed income."}
    if savings < 500:
        return {"risk_level": "medium", "reason": "Low savings balance."}

    return {"risk_level": "low", "reason": "User is financially stable."}

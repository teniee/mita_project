
from app.engine.financial.installment_evaluator import can_user_afford_installment as evaluate_installment_eligibility

def evaluate_installment(profile: dict, goal: float, income: float, fixed_expenses: float) -> dict:
    return evaluate_installment_eligibility(profile, goal, income, fixed_expenses)

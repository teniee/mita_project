
from decimal import Decimal

def calculate_monthly_budget(income: float, fixed_expenses: dict, savings: float) -> dict:
    fixed_total = sum(Decimal(v) for v in fixed_expenses.values())
    discretionary = Decimal(income) - fixed_total - Decimal(savings)
    if discretionary < 0:
        raise ValueError("Fixed + savings exceed income")

    return {
        "fixed_total": float(fixed_total),
        "discretionary": float(discretionary),
        "total_planned": float(fixed_total + savings),
        "savings": float(savings)
    }

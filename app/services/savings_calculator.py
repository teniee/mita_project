def calculate_savings_plan(
    savings_target: dict, income: float, fixed_total: float
) -> dict:
    """
    savings_target = {
        "amount": 3000,
        "deadline_months": 6,
        "priority_categories": ["travel", "entertainment", "shopping"]
    }
    """
    if not savings_target:
        return {"monthly_savings": 0.0, "explanation": "No savings target set."}

    amount = float(savings_target.get("amount", 0))
    months = int(savings_target.get("deadline_months", 1))
    categories = savings_target.get("priority_categories", [])

    monthly_savings = round(amount / months, 2)
    remaining = income - fixed_total - monthly_savings
    if remaining < 0:
        raise ValueError("Savings plan too aggressive for current income.")

    explanation = f"Saving ${amount} over {months} months requires ${monthly_savings}/mo. Reduced: {categories}."

    return {
        "monthly_savings": monthly_savings,
        "categories_to_cut": categories,
        "explanation": explanation,
    }

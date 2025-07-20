### goal_budget_engine.py — builds budget backwards from savings target


def build_goal_budget(
    income: float, fixed: dict, goal_amount: float, weights: dict
) -> dict:
    if goal_amount >= income:
        return {"error": "goal exceeds income"}

    flexible_total = income - sum(fixed.values()) - goal_amount
    if flexible_total < 0:
        return {"error": "fixed + goal exceed income"}

    total_weight = sum(weights.values())
    allocation = {}
    for category, weight in weights.items():
        allocation[category] = round((weight / total_weight) * flexible_total, 2)

    return {"fixed": fixed, "flexible": allocation, "savings_goal": goal_amount}

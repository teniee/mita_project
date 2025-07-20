from typing import Dict, List


def predict_user_behavior(transactions: List[Dict], income: float) -> str:
    """
    Analyzes user transactions to determine behavior.
    Returns: 'saver', 'spender', 'erratic', or 'neutral'
    """
    if not transactions:
        return "neutral"

    total_spent = sum(tx["amount"] for tx in transactions if tx["type"] == "expense")
    num_expenses = sum(1 for tx in transactions if tx["type"] == "expense")

    avg_tx = total_spent / num_expenses if num_expenses else 0
    savings_rate = max(0.0, (income - total_spent) / income)

    if savings_rate >= 0.3:
        return "saver"
    elif savings_rate < 0.05 and avg_tx > 100:
        return "spender"
    elif num_expenses > 20 and savings_rate < 0.1:
        return "erratic"
    return "neutral"

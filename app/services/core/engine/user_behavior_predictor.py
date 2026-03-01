from typing import Dict, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta


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


def predict_spending_behavior(user_id: int, db: Session) -> dict:
    """
    Predict user's spending behavior for upcoming periods.

    Returns predictions including next week and next month spending estimates.
    """
    from app.db.models.transaction import Transaction
    from app.db.models.user import User

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "next_week_spending": 0.0,
            "next_month_spending": 0.0,
            "confidence": 0.0,
            "insights": ["User not found"]
        }

    # Get recent transactions (last 60 days)
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.spent_at >= sixty_days_ago
    ).all()

    if not transactions:
        return {
            "next_week_spending": 0.0,
            "next_month_spending": 0.0,
            "confidence": 0.0,
            "insights": ["Not enough transaction history for predictions"]
        }

    # Calculate average daily spending
    total_spent = sum(float(t.amount) for t in transactions)
    days_covered = (datetime.utcnow() - sixty_days_ago).days
    avg_daily_spending = total_spent / days_covered if days_covered > 0 else 0.0

    # Predict next week (7 days)
    next_week_spending = avg_daily_spending * 7

    # Predict next month (30 days)
    next_month_spending = avg_daily_spending * 30

    # Calculate confidence based on transaction count
    confidence = min(1.0, len(transactions) / 50.0)

    insights = []
    if confidence < 0.3:
        insights.append("Low confidence - track more transactions for better predictions")
    elif avg_daily_spending > (user.monthly_income or 0) / 30:
        insights.append("Warning: Spending exceeds income rate")
    else:
        insights.append("Spending pattern is sustainable based on income")

    return {
        "next_week_spending": round(next_week_spending, 2),
        "next_month_spending": round(next_month_spending, 2),
        "confidence": round(confidence, 2),
        "insights": insights,
        "avg_daily_spending": round(avg_daily_spending, 2),
        "transaction_count": len(transactions)
    }

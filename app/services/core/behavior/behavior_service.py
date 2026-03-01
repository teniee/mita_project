from datetime import datetime
from sqlalchemy.orm import Session

from app.services.core.behavior.behavioral_budget_allocator import (
    get_behavioral_allocation,
)


def generate_behavioral_calendar(
    start_date: str,
    days: int,
    category_weights: dict,
) -> dict:
    """
    Generates a behavioral spending calendar based on start date and
    category weights.

    Params:
        start_date: str "YYYY-MM-DD"
        days: number of days in the month
        category_weights: {"coffee": 100, "entertainment": 200, ...}

    Returns:
        {1: {"coffee": X, ...}, 2: {...}, ..., 30: {...}}
    """
    # Call with correct parameters (start_date as string, not datetime)
    plan = get_behavioral_allocation(
        start_date=start_date,
        num_days=days,
        budget_plan=category_weights,
        user_context=None  # Will use default UserContext
    )
    return {i + 1: plan[i] for i in range(days)}


def analyze_user_behavior(
    user_id: int,
    db: Session,
    year: int,
    month: int
) -> dict:
    """
    Analyze user spending behavior for a given period.

    Returns behavioral insights including patterns, scores, and recommendations.
    """
    from app.db.models.transaction import Transaction

    # Query transactions for the period
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.spent_at >= start_date,
        Transaction.spent_at < end_date
    ).all()

    if not transactions:
        return {
            "spending_patterns": [],
            "behavioral_score": 0.5,
            "insights": ["Not enough transaction data for analysis"],
            "period": f"{year}-{month:02d}",
            "transaction_count": 0
        }

    # Analyze spending patterns by category
    category_spending = {}
    for txn in transactions:
        cat = txn.category or "uncategorized"
        category_spending[cat] = category_spending.get(cat, 0.0) + float(txn.amount)

    # Find dominant patterns
    patterns = []
    total_spending = sum(category_spending.values())

    for category, amount in sorted(category_spending.items(), key=lambda x: -x[1])[:5]:
        percentage = (amount / total_spending * 100) if total_spending > 0 else 0
        patterns.append({
            "category": category,
            "amount": amount,
            "percentage": round(percentage, 1),
            "transaction_count": sum(1 for t in transactions if (t.category or "uncategorized") == category)
        })

    # Calculate behavioral score (0-1, where 1 is best)
    # Simple heuristic: more categories = more balanced = better score
    category_diversity = len(category_spending)
    behavioral_score = min(1.0, category_diversity / 10.0)

    insights = []
    if category_diversity < 3:
        insights.append("Consider diversifying your spending categories for better tracking")
    if len(transactions) < 10:
        insights.append("Track more transactions to get detailed behavioral insights")

    return {
        "spending_patterns": patterns,
        "behavioral_score": behavioral_score,
        "insights": insights,
        "period": f"{year}-{month:02d}",
        "transaction_count": len(transactions),
        "total_spending": total_spending,
        "category_count": category_diversity
    }

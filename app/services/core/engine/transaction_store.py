from typing import Dict

from app.engine.budget_redistributor import BudgetRedistributor

TRANSACTIONS: Dict[str, Dict] = {}
CATEGORY_SPENT_TOTAL: Dict[str, Dict[str, float]] = {}


def create_transaction(
    user_id: str,
    date: str,
    tx_type: str,
    amount: float,
    category: str,
    calendar: Dict[str, Dict],
) -> Dict:
    tx_id = f"{user_id}_{date}_{category}_{len(TRANSACTIONS)}"
    TRANSACTIONS[tx_id] = {
        "user_id": user_id,
        "date": date,
        "type": tx_type,
        "amount": amount,
        "category": category,
    }
    apply_transaction(user_id, date, tx_type, amount, category, calendar)
    return {"status": "created", "transaction_id": tx_id}


def apply_transaction(
    user_id: str,
    date: str,
    tx_type: str,
    amount: float,
    category: str,
    calendar: Dict[str, Dict],
) -> None:
    if date not in calendar:
        calendar[date] = {}

    if tx_type == "expense":
        calendar[date].setdefault("actual_spending", {})
        calendar[date]["actual_spending"][category] = (
            calendar[date]["actual_spending"].get(category, 0.0) + amount
        )

        total_spent = sum(calendar[date]["actual_spending"].values())
        planned = sum(calendar[date].get("planned_budget", {}).values())
        if planned == 0:
            status = "neutral"
        elif total_spent <= planned:
            status = "green"
        elif total_spent <= planned * 1.2:
            status = "orange"
        else:
            status = "red"

        calendar[date]["status"] = {"category": category, "level": status}

        if user_id not in CATEGORY_SPENT_TOTAL:
            CATEGORY_SPENT_TOTAL[user_id] = {}

        CATEGORY_SPENT_TOTAL[user_id][category] = (
            CATEGORY_SPENT_TOTAL[user_id].get(category, 0.0) + amount
        )

        if status in ["orange", "red"]:
            redistributor = BudgetRedistributor(calendar)
            redistributor.redistribute_budget()


def delete_transaction(tx_id: str, calendar: Dict[str, Dict]) -> Dict:
    if tx_id not in TRANSACTIONS:
        return {"status": "not_found"}

    tx = TRANSACTIONS.pop(tx_id)
    date = tx["date"]
    category = tx["category"]
    amount = tx["amount"]

    if date in calendar and "actual_spending" in calendar[date]:
        calendar[date]["actual_spending"][category] = max(
            0.0, calendar[date]["actual_spending"].get(category, 0.0) - amount
        )

    return {"status": "deleted", "transaction_id": tx_id}


def get_transaction(tx_id: str) -> Dict:
    return TRANSACTIONS.get(tx_id, {})

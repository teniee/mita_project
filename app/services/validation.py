from fastapi import HTTPException

ALLOWED_CATEGORIES = {
    "rent",
    "utilities",
    "insurance",
    "loan",
    "other",
    "groceries",
    "restaurants",
    "entertainment",
    "shopping",
    "transport",
    "travel",
}


def validate_category(category: str):
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")


def validate_amount(amount: float):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0.")

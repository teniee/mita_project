
from fastapi import HTTPException

ALLOWED_CATEGORIES = {
    "rent", "utilities", "insurance", "loan", "other",
    "groceries", "restaurants", "entertainment", "shopping",
    "transport", "travel"
}

def validate_category(category: str):
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Недопустимая категория: {category}")

def validate_amount(amount: float):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть больше 0.")

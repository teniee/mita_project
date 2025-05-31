
# Основные категории расходов
ALLOWED_CATEGORIES = {
    "rent", "utilities", "insurance", "loan", "other",
    "groceries", "restaurants", "entertainment", "shopping",
    "transport", "travel", "subscriptions", "health", "education",
    "pets", "childcare", "donations", "gym", "personal_care"
}

# Базовые веса для распределения (для класса по умолчанию)
DEFAULT_WEIGHTS = {
    "groceries": 0.25,
    "restaurants": 0.15,
    "entertainment": 0.10,
    "shopping": 0.10,
    "transport": 0.10,
    "travel": 0.05,
    "subscriptions": 0.05,
    "health": 0.05,
    "education": 0.05,
    "personal_care": 0.05
}

# Поведенческие шаблоны по умолчанию
DEFAULT_TEMPLATES = {
    "rent": "fixed",
    "utilities": "fixed",
    "insurance": "fixed",
    "loan": "fixed",
    "groceries": "spread",
    "restaurants": "clustered",
    "entertainment": "clustered",
    "shopping": "clustered",
    "transport": "spread",
    "travel": "clustered",
    "subscriptions": "fixed",
    "health": "spread",
    "education": "spread",
    "personal_care": "clustered"
}

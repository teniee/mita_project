CATEGORY_PRIORITY = {
    "rent": 100,
    "utilities": 90,
    "debt": 80,
    "groceries": 70,
    "transportation": 60,
    "savings": 50,
    "shopping": 30,
    "entertainment": 20,
    "coffee": 10,
    "misc": 5,
}


def get_priority(category: str) -> int:
    return CATEGORY_PRIORITY.get(category, 0)

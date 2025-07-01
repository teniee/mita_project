# Externalized configuration for behavioral budget allocation

CATEGORY_TIME_BIAS = {
    "groceries": [0.9, 1.0, 1.0, 1.0, 0.9, 0.7, 0.7],
    "dining out": [0.4, 0.4, 0.6, 0.6, 0.8, 1.0, 1.0],
    "entertainment": [0.3, 0.3, 0.5, 0.6, 0.9, 1.0, 1.0],
    "shopping": [0.5, 0.5, 0.6, 0.7, 0.8, 1.0, 1.0],
    "transport": [1.0] * 7,
}

CATEGORY_COOLDOWN = {
    "groceries": 1,
    "dining out": 2,
    "entertainment": 3,
    "shopping": 3,
    "transport": 1,
}

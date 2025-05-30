
from app.engine.behavior.spending_pattern_extractor import extract_patterns

def apply_behavioral_adjustments(user_id: int, config: dict, db):
    # Извлекаем шаблоны поведения из истории
    year = config.get("year")
    month = config.get("month")

    if not year or not month:
        return config

    patterns = extract_patterns(user_id, year, month, db=db)

    # Корректируем веса/шаблоны категорий в config['weights']
    weights = config.get("weights", {})
    templates = config.get("template_map", {})

    # Повышаем вес выходных трат
    if "weekend_spender" in patterns:
        if "entertainment" in weights:
            weights["entertainment"] += 0.05
        if "restaurants" in weights:
            weights["restaurants"] += 0.05
        templates["entertainment"] = "clustered"
        templates["restaurants"] = "clustered"

    # Повышаем вес еды, если есть food_dominated
    if "food_dominated" in patterns:
        weights["groceries"] = weights.get("groceries", 0.1) + 0.05
        weights["restaurants"] = weights.get("restaurants", 0.1) + 0.05

    # Эмоциональные траты → уменьшить шопинг
    if "emotional_spender" in patterns:
        weights["shopping"] = max(weights.get("shopping", 0.1) - 0.05, 0.05)

    # Обновляем config
    config["weights"] = weights
    config["template_map"] = templates

    return config

from typing import Dict, Any
from statistics import mean


def calculate_checkpoint(user_profile: Dict[str, Any], transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вычисляет финансовую контрольную точку пользователя.

    :param user_profile: словарь с характеристиками пользователя (возраст, доход и т.п.)
    :param transaction_data: словарь с транзакциями по категориям: { "food": [10, 20, 30], ... }
    :return: словарь с результатами расчёта
    """

    # 1. Вычисляем общие суммы по категориям
    category_totals = {
        category: sum(values)
        for category, values in transaction_data.items()
        if isinstance(values, list) and all(isinstance(v, (int, float)) for v in values)
    }

    # 2. Общая сумма всех расходов
    total_spent = sum(category_totals.values())

    # 3. Средние значения по категориям
    category_averages = {
        category: round(mean(values), 2)
        for category, values in transaction_data.items()
        if isinstance(values, list) and values
    }

    # 4. Оценка финансового поведения
    behavior_score = assess_behavior(user_profile, category_totals)

    # 5. Финальный ответ
    return {
        "user_profile": user_profile,
        "total_spent": round(total_spent, 2),
        "category_totals": category_totals,
        "category_averages": category_averages,
        "behavior_score": behavior_score,
        "checkpoint_status": "generated"
    }


def assess_behavior(user_profile: Dict[str, Any], category_totals: Dict[str, float]) -> str:
    """
    Простейший анализ поведения: например, если доля "entertainment" > 30% от расходов — флаг.
    :return: строка: 'balanced', 'overspending', 'unusual'
    """
    total = sum(category_totals.values())
    if not total:
        return "no_activity"

    entertainment = category_totals.get("entertainment", 0)
    dining = category_totals.get("dining out", 0)

    if entertainment / total > 0.3 or dining / total > 0.25:
        return "overspending"

    return "balanced"

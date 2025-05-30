from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict

CATEGORY_TIME_BIAS: Dict[str, List[float]] = {
    "entertainment events": [0.1, 0.1, 0.1, 0.2, 0.6, 0.9, 1.0],
    "dining out": [0.1, 0.1, 0.2, 0.4, 0.8, 1.0, 0.9],
    "clothing": [0.1, 0.1, 0.1, 0.2, 0.6, 0.9, 0.9],
    "groceries": [0.8, 0.8, 0.8, 0.7, 0.6, 0.3, 0.3],
    "transport": [0.7, 0.7, 0.7, 0.7, 0.7, 0.2, 0.2]
}

CATEGORY_COOLDOWN: Dict[str, int] = {
    "entertainment events": 3,
    "dining out": 2,
    "clothing": 5,
    "groceries": 1,
    "transport": 0
}

def get_behavioral_allocation(start_date: str, num_days: int, budget_plan: Dict[str, float]) -> List[Dict[str, float]]:
    """
    Распределяет поведенческий бюджет по дням на основе дня недели, bias и cooldown.
    :param start_date: Дата начала (в формате YYYY-MM-DD)
    :param num_days: Кол-во дней в планируемом периоде
    :param budget_plan: Бюджет на категории, например {"groceries": 100.0, "transport": 50.0}
    :return: Список словарей, где каждый элемент — бюджет на день
    """
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    calendar = [base_date + timedelta(days=i) for i in range(num_days)]

    memory = defaultdict(list)
    result: List[Dict[str, float]] = [defaultdict(float) for _ in range(num_days)]

    for category, total in budget_plan.items():
        cooldown = CATEGORY_COOLDOWN.get(category, 0)
        bias = CATEGORY_TIME_BIAS.get(category, [1.0] * 7)
        slots = []

        for i, date in enumerate(calendar):
            weekday = date.weekday()
            score = bias[weekday]
            recent_days = memory[category]

            if recent_days and (i - recent_days[-1]) <= cooldown:
                score = 0

            if score > 0:
                slots.append((i, score))

        slots.sort(key=lambda x: -x[1])
        max_slots = 4 if category in ["entertainment events", "clothing", "dining out"] else len(slots)
        selected = sorted([i for i, _ in slots[:max_slots]])

        if selected:
            amount = round(total / len(selected), 2)
            for i in selected:
                result[i][category] += amount
                memory[category].append(i)

    return [dict(day) for day in result]

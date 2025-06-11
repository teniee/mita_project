from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.gpt_agent_service import GPTAgentService
from app.db.models import DailyPlan
from app.engine.behavior.spending_pattern_extractor import extract_patterns
from app.engine.mood_store import get_mood

GPT = GPTAgentService(api_key="sk-REPLACE_ME", model="gpt-4o")


def generate_push_advice(
    user_id: int,
    db: Session,
    year: int,
    month: int,
) -> dict:
    # Собираем статистику по статусам
    rows = (
        db.query(DailyPlan)
        .filter_by(user_id=user_id)
        .filter(
            DailyPlan.date >= date(year, month, 1),
            DailyPlan.date < date(year, month, 28) + timedelta(days=5),
        )
        .all()
    )

    status_summary = defaultdict(int)
    category_overspend = defaultdict(Decimal)
    total_spent = Decimal("0.00")

    for row in rows:
        status_summary[row.status] += 1
        total_spent += row.spent_amount
        if row.spent_amount > row.planned_amount:
            delta = row.spent_amount - row.planned_amount
            category_overspend[row.category] += delta

    # Список перерасходов
    overspent_categories = sorted(
        category_overspend.items(), key=lambda x: x[1], reverse=True
    )
    overspent_names = [k for k, v in overspent_categories[:3]]

    days_tracked = len(rows) or 1
    daily_avg = total_spent / days_tracked
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    next_month_days = monthrange(next_year, next_month)[1]
    predicted_expense = round(float(daily_avg * next_month_days), 2)

    mood = get_mood(str(user_id), date.today().isoformat())

    # Поведенческие паттерны
    patterns_result = extract_patterns(str(user_id), year, month)
    behavior_tags = patterns_result.get("patterns", [])

    prompt = (
        "Ты ИИ-финансовый аналитик."
        f" Сегодняшнее настроение пользователя: {mood or 'неизвестно'}."
        f" Итоговые траты за текущий месяц: {float(total_spent)}."
        f" Прогноз расходов на следующий месяц: {predicted_expense}."
        f" Статусы дней: {dict(status_summary)}."
        f" Категории перерасхода: {overspent_names}."
        f" Поведенческие признаки: {behavior_tags}."
        " Сгенерируй короткий совет (1 предложение) в стиле пуш-уведомления "
        "на русском языке."
        " Тон: доброжелательный, краткий, без паники."
    )

    ai_text = GPT.ask([{"role": "user", "content": prompt}])

    return {
        "text": ai_text,
        "overspent_categories": overspent_names,
        "status_summary": dict(status_summary),
        "behavior_tags": behavior_tags,
        "predicted_expense": predicted_expense,
        "mood": mood,
    }

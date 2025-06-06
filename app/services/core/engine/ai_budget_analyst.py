from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.gpt_agent_service import GPTAgentService
from app.core.config import settings
from app.db.models import DailyPlan
from app.engine.behavior.spending_pattern_extractor import extract_patterns

GPT = GPTAgentService(
    api_key=settings.openai_api_key,
    model=settings.openai_model,
)


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

    for row in rows:
        status_summary[row.status] += 1
        if row.spent_amount > row.planned_amount:
            diff = row.spent_amount - row.planned_amount
            category_overspend[row.category] += diff

    # Список перерасходов
    overspent_categories = sorted(
        category_overspend.items(), key=lambda x: x[1], reverse=True
    )
    overspent_names = [k for k, _ in overspent_categories[:3]]

    # Поведенческие паттерны
    patterns_result = extract_patterns(str(user_id), year, month)
    behavior_tags = patterns_result.get("patterns", [])

    prompt = (
        "Ты ИИ-финансовый аналитик."
        " Пользователь имеет такую статистику за месяц:"
        f" Статусы дней: {dict(status_summary)}."
        f" Категории перерасхода: {overspent_names}."
        f" Поведенческие признаки: {behavior_tags}."
        " Сгенерируй короткий совет (1 предложение) в стиле пуш-уведомления на"
        " русском языке. Тон: доброжелательный, краткий, без паники."
    )

    ai_text = GPT.ask([{"role": "user", "content": prompt}])

    return {
        "text": ai_text,
        "overspent_categories": overspent_names,
        "status_summary": dict(status_summary),
        "behavior_tags": behavior_tags,
    }

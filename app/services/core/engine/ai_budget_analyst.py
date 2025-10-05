from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.gpt_agent_service import GPTAgentService
from app.core.config import settings
from app.db.models import DailyPlan
from app.engine.behavior.spending_pattern_extractor import extract_patterns
from app.engine.mood_store import get_mood
from app.services.template_service import AIAdviceTemplateService


def generate_push_advice(
    user_id: int,
    db: Session,
    year: int,
    month: int,
) -> dict:
    # Collect status statistics for the month
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

    # Top overspent categories
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

    # Behavior patterns extracted from historical data
    patterns_result = extract_patterns(str(user_id), year, month)
    behavior_tags = patterns_result.get("patterns", [])

    tmpl_service = AIAdviceTemplateService(db)
    template = tmpl_service.get("push_advice_prompt")
    system_prompt = tmpl_service.get("system_prompt")
    gpt = GPTAgentService(
        api_key=settings.OPENAI_API_KEY, model="gpt-4o", system_prompt=system_prompt
    )
    if template:
        prompt = template.format(
            mood=mood or "unknown",
            total_spent=float(total_spent),
            predicted_expense=predicted_expense,
            status_summary=dict(status_summary),
            overspent_categories=overspent_names,
            behavior_tags=behavior_tags,
        )
    else:
        prompt = (
            "You are an AI financial analyst."
            f" Today's user mood: {mood or 'unknown'}."
            f" Total spending this month: {float(total_spent)}."
            f" Predicted spending next month: {predicted_expense}."
            f" Day statuses: {dict(status_summary)}."
            f" Overspent categories: {overspent_names}."
            f" Behavior patterns: {behavior_tags}."
            " Generate one short push-style tip in English."
            " Keep it friendly and concise."
        )

    ai_text = gpt.ask([{"role": "user", "content": prompt}])

    return {
        "text": ai_text,
        "overspent_categories": overspent_names,
        "status_summary": dict(status_summary),
        "behavior_tags": behavior_tags,
        "predicted_expense": predicted_expense,
        "mood": mood,
    }

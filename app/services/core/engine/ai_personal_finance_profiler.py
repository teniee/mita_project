import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.gpt_agent_service import GPTAgentService
from app.core.config import settings
from app.db.models.daily_plan import DailyPlan
from app.db.models.user import User
from app.engine.behavior.spending_pattern_extractor import extract_patterns
from app.services.template_service import AIAdviceTemplateService


def build_user_profile(user_id: int, db: Session, year: int, month: int) -> dict:
    # Query user from the database
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        return {"error": "User not found"}

    # Fetch all user plans within the month
    days = (
        db.query(DailyPlan)
        .filter_by(user_id=user_id)
        .filter(
            DailyPlan.date >= date(year, month, 1),
            DailyPlan.date < date(year, month, 28) + timedelta(days=5),
        )
        .all()
    )

    # Initialize data aggregators
    status_summary = defaultdict(int)
    category_totals = defaultdict(Decimal)

    # Aggregate spending data
    for day in days:
        status_summary[day.status] += 1
        category_totals[day.category] += day.spent_amount

    # Extract behavioral patterns using AI
    patterns = extract_patterns(str(user_id), year, month).get("patterns", [])

    # Build user profile dictionary
    return {
        "user_id": user.id,
        "email": user.email,
        "status_breakdown": dict(status_summary),
        "total_by_category": {k: float(v) for k, v in category_totals.items()},
        "behavior_tags": patterns,
        "is_premium": getattr(user, "is_premium", False),
    }


def generate_financial_rating(user_profile: dict, db) -> dict:
    tmpl_service = AIAdviceTemplateService(db)
    template = tmpl_service.get("financial_rating_prompt")
    if template:
        prompt = template.format(
            total_by_category=user_profile["total_by_category"],
            status_breakdown=user_profile["status_breakdown"],
            behavior_tags=user_profile["behavior_tags"],
        )
    else:
        # Construct the prompt to send to GPT
        prompt = (
            "Analyze the user's financial behavior.\n"
            f"Top spending categories: {user_profile['total_by_category']}.\n"
            f"Day statuses: {user_profile['status_breakdown']}.\n"
            f"Behavioral tags: {user_profile['behavior_tags']}.\n"
            "Write a short analytical summary in English with rating, overspending risk, and advice.\n"
            "Respond as JSON with fields: 'rating', 'risk', 'summary'."
        )

    # Ask GPT model
    system_prompt = tmpl_service.get("system_prompt")
    gpt = GPTAgentService(
        api_key=settings.OPENAI_API_KEY, model="gpt-4o", system_prompt=system_prompt
    )
    result = gpt.ask([{"role": "user", "content": prompt}])

    # Attempt to parse JSON response
    try:
        return json.loads(result)
    except Exception:
        return {
            "rating": "B",
            "risk": "moderate",
            "summary": "User spending is generally steady but occasionally exceeds the budget.",
        }

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.budget_planner import generate_budget_from_answers
from app.services.calendar_service_real import save_calendar_for_user
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions", response_model=dict)
async def get_questions():
    """Return onboarding questions from the config directory."""
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "config" / "onboarding_questions.json"
    if not path.exists():
        return success_response({"questions": []})
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return success_response(data)


@router.post("/submit")
async def submit_onboarding(
    answers: dict,
    db: Session = Depends(get_db),  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
):
    budget_plan = generate_budget_from_answers(answers)
    calendar_data = build_calendar({**answers, **budget_plan})
    save_calendar_for_user(db, current_user.id, calendar_data)
    return success_response({"status": "success", "calendar_days": len(calendar_data)})

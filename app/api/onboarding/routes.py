
from fastapi import APIRouter
import json
from pathlib import Path
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

@router.get("/questions", response_model=dict)
async def get_questions():
    path = Path("data/onboarding_questions.json")
    if not path.exists():
        return success_response({"questions": []})
    with path.open("r") as f:
        data = json.load(f)
    return success_response(data)



from fastapi import APIRouter, Depends
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.budget_planner import generate_budget_from_answers
from app.engine.calendar_engine_behavioral import build_calendar
from app.services.calendar_service_real import save_calendar_for_user

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

FAKE_USER_ID = 1  # TODO: заменить на токен после auth

@router.post("/submit")
async def submit_onboarding(answers: dict, db: Session = Depends(get_db)):
    budget_plan = generate_budget_from_answers(answers)
    calendar_data = build_calendar({**answers, **budget_plan})
    save_calendar_for_user(db, FAKE_USER_ID, calendar_data)
    return {"status": "success", "calendar_days": len(calendar_data)}
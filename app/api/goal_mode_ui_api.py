
from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/goal-mode", tags=["goal_mode"])

class GoalState(BaseModel):
    user_id: str
    region: str = "US-CA"
    cohort: str = "unknown"
    behavior: str = "neutral"
    income: float
    fixed_expenses: float
    goal: float
    saved: float

@router.post("/progress")
async def get_goal_progress_endpoint(payload: GoalState):
    income = payload.income
    fixed_expenses = payload.fixed_expenses
    goal = payload.goal
    saved = payload.saved

    if saved >= goal:
        try:
            from app.engine.analytics_engine import AnalyticsEngine
            analytics = AnalyticsEngine()
            analytics.log_behavior(
                user_id=payload.user_id,
                region=payload.region,
                cohort=payload.cohort,
                behavior_tag=payload.behavior,
                challenge_success=False,
                goal_completed=True
            )
        except Exception as e:
            print("Analytics error:", e)

    return success_response({
        "progress_pct": round(min(saved / goal * 100, 100), 2) if goal > 0 else 0,
        "target": goal,
        "saved": saved,
        "remaining": max(goal - saved, 0)
    })

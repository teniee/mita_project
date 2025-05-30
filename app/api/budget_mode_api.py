from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.budget_mode_selector import resolve_budget_mode
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/debug", tags=["debug"])

class SettingsInput(BaseModel):
    savings_target: float = 0.0

@router.post("/mode")
async def get_budget_mode(payload: SettingsInput):
    mode = resolve_budget_mode(payload.dict())
    return success_response({"mode": mode})
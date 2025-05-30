from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.budget_redistributor import redistribute_budget
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/calendar", tags=["calendar"])

class RedistributeInput(BaseModel):
    calendar: dict
    strategy: str = "balance"

@router.post("/redistribute")
async def redistribute(payload: RedistributeInput):
    updated = redistribute_budget(payload.calendar, payload.strategy)
    return success_response({"updated_calendar": updated})
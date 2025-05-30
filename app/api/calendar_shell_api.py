from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.budget_mode_shell_integration import get_shell_calendar
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/calendar", tags=["calendar"])

class ShellConfig(BaseModel):
    user_id: str
    savings_target: float
    income: float
    fixed: dict
    weights: dict
    year: int
    month: int

@router.post("/shell")
async def get_shell(payload: ShellConfig):
    result = get_shell_calendar(payload.user_id, payload.dict())
    return success_response(result)
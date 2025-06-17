from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.progress_logic import get_progress_data
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/progress", tags=["progress"])


class ProgressRequest(BaseModel):
    user_id: str
    year: int
    month: int


@router.post("/data")
async def get_progress(payload: ProgressRequest):
    result = get_progress_data(
        user_id=payload.user_id,
        year=payload.year,
        month=payload.month,
        config={},
    )
    return success_response(result)

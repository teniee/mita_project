
from fastapi import APIRouter
from app.api.checkpoint.schemas import CheckpointInput, CheckpointOut
from app.services.checkpoint_service import calculate_checkpoint
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])

@router.post("/today", response_model=CheckpointOut)
async def today_checkpoint(payload: CheckpointInput):
    value = calculate_checkpoint(payload.calendar, payload.income, payload.day)
    return success_response({"available_today": value})
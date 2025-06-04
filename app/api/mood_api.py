from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.mood_checkin_service import save_user_mood
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/mood", tags=["mood"])

class MoodInput(BaseModel):
    user_id: str
    mood: str
    timestamp: str

@router.post("/submit")
async def submit_mood(payload: MoodInput):
    save_user_mood(payload.user_id, payload.mood, payload.timestamp)
    return success_response({"status": "mood_saved"})
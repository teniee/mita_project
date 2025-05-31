from app.utils.response_wrapper import success_response
from fastapi import APIRouter, HTTPException, Body
from datetime import date
from app.engine.mood_store import save_mood, get_mood

router = APIRouter(prefix="/mood", tags=["mood"])

@router.post("/{user_id}")
def submit_mood(user_id: str, payload: dict = Body(...)):
    mood = payload.get("mood")
    today = date.today().isoformat()

    if mood not in ["happy", "neutral", "stressed", "sad", "energized"]:
        raise HTTPException(status_code=400, detail="Invalid mood value")

    save_mood(user_id, today, mood)
    return success_response({"status": "ok", "mood": mood, "date": today})

@router.get("/{user_id}")
def get_today_mood(user_id: str):
    today = date.today().isoformat()
    mood = get_mood(user_id, today)
    return success_response({"mood": mood, "date": today})

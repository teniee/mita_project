from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.style_personalization_engine import personalize_ui
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/style", tags=["style"])


class StyleInput(BaseModel):
    user_id: str
    profile: dict


@router.post("/personalize")
async def personalize(payload: StyleInput):
    """Return personalized styling info for the user."""

    result = personalize_ui(payload.user_id, payload.profile)
    return success_response({"style": result})

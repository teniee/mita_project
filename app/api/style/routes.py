
from fastapi import APIRouter

from app.api.style.schemas import StyleRequest, StyleResponse
from app.api.style.services import get_ui_style
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/style", tags=["style"])


@router.post("/", response_model=StyleResponse)
async def personalize(payload: StyleRequest):
    """Return styling configuration for the UI."""

    return success_response({
        "style": get_ui_style(payload.user_id, payload.profile),
    })

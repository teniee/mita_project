
from fastapi import APIRouter, Depends

from app.api.style.schemas import StyleRequest, StyleResponse
from app.api.style.services import get_ui_style
from app.utils.response_wrapper import success_response
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/style", tags=["style"])


@router.post("/", response_model=StyleResponse)
async def personalize(
    payload: StyleRequest, user=Depends(get_current_user)  # noqa: B008
):
    """Return styling configuration for the UI."""

    return success_response({"style": get_ui_style(user.id, payload.profile)})

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.api.users.schemas import UserProfileOut, UserUpdateIn
from app.core.db import get_db
from app.services.users_service import update_user_profile
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfileOut, summary="Get current user's profile")
async def get_profile(current_user=Depends(get_current_user)):
    return success_response(
        {
            "id": current_user.id,
            "email": current_user.email,
            "country": current_user.country,
            "created_at": current_user.created_at.isoformat(),
            "timezone": current_user.timezone,
        }
    )


@router.patch(
    "/me", response_model=UserProfileOut, summary="Update current user's profile"
)
async def update_profile(
    data: UserUpdateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user = update_user_profile(current_user, data, db)
    return success_response(
        {
            "id": user.id,
            "email": user.email,
            "country": user.country,
            "timezone": user.timezone,
            "updated_at": user.updated_at.isoformat(),
        }
    )

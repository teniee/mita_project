from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.jwt_utils import create_access_token, create_refresh_token
from app.services.google_auth_service import authenticate_google_user

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleAuthInput(BaseModel):
    id_token: str


@router.post("/google")
def google_login(
    payload: GoogleAuthInput,
    db: Session = Depends(get_db),  # noqa: B008
):
    user = authenticate_google_user(payload.id_token, db)
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "is_premium": user.is_premium,
    }

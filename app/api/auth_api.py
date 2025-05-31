
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.google_auth_service import authenticate_google_user

router = APIRouter(prefix="/auth", tags=["auth"])

class GoogleAuthInput(BaseModel):
    id_token: str

@router.post("/google")
def google_login(payload: GoogleAuthInput, db: Session = Depends(get_db)):
    user = authenticate_google_user(payload.id_token, db)
    return {
        "user_id": user.id,
        "email": user.email,
        "is_premium": user.is_premium
    }

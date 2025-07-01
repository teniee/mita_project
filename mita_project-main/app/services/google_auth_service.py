import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.db.models import User
from app.core.jwt_utils import hash_password
import uuid

ALLOWED_GOOGLE_CLIENT_IDS = [
    "796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com",  # Android
    "796406677497-0a9jg6vkuv2jtibddll5dp2b0394h21h.apps.googleusercontent.com",  # iOS
]

async def authenticate_google_user(id_token_str: str, db: Session) -> User:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token_str},
            timeout=5,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid ID token")

        payload = response.json()

    aud = payload.get("aud")
    if aud not in ALLOWED_GOOGLE_CLIENT_IDS:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Client ID: got {aud}, allowed {ALLOWED_GOOGLE_CLIENT_IDS}"
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email not found in token")

    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),
            is_premium=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

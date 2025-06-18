from fastapi import HTTPException
from google.auth.transport import requests as grequests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.db.models import User

# Your iOS OAuth Client ID
GOOGLE_CLIENT_ID = (
    "796406677497-0a9jg6vkuv2jtibddll5dp2b0394h21h.apps.googleusercontent.com"
)


def authenticate_google_user(id_token_str: str, db: Session) -> User:
    try:
        payload = id_token.verify_oauth2_token(
            id_token_str, grequests.Request(), GOOGLE_CLIENT_ID
        )
        email = payload.get("email")
        if not email:
            raise ValueError("Email not in token")

        user = db.query(User).filter_by(email=email).first()
        if not user:
            # Automatically create a user record with a random password
            import uuid

            from app.core.jwt_utils import hash_password

            user = User(
                email=email,
                password_hash=hash_password(uuid.uuid4().hex),
                is_premium=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid ID token: {str(e)}",
        )

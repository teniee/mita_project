
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from app.core.session import get_db
from app.db.models import User

GOOGLE_CLIENT_IDS = [
    "796406677497-0a9jg6vkuv2jtibddll5dp2b0394h21h.apps.googleusercontent.com",
    "147595998708-0pkq7emouan1rs2lrgjau0ee2lge35pl.apps.googleusercontent.com",
]

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]

    for client_id in GOOGLE_CLIENT_IDS:
        try:
            payload = id_token.verify_oauth2_token(
                token, grequests.Request(), client_id
            )
            email = payload.get("email")
            if not email:
                raise ValueError("Missing email in token")

            user = db.query(User).filter_by(email=email).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            return user
        except Exception:
            continue

    raise HTTPException(status_code=401, detail="Invalid token")

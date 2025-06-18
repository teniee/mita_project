from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth.schemas import LoginIn  # noqa: E501
from app.api.auth.schemas import GoogleAuthIn, RegisterIn, TokenOut
from app.core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.services.google_auth_service import authenticate_google_user
from app.utils.response_wrapper import success_response


def register_user(data: RegisterIn, db: Session) -> TokenOut:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        country=data.country,
        annual_income=data.annual_income,
        timezone=data.timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


def authenticate_user(data: LoginIn, db: Session) -> TokenOut:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


def refresh_token_for_user(user: User) -> TokenOut:
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


# Placeholder for token revocation.
# Replace with proper token blacklist logic.


def revoke_token(user: User):
    # e.g. save refresh token jti to blacklist in Redis
    return success_response({"message": "Logged out successfully"})


def authenticate_google(data: GoogleAuthIn, db: Session) -> TokenOut:
    user = authenticate_google_user(data.id_token, db)
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )

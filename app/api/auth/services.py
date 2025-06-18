from secrets import token_urlsafe

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
from app.db.models import EmailVerificationToken, PasswordResetToken, User
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


def create_password_reset(email: str, db: Session) -> str:
    user = db.query(User).filter_by(email=email).first()
    if not user:
        return ""
    token = token_urlsafe(32)
    record = PasswordResetToken(user_id=user.id, token=token)
    db.add(record)
    db.commit()
    return token


def reset_password(token: str, new_password: str, db: Session) -> None:
    query = db.query(PasswordResetToken).filter_by(token=token, used=False)
    record = query.first()
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user = db.query(User).filter_by(id=record.user_id).first()
    user.password_hash = hash_password(new_password)
    record.used = True
    db.commit()


def create_email_verification(user: User, db: Session) -> str:
    token = token_urlsafe(32)
    record = EmailVerificationToken(user_id=user.id, token=token)
    db.add(record)
    db.commit()
    return token


def verify_email_token(token: str, db: Session) -> None:
    query = db.query(EmailVerificationToken).filter_by(token=token, used=False)
    record = query.first()
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user = db.query(User).filter_by(id=record.user_id).first()
    user.is_email_verified = True
    record.used = True
    db.commit()

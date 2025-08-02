from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.auth.schemas import LoginIn  # noqa: E501
from app.api.auth.schemas import GoogleAuthIn, RegisterIn, TokenOut
from app.db.models import User
from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
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
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


def authenticate_user(data: LoginIn, db: Session) -> TokenOut:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenOut(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


def refresh_token_for_user(user: User) -> TokenOut:
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return TokenOut(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


# Placeholder for token revocation.
# Replace with proper token blacklist logic.


def revoke_token(user: User):
    # e.g. save refresh token jti to blacklist in Redis
    return success_response({"message": "Logged out successfully"})


async def authenticate_google(data: GoogleAuthIn, db: AsyncSession) -> TokenOut:
    user = await authenticate_google_user(data.id_token, db)
    return TokenOut(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


# Async versions of auth functions
async def register_user_async(data: RegisterIn, db: AsyncSession) -> TokenOut:
    # Check if user already exists
    result = await db.execute(select(User).filter(User.email == data.email))
    existing_user = result.scalars().first()
    
    if existing_user:
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
    await db.commit()
    await db.refresh(user)

    return TokenOut(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


async def authenticate_user_async(data: LoginIn, db: AsyncSession) -> TokenOut:
    result = await db.execute(select(User).filter(User.email == data.email))
    user = result.scalars().first()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    return TokenOut(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )

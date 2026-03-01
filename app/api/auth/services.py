from typing import Union
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.auth.schemas import LoginIn  # noqa: E501
from app.api.auth.schemas import GoogleAuthIn, RegisterIn, FastRegisterIn, TokenOut
from app.db.models import User
from app.services.auth_jwt_service import (
    create_token_pair,
    hash_password,
    verify_password
)
from app.services.resilient_google_auth_service import authenticate_google_user
from app.utils.response_wrapper import success_response


def register_user(data: RegisterIn, db: Session) -> TokenOut:
    # Нормализуем email для корректной проверки
    normalized_email = data.email.lower().strip()

    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists",
        )
    user = User(
        email=normalized_email,  # Используем нормализованный email
        password_hash=hash_password(data.password),
        country=data.country,
        annual_income=data.annual_income,
        timezone=data.timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Determine user role and create tokens with appropriate scopes
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": user.country,
        "token_version_id": user.token_version  # Security: token revocation support
    }

    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )


def authenticate_user(data: LoginIn, db: Session) -> TokenOut:
    # Нормализуем email для корректного поиска
    normalized_email = data.email.lower().strip()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    # Determine user role and create tokens with appropriate scopes
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": user.country,
        "token_version_id": user.token_version  # Security: token revocation support
    }

    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )


def refresh_token_for_user(user: User) -> TokenOut:
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Determine user role and create tokens with appropriate scopes
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": getattr(user, 'country', 'US')
    }
    
    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )


# Placeholder for token revocation.
# Replace with proper token blacklist logic.


def revoke_token(user: User):
    # e.g. save refresh token jti to blacklist in Redis
    return success_response({"message": "Logged out successfully"})


async def authenticate_google(data: GoogleAuthIn, db: AsyncSession) -> TokenOut:
    user = await authenticate_google_user(data.id_token)
    # Determine user role and create tokens with appropriate scopes
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": getattr(user, 'country', 'US')
    }
    
    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )


# Simplified registration function without complex async operations
async def register_user_async(data: Union[FastRegisterIn, RegisterIn], db: AsyncSession) -> TokenOut:
    """SIMPLIFIED: Clean registration without complex timeout operations that cause hangs."""
    
    # Basic validation
    if len(data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    
    # Simple user existence check without timeout
    existing_user = await db.scalar(
        select(User.id).where(User.email == data.email.lower())
    )
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )
    
    # Hash password synchronously (avoids thread pool issues)
    password_hash = hash_password(data.password)
    
    # Create user
    user = User(
        email=data.email.lower(),
        password_hash=password_hash,
        country=data.country,
        annual_income=getattr(data, 'annual_income', 0) or 0,
        timezone=data.timezone,
    )
    
    # Simple database transaction
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create tokens
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": user.country
    }
    
    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )


async def authenticate_user_async(data: LoginIn, db: AsyncSession) -> TokenOut:
    """SIMPLIFIED: Clean authentication without complex async operations that cause hangs."""
    
    # Simple user lookup
    result = await db.execute(select(User).filter(User.email == data.email.lower()))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify password synchronously (avoids thread pool issues)
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Create tokens
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": user.country
    }
    
    tokens = create_token_pair(user_data, user_role=user_role)
    
    return TokenOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )

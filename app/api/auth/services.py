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
    create_token_pair,
    hash_password,
    verify_password,
    async_hash_password,
    async_verify_password,
    get_user_scopes,
    UserRole
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

    # Determine user role and create tokens with appropriate scopes
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


def authenticate_user(data: LoginIn, db: Session) -> TokenOut:
    user = db.query(User).filter(User.email == data.email).first()
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
        "country": user.country
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
    user = await authenticate_google_user(data.id_token, db)
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


# Async versions of auth functions
async def register_user_async(data: RegisterIn, db: AsyncSession) -> TokenOut:
    # Validate password strength
    if len(data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    
    # Check password complexity
    import re
    if not re.search(r'[A-Za-z]', data.password) or not re.search(r'[0-9]', data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain both letters and numbers",
        )
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )
    
    # Check if user already exists
    result = await db.execute(select(User).filter(User.email == data.email.lower()))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )
    
    # Validate annual income range
    if data.annual_income and (data.annual_income < 0 or data.annual_income > 10000000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Annual income must be between 0 and 10,000,000",
        )
    
    # Hash password asynchronously to avoid blocking the event loop
    password_hash = await async_hash_password(data.password)
    
    user = User(
        email=data.email.lower(),
        password_hash=password_hash,
        country=data.country,
        annual_income=data.annual_income,
        timezone=data.timezone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Determine user role and create tokens with appropriate scopes
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
    # Rate limiting check for failed attempts would go here
    result = await db.execute(select(User).filter(User.email == data.email.lower()))
    user = result.scalars().first()
    
    if not user:
        # Note: Removed artificial delay for better performance
        # In production, consider using rate limiting instead
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify password asynchronously to avoid blocking the event loop
    is_valid_password = await async_verify_password(data.password, user.password_hash)
    
    if not is_valid_password:
        # Note: Removed artificial delay for better performance
        # In production, consider using rate limiting instead
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Determine user role and create tokens with appropriate scopes
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

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.async_session import get_async_db
from app.db.models import User
from app.services.auth_jwt_service import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user from JWT token
    Now uses async database operations for better performance
    """
    try:
        payload = verify_token(token) or {}
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token"
            )
        
        # Use async query with select statement
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User not found"
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token"
        )


async def require_premium_user(user: User = Depends(get_current_user)) -> User:
    """
    Require premium user access
    Raises 402 if the user is not premium
    """
    if not user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Premium membership required",
        )
    return user


async def require_admin_access(user: User = Depends(get_current_user)) -> User:
    """
    Require admin user access
    Raises 403 if the user is not an admin
    """
    # Check if user has admin role (assuming there's an is_admin field or role field)
    is_admin = getattr(user, 'is_admin', False) or getattr(user, 'role', '') == 'admin'
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


oauth2_refresh_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/refresh")


async def get_refresh_token_user(
    token: str = Depends(oauth2_refresh_scheme), 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get user from refresh token
    Now uses async database operations for better performance
    """
    try:
        payload = verify_token(token, scope="refresh_token") or {}
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid refresh token"
            )
        
        # Use async query with select statement
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User not found"
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid refresh token"
        )

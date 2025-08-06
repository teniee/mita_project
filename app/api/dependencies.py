from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.async_session import get_async_db
from app.db.models import User
from app.services.auth_jwt_service import verify_token

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user from JWT token
    Enhanced with better error handling and logging
    """
    try:
        # Validate token format
        if not token or token.strip() == "":
            logger.warning("Empty or invalid token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify and decode token
        payload = verify_token(token)
        if not payload:
            logger.warning("Token verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing user ID (sub claim)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Query user from database
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        except Exception as db_error:
            logger.error(f"Database error during user lookup: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )
        
        if not user:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.debug(f"Successfully authenticated user {user_id}")
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except JWTError as jwt_error:
        logger.warning(f"JWT validation error: {jwt_error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
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
    Enhanced with better error handling and logging
    """
    try:
        # Validate token format
        if not token or token.strip() == "":
            logger.warning("Empty or invalid refresh token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify and decode refresh token
        payload = verify_token(token, scope="refresh_token")
        if not payload:
            logger.warning("Refresh token verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Refresh token missing user ID (sub claim)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Query user from database
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        except Exception as db_error:
            logger.error(f"Database error during refresh token user lookup: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )
        
        if not user:
            logger.warning(f"User {user_id} not found during refresh token validation")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.debug(f"Successfully validated refresh token for user {user_id}")
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except JWTError as jwt_error:
        logger.warning(f"JWT refresh token validation error: {jwt_error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_refresh_token_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refresh token system error"
        )

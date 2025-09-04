from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from typing import Dict, Any, List

from app.core.async_session import get_async_db
from app.db.models import User
from app.services.auth_jwt_service import (
    verify_token, 
    get_user_scopes, 
    TokenScope,
    UserRole
)
# RESTORED: Re-enable audit logging with optimized performance (no database deadlocks)
from app.core.audit_logging import log_security_event, log_security_event_async
from app.core.performance_cache import user_cache, cache_user_data

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def _get_user_from_cache_or_db(user_id: str, db: AsyncSession) -> User:
    """Get user from cache or database with automatic caching"""
    cache_key = f"user:{user_id}"
    
    # Try cache first
    cached_user = user_cache.get(cache_key)
    if cached_user is not None:
        logger.debug(f"User {user_id} found in cache")
        return cached_user
    
    # Query from database
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        # Cache the result if user exists
        if user:
            user_cache.set(cache_key, user, ttl=300)  # Cache for 5 minutes
            logger.debug(f"User {user_id} cached for future requests")
        
        return user
    except Exception as db_error:
        logger.error(f"Database error during user lookup: {db_error}")
        raise


async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user from JWT token with enhanced scope validation.
    Enhanced with better error handling, logging, and scope information.
    """
    try:
        # Validate token format
        if not token or token.strip() == "":
            logger.warning("Empty or invalid token provided")
            log_security_event("authentication_failure", {
                "reason": "empty_token",
                "details": "No token provided in authorization header"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify and decode token with comprehensive validation
        payload = await verify_token(token, token_type="access_token")
        if not payload:
            logger.warning("Token verification failed")
            log_security_event("authentication_failure", {
                "reason": "invalid_token",
                "details": "Token verification failed"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing user ID (sub claim)")
            log_security_event("authentication_failure", {
                "reason": "missing_user_id",
                "details": "Token missing required sub claim"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Query user from cache or database
        try:
            user = await _get_user_from_cache_or_db(user_id, db)
        except Exception as db_error:
            log_security_event("database_error", {
                "operation": "user_lookup",
                "user_id": user_id,
                "error": str(db_error)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )
        
        if not user:
            logger.warning(f"User {user_id} not found in database")
            log_security_event("authentication_failure", {
                "reason": "user_not_found",
                "user_id": user_id,
                "details": "User exists in token but not in database"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Add token payload to user object for scope checking
        user._token_payload = payload
        user._token_scopes = payload.get("scope", "").split()
        
        logger.debug(f"Successfully authenticated user {user_id} with scopes: {user._token_scopes}")
        log_security_event("authentication_success", {
            "user_id": user_id,
            "scopes": user._token_scopes,
            "token_type": payload.get("token_type"),
            "role": payload.get("role")
        })
        
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except JWTError as jwt_error:
        logger.warning(f"JWT validation error: {jwt_error}")
        log_security_event("authentication_failure", {
            "reason": "jwt_error",
            "details": str(jwt_error)
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}")
        log_security_event("system_error", {
            "operation": "get_current_user",
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
        )


async def require_premium_user(user: User = Depends(get_current_user)) -> User:
    """
    Require premium user access with scope validation.
    Checks both database premium status and token scopes.
    Raises 402 if the user is not premium or lacks premium scopes.
    """
    # Check database premium status
    if not user.is_premium:
        log_security_event("premium_access_denied", {
            "user_id": str(user.id),
            "reason": "not_premium_user",
            "is_premium": user.is_premium
        })
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Premium membership required",
        )
    
    # Check token has premium scopes
    token_scopes = getattr(user, '_token_scopes', [])
    premium_scopes = [
        TokenScope.PREMIUM_FEATURES.value,
        TokenScope.PREMIUM_AI_INSIGHTS.value,
        TokenScope.ADVANCED_ANALYTICS.value,
        TokenScope.ADMIN_SYSTEM.value  # Admins have premium access
    ]
    
    has_premium_scope = any(scope in token_scopes for scope in premium_scopes)
    if not has_premium_scope:
        log_security_event("premium_scope_access_denied", {
            "user_id": str(user.id),
            "reason": "insufficient_premium_scopes",
            "token_scopes": token_scopes,
            "required_scopes": premium_scopes
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium access token required",
        )
    
    log_security_event("premium_access_granted", {
        "user_id": str(user.id),
        "token_scopes": token_scopes
    })
    
    return user


async def require_admin_access(user: User = Depends(get_current_user)) -> User:
    """
    Require admin user access with comprehensive scope validation.
    Checks both database admin status and token admin scopes.
    Raises 403 if the user is not an admin or lacks admin scopes.
    """
    # Check token has admin scopes
    token_scopes = getattr(user, '_token_scopes', [])
    admin_scopes = [
        TokenScope.ADMIN_SYSTEM.value,
        TokenScope.ADMIN_USERS.value,
        TokenScope.ADMIN_AUDIT.value
    ]
    
    has_admin_scope = any(scope in token_scopes for scope in admin_scopes)
    
    # Also check database admin status (if available)
    is_db_admin = getattr(user, 'is_admin', False) or getattr(user, 'role', '') == 'admin'
    
    # Check token role claim
    token_payload = getattr(user, '_token_payload', {})
    token_role = token_payload.get('role', '')
    is_token_admin = token_role == 'admin'
    
    if not (has_admin_scope or is_db_admin or is_token_admin):
        log_security_event("admin_access_denied", {
            "user_id": str(user.id),
            "reason": "insufficient_admin_privileges",
            "token_scopes": token_scopes,
            "token_role": token_role,
            "is_db_admin": is_db_admin,
            "required_scopes": admin_scopes
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    
    log_security_event("admin_access_granted", {
        "user_id": str(user.id),
        "token_scopes": token_scopes,
        "token_role": token_role,
        "access_method": "scope" if has_admin_scope else "role"
    })
    
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
        payload = await verify_token(token, token_type="refresh_token")
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
        
        # Query user from cache or database
        try:
            user = await _get_user_from_cache_or_db(user_id, db)
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


# Additional scope-aware dependency functions

async def get_current_user_with_payload(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Get current user with full token payload information.
    Returns both user object and token payload for scope checking.
    """
    user = await get_current_user(token, db)
    return {
        "user": user,
        "token_payload": getattr(user, '_token_payload', {}),
        "token_scopes": getattr(user, '_token_scopes', [])
    }


def require_scope_access(required_scope: str):
    """
    Create a dependency that requires a specific scope.
    
    Args:
        required_scope: The OAuth 2.0 scope required
        
    Returns:
        FastAPI dependency function
    """
    async def scope_check(user: User = Depends(get_current_user)) -> User:
        token_scopes = getattr(user, '_token_scopes', [])
        
        if required_scope not in token_scopes and TokenScope.ADMIN_SYSTEM.value not in token_scopes:
            log_security_event("scope_access_denied", {
                "user_id": str(user.id),
                "required_scope": required_scope,
                "token_scopes": token_scopes
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {required_scope}"
            )
        
        return user
    
    return Depends(scope_check)


def require_any_scope(required_scopes: List[str]):
    """
    Create a dependency that requires any of the specified scopes.
    
    Args:
        required_scopes: List of acceptable OAuth 2.0 scopes
        
    Returns:
        FastAPI dependency function
    """
    async def scope_check(user: User = Depends(get_current_user)) -> User:
        token_scopes = getattr(user, '_token_scopes', [])
        
        # Admin system scope bypasses all other requirements
        if TokenScope.ADMIN_SYSTEM.value in token_scopes:
            return user
        
        has_required_scope = any(scope in token_scopes for scope in required_scopes)
        if not has_required_scope:
            log_security_event("scope_access_denied", {
                "user_id": str(user.id),
                "required_scopes": required_scopes,
                "token_scopes": token_scopes
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required any of scopes: {required_scopes}"
            )
        
        return user
    
    return Depends(scope_check)


def require_all_scopes(required_scopes: List[str]):
    """
    Create a dependency that requires all specified scopes.
    
    Args:
        required_scopes: List of required OAuth 2.0 scopes
        
    Returns:
        FastAPI dependency function
    """
    async def scope_check(user: User = Depends(get_current_user)) -> User:
        token_scopes = getattr(user, '_token_scopes', [])
        
        # Admin system scope bypasses all other requirements
        if TokenScope.ADMIN_SYSTEM.value in token_scopes:
            return user
        
        missing_scopes = [scope for scope in required_scopes if scope not in token_scopes]
        if missing_scopes:
            log_security_event("scope_access_denied", {
                "user_id": str(user.id),
                "required_scopes": required_scopes,
                "missing_scopes": missing_scopes,
                "token_scopes": token_scopes
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scopes: {missing_scopes}"
            )
        
        return user
    
    return Depends(scope_check)


# Predefined dependencies for common operations

require_read_profile = require_scope_access(TokenScope.READ_PROFILE.value)
require_write_profile = require_scope_access(TokenScope.WRITE_PROFILE.value)

require_read_transactions = require_scope_access(TokenScope.READ_TRANSACTIONS.value)
require_write_transactions = require_scope_access(TokenScope.WRITE_TRANSACTIONS.value)
require_delete_transactions = require_scope_access(TokenScope.DELETE_TRANSACTIONS.value)

require_read_budget = require_scope_access(TokenScope.READ_BUDGET.value)
require_write_budget = require_scope_access(TokenScope.WRITE_BUDGET.value)
require_manage_budget = require_scope_access(TokenScope.MANAGE_BUDGET.value)

require_read_analytics = require_scope_access(TokenScope.READ_ANALYTICS.value)
require_advanced_analytics = require_scope_access(TokenScope.ADVANCED_ANALYTICS.value)

require_premium_features_scope = require_scope_access(TokenScope.PREMIUM_FEATURES.value)
require_premium_ai_insights = require_scope_access(TokenScope.PREMIUM_AI_INSIGHTS.value)

require_process_receipts = require_scope_access(TokenScope.PROCESS_RECEIPTS.value)
require_ocr_analysis = require_scope_access(TokenScope.OCR_ANALYSIS.value)

require_admin_users_scope = require_scope_access(TokenScope.ADMIN_USERS.value)
require_admin_system_scope = require_scope_access(TokenScope.ADMIN_SYSTEM.value)
require_admin_audit_scope = require_scope_access(TokenScope.ADMIN_AUDIT.value)

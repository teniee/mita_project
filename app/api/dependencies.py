from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import (
    InvalidTokenError,
    ExpiredSignatureError,
    DecodeError,
    InvalidSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    MissingRequiredClaimError,
    PyJWTError
)
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def _get_user_from_cache_or_db(user_id: str, db: AsyncSession) -> User:
    """
    Get user from database (caching DISABLED to prevent DetachedInstanceError).

    CRITICAL: User object caching was causing DetachedInstanceError because:
    - Cached User objects are detached from SQLAlchemy session
    - Accessing attributes on detached objects raises DetachedInstanceError
    - Solution: Always query fresh from database, keep object attached to session

    TODO: Implement data-dict caching (not ORM object caching) for performance
    """
    # CACHING DISABLED: ORM objects become detached from session when cached
    # cache_key = f"user:{user_id}"
    # cached_user = user_cache.get(cache_key)
    # if cached_user is not None:
    #     logger.debug(f"User {user_id} found in cache")
    #     return cached_user  # ❌ Returns detached object

    # Always query from database to ensure object is attached to current session
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        # Don't cache ORM objects - they become detached from session
        # if user:
        #     user_cache.set(cache_key, user, ttl=300)
        #     logger.debug(f"User {user_id} cached for future requests")

        if user:
            logger.debug(f"User {user_id} loaded fresh from database (session-attached)")

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

    SECURITY: All authentication failures return 401, never 500.

    CRITICAL FIX: With auto_error=False, OAuth2PasswordBearer returns None when no token is present.
    We must explicitly check for None and raise 401 before any other processing.
    """
    logger.info("🔐 GET_CURRENT_USER CALLED")

    # CRITICAL: Check for None token first (when auto_error=False, scheme returns None)
    if token is None:
        logger.warning("❌ No token provided (Authorization header missing)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Validate token format
        logger.info(f"Token received - length: {len(token) if token else 0}")
        logger.info(f"Token (first 30 chars): {token[:30] if token else 'None'}...")

        if not token or token.strip() == "":
            logger.warning("❌ Empty or invalid token provided")
            try:
                log_security_event("authentication_failure", {
                    "reason": "empty_token",
                    "details": "No token provided in authorization header"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Verify and decode token with comprehensive validation
        # Wrap in try-except to catch ANY exception from verify_token
        logger.info("📞 Calling verify_token for access_token...")
        try:
            payload = await verify_token(token, token_type="access_token")
            logger.info(f"✅ verify_token returned - payload is {'None' if payload is None else 'present'}")
            if payload:
                logger.info(f"Payload user_id (sub): {payload.get('sub')}")
        except (
            InvalidTokenError,
            ExpiredSignatureError,
            DecodeError,
            InvalidSignatureError,
            InvalidAudienceError,
            InvalidIssuerError,
            MissingRequiredClaimError,
            PyJWTError
        ) as jwt_error:
            # JWT errors should always return 401
            logger.warning(f"❌ JWT validation error during verify_token: {jwt_error}")
            try:
                log_security_event("authentication_failure", {
                    "reason": "jwt_verify_error",
                    "error_type": type(jwt_error).__name__,
                    "details": "Token verification failed"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as verify_error:
            # ANY other error from verify_token should also return 401 (not 500)
            # This handles database errors, network errors, etc. during token verification
            logger.warning(f"❌ Token verification system error: {verify_error}", exc_info=True)
            try:
                log_security_event("authentication_failure", {
                    "reason": "verify_system_error",
                    "error_type": type(verify_error).__name__,
                    "details": "Token verification encountered system error"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if not payload:
            logger.warning("❌ Token verification failed - returned None")
            try:
                log_security_event("authentication_failure", {
                    "reason": "invalid_token",
                    "details": "Token verification returned None"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info("🔍 Extracting user_id from payload...")
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("❌ Token missing user ID (sub claim)")
            try:
                log_security_event("authentication_failure", {
                    "reason": "missing_user_id",
                    "details": "Token missing required sub claim"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info(f"✅ User ID extracted: {user_id}")

        # Query user from cache or database
        logger.info(f"📊 Querying user from cache/database for user_id={user_id}...")
        try:
            user = await _get_user_from_cache_or_db(user_id, db)
            logger.info(f"✅ User query completed - user is {'None' if user is None else 'found'}")
            if user:
                # CRITICAL FIX: Access ALL attributes before session closes to prevent DetachedInstanceError
                # Accessing these attributes loads them into SQLAlchemy's instance state,
                # making them available even after the session closes (prevents DetachedInstanceError)
                # This is necessary because services access these attributes after the DB session ends
                # NOTE: With caching disabled, object should remain attached to session,
                # but we still preload for safety and to ensure all attributes are loaded
                user_id_val = user.id
                email = user.email
                has_onboarded = user.has_onboarded
                timezone = user.timezone if hasattr(user, 'timezone') else 'UTC'  # Safe access with fallback
                currency = user.currency if hasattr(user, 'currency') else 'USD'
                name = user.name if hasattr(user, 'name') else None
                monthly_income = user.monthly_income if hasattr(user, 'monthly_income') else None
                budget_method = user.budget_method if hasattr(user, 'budget_method') else None
                savings_goal = user.savings_goal if hasattr(user, 'savings_goal') else None
                is_premium = user.is_premium if hasattr(user, 'is_premium') else False
                logger.info(f"User preloaded: email={email}, timezone={timezone}, is_premium={is_premium}")
        except Exception as db_error:
            # Database errors during user lookup are system errors (500)
            logger.error(f"❌ Database error during user lookup: {db_error}", exc_info=True)
            try:
                log_security_event("database_error", {
                    "operation": "user_lookup",
                    "user_id": user_id,
                    "error": str(db_error)
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )

        if not user:
            logger.warning(f"❌ User {user_id} not found in database")
            try:
                log_security_event("authentication_failure", {
                    "reason": "user_not_found",
                    "user_id": user_id,
                    "details": "User exists in token but not in database"
                })
            except Exception as log_err:
                logger.error(f"Failed to log security event: {log_err}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Add token payload to user object for scope checking
        user._token_payload = payload
        user._token_scopes = payload.get("scope", "").split()

        logger.info(f"✅✅✅ Successfully authenticated user {user_id} with scopes: {user._token_scopes}")
        try:
            log_security_event("authentication_success", {
                "user_id": user_id,
                "scopes": user._token_scopes,
                "token_type": payload.get("token_type"),
                "role": payload.get("role")
            })
        except Exception as log_err:
            logger.error(f"Failed to log security event: {log_err}")

        logger.info(f"🎉 RETURNING USER OBJECT for {user_id}")
        return user

    except HTTPException:
        # Re-raise HTTP exceptions as-is (401, 500, etc.)
        raise
    except (
        InvalidTokenError,
        ExpiredSignatureError,
        DecodeError,
        InvalidSignatureError,
        InvalidAudienceError,
        InvalidIssuerError,
        MissingRequiredClaimError,
        PyJWTError
    ) as jwt_error:
        # ALL JWT-related exceptions should return 401 Unauthorized
        logger.warning(f"JWT validation error: {jwt_error}")
        try:
            log_security_event("authentication_failure", {
                "reason": "jwt_error",
                "error_type": type(jwt_error).__name__,
                "details": "JWT validation failed"
            })
        except Exception as log_err:
            logger.error(f"Failed to log security event: {log_err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        # Only truly unexpected non-JWT, non-HTTP errors should return 500
        logger.error(f"Unexpected error in get_current_user: {e}", exc_info=True)
        try:
            log_security_event("system_error", {
                "operation": "get_current_user",
                "error": str(e),
                "error_type": type(e).__name__
            })
        except Exception as log_err:
            logger.error(f"Failed to log security event: {log_err}")
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


oauth2_refresh_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/refresh", auto_error=False)


async def get_refresh_token_user(
    token: str = Depends(oauth2_refresh_scheme),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get user from refresh token
    Enhanced with better error handling and logging

    CRITICAL FIX: With auto_error=False, OAuth2PasswordBearer returns None when no token is present.
    """
    # CRITICAL: Check for None token first (when auto_error=False, scheme returns None)
    if token is None:
        logger.warning("❌ No refresh token provided (Authorization header missing)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

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
    except (
        InvalidTokenError,
        ExpiredSignatureError,
        DecodeError,
        InvalidSignatureError,
        InvalidAudienceError,
        InvalidIssuerError,
        MissingRequiredClaimError,
        PyJWTError
    ) as jwt_error:
        # ALL JWT-related exceptions should return 401 Unauthorized
        logger.warning(f"JWT refresh token validation error: {jwt_error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        # Only truly unexpected non-JWT errors should return 500
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

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.schemas import LoginIn  # noqa: E501
from app.api.auth.schemas import GoogleAuthIn, RegisterIn, TokenOut
from app.api.auth.services import authenticate_google  # noqa: E501
from app.api.auth.services import authenticate_user_async, register_user_async
from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event
from app.core.security import (
    require_auth_endpoint_protection,
    comprehensive_auth_security,
    get_rate_limiter,
    AdvancedRateLimiter,
    SecurityConfig
)
from app.db.models import User
from app.services import auth_jwt_service as jwt_utils
from app.services.auth_jwt_service import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    verify_token,
    validate_token_security,
    get_token_info,
    get_user_scopes,
    UserRole
)
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth", 
    tags=["Authentication"],
    dependencies=[Depends(require_auth_endpoint_protection())]  # Apply base security to all auth endpoints
)


# ------------------------------------------------------------------
# Auth & registration
# ------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(comprehensive_auth_security())]
)
async def register(
    payload: RegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Create a new user account with comprehensive rate limiting and security."""
    # Apply registration-specific rate limiting
    rate_limiter.check_auth_rate_limit(request, payload.email, "register")
    
    # Log registration attempt
    log_security_event("registration_attempt", {
        "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid",
        "user_agent": request.headers.get('User-Agent', '')[:100],
        "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
    })
    
    try:
        result = await register_user_async(payload, db)
        
        # Log successful registration
        log_security_event("registration_success", {
            "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid"
        })
        
        return result
        
    except Exception as e:
        # Log failed registration
        log_security_event("registration_failed", {
            "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid",
            "error": str(e)[:200]
        })
        raise


@router.post(
    "/login", 
    response_model=TokenOut,
    dependencies=[Depends(comprehensive_auth_security())]
)
async def login(
    payload: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Authenticate an existing user with comprehensive security and rate limiting."""
    # Apply login-specific rate limiting
    rate_limiter.check_auth_rate_limit(request, payload.email, "login")
    
    # Log login attempt
    log_security_event("login_attempt", {
        "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid",
        "user_agent": request.headers.get('User-Agent', '')[:100],
        "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
    })
    
    try:
        result = await authenticate_user_async(payload, db)
        
        # Log successful login
        log_security_event("login_success", {
            "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid",
            "user_id": str(result.get('user_id', 'unknown')) if isinstance(result, dict) else 'unknown'
        })
        
        return result
        
    except Exception as e:
        # Log failed login
        log_security_event("login_failed", {
            "email_hash": payload.email[:3] + "***@" + payload.email.split('@')[1] if '@' in payload.email else "invalid",
            "error": str(e)[:200],
            "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
        })
        raise


# ------------------------------------------------------------------
# Token refresh / logout
# ------------------------------------------------------------------

@router.post(
    "/refresh",
    dependencies=[Depends(comprehensive_auth_security())]
)
async def refresh_token(
    request: Request,
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Issue a new access & refresh token pair from a valid refresh token with rotation and rate limiting."""
    # Apply token refresh rate limiting
    rate_limiter.check_rate_limit(request, SecurityConfig.TOKEN_REFRESH_RATE_LIMIT, 300, "token_refresh")
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        logger.warning("Refresh token request without token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    # Get token info for logging before verification
    token_info = get_token_info(token)
    user_id = token_info.get("user_id") if token_info else "unknown"
    
    try:
        payload = verify_token(token, token_type="refresh_token")

        if payload:
            logger.info(f"Refreshing tokens for user {payload.get('sub')}")
            
            # SECURITY: Blacklist old refresh token immediately (rotation)
            if not blacklist_token(token):
                logger.error(f"Failed to blacklist old refresh token for user {payload.get('sub')}")
                # Continue anyway, but log the security concern
                log_security_event("refresh_token_blacklist_failed", {
                    "user_id": payload.get("sub"),
                    "jti": payload.get("jti", "")[:8] + "..."
                })
            
            # Create clean user data (remove JWT-specific claims)
            user_data = {k: v for k, v in payload.items() 
                        if k not in ["exp", "iat", "nbf", "scope", "jti", "iss", "aud", "token_type", "token_version", "security_level"]}
            
            # Determine user role from token or default
            user_role = payload.get("role", "basic_user")
            is_premium = payload.get("is_premium", False)
            
            # Adjust role based on premium status
            if is_premium and user_role == "basic_user":
                user_role = "premium_user"

            new_access = create_access_token(user_data, user_role=user_role)
            new_refresh = create_refresh_token(user_data, user_role=user_role)
            
            log_security_event("token_refresh_success", {
                "user_id": payload.get("sub"),
                "old_jti": payload.get("jti", "")[:8] + "..."
            })
            
            return success_response(
                {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "token_type": "bearer",
                }
            )

        # Fallback for legacy refresh tokens (without `scope`)
        try:
            legacy = jwt_utils.decode_token(token)
            if legacy.get("type") != "refresh":
                raise ValueError("Incorrect token type")

            user_id = str(legacy["sub"])
            logger.warning(f"Using legacy refresh token format for user {user_id}")
            
            # For legacy tokens, use basic user role as default
            user_data = {"sub": user_id}
            access = create_access_token(user_data, user_role="basic_user")
            refresh = create_refresh_token(user_data, user_role="basic_user")
            
            log_security_event("legacy_token_refresh", {"user_id": user_id})
            
            return success_response(
                {
                    "access_token": access,
                    "refresh_token": refresh,
                    "token_type": "bearer",
                }
            )
        except Exception as e:
            logger.warning(f"Legacy refresh token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid refresh token"
            )
            
    except Exception as e:
        logger.warning(f"Token refresh failed for user {user_id}: {e}")
        log_security_event("token_refresh_failed", {
            "user_id": user_id,
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


@router.post(
    "/logout",
    dependencies=[Depends(comprehensive_auth_security())]
)
async def logout(
    request: Request,
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Securely logout by blacklisting current access token with rate limiting."""
    # Apply logout rate limiting (prevent spam) - More lenient
    rate_limiter.check_rate_limit(request, 20, 300, "logout")  # 20 logouts per 5 minutes (increased)
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        logger.warning("Logout request without token")
        return success_response({"message": "No active session to logout."})
    
    # Get user info for logging
    token_info = get_token_info(token)
    user_id = token_info.get("user_id", "unknown") if token_info else "unknown"
    
    try:
        success = blacklist_token(token)
        if success:
            logger.info(f"User {user_id} logged out successfully")
            log_security_event("user_logout_success", {
                "user_id": user_id,
                "jti": token_info.get("jti", "")[:8] + "..." if token_info else "unknown"
            })
            return success_response({"message": "Successfully logged out."})
        else:
            logger.warning(f"Failed to blacklist token during logout for user {user_id}")
            # Still return success to user, but log the issue
            log_security_event("logout_blacklist_failed", {"user_id": user_id})
            return success_response({"message": "Logged out (with warnings)."})
            
    except Exception as e:
        logger.error(f"Logout error for user {user_id}: {e}")
        log_security_event("logout_error", {
            "user_id": user_id,
            "error": str(e)
        })
        # Still return success to avoid leaking information
        return success_response({"message": "Logout processed."})


# ------------------------------------------------------------------
# Third-party login
# ------------------------------------------------------------------

@router.post(
    "/revoke",
    dependencies=[Depends(comprehensive_auth_security())]
)
async def revoke_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Explicitly revoke a specific token with rate limiting."""
    # Apply token revocation rate limiting - More lenient
    rate_limiter.check_rate_limit(request, 10, 300, "token_revoke", str(current_user.id))  # 10 revocations per 5 minutes per user (increased)
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token required for revocation"
        )
    
    try:
        success = blacklist_token(token)
        if success:
            logger.info(f"Token explicitly revoked by user {current_user.id}")
            log_security_event("explicit_token_revocation", {
                "user_id": str(current_user.id),
                "revoked_by": str(current_user.id)
            })
            return success_response({"message": "Token successfully revoked."})
        else:
            logger.warning(f"Failed to revoke token for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke token"
            )
    except Exception as e:
        logger.error(f"Token revocation error for user {current_user.id}: {e}")
        log_security_event("token_revocation_error", {
            "user_id": str(current_user.id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token revocation failed"
        )


@router.get(
    "/token/validate",
    dependencies=[Depends(comprehensive_auth_security())]
)
async def validate_current_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Validate current token security properties with rate limiting."""
    # Apply token validation rate limiting - More lenient
    rate_limiter.check_rate_limit(request, 40, 300, "token_validate", str(current_user.id))  # 40 validations per 5 minutes per user (increased)
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token required for validation"
        )
    
    validation = validate_token_security(token)
    
    return success_response({
        "user_id": str(current_user.id),
        "token_validation": validation
    })


@router.post(
    "/google", 
    response_model=TokenOut,
    dependencies=[Depends(comprehensive_auth_security())]
)
async def google_login(
    payload: GoogleAuthIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Authenticate a user using a Google ID token with security and rate limiting."""
    # Apply OAuth rate limiting (more lenient than regular login) - Further increased
    rate_limiter.check_rate_limit(request, 20, 600, "oauth_login")  # 20 OAuth attempts per 10 minutes (increased)
    
    # Log OAuth login attempt
    log_security_event("oauth_login_attempt", {
        "provider": "google",
        "user_agent": request.headers.get('User-Agent', '')[:100],
        "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
    })
    
    try:
        result = await authenticate_google(payload, db)
        
        # Log successful OAuth login
        log_security_event("oauth_login_success", {
            "provider": "google",
            "user_id": str(result.get('user_id', 'unknown')) if isinstance(result, dict) else 'unknown'
        })
        
        return result
        
    except Exception as e:
        # Log failed OAuth login
        log_security_event("oauth_login_failed", {
            "provider": "google",
            "error": str(e)[:200],
            "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
        })
        raise


# ------------------------------------------------------------------
# Password reset and security monitoring endpoints
# ------------------------------------------------------------------

@router.post(
    "/password-reset/request",
    dependencies=[Depends(comprehensive_auth_security())]
)
async def request_password_reset(
    email: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Request password reset with strict rate limiting."""
    # Apply password reset rate limiting
    rate_limiter.check_auth_rate_limit(request, email, "password_reset")
    
    # Log password reset request
    log_security_event("password_reset_request", {
        "email_hash": email[:3] + "***@" + email.split('@')[1] if '@' in email else "invalid",
        "user_agent": request.headers.get('User-Agent', '')[:100],
        "ip_hash": str(hash(request.client.host if request.client else 'unknown'))[:8]
    })
    
    # Always return success to prevent email enumeration
    # Actual implementation would send email only if user exists
    return success_response({
        "message": "If this email is registered, you will receive password reset instructions."
    })


@router.get("/security/status")
async def get_security_status(
    request: Request,
    rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)
):
    """Get current security status for monitoring (admin endpoint)."""
    # Apply monitoring rate limiting - More lenient for admin monitoring
    rate_limiter.check_rate_limit(request, 15, 300, "security_status")  # 15 requests per 5 minutes (increased)
    
    from app.core.security import get_security_health_status
    
    status_info = get_security_health_status()
    rate_limit_status = rate_limiter.get_rate_limit_status(request, "security_status")
    
    return success_response({
        "security_health": status_info,
        "rate_limit_status": rate_limit_status,
        "endpoint": "auth_security_status"
    })

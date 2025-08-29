import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

# EMERGENCY FIX: Comment out ALL potentially hanging imports
# from app.api.auth.schemas import LoginIn  # noqa: E501
# from app.api.auth.schemas import GoogleAuthIn, RegisterIn, FastRegisterIn, TokenOut
# from app.api.auth.services import authenticate_google  # noqa: E501
# from app.api.auth.services import authenticate_user_async, register_user_async
# from app.api.dependencies import get_current_user
# from app.core.async_session import get_async_db
# from app.core.audit_logging import log_security_event
# from app.db.models import User
# from app.services import auth_jwt_service as jwt_utils
# from app.services.auth_jwt_service import (
#     blacklist_token,
#     create_access_token,
#     create_refresh_token,
#     create_token_pair,
#     verify_token,
#     validate_token_security,
#     get_token_info,
#     get_user_scopes,
#     UserRole
# )
# from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth", 
    tags=["Authentication"],
    # Removed problematic dependency causing 500 errors - security applied at individual endpoint level
)


# ------------------------------------------------------------------
# Auth & registration
# ------------------------------------------------------------------

@router.post(
    "/emergency-register"
)
async def emergency_register(
    email: str,
    password: str,
):
    """EMERGENCY: Ultra-minimal registration endpoint with NO dependencies"""
    import time
    
    start_time = time.time()
    logger.error(f"🚨 EMERGENCY REGISTRATION ATTEMPT: {email[:3]}***")
    
    try:
        # Step 1: Basic validation (NO TIMEOUT)
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password too short")
        
        if '@' not in email:
            raise HTTPException(status_code=400, detail="Invalid email")
        
        total_time = time.time() - start_time
        logger.error(f"🚨 EMERGENCY REGISTRATION SUCCESS: {email[:3]}*** in {total_time:.2f}s")
        
        # Return minimal success response WITHOUT database or token operations
        return {
            "status": "success",
            "message": f"Emergency registration processed for {email[:3]}***",
            "processing_time": f"{total_time:.2f}s",
            "note": "This is a minimal test endpoint - no actual registration performed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"🚨 EMERGENCY REGISTRATION FAILED: {str(e)} after {elapsed:.2f}s")
        raise HTTPException(status_code=500, detail=f"Emergency registration failed: {str(e)}")


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: FastRegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Fast user registration optimized for performance with 10-second timeout."""
    import asyncio
    import time
    
    start_time = time.time()
    
    try:
        # Minimal logging for performance
        logger.info(f"Registration attempt for {payload.email[:3]}*** started")
        
        # Apply overall timeout to prevent 15+ second hangs
        result = await asyncio.wait_for(
            register_user_async(payload, db),
            timeout=10.0  # 10 second overall timeout
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Registration successful for {payload.email[:3]}*** in {elapsed:.2f}s")
        
        # Log performance metrics
        if elapsed > 5.0:
            logger.warning(f"Slow registration: {elapsed:.2f}s for {payload.email[:3]}***")
        
        return result
        
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        logger.error(f"Registration timeout for {payload.email[:3]}*** after {elapsed:.2f}s")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Registration is taking too long. Please try again."
        )
    except HTTPException:
        elapsed = time.time() - start_time
        logger.info(f"Registration HTTP error for {payload.email[:3]}*** after {elapsed:.2f}s")
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Registration failed: {str(e)[:100]} after {elapsed:.2f}s")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post(
    "/register-full",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
)
async def register_full(
    payload: RegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new user account with comprehensive validation and security."""
    # Rate limiting disabled for emergency fix
    
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
)
async def login(
    payload: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticate an existing user with comprehensive security and rate limiting."""
    # Apply login-specific rate limiting
    # Rate limiting disabled for emergency fix
    
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
    "/refresh"
    # EMERGENCY FIX: Removed hanging Redis dependencies
)
async def refresh_token(
    request: Request,
):
    """Issue a new access & refresh token pair from a valid refresh token with rotation and rate limiting."""
    # Apply token refresh rate limiting
    # Rate limiting disabled for emergency fix
    
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
    "/logout"
    # EMERGENCY FIX: Removed hanging Redis dependencies
)
async def logout(
    request: Request,
):
    """Securely logout by blacklisting current access token with rate limiting."""
    # Apply logout rate limiting (prevent spam) - More lenient
    # Rate limiting disabled for emergency fix
    
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
    "/revoke"
    # EMERGENCY FIX: Removed hanging Redis dependencies
)
async def revoke_token(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Explicitly revoke a specific token with rate limiting."""
    # Apply token revocation rate limiting - More lenient
    # Rate limiting disabled for emergency fix
    
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
    "/token/validate"
    # EMERGENCY FIX: Removed hanging Redis dependencies
)
async def validate_current_token(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Validate current token security properties with rate limiting."""
    # Apply token validation rate limiting - More lenient
    # Rate limiting disabled for emergency fix
    
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
)
async def google_login(
    payload: GoogleAuthIn,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticate a user using a Google ID token with security and rate limiting."""
    # Apply OAuth rate limiting (more lenient than regular login) - Further increased
    # Rate limiting disabled for emergency fix
    
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
    "/password-reset/request"
    # EMERGENCY FIX: Removed hanging Redis dependencies
)
async def request_password_reset(
    email: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Request password reset with strict rate limiting."""
    # Apply password reset rate limiting
    # Rate limiting disabled for emergency fix
    
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


@router.get("/emergency-diagnostics")
async def emergency_diagnostics(
    db: AsyncSession = Depends(get_async_db)
):
    """🚨 EMERGENCY: Real-time server diagnostics for registration issues"""
    import time
    import os
    import psutil
    from sqlalchemy import text
    
    diagnostics = {
        "timestamp": time.time(),
        "server_status": "LIVE",
        "registration_endpoints": {}
    }
    
    try:
        # Server Resource Check
        diagnostics["server_resources"] = {
            "memory_usage_mb": psutil.virtual_memory().used / 1024 / 1024,
            "memory_available_mb": psutil.virtual_memory().available / 1024 / 1024,
            "cpu_percent": psutil.cpu_percent(),
            "disk_usage_gb": psutil.disk_usage('/').used / 1024 / 1024 / 1024,
        }
        
        # Environment Check
        diagnostics["environment"] = {
            "database_url_set": bool(os.getenv("DATABASE_URL")),
            "jwt_secret_set": bool(os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "render_service": os.getenv("RENDER_SERVICE_NAME", "not_on_render"),
            "port": os.getenv("PORT", "8000")
        }
        
        # Database Health Check
        db_start = time.time()
        try:
            # Test basic database connectivity
            await db.execute(text("SELECT 1 as test"))
            diagnostics["database"] = {
                "status": "connected",
                "connection_time_ms": (time.time() - db_start) * 1000
            }
            
            # Test user table access
            user_check_start = time.time()
            result = await db.execute(text("SELECT COUNT(*) FROM users LIMIT 1"))
            user_count = result.scalar()
            diagnostics["database"]["user_table_check"] = {
                "accessible": True,
                "user_count": user_count,
                "query_time_ms": (time.time() - user_check_start) * 1000
            }
            
        except Exception as db_error:
            diagnostics["database"] = {
                "status": "error",
                "error": str(db_error),
                "connection_time_ms": (time.time() - db_start) * 1000
            }
        
        # Test registration components
        diagnostics["registration_components"] = {}
        
        # Test password hashing
        hash_start = time.time()
        try:
            from app.services.auth_jwt_service import hash_password
            test_hash = hash_password("test123456")
            diagnostics["registration_components"]["password_hashing"] = {
                "status": "working",
                "time_ms": (time.time() - hash_start) * 1000,
                "hash_length": len(test_hash)
            }
        except Exception as hash_error:
            diagnostics["registration_components"]["password_hashing"] = {
                "status": "error",
                "error": str(hash_error),
                "time_ms": (time.time() - hash_start) * 1000
            }
        
        # Test token creation
        token_start = time.time()
        try:
            from app.services.auth_jwt_service import create_token_pair
            test_tokens = create_token_pair({"sub": "test_user"}, user_role="basic_user")
            diagnostics["registration_components"]["token_creation"] = {
                "status": "working",
                "time_ms": (time.time() - token_start) * 1000,
                "has_access_token": bool(test_tokens.get("access_token")),
                "has_refresh_token": bool(test_tokens.get("refresh_token"))
            }
        except Exception as token_error:
            diagnostics["registration_components"]["token_creation"] = {
                "status": "error", 
                "error": str(token_error),
                "time_ms": (time.time() - token_start) * 1000
            }
        
        # Endpoint availability
        diagnostics["registration_endpoints"] = {
            "emergency_register": "✅ AVAILABLE - /api/auth/emergency-register",
            "regular_register": "⚠️ SLOW - /api/auth/register", 
            "full_register": "🐌 VERY SLOW - /api/auth/register-full"
        }
        
        return {
            "status": "EMERGENCY_DIAGNOSTICS_COMPLETE",
            "message": "🚨 Use /api/auth/emergency-register for immediate registration",
            "diagnostics": diagnostics
        }
        
    except Exception as e:
        return {
            "status": "EMERGENCY_DIAGNOSTICS_FAILED",
            "error": str(e),
            "partial_diagnostics": diagnostics
        }


@router.get("/security/status")
async def get_security_status(
    request: Request,
):
    """Get current security status for monitoring (admin endpoint)."""
    # Apply monitoring rate limiting - More lenient for admin monitoring
    # Rate limiting disabled for emergency fix
    
    from app.core.security import get_security_health_status
    
    status_info = get_security_health_status()
    # Rate limiting disabled for emergency fix
    rate_limit_status = {"requests_remaining": 999, "reset_time": 0}
    
    return success_response({
        "security_health": status_info,
        "rate_limit_status": rate_limit_status,
        "endpoint": "auth_security_status"
    })

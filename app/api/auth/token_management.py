"""
Token management endpoints.

Handles:
- Token refresh (exchange refresh token for new access token)
- Token validation and verification
- Token blacklisting
- Logout and token invalidation
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.schemas import TokenOut
from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event_async
from app.core.error_decorators import handle_auth_errors
from app.core.simple_rate_limiter import check_token_refresh_rate_limit
from app.core.standardized_error_handler import (
    AuthenticationError,
    ErrorCode,
    ValidationError,
)
from app.db.models import User
from app.services.auth_jwt_service import (
    blacklist_token,
    create_token_pair,
    verify_token,
)
from app.utils.response_wrapper import AuthResponseHelper, StandardizedResponse

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Token Management"])


@router.post("/refresh-token", response_model=TokenOut, summary="Refresh access token")
@handle_auth_errors
async def refresh_token_standardized(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Refresh an expired access token using a valid refresh token.

    Features:
    - Refresh token validation
    - Rate limiting protection
    - Security audit logging
    - Token blacklisting support
    """

    # Apply rate limiting
    await check_token_refresh_rate_limit(request)

    if not refresh_token or not refresh_token.strip():
        raise ValidationError(
            "Refresh token is required",
            ErrorCode.VALIDATION_REQUIRED_FIELD
        )

    # Verify refresh token
    try:
        token_data = await verify_token(refresh_token)
        if not token_data or token_data.get("token_type") != "refresh":
            raise AuthenticationError(
                "Invalid refresh token",
                ErrorCode.AUTH_TOKEN_INVALID
            )

        user_id = token_data.get("sub")
        if not user_id:
            raise AuthenticationError(
                "Invalid token payload",
                ErrorCode.AUTH_TOKEN_INVALID
            )

        # Find user
        from sqlalchemy import select
        user_query = select(User).where(User.id == user_id)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError(
                "User not found",
                ErrorCode.AUTH_INVALID_CREDENTIALS
            )

        # Generate new token pair
        user_role = "premium_user" if user.is_premium else "basic_user"
        user_data = {
            "sub": str(user.id),
            "is_premium": user.is_premium,
            "country": user.country,
            "token_version_id": user.token_version  # Security: track token version for revocation
        }

        new_tokens = create_token_pair(user_data, user_role=user_role)

        # Blacklist the old refresh token
        await blacklist_token(refresh_token, "refresh")

        # Log successful token refresh
        await log_security_event_async(
            event_type="token_refresh_success",
            user_id=str(user.id),
            request=request,
            details={"token_jti": token_data.get("jti", "")}
        )

        return AuthResponseHelper.token_refreshed(new_tokens)

    except Exception as e:
        # Log failed token refresh
        await log_security_event_async(
            event_type="token_refresh_failure",
            user_id=None,
            request=request,
            details={"error": str(e), "token_prefix": refresh_token[:20] if refresh_token else ""}
        )

        if isinstance(e, (AuthenticationError, ValidationError)):
            raise
        else:
            raise AuthenticationError(
                "Token refresh failed",
                ErrorCode.AUTH_TOKEN_INVALID
            )


@router.post("/logout", summary="Logout and invalidate tokens")
@handle_auth_errors
async def logout_user_standardized(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Logout user and invalidate their tokens.

    Features:
    - Token blacklisting
    - Security audit logging
    - Comprehensive cleanup
    """

    # Get the current access token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    access_token = ""
    if auth_header.startswith("Bearer "):
        access_token = auth_header.replace("Bearer ", "")

    try:
        # Blacklist the current access token
        if access_token:
            await blacklist_token(access_token, "access")

        # Log successful logout
        await log_security_event_async(
            event_type="user_logout_success",
            user_id=str(current_user.id),
            request=request,
            details={"email": current_user.email}
        )

        return StandardizedResponse.success(
            message="Logged out successfully",
            data={"logout_time": datetime.utcnow().isoformat() + "Z"}
        )

    except Exception as e:
        # Log failed logout
        await log_security_event_async(
            event_type="user_logout_failure",
            user_id=str(current_user.id),
            request=request,
            details={"error": str(e)}
        )

        raise AuthenticationError(
            "Logout failed",
            ErrorCode.AUTH_TOKEN_INVALID
        )

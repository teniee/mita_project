"""
User login endpoints.

Handles:
- Email/password authentication
- Password verification
- Token generation with proper scopes
- Login audit logging
- Account status checks
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.schemas import LoginIn, TokenOut
from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event_async
from app.core.error_decorators import handle_auth_errors
from app.core.password_security import verify_password_async
from app.core.simple_rate_limiter import check_login_rate_limit
from app.core.standardized_error_handler import (
    AuthenticationError,
    ErrorCode,
    validate_email,
    validate_required_fields,
)
from app.db.models import User
from app.services.auth_jwt_service import create_token_pair
from app.utils.response_wrapper import AuthResponseHelper

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Login"])


@router.post("/login", response_model=TokenOut, summary="Authenticate user login")
@handle_auth_errors
async def login_user_standardized(
    request: Request,
    login_data: LoginIn,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Authenticate user login with comprehensive security and error handling.

    Features:
    - Rate limiting protection
    - Secure password verification
    - Comprehensive audit logging
    - Standardized error responses
    - JWT token generation with proper scopes
    """

    # Apply rate limiting
    await check_login_rate_limit(request)

    # Validate required fields
    login_dict = login_data.dict()
    validate_required_fields(login_dict, ["email", "password"])

    # Validate email format
    validated_email = validate_email(login_data.email)

    # Find user
    from sqlalchemy import select
    user_query = select(User).where(User.email == validated_email)
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        # Log failed login attempt
        await log_security_event_async(
            event_type="login_attempt_user_not_found",
            user_id=None,
            request=request,
            details={"email": validated_email}
        )
        raise AuthenticationError(
            "Invalid email or password",
            ErrorCode.AUTH_INVALID_CREDENTIALS
        )

    # Verify password
    password_valid = await verify_password_async(login_data.password, user.password_hash)
    if not password_valid:
        # Log failed login attempt
        await log_security_event_async(
            event_type="login_attempt_invalid_password",
            user_id=str(user.id),
            request=request,
            details={"email": validated_email}
        )
        raise AuthenticationError(
            "Invalid email or password",
            ErrorCode.AUTH_INVALID_CREDENTIALS
        )

    # Check if account is active (add account status checks here if needed)
    if hasattr(user, 'is_active') and not user.is_active:
        await log_security_event_async(
            event_type="login_attempt_inactive_account",
            user_id=str(user.id),
            request=request,
            details={"email": validated_email}
        )
        raise AuthenticationError(
            "Account is inactive",
            ErrorCode.AUTH_ACCOUNT_LOCKED
        )

    # Generate tokens
    user_role = "premium_user" if user.is_premium else "basic_user"
    user_data = {
        "sub": str(user.id),
        "is_premium": user.is_premium,
        "country": user.country
    }

    tokens = create_token_pair(user_data, user_role=user_role)

    # Log successful login
    await log_security_event_async(
        event_type="user_login_success",
        user_id=str(user.id),
        request=request,
        details={"email": validated_email, "user_agent": request.headers.get("user-agent", "")}
    )

    # Prepare response data
    user_response_data = {
        "id": str(user.id),
        "email": user.email,
        "country": user.country,
        "is_premium": user.is_premium,
        "last_login": user.updated_at.isoformat() + "Z" if user.updated_at else None
    }

    # Update last login timestamp
    user.updated_at = datetime.utcnow()
    await db.commit()

    return AuthResponseHelper.login_success(
        tokens=tokens,
        user_data=user_response_data,
        login_info={
            "login_time": datetime.utcnow().isoformat() + "Z",
            "client_ip": request.client.host if request.client else 'unknown',
            "requires_password_change": False  # Add logic for password expiry if needed
        }
    )

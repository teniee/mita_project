"""
User registration endpoints.

Handles:
- Standard user registration with email/password
- Email validation and duplicate checks
- Password hashing and security
- Welcome information and onboarding setup
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.schemas import RegisterIn, TokenOut
from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event_async
from app.core.error_decorators import handle_auth_errors
from app.core.password_security import hash_password_async
from app.core.simple_rate_limiter import check_register_rate_limit
from app.core.standardized_error_handler import (
    BusinessLogicError,
    ErrorCode,
    validate_email,
    validate_password,
    validate_required_fields,
)
from app.db.models import User
from app.services.auth_jwt_service import create_token_pair
from app.utils.response_wrapper import AuthResponseHelper

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Registration"])


@router.post("/register", response_model=TokenOut, summary="Register new user account")
@handle_auth_errors
async def register_user_standardized(
    request: Request,
    registration_data: RegisterIn,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Register a new user account with comprehensive error handling and validation.

    This endpoint uses the standardized error handling system to provide:
    - Consistent error response formats
    - Proper HTTP status codes
    - Detailed validation error messages
    - Security audit logging
    """

    # Apply rate limiting
    await check_register_rate_limit(request)

    # Validate required fields
    registration_dict = registration_data.dict()
    validate_required_fields(registration_dict, ["email", "password", "country"])

    # Validate email format
    validated_email = validate_email(registration_data.email)

    # Validate password strength
    validate_password(registration_data.password)

    # Check if user already exists
    from sqlalchemy import select
    existing_user_query = select(User).where(User.email == validated_email)
    result = await db.execute(existing_user_query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Log security event
        await log_security_event_async(
            event_type="registration_attempt_duplicate_email",
            user_id=None,
            request=request,
            details={"email": validated_email}
        )
        raise BusinessLogicError(
            "An account with this email address already exists",
            ErrorCode.RESOURCE_ALREADY_EXISTS,
            details={"email": validated_email}
        )

    # Hash password securely
    password_hash = await hash_password_async(registration_data.password)

    # Create new user with all required fields
    new_user = User(
        email=validated_email,
        password_hash=password_hash,
        country=registration_data.country,
        annual_income=registration_data.annual_income or 0,
        timezone=registration_data.timezone or "UTC",
        # Explicitly set datetime fields
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        # Set default boolean fields
        is_premium=False,
        email_verified=False,
        has_onboarded=False,
        notifications_enabled=True,
        dark_mode_enabled=False,
        # Set token version
        token_version=1,
        # Set optional profile fields
        name=registration_data.name or "",
        monthly_income=0,
        savings_goal=0,
        budget_method="50/30/20 Rule",
        currency="USD"
    )

    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Log successful registration
        await log_security_event_async(
            event_type="user_registration_success",
            user_id=str(new_user.id),
            request=request,
            details={"email": validated_email, "country": registration_data.country}
        )

        # Create secure token pair
        user_role = "premium_user" if new_user.is_premium else "basic_user"
        user_data = {
            "sub": str(new_user.id),
            "is_premium": new_user.is_premium,
            "country": new_user.country,
            "token_version_id": new_user.token_version  # Security: track token version for revocation
        }

        tokens = create_token_pair(user_data, user_role=user_role)

        # Prepare response data
        user_response_data = {
            "id": str(new_user.id),
            "email": new_user.email,
            "country": new_user.country,
            "is_premium": new_user.is_premium,
            "created_at": new_user.created_at.isoformat() + "Z"
        }

        return AuthResponseHelper.registration_success(
            tokens=tokens,
            user_data=user_response_data,
            welcome_info={
                "onboarding_required": True,
                "features_unlocked": ["basic_budgeting", "expense_tracking"]
            }
        )

    except Exception as e:
        await db.rollback()
        await log_security_event_async(
            event_type="user_registration_failure",
            user_id=None,
            request=request,
            details={"email": validated_email, "error": str(e)}
        )
        raise

"""
Password reset endpoints.

Handles:
- Password reset request (generate and send reset token)
- Password reset confirmation (verify token and set new password)
- Email queue integration for reset notifications
- Security event logging
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event_async
from app.core.error_decorators import handle_auth_errors
from app.core.password_security import hash_password_async
from app.core.simple_rate_limiter import check_password_reset_rate_limit
from app.core.standardized_error_handler import (
    AuthenticationError,
    ErrorCode,
    ValidationError,
    validate_email,
    validate_password,
    validate_required_fields,
)
from app.db.models import User
from app.utils.response_wrapper import StandardizedResponse, success_response

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Password Reset"])


@router.post(
    "/password-reset/request",
    dependencies=[Depends(check_password_reset_rate_limit)]
)
async def request_password_reset(
    email: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Request password reset with email integration and strict rate limiting."""
    from app.services.email_service import PasswordResetTokenManager
    from app.services.email_queue_service import queue_password_reset_email
    from sqlalchemy import select

    # Apply password reset rate limiting
    # Rate limiting: 3 attempts per 5 minutes per IP (prevent spam registrations)

    # Validate email format
    validated_email = validate_email(email.lower().strip())

    # Log password reset request for security monitoring
    await log_security_event_async("password_reset_request", {
        "email_hash": validated_email[:3] + "***@" + validated_email.split('@')[1] if '@' in validated_email else "invalid",
        "user_agent": request.headers.get('User-Agent', '')[:100],
        "client_ip": request.client.host if request.client else 'unknown'
    }, request=request)

    try:
        # Check if user exists (but don't reveal this to prevent enumeration)
        user_query = select(User).where(User.email == validated_email)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if user:
            # Generate secure reset token
            reset_token, token_hash = PasswordResetTokenManager.generate_reset_token(str(user.id))

            # Store token hash in user record (you may want to create a separate tokens table)
            user.password_reset_token = token_hash
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=2)
            user.password_reset_attempts = getattr(user, 'password_reset_attempts', 0) + 1

            await db.commit()

            # Queue password reset email
            user_name = validated_email.split('@')[0].title()
            job_id = await queue_password_reset_email(
                user_email=validated_email,
                user_name=user_name,
                reset_token=reset_token,
                user_id=str(user.id)
            )

            # Log successful password reset email queued
            await log_security_event_async("password_reset_email_sent", {
                "user_id": str(user.id),
                "email_hash": validated_email[:3] + "***@" + validated_email.split('@')[1],
                "job_id": job_id,
                "success": True
            }, request=request, user_id=str(user.id))

            logger.info(f"Password reset email queued for {validated_email[:3]}*** (job: {job_id})")
        else:
            # Log attempt for non-existent email (security monitoring)
            await log_security_event_async("password_reset_nonexistent_email", {
                "email_hash": validated_email[:3] + "***@" + validated_email.split('@')[1],
                "client_ip": request.client.host if request.client else 'unknown'
            }, request=request)

            logger.info(f"Password reset requested for non-existent email: {validated_email[:3]}***")

        # Always return success to prevent email enumeration attacks
        return success_response({
            "message": "If this email is registered, you will receive password reset instructions within a few minutes.",
            "instructions": "Check your email and spam folder. The reset link expires in 2 hours."
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        await log_security_event_async("password_reset_error", {
            "email_hash": validated_email[:3] + "***@" + validated_email.split('@')[1] if validated_email else "invalid",
            "error": str(e)[:200]
        }, request=request)

        # Still return success to prevent information leakage
        return success_response({
            "message": "If this email is registered, you will receive password reset instructions."
        })


@router.post(
    "/password-reset/confirm",
    summary="Confirm password reset with token"
)
@handle_auth_errors
async def confirm_password_reset(
    request: Request,
    email: str,
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Confirm password reset using token and set new password.

    Features:
    - Secure token verification
    - Password strength validation
    - Account security logging
    - Token invalidation after use
    """
    from app.services.email_service import PasswordResetTokenManager
    from sqlalchemy import select

    # Apply rate limiting for password reset confirmation
    await check_password_reset_rate_limit(request)

    # Validate inputs
    validate_required_fields({"email": email, "token": token, "new_password": new_password})
    validated_email = validate_email(email.lower().strip())
    validate_password(new_password)

    try:
        # Find user
        user_query = select(User).where(User.email == validated_email)
        result = await db.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            await log_security_event_async(
                event_type="password_reset_invalid_user",
                user_id=None,
                request=request,
                details={"email": validated_email}
            )
            raise AuthenticationError(
                "Invalid password reset request",
                ErrorCode.AUTH_INVALID_CREDENTIALS
            )

        # Check if user has a reset token
        if not hasattr(user, 'password_reset_token') or not user.password_reset_token:
            await log_security_event_async(
                event_type="password_reset_no_token",
                user_id=str(user.id),
                request=request,
                details={"email": validated_email}
            )
            raise AuthenticationError(
                "Invalid or expired password reset token",
                ErrorCode.AUTH_TOKEN_INVALID
            )

        # Check token expiry
        if hasattr(user, 'password_reset_expires') and user.password_reset_expires:
            if datetime.utcnow() > user.password_reset_expires:
                await log_security_event_async(
                    event_type="password_reset_token_expired",
                    user_id=str(user.id),
                    request=request,
                    details={"email": validated_email}
                )
                raise AuthenticationError(
                    "Password reset token has expired",
                    ErrorCode.AUTH_TOKEN_EXPIRED
                )

        # Verify token
        if not PasswordResetTokenManager.verify_reset_token(token, user.password_reset_token, str(user.id)):
            await log_security_event_async(
                event_type="password_reset_invalid_token",
                user_id=str(user.id),
                request=request,
                details={"email": validated_email}
            )
            raise AuthenticationError(
                "Invalid password reset token",
                ErrorCode.AUTH_TOKEN_INVALID
            )

        # Hash new password
        new_password_hash = await hash_password_async(new_password)

        # Update user password and clear reset token
        user.password_hash = new_password_hash
        user.password_reset_token = None
        user.password_reset_expires = None
        user.password_reset_attempts = 0
        user.updated_at = datetime.utcnow()

        # Increment token version to invalidate existing JWT tokens
        user.token_version = (getattr(user, 'token_version', 0) or 0) + 1

        await db.commit()

        # Log successful password reset
        await log_security_event_async(
            event_type="password_reset_success",
            user_id=str(user.id),
            request=request,
            details={
                "email": validated_email,
                "user_agent": request.headers.get("user-agent", "")[:100]
            }
        )

        # Queue security notification email
        from app.services.email_queue_service import queue_email
        from app.services.email_service import EmailType, EmailPriority

        security_variables = {
            'user_name': validated_email.split('@')[0].title(),
            'alert_type': 'Password Successfully Changed',
            'alert_details': f'Your password was successfully changed on {datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")}.',
            'timestamp': datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC'),
            'email': validated_email,
            'action_taken': 'All existing sessions have been terminated for your security.',
            'recommended_actions': [
                'Log back into your account with your new password',
                'Review your account activity',
                'Enable two-factor authentication if not already enabled'
            ]
        }

        await queue_email(
            to_email=validated_email,
            email_type=EmailType.SECURITY_ALERT,
            variables=security_variables,
            priority=EmailPriority.HIGH,
            user_id=str(user.id)
        )

        logger.info(f"Password reset completed successfully for user {user.id}")

        return StandardizedResponse.success(
            message="Password reset successful. You can now log in with your new password.",
            data={
                "password_changed": True,
                "sessions_invalidated": True,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

    except (AuthenticationError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Password reset confirmation error: {e}")
        await log_security_event_async(
            event_type="password_reset_confirmation_error",
            user_id=None,
            request=request,
            details={"email": validated_email, "error": str(e)[:200]}
        )
        raise AuthenticationError(
            "Password reset failed",
            ErrorCode.AUTH_TOKEN_INVALID
        )

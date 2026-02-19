"""
Account management endpoints.

Handles:
- Password change (with current password verification)
- Account deletion (permanent with token revocation)
- Forgot password (mobile app integration)
- Reset token verification
- Password reset with token
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.utils import log_security_event
from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db
from app.core.error_decorators import handle_auth_errors
from app.core.password_security import hash_password_async, verify_password_async
from app.core.standardized_error_handler import (
    AuthenticationError,
    ErrorCode,
    ResourceNotFoundError,
    ValidationError,
    validate_password,
    validate_required_fields,
    validate_email,
)
from app.db.models import User
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Account Management"])


# --- Request schemas (accept JSON body from mobile app) ---

class ForgotPasswordRequest(BaseModel):
    email: str
    client_id: Optional[str] = None
    redirect_url: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# Alias for backward compatibility
get_db = get_async_db
get_current_active_user = get_current_user


@router.post("/change-password", summary="Change user password")
async def change_password(
    request: Request,
    current_password: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Change user password with current password verification."""
    try:
        # Validate inputs
        validate_required_fields({"current_password": current_password, "new_password": new_password})
        validate_password(new_password)

        # Verify current password
        if not await verify_password_async(current_password, current_user.password_hash):
            raise AuthenticationError("Current password is incorrect", ErrorCode.INVALID_CREDENTIALS)

        # Hash new password
        new_password_hash = await hash_password_async(new_password)

        # Update user password
        current_user.password_hash = new_password_hash
        current_user.updated_at = datetime.utcnow()

        # Increment token version to invalidate existing tokens
        current_user.token_version = (current_user.token_version or 1) + 1

        db.add(current_user)
        await db.commit()

        # Log security event
        log_security_event("password_changed", {
            "user_id": str(current_user.id),
            "user_email": current_user.email,
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Password changed successfully for user {current_user.id}")

        return success_response({
            "message": "Password changed successfully",
            "timestamp": datetime.utcnow().isoformat()
        })

    except (AuthenticationError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.delete("/delete-account", summary="Delete user account permanently")
async def delete_account(
    request: Request,
    confirmation: bool,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Delete user account permanently with all associated data."""
    try:
        # Validate confirmation
        if not confirmation:
            raise ValidationError("Account deletion must be confirmed", ErrorCode.MISSING_FIELD)

        # Log security event before deletion
        log_security_event("account_deletion_initiated", {
            "user_id": str(current_user.id),
            "user_email": current_user.email,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Revoke all user tokens before deletion
        try:
            from app.api.auth.utils import revoke_user_tokens
            await revoke_user_tokens(
                user_id=str(current_user.id),
                reason="account_deletion",
                revoked_by=str(current_user.id)
            )
        except Exception as e:
            logger.warning(f"Failed to revoke tokens during account deletion: {e}")

        # Delete user and all related data (CASCADE should handle relationships)
        await db.delete(current_user)
        await db.commit()

        logger.critical(f"Account deleted permanently: user_id={current_user.id}, email={current_user.email}")

        return success_response({
            "message": "Account deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Account deletion failed for user {current_user.id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )


@router.post("/forgot-password", summary="Initiate password reset")
@handle_auth_errors
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate password reset process by sending reset token to user's email.
    """
    email = body.email
    try:
        validate_email(email)

        # Find user by email
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal if email exists - security best practice
            return success_response({
                "message": "If the email exists, a password reset link has been sent.",
                "email": email
            })

        # Generate reset token
        from app.services.auth_jwt_service import generate_password_reset_token
        reset_token = generate_password_reset_token(user.id)

        # Store token in database
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        user.password_reset_attempts = 0

        await db.commit()

        # Send reset email
        try:
            from app.services.email_service import send_password_reset_email
            await send_password_reset_email(user.email, reset_token, user.name or "User")
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            # Don't fail the request if email fails

        log_security_event("password_reset_initiated", {
            "user_id": str(user.id),
            "email": email
        }, request)

        return success_response({
            "message": "If the email exists, a password reset link has been sent.",
            "email": email
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Password reset initiation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        )


async def _do_verify_reset_token(token: str, db: AsyncSession):
    """Shared logic for verifying a password reset token."""
    from app.services.auth_jwt_service import verify_password_reset_token as _verify

    user_id = _verify(token)
    if not user_id:
        return success_response({"valid": False, "message": "Invalid or expired token"})

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        return success_response({"valid": False, "message": "Invalid or expired token"})

    if not hasattr(user, 'password_reset_token') or user.password_reset_token != token:
        return success_response({"valid": False, "message": "Invalid or expired token"})

    if hasattr(user, 'password_reset_expires') and user.password_reset_expires:
        if user.password_reset_expires < datetime.utcnow():
            return success_response({"valid": False, "message": "Reset token has expired"})

    return success_response({"valid": True, "message": "Reset token is valid", "user_id": str(user_id)})


@router.get("/verify-reset-token", summary="Verify password reset token (GET)")
@handle_auth_errors
async def verify_reset_token_get(
    request: Request,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Verify if password reset token is valid (GET, used by mobile app)."""
    return await _do_verify_reset_token(token, db)


@router.post("/verify-reset-token", summary="Verify password reset token (POST)")
@handle_auth_errors
async def verify_reset_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify if password reset token is valid and not expired."""
    return await _do_verify_reset_token(token, db)


@router.post("/reset-password", summary="Reset password with token")
@handle_auth_errors
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset user password using valid reset token.
    """
    token = body.token
    new_password = body.new_password
    try:
        # Validate new password
        validate_password(new_password)

        # Verify token
        from app.services.auth_jwt_service import verify_password_reset_token
        user_id = verify_password_reset_token(token)

        if not user_id:
            raise ValidationError(
                "Invalid or expired reset token",
                ErrorCode.AUTHENTICATION_TOKEN_INVALID
            )

        # Get user
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise ResourceNotFoundError("User not found")

        # Verify token matches
        if not hasattr(user, 'password_reset_token') or user.password_reset_token != token:
            raise ValidationError(
                "Invalid reset token",
                ErrorCode.AUTHENTICATION_TOKEN_INVALID
            )

        # Check expiration
        if hasattr(user, 'password_reset_expires') and user.password_reset_expires:
            if user.password_reset_expires < datetime.utcnow():
                raise ValidationError(
                    "Reset token has expired",
                    ErrorCode.AUTHENTICATION_TOKEN_EXPIRED
                )

        # Hash new password
        hashed_password = await hash_password_async(new_password)

        # Update password and clear reset token
        user.password_hash = hashed_password
        user.password_reset_token = None
        user.password_reset_expires = None
        user.password_reset_attempts = 0

        await db.commit()

        # Revoke all existing tokens for security
        try:
            from app.api.auth.utils import revoke_user_tokens
            await revoke_user_tokens(str(user.id), "password_reset")
        except Exception as e:
            logger.warning(f"Failed to revoke tokens after password reset: {e}")

        log_security_event("password_reset_completed", {
            "user_id": str(user.id),
            "email": user.email
        }, request)

        return success_response({
            "message": "Password has been reset successfully. Please login with your new password.",
            "success": True
        })

    except (ValidationError, ResourceNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Password reset failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

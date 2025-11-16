"""
Google OAuth authentication endpoints.

Handles:
- Google OAuth token verification
- User authentication via Google
- Security event logging for OAuth flows
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.schemas import GoogleAuthIn
from app.api.auth.services import authenticate_google
from app.api.auth.utils import log_security_event
from app.core.async_session import get_async_db
from app.core.error_decorators import handle_auth_errors
from app.core.standardized_error_handler import AuthenticationError, ErrorCode
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Google OAuth"])


@router.post("/google", summary="Google OAuth authentication")
@handle_auth_errors
async def google_auth(
    request: Request,
    google_data: GoogleAuthIn,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Authenticate user with Google OAuth token.
    """
    try:
        # Use existing Google authentication service
        result = await authenticate_google(google_data, db)

        if not result:
            raise AuthenticationError(
                "Google authentication failed",
                ErrorCode.AUTHENTICATION_GOOGLE_FAILED
            )

        log_security_event("google_auth_success", {
            "email": google_data.email if hasattr(google_data, 'email') else None
        }, request)

        return success_response(result)

    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Google authentication failed: {e}")
        raise AuthenticationError(
            "Google authentication failed",
            ErrorCode.AUTHENTICATION_GOOGLE_FAILED,
            details={"error": str(e)}
        )

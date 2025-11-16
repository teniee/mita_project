"""
Authentication utilities module.

Contains shared utility functions used across authentication endpoints:
- Token revocation
- Security event logging (sync and async)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.audit_logging import log_security_event_async
from app.core.async_session import get_async_db
from app.db.models import User

logger = logging.getLogger(__name__)


def log_security_event(event_type, details, request=None, user_id=None):
    """
    Synchronous security event logging function.

    Creates an async task for non-blocking security event logging.

    Args:
        event_type: Type of security event
        details: Event details dictionary
        request: Optional FastAPI request object
        user_id: Optional user ID associated with the event
    """
    try:
        # Create task for async logging without blocking
        asyncio.create_task(log_security_event_async(event_type, user_id, request, details))
    except Exception as e:
        logger.warning(f"Failed to log security event: {e}")


async def revoke_user_tokens(
    user_id: str,
    reason: str = "admin_action",
    revoked_by: Optional[str] = None
) -> int:
    """
    Revoke all active tokens for a user by incrementing token_version.

    Args:
        user_id: UUID of the user whose tokens should be revoked
        reason: Reason for revocation (e.g., "admin_action", "security_incident")
        revoked_by: UUID of admin who initiated revocation

    Returns:
        Number of tokens revoked (always returns 1 for token_version increment)

    Raises:
        ValueError: If user not found
        RuntimeError: If token revocation fails
    """
    from sqlalchemy import select

    try:
        # Convert user_id to UUID if it's a string
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

        # Get async database session
        async for db in get_async_db():
            # Find user and increment token_version
            result = await db.execute(
                select(User).where(User.id == user_uuid)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User {user_id} not found for token revocation")
                raise ValueError(f"User {user_id} not found")

            # Increment token_version to invalidate all existing JWTs
            old_version = user.token_version
            user.token_version += 1

            # Commit the change
            await db.commit()
            await db.refresh(user)

            # Log security event
            await log_security_event_async(
                event_type="token_revocation",
                user_id=str(user_uuid),
                request=None,
                details={
                    "reason": reason,
                    "revoked_by": revoked_by,
                    "old_token_version": old_version,
                    "new_token_version": user.token_version,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                f"Revoked all tokens for user {user_id} (version {old_version} -> {user.token_version}), "
                f"reason: {reason}, revoked_by: {revoked_by}"
            )

            # Return 1 to indicate successful revocation
            return 1

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Token revocation failed for user {user_id}: {e}")
        raise RuntimeError(f"Failed to revoke tokens: {str(e)}")

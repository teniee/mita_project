"""
Administrative endpoints for user and token management.

Handles:
- Admin token revocation (bulk user tokens)
- Token blacklist management (revoke specific token by JTI)
- Blacklist metrics and monitoring
- User token inspection
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth.utils import revoke_user_tokens
from app.api.dependencies import get_current_user
from app.db.models import User
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Admin"])


@router.post("/admin/revoke-user-tokens")
async def admin_revoke_user_tokens(
    request: Request,
    user_id: str,
    reason: str = "admin_action",
    current_user: User = Depends(get_current_user),
):
    """Revoke all tokens for a specific user (admin only)."""
    # Verify admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        revoked_count = await revoke_user_tokens(
            user_id=user_id,
            reason=reason,
            revoked_by=str(current_user.id)
        )

        logger.info(f"Admin {current_user.id} revoked {revoked_count} tokens for user {user_id}")

        return success_response({
            "message": f"Successfully revoked {revoked_count} tokens for user {user_id}",
            "user_id": user_id,
            "tokens_revoked": revoked_count,
            "revoked_by": str(current_user.id),
            "reason": reason
        })

    except Exception as e:
        logger.error(f"Admin token revocation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke user tokens: {str(e)}"
        )


@router.post("/admin/revoke-token-by-jti")
async def admin_revoke_token_by_jti(
    request: Request,
    jti: str,
    reason: str = "admin_action",
    current_user: User = Depends(get_current_user),
):
    """Revoke a specific token by JTI (admin only)."""
    # Verify admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        from app.services.token_blacklist_service import get_blacklist_service, BlacklistReason

        reason_mapping = {
            "admin_action": BlacklistReason.ADMIN_REVOKE,
            "security_incident": BlacklistReason.SECURITY_INCIDENT,
            "suspicious_activity": BlacklistReason.SUSPICIOUS_ACTIVITY
        }

        blacklist_reason = reason_mapping.get(reason, BlacklistReason.ADMIN_REVOKE)
        blacklist_service = await get_blacklist_service()

        success = await blacklist_service.revoke_token_by_jti(
            jti=jti,
            reason=blacklist_reason,
            revoked_by=str(current_user.id)
        )

        if success:
            logger.info(f"Admin {current_user.id} revoked token {jti[:8]}...")
            return success_response({
                "message": f"Token {jti[:8]}... successfully revoked",
                "jti": jti[:8] + "...",
                "revoked_by": str(current_user.id),
                "reason": reason
            })
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke token - may be invalid or already expired"
            )

    except Exception as e:
        logger.error(f"Admin token revocation by JTI failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke token: {str(e)}"
        )


@router.get("/admin/blacklist-metrics")
async def get_blacklist_metrics(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get blacklist service metrics (admin only)."""
    # Verify admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        from app.services.token_blacklist_service import get_blacklist_service

        blacklist_service = await get_blacklist_service()
        metrics = await blacklist_service.get_blacklist_metrics()
        health = await blacklist_service.health_check()

        return success_response({
            "blacklist_metrics": {
                "total_blacklisted": metrics.total_blacklisted,
                "access_tokens_blacklisted": metrics.access_tokens_blacklisted,
                "refresh_tokens_blacklisted": metrics.refresh_tokens_blacklisted,
                "blacklist_checks": metrics.blacklist_checks,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "average_check_time_ms": metrics.average_check_time_ms,
                "redis_errors": metrics.redis_errors,
                "last_cleanup": metrics.last_cleanup.isoformat() if metrics.last_cleanup else None
            },
            "service_health": health,
            "requested_by": str(current_user.id)
        })

    except Exception as e:
        logger.error(f"Failed to get blacklist metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get("/admin/user-blacklisted-tokens/{user_id}")
async def get_user_blacklisted_tokens(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get list of blacklisted tokens for a specific user (admin only)."""
    # Verify admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        from app.services.token_blacklist_service import get_blacklist_service

        blacklist_service = await get_blacklist_service()
        blacklisted_jtis = await blacklist_service.get_user_blacklisted_tokens(user_id)

        return success_response({
            "user_id": user_id,
            "blacklisted_token_count": len(blacklisted_jtis),
            "blacklisted_tokens": [jti[:8] + "..." for jti in blacklisted_jtis],
            "requested_by": str(current_user.id)
        })

    except Exception as e:
        logger.error(f"Failed to get user blacklisted tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user tokens: {str(e)}"
        )

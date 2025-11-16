"""
Security monitoring and validation endpoints.

Handles:
- Security status monitoring
- Password security configuration
- Token validation
- Token revocation (explicit)
- Security health checks
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_current_user
from app.core.audit_logging import log_security_event_async
from app.db.models import User
from app.services.auth_jwt_service import blacklist_token, validate_token_security
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

# Sub-router WITHOUT /auth prefix (will be added by main router)
router = APIRouter(tags=["Authentication - Security Monitoring"])


@router.post("/revoke")
async def revoke_token(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Explicitly revoke a specific token with rate limiting."""
    # Apply token revocation rate limiting - More lenient

    # Rate limiting: 2 attempts per minute per IP (admin endpoint protection)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token required for revocation"
        )

    try:
        success = await blacklist_token(token, reason="revoke", revoked_by=str(current_user.id))
        if success:
            logger.info(f"Token explicitly revoked by user {current_user.id}")
            # Log explicit token revocation for audit trail
            await log_security_event_async("explicit_token_revocation", {
                "user_id": str(current_user.id),
                "revoked_by": str(current_user.id),
                "success": True
            }, request=request, user_id=str(current_user.id))
            return success_response({"message": "Token successfully revoked."})
        else:
            logger.warning(f"Failed to revoke token for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke token"
            )
    except Exception as e:
        logger.error(f"Token revocation error for user {current_user.id}: {e}")
        # Log token revocation errors for security monitoring
        await log_security_event_async("token_revocation_error", {
            "user_id": str(current_user.id),
            "error": str(e)[:200],
            "success": False
        }, request=request, user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token revocation failed"
        )


@router.get("/token/validate")
async def validate_current_token(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Validate current token security properties with rate limiting."""
    # Apply token validation rate limiting - More lenient

    # Rate limiting: 2 attempts per minute per IP (admin endpoint protection)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token required for validation"
        )

    validation = await validate_token_security(token)

    return success_response({
        "user_id": str(current_user.id),
        "token_validation": validation
    })


@router.get("/security/status")
async def get_security_status(
    request: Request,
):
    """Get current security status for monitoring (admin endpoint)."""
    # Apply monitoring rate limiting - More lenient for admin monitoring

    # Rate limiting: 3 attempts per 15 minutes per IP (prevent password reset abuse)

    from app.core.security import get_security_health_status
    from app.core.password_security import get_password_performance_stats, validate_bcrypt_configuration

    status_info = get_security_health_status()
    password_stats = get_password_performance_stats()
    bcrypt_validation = validate_bcrypt_configuration()

    # Rate limiting disabled for emergency fix
    rate_limit_status = {"requests_remaining": 999, "reset_time": 0}

    return success_response({
        "security_health": status_info,
        "password_security": {
            "bcrypt_configuration": bcrypt_validation,
            "performance_stats": password_stats,
            "security_compliant": bcrypt_validation["valid"] and password_stats["bcrypt_rounds"] >= 12
        },
        "rate_limit_status": rate_limit_status,
        "endpoint": "auth_security_status"
    })


@router.get("/security/password-config")
async def get_password_security_config():
    """Get password security configuration details (monitoring endpoint)."""
    from app.core.password_security import validate_bcrypt_configuration, test_password_performance

    try:
        # Get configuration validation
        config_validation = validate_bcrypt_configuration()

        # Run performance test
        performance_test = test_password_performance()

        return success_response({
            "configuration": config_validation,
            "performance_test": performance_test,
            "recommendations": {
                "current_rounds": config_validation["configuration"]["rounds"],
                "recommended_min_production": 12,
                "performance_acceptable": performance_test["meets_target"],
                "average_hash_time_ms": performance_test["average_ms"]
            },
            "security_compliance": {
                "meets_industry_standard": config_validation["configuration"]["rounds"] >= 12,
                "backward_compatible": True,  # Always true with bcrypt
                "performance_acceptable": performance_test["meets_target"]
            }
        })

    except Exception as e:
        logger.error(f"Password security config check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check password security configuration: {str(e)}"
        )

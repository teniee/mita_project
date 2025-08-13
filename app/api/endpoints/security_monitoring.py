"""
Security Monitoring Endpoints for MITA Financial Application

Provides endpoints for monitoring token security, viewing audit trails,
and managing security alerts. These endpoints are designed for:
- DevOps team monitoring
- Security team analysis
- Compliance reporting
- Incident response

Security Note: These endpoints should be restricted to admin users only.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin_access
from app.core.async_session import get_async_db
from app.core.audit_logging import log_security_event
from app.db.models import User
from app.services.token_security_service import token_security_service
from app.core.upstash import get_blacklist_metrics
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/security", tags=["Security Monitoring"])


@router.get("/metrics")
async def get_security_metrics(
    current_user: User = Depends(require_admin_access)
):
    """
    Get comprehensive security metrics for monitoring dashboards.
    
    Provides real-time metrics on:
    - Token operations (issued, verified, blacklisted)
    - Security alerts and threats
    - Redis blacklist performance
    - Suspicious activity patterns
    """
    try:
        metrics = token_security_service.get_security_metrics()
        
        log_security_event("security_metrics_accessed", {
            "admin_user_id": str(current_user.id),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return success_response({
            "metrics": metrics,
            "generated_at": datetime.utcnow().isoformat(),
            "status": "healthy"
        })
        
    except Exception as e:
        logger.error(f"Error retrieving security metrics: {e}")
        log_security_event("security_metrics_error", {
            "admin_user_id": str(current_user.id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security metrics"
        )


@router.get("/alerts")
async def get_security_alerts(
    limit: int = Query(50, ge=1, le=1000),
    severity: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    current_user: User = Depends(require_admin_access)
):
    """
    Get recent security alerts with optional filtering.
    
    Args:
        limit: Maximum number of alerts to return (1-1000)
        severity: Filter by alert severity (LOW, MEDIUM, HIGH, CRITICAL)
    """
    try:
        alerts = token_security_service.get_recent_alerts(limit=limit)
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert["severity"] == severity]
        
        # Add summary statistics
        summary = {
            "total_alerts": len(alerts),
            "critical_count": sum(1 for a in alerts if a["severity"] == "CRITICAL"),
            "high_count": sum(1 for a in alerts if a["severity"] == "HIGH"),
            "medium_count": sum(1 for a in alerts if a["severity"] == "MEDIUM"),
            "low_count": sum(1 for a in alerts if a["severity"] == "LOW"),
        }
        
        log_security_event("security_alerts_accessed", {
            "admin_user_id": str(current_user.id),
            "alerts_retrieved": len(alerts),
            "severity_filter": severity
        })
        
        return success_response({
            "alerts": alerts,
            "summary": summary,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error retrieving security alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security alerts"
        )


@router.get("/user/{user_id}/activity")
async def get_user_security_activity(
    user_id: str,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed security activity for a specific user.
    
    Useful for investigating suspicious behavior or compliance audits.
    """
    try:
        # Verify user exists (for audit purposes)
        from sqlalchemy import select
        from app.db.models import User as UserModel
        
        result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        target_user = result.scalar_one_or_none()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user activity summary
        activity_summary = token_security_service.get_user_activity_summary(user_id)
        
        log_security_event("user_security_activity_accessed", {
            "admin_user_id": str(current_user.id),
            "target_user_id": user_id,
            "target_user_email": target_user.email
        })
        
        return success_response({
            "user_id": user_id,
            "user_email": target_user.email,
            "activity_summary": activity_summary,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user security activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user security activity"
        )


@router.get("/blacklist/status")
async def get_blacklist_status(
    current_user: User = Depends(require_admin_access)
):
    """
    Get Redis blacklist system status and performance metrics.
    """
    try:
        blacklist_metrics = get_blacklist_metrics()
        
        status_info = {
            "redis_metrics": blacklist_metrics,
            "system_status": "operational",
            "last_checked": datetime.utcnow().isoformat()
        }
        
        # Test Redis connectivity
        try:
            # Perform a simple test operation
            from app.core.upstash import is_token_blacklisted
            test_result = is_token_blacklisted("test-connectivity-jti")
            status_info["connectivity_test"] = "passed"
        except Exception as redis_error:
            logger.warning(f"Redis connectivity test failed: {redis_error}")
            status_info["connectivity_test"] = "failed"
            status_info["connectivity_error"] = str(redis_error)
            status_info["system_status"] = "degraded"
        
        log_security_event("blacklist_status_checked", {
            "admin_user_id": str(current_user.id),
            "system_status": status_info["system_status"]
        })
        
        return success_response(status_info)
        
    except Exception as e:
        logger.error(f"Error checking blacklist status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check blacklist status"
        )


@router.post("/token/revoke-user/{user_id}")
async def admin_revoke_user_tokens(
    user_id: str,
    reason: str = Query(..., min_length=3, max_length=200),
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Admin endpoint to revoke all tokens for a specific user.
    
    This is a security action that should be used in cases of:
    - Account compromise
    - Security policy violations
    - Emergency response
    
    Args:
        user_id: ID of the user whose tokens should be revoked
        reason: Reason for the revocation (for audit trail)
    """
    try:
        # Verify target user exists
        from sqlalchemy import select
        from app.db.models import User as UserModel
        
        result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        target_user = result.scalar_one_or_none()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # TODO: Implement user-level token revocation
        # This would require storing active JTIs per user or implementing
        # a user token version system
        
        # For now, log the admin action
        log_security_event("admin_user_token_revocation", {
            "admin_user_id": str(current_user.id),
            "admin_email": current_user.email,
            "target_user_id": user_id,
            "target_user_email": target_user.email,
            "reason": reason,
            "action_timestamp": datetime.utcnow().isoformat()
        })
        
        logger.critical(f"ADMIN ACTION: User {current_user.email} revoked tokens for user {target_user.email}. Reason: {reason}")
        
        return success_response({
            "message": f"Token revocation initiated for user {user_id}",
            "reason": reason,
            "revoked_by": current_user.email,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Implementation pending: User-level token revocation system"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin token revocation: {e}")
        log_security_event("admin_token_revocation_error", {
            "admin_user_id": str(current_user.id),
            "target_user_id": user_id,
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke user tokens"
        )


@router.get("/health")
async def security_system_health(
    current_user: User = Depends(require_admin_access)
):
    """
    Comprehensive health check for the security system.
    
    Returns status of all security components:
    - Token blacklist system
    - Security monitoring service
    - Audit logging
    - Performance metrics
    """
    health_status = {
        "overall_status": "healthy",
        "components": {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        # Check Redis blacklist system
        try:
            blacklist_metrics = get_blacklist_metrics()
            health_status["components"]["blacklist_system"] = {
                "status": "healthy",
                "metrics": blacklist_metrics
            }
        except Exception as e:
            health_status["components"]["blacklist_system"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_status"] = "degraded"
        
        # Check security monitoring service
        try:
            security_metrics = token_security_service.get_security_metrics()
            health_status["components"]["monitoring_service"] = {
                "status": "healthy",
                "active_users": security_metrics["suspicious_activity"]["active_users"],
                "total_alerts": security_metrics["alert_summary"]["total_alerts"]
            }
        except Exception as e:
            health_status["components"]["monitoring_service"] = {
                "status": "unhealthy", 
                "error": str(e)
            }
            health_status["overall_status"] = "degraded"
        
        # Check JWT service functionality
        try:
            from app.services.auth_jwt_service import create_access_token, verify_token
            test_token = create_access_token({"sub": "health-check"})
            test_verify = verify_token(test_token)
            
            if test_verify and test_verify.get("sub") == "health-check":
                health_status["components"]["jwt_service"] = {"status": "healthy"}
            else:
                health_status["components"]["jwt_service"] = {"status": "unhealthy", "error": "Token verification failed"}
                health_status["overall_status"] = "degraded"
                
        except Exception as e:
            health_status["components"]["jwt_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_status"] = "unhealthy"
        
        # Log health check
        log_security_event("security_health_check", {
            "admin_user_id": str(current_user.id),
            "overall_status": health_status["overall_status"]
        })
        
        # Return appropriate HTTP status
        if health_status["overall_status"] == "unhealthy":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_status["overall_status"] == "degraded":
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_200_OK
        
        return success_response(health_status)
        
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        health_status["overall_status"] = "unhealthy"
        health_status["error"] = str(e)
        
        return success_response(health_status)


@router.get("/audit/summary")
async def get_audit_summary(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 7 days
    current_user: User = Depends(require_admin_access)
):
    """
    Get audit summary for compliance reporting.
    
    Args:
        hours: Number of hours to include in summary (1-168)
    """
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Get security metrics
        metrics = token_security_service.get_security_metrics()
        
        # Get recent alerts in time range
        alerts = token_security_service.get_recent_alerts(limit=1000)
        time_filtered_alerts = [
            alert for alert in alerts 
            if datetime.fromisoformat(alert["timestamp"]) >= start_time
        ]
        
        # Create audit summary
        audit_summary = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "token_operations": {
                "tokens_issued": metrics["token_metrics"]["total_issued"],
                "tokens_verified": metrics["token_metrics"]["total_verified"],
                "tokens_blacklisted": metrics["token_metrics"]["total_blacklisted"],
                "verification_failures": metrics["token_metrics"]["verification_failures"],
                "blacklist_hits": metrics["token_metrics"]["blacklist_hits"]
            },
            "security_alerts": {
                "total_in_period": len(time_filtered_alerts),
                "critical_alerts": sum(1 for a in time_filtered_alerts if a["severity"] == "CRITICAL"),
                "high_alerts": sum(1 for a in time_filtered_alerts if a["severity"] == "HIGH"),
                "medium_alerts": sum(1 for a in time_filtered_alerts if a["severity"] == "MEDIUM"),
                "low_alerts": sum(1 for a in time_filtered_alerts if a["severity"] == "LOW")
            },
            "system_performance": {
                "redis_operations": metrics.get("redis_metrics", {}),
                "active_monitored_users": metrics["suspicious_activity"]["active_users"],
                "suspicious_ips": metrics["suspicious_activity"]["suspicious_ips"]
            }
        }
        
        log_security_event("audit_summary_generated", {
            "admin_user_id": str(current_user.id),
            "time_range_hours": hours,
            "alerts_in_period": len(time_filtered_alerts)
        })
        
        return success_response({
            "audit_summary": audit_summary,
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": current_user.email
        })
        
    except Exception as e:
        logger.error(f"Error generating audit summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate audit summary"
        )
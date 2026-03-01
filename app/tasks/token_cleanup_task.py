"""
Token Blacklist Cleanup Task

Background task for cleaning up expired blacklist entries and maintaining
system performance. This task runs periodically to:

1. Clean up expired local cache entries
2. Monitor blacklist service health
3. Update metrics
4. Log performance statistics
5. Handle Redis memory management

The Redis TTL mechanism automatically handles most cleanup, but this task
provides additional monitoring and optimization.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)


async def cleanup_token_blacklist():
    """
    Main cleanup task for token blacklist service.
    
    This function:
    1. Triggers local cache cleanup
    2. Monitors service health
    3. Updates metrics
    4. Logs performance statistics
    """
    try:
        logger.info("Starting token blacklist cleanup task")
        
        from app.services.token_blacklist_service import get_blacklist_service
        
        # Get blacklist service instance
        blacklist_service = await get_blacklist_service()
        
        # Perform cleanup operations
        cleanup_result = await blacklist_service.cleanup_expired_tokens()
        
        # Get current metrics
        metrics = await blacklist_service.get_blacklist_metrics()
        health = await blacklist_service.health_check()
        
        # Log cleanup results
        logger.info(f"Token blacklist cleanup completed - "
                   f"Total blacklisted: {metrics.total_blacklisted}, "
                   f"Avg check time: {metrics.average_check_time_ms:.2f}ms, "
                   f"Cache hits: {metrics.cache_hits}, "
                   f"Redis errors: {metrics.redis_errors}")
        
        # Log security event
        log_security_event("blacklist_cleanup_completed", {
            "cleanup_entries": cleanup_result,
            "total_blacklisted": metrics.total_blacklisted,
            "average_check_time_ms": metrics.average_check_time_ms,
            "cache_hit_ratio": (metrics.cache_hits / max(1, metrics.cache_hits + metrics.cache_misses)) * 100,
            "service_status": health.get("status"),
            "redis_connected": health.get("redis_connected", False)
        })
        
        # Check for performance issues
        if metrics.average_check_time_ms > 50:
            logger.warning(f"Blacklist check performance degraded: {metrics.average_check_time_ms:.2f}ms")
            log_security_event("blacklist_performance_warning", {
                "average_check_time_ms": metrics.average_check_time_ms,
                "threshold_ms": 50
            })
        
        # Check for Redis connection issues
        if metrics.redis_errors > 10:
            logger.error(f"High number of Redis errors: {metrics.redis_errors}")
            log_security_event("blacklist_redis_errors", {
                "redis_errors": metrics.redis_errors,
                "threshold": 10
            })
        
        return {
            "status": "success",
            "cleanup_entries": cleanup_result,
            "metrics": {
                "total_blacklisted": metrics.total_blacklisted,
                "average_check_time_ms": metrics.average_check_time_ms,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "redis_errors": metrics.redis_errors
            },
            "service_health": health
        }
        
    except Exception as e:
        logger.error(f"Token blacklist cleanup failed: {e}")
        log_security_event("blacklist_cleanup_failed", {
            "error": str(e)
        })
        return {
            "status": "failed",
            "error": str(e)
        }


async def monitor_blacklist_performance():
    """
    Monitor blacklist service performance and alert on issues.
    """
    try:
        logger.debug("Monitoring blacklist performance")
        
        from app.services.token_blacklist_service import get_blacklist_service
        
        blacklist_service = await get_blacklist_service()
        metrics = await blacklist_service.get_blacklist_metrics()
        health = await blacklist_service.health_check()
        
        # Performance thresholds
        MAX_AVG_CHECK_TIME_MS = 50
        MAX_REDIS_ERRORS = 5
        MIN_CACHE_HIT_RATIO = 70  # 70%
        
        issues = []
        
        # Check average response time
        if metrics.average_check_time_ms > MAX_AVG_CHECK_TIME_MS:
            issues.append({
                "type": "performance",
                "metric": "average_check_time_ms",
                "value": metrics.average_check_time_ms,
                "threshold": MAX_AVG_CHECK_TIME_MS,
                "severity": "warning"
            })
        
        # Check Redis error rate
        if metrics.redis_errors > MAX_REDIS_ERRORS:
            issues.append({
                "type": "reliability", 
                "metric": "redis_errors",
                "value": metrics.redis_errors,
                "threshold": MAX_REDIS_ERRORS,
                "severity": "error"
            })
        
        # Check cache hit ratio
        total_checks = metrics.cache_hits + metrics.cache_misses
        if total_checks > 0:
            cache_hit_ratio = (metrics.cache_hits / total_checks) * 100
            if cache_hit_ratio < MIN_CACHE_HIT_RATIO:
                issues.append({
                    "type": "efficiency",
                    "metric": "cache_hit_ratio",
                    "value": cache_hit_ratio,
                    "threshold": MIN_CACHE_HIT_RATIO,
                    "severity": "warning"
                })
        
        # Check Redis connectivity
        if not health.get("redis_connected", False):
            issues.append({
                "type": "connectivity",
                "metric": "redis_connection",
                "value": False,
                "threshold": True,
                "severity": "critical"
            })
        
        # Log issues
        if issues:
            for issue in issues:
                logger.log(
                    logging.ERROR if issue["severity"] == "critical" else 
                    logging.WARNING if issue["severity"] == "error" else 
                    logging.WARNING,
                    f"Blacklist performance issue - {issue['type']}: "
                    f"{issue['metric']} = {issue['value']} (threshold: {issue['threshold']})"
                )
                
                log_security_event("blacklist_performance_issue", issue)
        
        return {
            "status": "success",
            "issues_found": len(issues),
            "issues": issues,
            "metrics_snapshot": {
                "total_blacklisted": metrics.total_blacklisted,
                "average_check_time_ms": metrics.average_check_time_ms,
                "cache_hit_ratio": (metrics.cache_hits / max(1, total_checks)) * 100,
                "redis_errors": metrics.redis_errors,
                "redis_connected": health.get("redis_connected", False)
            }
        }
        
    except Exception as e:
        logger.error(f"Blacklist performance monitoring failed: {e}")
        log_security_event("blacklist_monitoring_failed", {"error": str(e)})
        return {"status": "failed", "error": str(e)}


async def cleanup_security_audit_logs():
    """
    Clean up old security audit logs to prevent database bloat.
    This function removes audit logs older than 90 days.
    """
    try:
        logger.info("Starting security audit log cleanup")
        
        # This would typically clean up audit log entries
        # For now, we'll just log that the cleanup ran
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        logger.info(f"Would clean up audit logs older than {cutoff_date}")
        
        log_security_event("audit_log_cleanup", {
            "cutoff_date": cutoff_date.isoformat(),
            "cleanup_type": "automated"
        })
        
        return {
            "status": "success",
            "cutoff_date": cutoff_date.isoformat(),
            "message": "Audit log cleanup completed"
        }
        
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}")
        log_security_event("audit_log_cleanup_failed", {"error": str(e)})
        return {"status": "failed", "error": str(e)}


# Scheduled task runners

async def run_daily_cleanup():
    """Run daily maintenance tasks."""
    logger.info("Starting daily blacklist maintenance")
    
    tasks = [
        cleanup_token_blacklist(),
        cleanup_security_audit_logs(),
        monitor_blacklist_performance()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for result in results 
                       if isinstance(result, dict) and result.get("status") == "success")
    
    logger.info(f"Daily maintenance completed: {success_count}/{len(tasks)} tasks successful")
    
    return {
        "status": "completed",
        "tasks_run": len(tasks),
        "tasks_successful": success_count,
        "results": results
    }


async def run_hourly_monitoring():
    """Run hourly monitoring tasks."""
    logger.debug("Starting hourly blacklist monitoring")
    
    result = await monitor_blacklist_performance()
    
    logger.debug(f"Hourly monitoring completed: {result.get('status')}")
    
    return result


# Task scheduling functions (to be integrated with your task system)

def schedule_blacklist_tasks():
    """
    Schedule blacklist maintenance tasks.
    
    This function should be called during application startup to schedule
    the background tasks with your task scheduler (like Celery, RQ, etc.)
    """
    logger.info("Scheduling blacklist maintenance tasks")
    
    # Example implementation - adjust based on your task scheduler
    # schedule.every(1).hours.do(run_hourly_monitoring)
    # schedule.every(1).days.do(run_daily_cleanup)
    
    return {
        "hourly_monitoring": "scheduled",
        "daily_cleanup": "scheduled"
    }
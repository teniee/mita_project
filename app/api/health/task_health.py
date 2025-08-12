"""
Task system health checks for MITA financial platform.
Provides comprehensive health monitoring for the async task queue system.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter

from app.services.task_manager import task_manager
from app.core.task_queue import task_queue
from app.core.logger import get_logger
from app.utils.response_wrapper import success_response

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/tasks")
async def task_system_health():
    """
    Comprehensive task system health check.
    
    Returns:
        Dict containing detailed task system health information
    """
    try:
        start_time = time.time()
        
        # Get queue statistics
        queue_stats = task_queue.get_queue_stats()
        
        # Calculate health metrics
        health_metrics = _calculate_health_metrics(queue_stats)
        
        # Test Redis connectivity
        redis_health = _test_redis_connectivity()
        
        # Test worker connectivity
        worker_health = _test_worker_health(queue_stats)
        
        # Overall system health
        overall_health = _determine_overall_health(health_metrics, redis_health, worker_health)
        
        response_time = time.time() - start_time
        
        health_report = {
            "status": overall_health["status"],
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time * 1000, 2),
            "components": {
                "redis": redis_health,
                "workers": worker_health,
                "queues": health_metrics["queue_health"],
                "system_load": health_metrics["system_load"]
            },
            "statistics": queue_stats,
            "alerts": overall_health["alerts"],
            "recommendations": overall_health["recommendations"]
        }
        
        # Log health check
        logger.info(
            f"Task system health check: {overall_health['status']}",
            extra={
                "health_status": overall_health["status"],
                "response_time": response_time,
                "alert_count": len(overall_health["alerts"])
            }
        )
        
        return success_response(health_report)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        
        return success_response({
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "components": {
                "redis": {"status": "unknown"},
                "workers": {"status": "unknown"},
                "queues": {"status": "unknown"}
            }
        })


@router.get("/tasks/detailed")
async def detailed_task_health(
    _: None = Depends(RateLimiter(times=5, seconds=60))
):
    """
    Detailed task system health check with extended metrics.
    Rate limited to prevent abuse.
    
    Returns:
        Dict containing comprehensive task system diagnostics
    """
    try:
        start_time = time.time()
        
        # Basic health check
        basic_health = await task_system_health()
        
        # Additional detailed metrics
        detailed_metrics = {
            "queue_depth_history": _get_queue_depth_history(),
            "error_rate_analysis": _analyze_error_rates(),
            "performance_metrics": _get_performance_metrics(),
            "capacity_analysis": _analyze_system_capacity(),
            "maintenance_status": _get_maintenance_status()
        }
        
        response_time = time.time() - start_time
        
        # Combine basic health with detailed metrics
        detailed_report = basic_health["data"]
        detailed_report["detailed_metrics"] = detailed_metrics
        detailed_report["detailed_response_time_ms"] = round(response_time * 1000, 2)
        
        return success_response(detailed_report)
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get("/tasks/readiness")
async def task_system_readiness():
    """
    Task system readiness check for load balancer health checks.
    Fast, lightweight check for system readiness.
    
    Returns:
        Simple ready/not ready status
    """
    try:
        # Quick checks for system readiness
        redis_ready = task_queue.redis_conn.ping()
        workers_available = len([
            w for w in task_queue.redis_conn.smembers('rq:workers')
        ]) > 0
        
        if redis_ready and workers_available:
            return success_response({
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            return success_response({
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "redis_ready": redis_ready,
                "workers_available": workers_available
            })
            
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return success_response({
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        })


@router.get("/tasks/liveness")
async def task_system_liveness():
    """
    Task system liveness check for container orchestration.
    Indicates if the system is alive and should continue running.
    
    Returns:
        Simple alive/dead status
    """
    try:
        # Basic liveness indicators
        can_connect_redis = task_queue.redis_conn.ping()
        
        if can_connect_redis:
            return success_response({
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            # System is not alive - container should be restarted
            raise HTTPException(
                status_code=503,
                detail="Task system is not alive - Redis connection failed"
            )
            
    except Exception as e:
        logger.error(f"Liveness check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Task system liveness check failed: {str(e)}"
        )


def _calculate_health_metrics(queue_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate health metrics from queue statistics."""
    metrics = {
        "queue_health": {},
        "system_load": {}
    }
    
    total_queued = 0
    total_failed = 0
    total_processing = 0
    
    for queue_name, stats in queue_stats.items():
        if isinstance(stats, dict):
            queued = stats.get('length', 0)
            failed = stats.get('failed_job_count', 0)
            started = stats.get('started_job_count', 0)
            
            total_queued += queued
            total_failed += failed
            total_processing += started
            
            # Determine queue health
            queue_health = "healthy"
            if queued > 100:
                queue_health = "overloaded"
            elif queued > 50:
                queue_health = "busy"
            elif failed > 10:
                queue_health = "errors"
            
            metrics["queue_health"][queue_name] = {
                "status": queue_health,
                "queued": queued,
                "failed": failed,
                "processing": started
            }
    
    # Overall system load
    if total_queued > 200:
        system_load_status = "high"
    elif total_queued > 100:
        system_load_status = "medium"
    else:
        system_load_status = "low"
    
    metrics["system_load"] = {
        "status": system_load_status,
        "total_queued": total_queued,
        "total_failed": total_failed,
        "total_processing": total_processing
    }
    
    return metrics


def _test_redis_connectivity() -> Dict[str, Any]:
    """Test Redis connectivity and performance."""
    try:
        start_time = time.time()
        
        # Test basic connectivity
        ping_result = task_queue.redis_conn.ping()
        ping_time = time.time() - start_time
        
        # Test read/write operations
        test_key = f"health_check:{int(time.time())}"
        task_queue.redis_conn.set(test_key, "test_value", ex=10)
        read_value = task_queue.redis_conn.get(test_key)
        task_queue.redis_conn.delete(test_key)
        
        total_time = time.time() - start_time
        
        return {
            "status": "healthy" if ping_result and read_value == b"test_value" else "unhealthy",
            "ping_response_ms": round(ping_time * 1000, 2),
            "total_response_ms": round(total_time * 1000, 2),
            "read_write_test": "passed" if read_value == b"test_value" else "failed"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "ping_response_ms": None,
            "total_response_ms": None,
            "read_write_test": "failed"
        }


def _test_worker_health(queue_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Test worker health and availability."""
    try:
        workers_info = queue_stats.get('workers', {})
        total_workers = workers_info.get('total', 0)
        active_workers = workers_info.get('active', 0)
        idle_workers = workers_info.get('idle', 0)
        
        if total_workers == 0:
            status = "no_workers"
        elif active_workers / total_workers > 0.9:
            status = "overloaded"
        elif active_workers / total_workers > 0.7:
            status = "busy"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_workers": total_workers,
            "active_workers": active_workers,
            "idle_workers": idle_workers,
            "utilization_percentage": round((active_workers / max(total_workers, 1)) * 100, 1)
        }
        
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e),
            "total_workers": 0,
            "active_workers": 0,
            "idle_workers": 0
        }


def _determine_overall_health(
    health_metrics: Dict[str, Any],
    redis_health: Dict[str, Any],
    worker_health: Dict[str, Any]
) -> Dict[str, Any]:
    """Determine overall system health and generate alerts."""
    
    alerts = []
    recommendations = []
    
    # Check Redis health
    if redis_health["status"] != "healthy":
        alerts.append({
            "severity": "critical",
            "component": "redis",
            "message": "Redis connectivity issues detected",
            "details": redis_health
        })
        recommendations.append("Check Redis server status and network connectivity")
    
    # Check worker health
    if worker_health["status"] == "no_workers":
        alerts.append({
            "severity": "critical",
            "component": "workers",
            "message": "No workers available",
            "details": worker_health
        })
        recommendations.append("Start worker processes to handle task queue")
    elif worker_health["status"] == "overloaded":
        alerts.append({
            "severity": "warning",
            "component": "workers",
            "message": "Workers are overloaded",
            "details": worker_health
        })
        recommendations.append("Consider scaling up worker processes")
    
    # Check queue health
    system_load = health_metrics["system_load"]
    if system_load["status"] == "high":
        alerts.append({
            "severity": "warning",
            "component": "queues",
            "message": "High queue load detected",
            "details": system_load
        })
        recommendations.append("Monitor queue processing and consider adding more workers")
    
    # Check for high failure rates
    if system_load["total_failed"] > 20:
        alerts.append({
            "severity": "warning",
            "component": "tasks",
            "message": "High task failure rate",
            "details": {"failed_tasks": system_load["total_failed"]}
        })
        recommendations.append("Investigate task failures and improve error handling")
    
    # Determine overall status
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]
    warning_alerts = [a for a in alerts if a["severity"] == "warning"]
    
    if critical_alerts:
        overall_status = "critical"
    elif warning_alerts:
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return {
        "status": overall_status,
        "alerts": alerts,
        "recommendations": recommendations
    }


def _get_queue_depth_history() -> Dict[str, Any]:
    """Get historical queue depth information (simplified)."""
    # In production, you'd store this in Redis or a time-series database
    return {
        "note": "Queue depth history would be tracked in production time-series DB",
        "current_snapshot": task_queue.get_queue_stats()
    }


def _analyze_error_rates() -> Dict[str, Any]:
    """Analyze task error rates (simplified)."""
    # In production, you'd analyze error patterns from logs or metrics
    queue_stats = task_queue.get_queue_stats()
    total_failed = sum(
        stats.get('failed_job_count', 0)
        for stats in queue_stats.values()
        if isinstance(stats, dict)
    )
    
    return {
        "total_failed_tasks": total_failed,
        "error_analysis": "Detailed error analysis would require metrics collection",
        "common_errors": "Would be extracted from task logs in production"
    }


def _get_performance_metrics() -> Dict[str, Any]:
    """Get task performance metrics (simplified)."""
    return {
        "note": "Performance metrics would be collected from task execution logs",
        "average_task_duration": "Not implemented - would require execution tracking",
        "throughput": "Not implemented - would require time-series data"
    }


def _analyze_system_capacity() -> Dict[str, Any]:
    """Analyze system capacity and scaling needs."""
    queue_stats = task_queue.get_queue_stats()
    workers = queue_stats.get('workers', {})
    
    return {
        "current_capacity": workers,
        "scaling_recommendation": "Monitor queue depth and worker utilization",
        "bottlenecks": "Analyze based on queue lengths and worker utilization"
    }


def _get_maintenance_status() -> Dict[str, Any]:
    """Get system maintenance status."""
    return {
        "last_cleanup": "Not tracked - would require maintenance job logging",
        "next_maintenance": "Scheduled maintenance not implemented",
        "maintenance_needed": False
    }
"""
Production Health Checks for MITA Finance
Comprehensive health monitoring for financial-grade applications
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Depends
import psutil
import aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.async_session import get_async_session
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ProductionHealthChecker:
    """Comprehensive health checker for production environment"""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.health_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
    
    async def check_database_health(self, session: AsyncSession) -> Dict[str, Any]:
        """Check PostgreSQL database health"""
        try:
            start_time = time.time()
            
            # Basic connectivity test
            result = await session.execute(text("SELECT 1 as health_check"))
            health_result = result.scalar()
            
            if health_result != 1:
                return {
                    "status": "unhealthy",
                    "message": "Database query returned unexpected result",
                    "response_time": None
                }
            
            # Check database version and basic stats
            version_result = await session.execute(text("SELECT version()"))
            version = version_result.scalar()
            
            # Check connection count
            connections_result = await session.execute(text("""
                SELECT count(*) as active_connections 
                FROM pg_stat_activity 
                WHERE state = 'active'
            """))
            active_connections = connections_result.scalar()
            
            # Check for long-running transactions
            long_transactions_result = await session.execute(text("""
                SELECT count(*) as long_transactions
                FROM pg_stat_activity 
                WHERE state = 'active' 
                AND query_start < NOW() - INTERVAL '5 minutes'
            """))
            long_transactions = long_transactions_result.scalar()
            
            # Check database size
            db_size_result = await session.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
            """))
            db_size = db_size_result.scalar()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Determine health status
            status = "healthy"
            issues = []
            
            if response_time > 1000:  # More than 1 second
                status = "degraded"
                issues.append("High database response time")
            
            if active_connections > 80:  # Assuming max 100 connections
                status = "degraded"
                issues.append("High number of active connections")
            
            if long_transactions > 0:
                status = "degraded"
                issues.append("Long-running transactions detected")
            
            return {
                "status": status,
                "response_time_ms": round(response_time, 2),
                "version": version.split()[1] if version else "unknown",
                "active_connections": active_connections,
                "long_transactions": long_transactions,
                "database_size": db_size,
                "issues": issues,
                "message": "Database is healthy" if status == "healthy" else f"Database issues: {', '.join(issues)}"
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}",
                "response_time_ms": None,
                "error": str(e)
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache health"""
        try:
            start_time = time.time()
            
            # Connect to Redis
            redis = aioredis.from_url(settings.REDIS_URL)
            
            # Test basic operations
            test_key = "health_check_test"
            test_value = f"test_value_{int(time.time())}"
            
            # Set a test value
            await redis.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            
            # Get the test value back
            retrieved_value = await redis.get(test_key)
            
            # Clean up test value
            await redis.delete(test_key)
            
            if retrieved_value.decode() != test_value:
                return {
                    "status": "unhealthy",
                    "message": "Redis set/get operation failed",
                    "response_time_ms": None
                }
            
            # Get Redis info
            info = await redis.info()
            used_memory = info.get('used_memory_human', 'unknown')
            connected_clients = info.get('connected_clients', 'unknown')
            redis_version = info.get('redis_version', 'unknown')
            
            await redis.close()
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            status = "healthy"
            issues = []
            
            if response_time > 500:  # More than 500ms
                status = "degraded"
                issues.append("High Redis response time")
            
            if isinstance(connected_clients, int) and connected_clients > 50:
                status = "degraded"
                issues.append("High number of Redis connections")
            
            return {
                "status": status,
                "response_time_ms": round(response_time, 2),
                "version": redis_version,
                "used_memory": used_memory,
                "connected_clients": connected_clients,
                "issues": issues,
                "message": "Redis is healthy" if status == "healthy" else f"Redis issues: {', '.join(issues)}"
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}",
                "response_time_ms": None,
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free_gb = disk.free / (1024**3)
            
            # Load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()
                load_1min = load_avg[0]
            except AttributeError:
                load_1min = None  # Windows doesn't have load average
            
            # Determine health status
            status = "healthy"
            issues = []
            
            if cpu_percent > 80:
                status = "degraded" if status == "healthy" else status
                issues.append(f"High CPU usage: {cpu_percent}%")
            
            if memory_percent > 85:
                status = "degraded" if status == "healthy" else status
                issues.append(f"High memory usage: {memory_percent}%")
            
            if memory_available_gb < 0.5:  # Less than 500MB available
                status = "critical"
                issues.append("Very low available memory")
            
            if disk_percent > 90:
                status = "critical"
                issues.append(f"High disk usage: {disk_percent}%")
            
            if disk_free_gb < 1:  # Less than 1GB free
                status = "critical"
                issues.append("Very low disk space")
            
            if load_1min and load_1min > psutil.cpu_count() * 2:
                status = "degraded" if status == "healthy" else status
                issues.append(f"High system load: {load_1min}")
            
            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_gb": round(memory_available_gb, 2),
                "disk_percent": disk_percent,
                "disk_free_gb": round(disk_free_gb, 2),
                "load_1min": load_1min,
                "issues": issues,
                "message": "System resources healthy" if status == "healthy" else f"Resource issues: {', '.join(issues)}"
            }
            
        except Exception as e:
            logger.error(f"System resource check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"System resource check failed: {str(e)}",
                "error": str(e)
            }
    
    def check_application_health(self) -> Dict[str, Any]:
        """Check application-specific health metrics"""
        try:
            current_time = datetime.utcnow()
            uptime = current_time - self.start_time
            uptime_seconds = int(uptime.total_seconds())
            
            # Calculate uptime string
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
            
            return {
                "status": "healthy",
                "uptime_seconds": uptime_seconds,
                "uptime_human": uptime_str,
                "started_at": self.start_time.isoformat(),
                "current_time": current_time.isoformat(),
                "environment": settings.ENVIRONMENT,
                "debug_mode": settings.DEBUG,
                "log_level": settings.LOG_LEVEL,
                "message": "Application is running normally"
            }
            
        except Exception as e:
            logger.error(f"Application health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Application health check failed: {str(e)}",
                "error": str(e)
            }
    
    async def run_comprehensive_health_check(self, session: AsyncSession) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status"""
        try:
            # Run all health checks concurrently
            db_health_task = self.check_database_health(session)
            redis_health_task = self.check_redis_health()
            
            # System and application checks are synchronous
            system_health = self.check_system_resources()
            app_health = self.check_application_health()
            
            # Wait for async tasks
            db_health, redis_health = await asyncio.gather(
                db_health_task, redis_health_task, return_exceptions=True
            )
            
            # Handle exceptions in async tasks
            if isinstance(db_health, Exception):
                db_health = {
                    "status": "unhealthy",
                    "message": f"Database health check exception: {str(db_health)}",
                    "error": str(db_health)
                }
            
            if isinstance(redis_health, Exception):
                redis_health = {
                    "status": "unhealthy", 
                    "message": f"Redis health check exception: {str(redis_health)}",
                    "error": str(redis_health)
                }
            
            # Aggregate health status
            all_checks = {
                "database": db_health,
                "redis": redis_health,
                "system": system_health,
                "application": app_health
            }
            
            # Determine overall health
            statuses = [check["status"] for check in all_checks.values()]
            
            if "unhealthy" in statuses:
                overall_status = "unhealthy"
            elif "critical" in statuses:
                overall_status = "critical"
            elif "degraded" in statuses:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
            
            # Count healthy vs unhealthy services
            healthy_count = sum(1 for status in statuses if status == "healthy")
            total_count = len(statuses)
            
            health_report = {
                "overall_status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "services": all_checks,
                "summary": {
                    "healthy_services": healthy_count,
                    "total_services": total_count,
                    "health_percentage": round((healthy_count / total_count) * 100, 1),
                    "critical_issues": [
                        f"{service}: {data['message']}" 
                        for service, data in all_checks.items() 
                        if data["status"] in ["unhealthy", "critical"]
                    ]
                },
                "message": self._get_overall_health_message(overall_status, healthy_count, total_count)
            }
            
            # Store in history
            self._store_health_history(health_report)
            
            return health_report
            
        except Exception as e:
            logger.error(f"Comprehensive health check failed: {str(e)}")
            return {
                "overall_status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Health check system failure: {str(e)}",
                "error": str(e)
            }
    
    def _get_overall_health_message(self, status: str, healthy_count: int, total_count: int) -> str:
        """Get human-readable overall health message"""
        if status == "healthy":
            return f"All {total_count} services are healthy and operational"
        elif status == "degraded":
            return f"{healthy_count}/{total_count} services are healthy, some performance issues detected"
        elif status == "critical":
            return f"{healthy_count}/{total_count} services are healthy, critical issues require immediate attention"
        else:
            return f"System is unhealthy, {total_count - healthy_count} services are down"
    
    def _store_health_history(self, health_report: Dict[str, Any]):
        """Store health check result in history"""
        self.health_history.append({
            "timestamp": health_report["timestamp"],
            "overall_status": health_report["overall_status"],
            "healthy_services": health_report["summary"]["healthy_services"],
            "total_services": health_report["summary"]["total_services"]
        })
        
        # Keep only recent history
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size:]


# Global health checker instance
health_checker = ProductionHealthChecker()


@router.get("/health/production", response_model=Dict[str, Any])
async def production_health_check(session: AsyncSession = Depends(get_async_session)):
    """Comprehensive production health check endpoint"""
    try:
        health_report = await health_checker.run_comprehensive_health_check(session)
        
        # Return appropriate HTTP status based on health
        if health_report["overall_status"] == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_report
            )
        elif health_report["overall_status"] in ["critical", "degraded"]:
            # Return 200 but with degraded status information
            pass
        
        return health_report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Production health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "overall_status": "unhealthy",
                "message": "Health check system failure",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/health/history", response_model=Dict[str, Any])
async def get_health_history():
    """Get recent health check history"""
    return {
        "history": health_checker.health_history,
        "total_checks": len(health_checker.health_history),
        "oldest_check": health_checker.health_history[0]["timestamp"] if health_checker.health_history else None,
        "newest_check": health_checker.health_history[-1]["timestamp"] if health_checker.health_history else None
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def prometheus_metrics(session: AsyncSession = Depends(get_async_session)):
    """Metrics endpoint for Prometheus scraping"""
    try:
        health_report = await health_checker.run_comprehensive_health_check(session)
        
        # Convert to Prometheus format
        metrics = []
        
        # Overall health (1 = healthy, 0.5 = degraded, 0 = unhealthy)
        health_value = {
            "healthy": 1.0,
            "degraded": 0.5,
            "critical": 0.25,
            "unhealthy": 0.0
        }.get(health_report["overall_status"], 0.0)
        
        metrics.append(f"mita_health_status {health_value}")
        
        # Service-specific metrics
        for service_name, service_data in health_report.get("services", {}).items():
            service_value = 1.0 if service_data["status"] == "healthy" else 0.0
            metrics.append(f'mita_service_health{{service="{service_name}"}} {service_value}')
            
            # Response time metrics
            if "response_time_ms" in service_data and service_data["response_time_ms"] is not None:
                metrics.append(f'mita_service_response_time_ms{{service="{service_name}"}} {service_data["response_time_ms"]}')
        
        # System metrics
        system_data = health_report.get("services", {}).get("system", {})
        if "cpu_percent" in system_data:
            metrics.append(f"mita_cpu_usage_percent {system_data['cpu_percent']}")
        if "memory_percent" in system_data:
            metrics.append(f"mita_memory_usage_percent {system_data['memory_percent']}")
        if "disk_percent" in system_data:
            metrics.append(f"mita_disk_usage_percent {system_data['disk_percent']}")
        
        # Application uptime
        app_data = health_report.get("services", {}).get("application", {})
        if "uptime_seconds" in app_data:
            metrics.append(f"mita_uptime_seconds {app_data['uptime_seconds']}")
        
        return {
            "metrics": "\n".join(metrics),
            "timestamp": datetime.utcnow().isoformat(),
            "format": "prometheus"
        }
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {str(e)}")
        return {
            "metrics": "mita_health_status 0\nmita_metrics_error 1",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
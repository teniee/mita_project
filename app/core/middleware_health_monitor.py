"""
Advanced Middleware Health Monitoring System
Comprehensive health checks for all middleware components to detect issues before they affect users
"""

import time
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import redis
import psutil
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.rate_limiter import rate_limiter, RateLimitRule
from app.core.jwt_security import validate_jwt_security_config
from app.core.audit_logging import SecurityAuditLogger

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthMetric:
    """Individual health metric"""
    name: str
    status: HealthStatus
    value: Optional[float] = None
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MiddlewareHealthReport:
    """Comprehensive middleware health report"""
    overall_status: HealthStatus
    timestamp: datetime
    metrics: Dict[str, HealthMetric]
    performance_summary: Dict[str, Any]
    alerts: List[str]
    response_time_ms: float
    issues_detected: List[str]
    recommendations: List[str]


class MiddlewareHealthMonitor:
    """
    Comprehensive middleware health monitoring system
    Designed to detect issues that could cause 8-15+ second timeouts
    """
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.health_history: List[MiddlewareHealthReport] = []
        self.max_history_size = 1000
        self.performance_thresholds = {
            'response_time_warning': 2000,  # 2 seconds
            'response_time_critical': 5000, # 5 seconds
            'database_connection_warning': 1000,  # 1 second
            'database_connection_critical': 3000, # 3 seconds
            'redis_response_warning': 500,        # 500ms
            'redis_response_critical': 2000,      # 2 seconds
            'memory_usage_warning': 80,           # 80%
            'memory_usage_critical': 90,          # 90%
            'cpu_usage_warning': 80,              # 80%
            'cpu_usage_critical': 90,             # 90%
        }
        self.thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="health_check")
        self._lock = threading.Lock()

    async def check_rate_limiter_health(self) -> HealthMetric:
        """Check rate limiter middleware health"""
        start_time = time.time()
        
        try:
            # Test rate limiter functionality
            test_rule = RateLimitRule('health_check', 1000, 3600, per='ip')
            
            # Check Redis connectivity if using Redis
            redis_status = "healthy"
            redis_details = {}
            
            if rate_limiter.redis_client:
                try:
                    # Test Redis connectivity
                    ping_start = time.time()
                    rate_limiter.redis_client.ping()
                    redis_response_time = (time.time() - ping_start) * 1000
                    
                    # Get Redis info
                    info = rate_limiter.redis_client.info()
                    redis_details = {
                        'connected_clients': info.get('connected_clients', 0),
                        'used_memory_human': info.get('used_memory_human', 'unknown'),
                        'total_commands_processed': info.get('total_commands_processed', 0),
                        'response_time_ms': redis_response_time
                    }
                    
                    if redis_response_time > self.performance_thresholds['redis_response_critical']:
                        redis_status = "critical"
                    elif redis_response_time > self.performance_thresholds['redis_response_warning']:
                        redis_status = "degraded"
                        
                except Exception as e:
                    redis_status = "unhealthy"
                    redis_details = {'error': str(e)}
            else:
                redis_details = {'mode': 'memory_only', 'redis_client': 'not_configured'}
            
            # Test rate limiter logic
            mock_request = type('MockRequest', (), {
                'client': type('Client', (), {'host': '127.0.0.1'})(),
                'headers': {},
                'state': type('State', (), {})()
            })()
            
            allowed, limit_info = await rate_limiter.check_rate_limit(
                'health_test', test_rule, mock_request
            )
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine overall health
            if redis_status == "unhealthy":
                status = HealthStatus.CRITICAL
                message = f"Rate limiter Redis connection failed: {redis_details.get('error', 'Unknown error')}"
            elif redis_status == "critical":
                status = HealthStatus.CRITICAL
                message = f"Rate limiter Redis response time too high: {redis_details.get('response_time_ms', 0):.1f}ms"
            elif redis_status == "degraded":
                status = HealthStatus.DEGRADED
                message = f"Rate limiter Redis performance degraded: {redis_details.get('response_time_ms', 0):.1f}ms"
            elif response_time > self.performance_thresholds['response_time_critical']:
                status = HealthStatus.CRITICAL
                message = f"Rate limiter response time critical: {response_time:.1f}ms"
            elif response_time > self.performance_thresholds['response_time_warning']:
                status = HealthStatus.DEGRADED
                message = f"Rate limiter response time elevated: {response_time:.1f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = "Rate limiter functioning normally"
            
            return HealthMetric(
                name="rate_limiter",
                status=status,
                value=response_time,
                threshold_warning=self.performance_thresholds['response_time_warning'],
                threshold_critical=self.performance_thresholds['response_time_critical'],
                message=message,
                response_time_ms=response_time,
                details={
                    'redis_status': redis_status,
                    'redis_details': redis_details,
                    'limit_check_successful': allowed is not None,
                    'test_limit_info': limit_info
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Rate limiter health check failed: {str(e)}")
            return HealthMetric(
                name="rate_limiter",
                status=HealthStatus.UNHEALTHY,
                message=f"Rate limiter health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    async def check_jwt_service_health(self) -> HealthMetric:
        """Check JWT service and authentication middleware health"""
        start_time = time.time()
        
        try:
            # Validate JWT configuration
            jwt_config = validate_jwt_security_config()
            
            if not jwt_config['valid']:
                return HealthMetric(
                    name="jwt_service",
                    status=HealthStatus.UNHEALTHY,
                    message=f"JWT configuration invalid: {', '.join(jwt_config['issues'])}",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details=jwt_config
                )
            
            # Test JWT token creation and validation
            from app.core.jwt_security import create_secure_token_pair, validate_jwt_token
            
            test_user_data = {
                'user_id': 'health_check_user',
                'sub': 'health_check_user',
                'is_premium': False,
                'country': 'US'
            }
            
            # Create tokens
            token_creation_start = time.time()
            tokens = create_secure_token_pair(test_user_data)
            token_creation_time = (time.time() - token_creation_start) * 1000
            
            # Validate tokens
            token_validation_start = time.time()
            access_payload = validate_jwt_token(tokens['access_token'], 'access_token')
            refresh_payload = validate_jwt_token(tokens['refresh_token'], 'refresh_token')
            token_validation_time = (time.time() - token_validation_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Check if token operations succeeded
            if not access_payload or not refresh_payload:
                return HealthMetric(
                    name="jwt_service",
                    status=HealthStatus.UNHEALTHY,
                    message="JWT token creation/validation failed",
                    response_time_ms=response_time,
                    details={
                        'access_token_valid': access_payload is not None,
                        'refresh_token_valid': refresh_payload is not None,
                        'token_creation_time_ms': token_creation_time,
                        'token_validation_time_ms': token_validation_time
                    }
                )
            
            # Determine health status based on performance
            total_jwt_time = token_creation_time + token_validation_time
            
            if total_jwt_time > 1000:  # More than 1 second for JWT operations
                status = HealthStatus.CRITICAL
                message = f"JWT operations too slow: {total_jwt_time:.1f}ms"
            elif total_jwt_time > 500:  # More than 500ms
                status = HealthStatus.DEGRADED
                message = f"JWT operations slow: {total_jwt_time:.1f}ms"
            elif jwt_config['warnings']:
                status = HealthStatus.DEGRADED
                message = f"JWT configuration warnings: {', '.join(jwt_config['warnings'])}"
            else:
                status = HealthStatus.HEALTHY
                message = "JWT service functioning normally"
            
            return HealthMetric(
                name="jwt_service",
                status=status,
                value=total_jwt_time,
                threshold_warning=500,
                threshold_critical=1000,
                message=message,
                response_time_ms=response_time,
                details={
                    'jwt_config': jwt_config,
                    'token_creation_time_ms': token_creation_time,
                    'token_validation_time_ms': token_validation_time,
                    'total_jwt_time_ms': total_jwt_time,
                    'access_token_claims': len(access_payload) if access_payload else 0,
                    'refresh_token_claims': len(refresh_payload) if refresh_payload else 0
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"JWT service health check failed: {str(e)}")
            return HealthMetric(
                name="jwt_service",
                status=HealthStatus.UNHEALTHY,
                message=f"JWT service health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    async def check_database_session_health(self, session: AsyncSession) -> HealthMetric:
        """Check database session manager and connection pool health"""
        start_time = time.time()
        
        try:
            # Test basic connectivity
            connectivity_start = time.time()
            result = await session.execute(text("SELECT 1 as health_check"))
            health_result = result.scalar()
            connectivity_time = (time.time() - connectivity_start) * 1000
            
            if health_result != 1:
                return HealthMetric(
                    name="database_session",
                    status=HealthStatus.UNHEALTHY,
                    message="Database connectivity test failed",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={'connectivity_result': health_result}
                )
            
            # Test connection pool status
            pool_stats_start = time.time()
            pool_stats = await session.execute(text("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections,
                    count(*) FILTER (WHERE query_start < NOW() - INTERVAL '30 seconds') as long_queries,
                    count(*) FILTER (WHERE query_start < NOW() - INTERVAL '5 minutes') as very_long_queries
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """))
            pool_data = pool_stats.first()
            pool_stats_time = (time.time() - pool_stats_start) * 1000
            
            # Test database performance
            performance_start = time.time()
            perf_result = await session.execute(text("""
                SELECT 
                    pg_database_size(current_database()) as db_size,
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '10 seconds') as slow_queries,
                    (SELECT count(*) FROM pg_locks WHERE granted = false) as blocked_queries
            """))
            perf_data = perf_result.first()
            performance_time = (time.time() - performance_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Analyze results
            total_connections = pool_data.total_connections or 0
            active_connections = pool_data.active_connections or 0
            long_queries = pool_data.long_queries or 0
            very_long_queries = pool_data.very_long_queries or 0
            slow_queries = perf_data.slow_queries or 0
            blocked_queries = perf_data.blocked_queries or 0
            
            # Determine health status
            issues = []
            
            if connectivity_time > self.performance_thresholds['database_connection_critical']:
                issues.append(f"Critical database connectivity time: {connectivity_time:.1f}ms")
            elif connectivity_time > self.performance_thresholds['database_connection_warning']:
                issues.append(f"Slow database connectivity: {connectivity_time:.1f}ms")
            
            if very_long_queries > 0:
                issues.append(f"{very_long_queries} queries running >5 minutes")
            elif long_queries > 5:
                issues.append(f"{long_queries} queries running >30 seconds")
            
            if blocked_queries > 0:
                issues.append(f"{blocked_queries} blocked queries")
            
            if active_connections > 80:  # Assuming 100 max connections
                issues.append(f"High connection count: {active_connections}")
            
            if slow_queries > 10:
                issues.append(f"{slow_queries} slow queries detected")
            
            # Determine overall status
            if any("Critical" in issue for issue in issues) or very_long_queries > 0 or blocked_queries > 5:
                status = HealthStatus.CRITICAL
            elif issues:
                status = HealthStatus.DEGRADED
            elif connectivity_time > 500 or pool_stats_time > 200:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            message = "Database session healthy" if status == HealthStatus.HEALTHY else f"Database issues: {', '.join(issues)}"
            
            return HealthMetric(
                name="database_session",
                status=status,
                value=connectivity_time,
                threshold_warning=self.performance_thresholds['database_connection_warning'],
                threshold_critical=self.performance_thresholds['database_connection_critical'],
                message=message,
                response_time_ms=response_time,
                details={
                    'connectivity_time_ms': connectivity_time,
                    'pool_stats_time_ms': pool_stats_time,
                    'performance_time_ms': performance_time,
                    'total_connections': total_connections,
                    'active_connections': active_connections,
                    'idle_connections': pool_data.idle_connections or 0,
                    'long_queries': long_queries,
                    'very_long_queries': very_long_queries,
                    'slow_queries': slow_queries,
                    'blocked_queries': blocked_queries,
                    'database_size_bytes': perf_data.db_size or 0,
                    'issues': issues
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database session health check failed: {str(e)}")
            return HealthMetric(
                name="database_session",
                status=HealthStatus.UNHEALTHY,
                message=f"Database session health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    async def check_audit_logging_health(self) -> HealthMetric:
        """Check audit logging middleware health"""
        start_time = time.time()
        
        try:
            # Test audit logger functionality
            test_logger = SecurityAuditLogger()
            
            # Test log writing
            log_start = time.time()
            await test_logger.log_security_event(
                event_type="health_check",
                user_id="system",
                details={"test": True, "timestamp": datetime.utcnow().isoformat()},
                severity="info"
            )
            log_time = (time.time() - log_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Check log file accessibility and recent activity
            log_file_status = "healthy"
            log_details = {}
            
            try:
                # Check if we can access audit logs
                import os
                audit_log_dir = "logs/audit"
                if os.path.exists(audit_log_dir):
                    log_files = os.listdir(audit_log_dir)
                    recent_logs = [f for f in log_files if f.endswith('.jsonl')]
                    log_details['log_files_count'] = len(recent_logs)
                    log_details['recent_log_files'] = recent_logs[:5]  # Show up to 5 recent files
                else:
                    log_file_status = "degraded"
                    log_details['warning'] = "Audit log directory not found"
            except Exception as e:
                log_file_status = "degraded"
                log_details['file_check_error'] = str(e)
            
            # Determine health status
            if log_time > 1000:  # More than 1 second to write a log entry
                status = HealthStatus.CRITICAL
                message = f"Audit logging too slow: {log_time:.1f}ms"
            elif log_time > 500:
                status = HealthStatus.DEGRADED
                message = f"Audit logging slow: {log_time:.1f}ms"
            elif log_file_status == "degraded":
                status = HealthStatus.DEGRADED
                message = f"Audit logging degraded: {log_details.get('warning', 'File system issues')}"
            else:
                status = HealthStatus.HEALTHY
                message = "Audit logging functioning normally"
            
            return HealthMetric(
                name="audit_logging",
                status=status,
                value=log_time,
                threshold_warning=500,
                threshold_critical=1000,
                message=message,
                response_time_ms=response_time,
                details={
                    'log_write_time_ms': log_time,
                    'log_file_status': log_file_status,
                    'log_details': log_details,
                    'test_successful': True
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Audit logging health check failed: {str(e)}")
            return HealthMetric(
                name="audit_logging",
                status=HealthStatus.UNHEALTHY,
                message=f"Audit logging health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    def check_system_performance_health(self) -> HealthMetric:
        """Check system performance metrics that could cause middleware slowdowns"""
        start_time = time.time()
        
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)  # Quick snapshot
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get load average if available
            load_avg = None
            try:
                load_avg = psutil.getloadavg()[0]  # 1-minute load average
            except AttributeError:
                pass  # Windows doesn't have load average
            
            # Get process-specific metrics
            current_process = psutil.Process()
            process_memory = current_process.memory_info()
            process_cpu = current_process.cpu_percent()
            
            # Check for potential issues
            issues = []
            
            if cpu_percent > self.performance_thresholds['cpu_usage_critical']:
                issues.append(f"Critical CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > self.performance_thresholds['cpu_usage_warning']:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > self.performance_thresholds['memory_usage_critical']:
                issues.append(f"Critical memory usage: {memory.percent:.1f}%")
            elif memory.percent > self.performance_thresholds['memory_usage_warning']:
                issues.append(f"High memory usage: {memory.percent:.1f}%")
            
            if memory.available < 500 * 1024 * 1024:  # Less than 500MB available
                issues.append("Very low available memory")
            
            if disk.percent > 95:
                issues.append(f"Critical disk usage: {disk.percent:.1f}%")
            elif disk.percent > 85:
                issues.append(f"High disk usage: {disk.percent:.1f}%")
            
            if load_avg and load_avg > psutil.cpu_count() * 2:
                issues.append(f"High system load: {load_avg:.2f}")
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            if any("Critical" in issue for issue in issues):
                status = HealthStatus.CRITICAL
            elif issues:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            message = "System performance healthy" if status == HealthStatus.HEALTHY else f"Performance issues: {', '.join(issues)}"
            
            return HealthMetric(
                name="system_performance",
                status=status,
                value=cpu_percent,
                threshold_warning=self.performance_thresholds['cpu_usage_warning'],
                threshold_critical=self.performance_thresholds['cpu_usage_critical'],
                message=message,
                response_time_ms=response_time,
                details={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                    'disk_percent': disk.percent,
                    'disk_free_gb': disk.free / (1024**3),
                    'load_average_1min': load_avg,
                    'process_memory_mb': process_memory.rss / (1024**2),
                    'process_cpu_percent': process_cpu,
                    'issues': issues
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"System performance health check failed: {str(e)}")
            return HealthMetric(
                name="system_performance",
                status=HealthStatus.UNHEALTHY,
                message=f"System performance health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    async def check_input_validation_health(self) -> HealthMetric:
        """Check input validation middleware health"""
        start_time = time.time()
        
        try:
            from app.core.input_validation import validate_input, ValidationRule, InputValidator
            
            # Test input validation functionality
            validator = InputValidator()
            
            # Test various validation scenarios
            validation_tests = [
                {"input": "test@example.com", "rule": ValidationRule("email"), "should_pass": True},
                {"input": "invalid-email", "rule": ValidationRule("email"), "should_pass": False},
                {"input": "ValidPassword123!", "rule": ValidationRule("password"), "should_pass": True},
                {"input": "weak", "rule": ValidationRule("password"), "should_pass": False},
            ]
            
            validation_start = time.time()
            test_results = []
            
            for test in validation_tests:
                try:
                    result = validator.validate(test["input"], test["rule"])
                    test_results.append({
                        'test': f"{test['rule'].type}_{test['should_pass']}",
                        'passed': result.is_valid == test["should_pass"],
                        'validation_time_ms': result.validation_time_ms if hasattr(result, 'validation_time_ms') else 0
                    })
                except Exception as e:
                    test_results.append({
                        'test': f"{test['rule'].type}_{test['should_pass']}",
                        'passed': False,
                        'error': str(e)
                    })
            
            validation_time = (time.time() - validation_start) * 1000
            response_time = (time.time() - start_time) * 1000
            
            # Analyze results
            passed_tests = sum(1 for result in test_results if result.get('passed', False))
            total_tests = len(test_results)
            
            if passed_tests == total_tests and validation_time < 100:  # All tests pass and fast
                status = HealthStatus.HEALTHY
                message = "Input validation functioning normally"
            elif passed_tests == total_tests and validation_time < 500:
                status = HealthStatus.DEGRADED
                message = f"Input validation slow: {validation_time:.1f}ms"
            elif passed_tests < total_tests:
                status = HealthStatus.CRITICAL
                message = f"Input validation failures: {total_tests - passed_tests}/{total_tests} tests failed"
            else:
                status = HealthStatus.CRITICAL
                message = f"Input validation critical: {validation_time:.1f}ms"
            
            return HealthMetric(
                name="input_validation",
                status=status,
                value=validation_time,
                threshold_warning=100,
                threshold_critical=500,
                message=message,
                response_time_ms=response_time,
                details={
                    'validation_time_ms': validation_time,
                    'tests_passed': passed_tests,
                    'total_tests': total_tests,
                    'test_results': test_results
                }
            )
            
        except ImportError:
            # Input validation module not available
            return HealthMetric(
                name="input_validation",
                status=HealthStatus.DEGRADED,
                message="Input validation module not available",
                response_time_ms=(time.time() - start_time) * 1000,
                details={'warning': 'Input validation module not found'}
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Input validation health check failed: {str(e)}")
            return HealthMetric(
                name="input_validation",
                status=HealthStatus.UNHEALTHY,
                message=f"Input validation health check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )

    async def run_comprehensive_middleware_health_check(self, session: AsyncSession) -> MiddlewareHealthReport:
        """Run comprehensive health check on all middleware components"""
        overall_start_time = time.time()
        
        try:
            # Run all health checks concurrently where possible
            health_tasks = [
                self.check_rate_limiter_health(),
                self.check_jwt_service_health(),
                self.check_database_session_health(session),
                self.check_audit_logging_health(),
                self.check_input_validation_health(),
            ]
            
            # System performance check is sync, so run it separately
            system_health = self.check_system_performance_health()
            
            # Wait for async tasks
            async_results = await asyncio.gather(*health_tasks, return_exceptions=True)
            
            # Combine all results
            all_metrics = {'system_performance': system_health}
            metric_names = ['rate_limiter', 'jwt_service', 'database_session', 'audit_logging', 'input_validation']
            
            for i, result in enumerate(async_results):
                if isinstance(result, Exception):
                    # Create error metric for failed check
                    all_metrics[metric_names[i]] = HealthMetric(
                        name=metric_names[i],
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check exception: {str(result)}",
                        details={'exception': str(result)}
                    )
                else:
                    all_metrics[metric_names[i]] = result
            
            # Calculate overall health and performance metrics
            overall_response_time = (time.time() - overall_start_time) * 1000
            
            # Determine overall status
            statuses = [metric.status for metric in all_metrics.values()]
            
            if HealthStatus.UNHEALTHY in statuses:
                overall_status = HealthStatus.UNHEALTHY
            elif HealthStatus.CRITICAL in statuses:
                overall_status = HealthStatus.CRITICAL
            elif HealthStatus.DEGRADED in statuses:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
            
            # Collect performance summary
            response_times = [m.response_time_ms for m in all_metrics.values() if m.response_time_ms]
            performance_summary = {
                'total_response_time_ms': overall_response_time,
                'average_component_response_time_ms': sum(response_times) / len(response_times) if response_times else 0,
                'max_component_response_time_ms': max(response_times) if response_times else 0,
                'min_component_response_time_ms': min(response_times) if response_times else 0,
                'components_checked': len(all_metrics),
                'healthy_components': sum(1 for m in all_metrics.values() if m.status == HealthStatus.HEALTHY),
                'degraded_components': sum(1 for m in all_metrics.values() if m.status == HealthStatus.DEGRADED),
                'critical_components': sum(1 for m in all_metrics.values() if m.status == HealthStatus.CRITICAL),
                'unhealthy_components': sum(1 for m in all_metrics.values() if m.status == HealthStatus.UNHEALTHY),
            }
            
            # Generate alerts and issues
            alerts = []
            issues_detected = []
            recommendations = []
            
            for name, metric in all_metrics.items():
                if metric.status in [HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]:
                    alerts.append(f"ALERT: {name} is {metric.status.value}: {metric.message}")
                    issues_detected.append(f"{name}: {metric.message}")
                elif metric.status == HealthStatus.DEGRADED:
                    issues_detected.append(f"{name} degraded: {metric.message}")
                
                # Generate recommendations
                if name == "rate_limiter" and metric.response_time_ms and metric.response_time_ms > 1000:
                    recommendations.append("Consider optimizing Redis connection or increasing Redis resources")
                elif name == "database_session" and metric.response_time_ms and metric.response_time_ms > 2000:
                    recommendations.append("Database performance issues detected - check connection pool and query performance")
                elif name == "system_performance" and 'cpu_percent' in metric.details and metric.details['cpu_percent'] > 80:
                    recommendations.append("High CPU usage detected - consider scaling up or optimizing application")
                elif name == "jwt_service" and metric.response_time_ms and metric.response_time_ms > 500:
                    recommendations.append("JWT operations slow - consider JWT secret optimization or caching")
            
            # Check for patterns that could cause 8-15+ second timeouts
            if performance_summary['max_component_response_time_ms'] > 5000:
                alerts.append("CRITICAL: Component response time exceeds 5 seconds - timeout risk high")
                recommendations.append("URGENT: Investigate slow component - this could cause user-facing timeouts")
            
            if performance_summary['average_component_response_time_ms'] > 2000:
                alerts.append("WARNING: Average component response time above 2 seconds")
                recommendations.append("Monitor middleware performance - approaching timeout thresholds")
            
            # Create comprehensive report
            report = MiddlewareHealthReport(
                overall_status=overall_status,
                timestamp=datetime.utcnow(),
                metrics=all_metrics,
                performance_summary=performance_summary,
                alerts=alerts,
                response_time_ms=overall_response_time,
                issues_detected=issues_detected,
                recommendations=recommendations
            )
            
            # Store in history
            with self._lock:
                self.health_history.append(report)
                if len(self.health_history) > self.max_history_size:
                    self.health_history = self.health_history[-self.max_history_size:]
            
            return report
            
        except Exception as e:
            logger.error(f"Comprehensive middleware health check failed: {str(e)}")
            
            # Return emergency health report
            return MiddlewareHealthReport(
                overall_status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                metrics={},
                performance_summary={
                    'total_response_time_ms': (time.time() - overall_start_time) * 1000,
                    'error': 'Health check system failure'
                },
                alerts=[f"CRITICAL: Middleware health check system failure: {str(e)}"],
                response_time_ms=(time.time() - overall_start_time) * 1000,
                issues_detected=[f"Health monitoring system error: {str(e)}"],
                recommendations=["Investigate health monitoring system immediately"]
            )

    def get_health_history(self, limit: int = 100) -> List[MiddlewareHealthReport]:
        """Get recent health check history"""
        with self._lock:
            return self.health_history[-limit:] if limit else self.health_history.copy()

    def get_health_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze health trends over time"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            recent_reports = [
                report for report in self.health_history 
                if report.timestamp >= cutoff_time
            ]
        
        if not recent_reports:
            return {"error": "No health data available for the specified time period"}
        
        # Analyze trends
        status_counts = {}
        response_time_trend = []
        component_reliability = {}
        
        for report in recent_reports:
            # Count overall statuses
            status = report.overall_status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Track response times
            response_time_trend.append({
                'timestamp': report.timestamp.isoformat(),
                'response_time_ms': report.response_time_ms
            })
            
            # Track component reliability
            for name, metric in report.metrics.items():
                if name not in component_reliability:
                    component_reliability[name] = {'healthy': 0, 'total': 0}
                
                component_reliability[name]['total'] += 1
                if metric.status == HealthStatus.HEALTHY:
                    component_reliability[name]['healthy'] += 1
        
        # Calculate reliability percentages
        for name, stats in component_reliability.items():
            stats['reliability_percent'] = (stats['healthy'] / stats['total']) * 100 if stats['total'] > 0 else 0
        
        return {
            'time_period_hours': hours,
            'total_checks': len(recent_reports),
            'status_distribution': status_counts,
            'response_time_trend': response_time_trend,
            'component_reliability': component_reliability,
            'average_response_time_ms': sum(r.response_time_ms for r in recent_reports) / len(recent_reports),
            'max_response_time_ms': max(r.response_time_ms for r in recent_reports),
            'min_response_time_ms': min(r.response_time_ms for r in recent_reports)
        }


# Global middleware health monitor instance
middleware_health_monitor = MiddlewareHealthMonitor()
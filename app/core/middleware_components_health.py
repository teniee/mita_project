"""
Middleware Components Health Monitoring
Specialized health checks for individual middleware components
"""

import time
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import redis
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.middleware_health_monitor import HealthMetric, HealthStatus

logger = logging.getLogger(__name__)


class SecurityMiddlewareHealthChecker:
    """Health checker for security-related middleware components"""
    
    def __init__(self):
        self.test_lock = threading.Lock()
    
    async def check_authentication_middleware(self) -> HealthMetric:
        """Check authentication middleware health and performance"""
        start_time = time.time()
        
        try:
            from app.core.jwt_security import create_secure_token_pair, validate_jwt_token
            from app.services.auth_jwt_service import AuthJWTService
            
            # Test JWT service functionality
            jwt_service = AuthJWTService()
            
            # Test token creation and validation pipeline
            test_user_data = {
                'user_id': 'auth_health_test',
                'sub': 'auth_health_test',
                'is_premium': False,
                'country': 'US'
            }
            
            # Test token creation
            token_start = time.time()
            tokens = create_secure_token_pair(test_user_data)
            token_creation_time = (time.time() - token_start) * 1000
            
            # Test token validation
            validation_start = time.time()
            payload = validate_jwt_token(tokens['access_token'])
            validation_time = (time.time() - validation_start) * 1000
            
            # Test JWT service methods
            service_start = time.time()
            service_test = jwt_service.create_tokens_for_user(test_user_data)
            service_time = (time.time() - service_start) * 1000
            
            total_auth_time = token_creation_time + validation_time + service_time
            response_time = (time.time() - start_time) * 1000
            
            # Check results
            if not payload or payload.get('sub') != test_user_data['user_id']:
                return HealthMetric(
                    name="authentication_middleware",
                    status=HealthStatus.UNHEALTHY,
                    message="Authentication token validation failed",
                    response_time_ms=response_time,
                    details={
                        'token_creation_time_ms': token_creation_time,
                        'validation_time_ms': validation_time,
                        'payload_valid': payload is not None
                    }
                )
            
            # Determine health status
            if total_auth_time > 2000:  # More than 2 seconds
                status = HealthStatus.CRITICAL
                message = f"Authentication middleware critical: {total_auth_time:.1f}ms"
            elif total_auth_time > 1000:  # More than 1 second
                status = HealthStatus.DEGRADED
                message = f"Authentication middleware slow: {total_auth_time:.1f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = "Authentication middleware functioning normally"
            
            return HealthMetric(
                name="authentication_middleware",
                status=status,
                value=total_auth_time,
                threshold_warning=1000,
                threshold_critical=2000,
                message=message,
                response_time_ms=response_time,
                details={
                    'token_creation_time_ms': token_creation_time,
                    'validation_time_ms': validation_time,
                    'service_time_ms': service_time,
                    'total_auth_time_ms': total_auth_time,
                    'tokens_created': len(tokens),
                    'payload_claims': len(payload) if payload else 0
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Authentication middleware health check failed: {str(e)}")
            return HealthMetric(
                name="authentication_middleware",
                status=HealthStatus.UNHEALTHY,
                message=f"Authentication middleware check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )
    
    async def check_security_event_logging(self) -> HealthMetric:
        """Check security event logging middleware health"""
        start_time = time.time()
        
        try:
            from app.core.audit_logging import SecurityAuditLogger
            
            # Test security audit logger
            audit_logger = SecurityAuditLogger()
            
            # Test log writing performance
            log_start = time.time()
            await audit_logger.log_security_event(
                event_type="middleware_health_test",
                user_id="system_health_checker",
                details={
                    "test": True,
                    "timestamp": datetime.utcnow().isoformat(),
                    "component": "security_event_logging"
                },
                severity="info"
            )
            log_time = (time.time() - log_start) * 1000
            
            # Test log file system health
            log_file_health = self._check_log_file_system()
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine health status
            if log_time > 2000:  # More than 2 seconds to log
                status = HealthStatus.CRITICAL
                message = f"Security logging critical: {log_time:.1f}ms"
            elif log_time > 1000:  # More than 1 second
                status = HealthStatus.DEGRADED
                message = f"Security logging slow: {log_time:.1f}ms"
            elif log_file_health['status'] != 'healthy':
                status = HealthStatus.DEGRADED
                message = f"Security logging file system issues: {log_file_health['message']}"
            else:
                status = HealthStatus.HEALTHY
                message = "Security event logging functioning normally"
            
            return HealthMetric(
                name="security_event_logging",
                status=status,
                value=log_time,
                threshold_warning=1000,
                threshold_critical=2000,
                message=message,
                response_time_ms=response_time,
                details={
                    'log_write_time_ms': log_time,
                    'log_file_health': log_file_health,
                    'test_successful': True
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Security event logging health check failed: {str(e)}")
            return HealthMetric(
                name="security_event_logging",
                status=HealthStatus.UNHEALTHY,
                message=f"Security logging check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )
    
    def _check_log_file_system(self) -> Dict[str, Any]:
        """Check log file system health"""
        try:
            audit_log_dir = "logs/audit"
            
            if not os.path.exists(audit_log_dir):
                return {
                    'status': 'degraded',
                    'message': 'Audit log directory does not exist',
                    'directory_exists': False
                }
            
            # Check directory permissions
            if not os.access(audit_log_dir, os.W_OK):
                return {
                    'status': 'critical',
                    'message': 'Cannot write to audit log directory',
                    'directory_writable': False
                }
            
            # Check log files
            log_files = [f for f in os.listdir(audit_log_dir) if f.endswith('.jsonl')]
            recent_files = []
            
            for log_file in log_files[:5]:  # Check up to 5 recent files
                file_path = os.path.join(audit_log_dir, log_file)
                stat = os.stat(file_path)
                recent_files.append({
                    'filename': log_file,
                    'size_bytes': stat.st_size,
                    'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
            return {
                'status': 'healthy',
                'message': f'{len(log_files)} log files available',
                'directory_exists': True,
                'directory_writable': True,
                'total_log_files': len(log_files),
                'recent_files': recent_files
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'message': f'Log file system check failed: {str(e)}',
                'error': str(e)
            }


class DatabaseMiddlewareHealthChecker:
    """Health checker for database-related middleware components"""
    
    def __init__(self):
        self.connection_pool_stats = {}
    
    async def check_connection_pool_health(self, session: AsyncSession) -> HealthMetric:
        """Check database connection pool health and performance"""
        start_time = time.time()
        
        try:
            # Test basic connectivity with timing
            connectivity_start = time.time()
            basic_result = await session.execute(text("SELECT 1, NOW() as current_time"))
            basic_data = basic_result.first()
            connectivity_time = (time.time() - connectivity_start) * 1000
            
            # Get connection pool statistics
            pool_start = time.time()
            pool_stats = await session.execute(text("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                    count(*) FILTER (WHERE query_start < NOW() - INTERVAL '30 seconds') as long_running_queries,
                    count(*) FILTER (WHERE query_start < NOW() - INTERVAL '5 minutes') as very_long_queries,
                    max(EXTRACT(EPOCH FROM (NOW() - query_start))) as max_query_duration_seconds
                FROM pg_stat_activity 
                WHERE datname = current_database()
                AND pid != pg_backend_pid()
            """))
            pool_data = pool_stats.first()
            pool_query_time = (time.time() - pool_start) * 1000
            
            # Test transaction performance
            transaction_start = time.time()
            await session.execute(text("BEGIN; SELECT 1; COMMIT;"))
            transaction_time = (time.time() - transaction_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Analyze results
            total_connections = pool_data.total_connections or 0
            active_connections = pool_data.active_connections or 0
            idle_connections = pool_data.idle_connections or 0
            long_running_queries = pool_data.long_running_queries or 0
            very_long_queries = pool_data.very_long_queries or 0
            max_query_duration = pool_data.max_query_duration_seconds or 0
            
            # Calculate connection pool health
            issues = []
            
            if connectivity_time > 3000:  # More than 3 seconds for basic query
                issues.append(f"Critical connectivity time: {connectivity_time:.1f}ms")
            elif connectivity_time > 1000:
                issues.append(f"Slow connectivity: {connectivity_time:.1f}ms")
            
            if very_long_queries > 0:
                issues.append(f"{very_long_queries} queries running >5 minutes")
            
            if long_running_queries > 10:
                issues.append(f"{long_running_queries} queries running >30 seconds")
            
            if total_connections > 80:  # Assuming 100 max connections
                issues.append(f"High connection count: {total_connections}")
            
            if active_connections > 60:
                issues.append(f"High active connections: {active_connections}")
            
            if max_query_duration > 300:  # 5 minutes
                issues.append(f"Very long query detected: {max_query_duration:.1f}s")
            
            # Determine health status
            if any("Critical" in issue for issue in issues) or very_long_queries > 0:
                status = HealthStatus.CRITICAL
            elif issues:
                status = HealthStatus.DEGRADED
            elif connectivity_time > 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            message = "Database connection pool healthy" if status == HealthStatus.HEALTHY else f"Connection pool issues: {', '.join(issues)}"
            
            return HealthMetric(
                name="database_connection_pool",
                status=status,
                value=connectivity_time,
                threshold_warning=1000,
                threshold_critical=3000,
                message=message,
                response_time_ms=response_time,
                details={
                    'connectivity_time_ms': connectivity_time,
                    'pool_query_time_ms': pool_query_time,
                    'transaction_time_ms': transaction_time,
                    'total_connections': total_connections,
                    'active_connections': active_connections,
                    'idle_connections': idle_connections,
                    'idle_in_transaction': pool_data.idle_in_transaction or 0,
                    'long_running_queries': long_running_queries,
                    'very_long_queries': very_long_queries,
                    'max_query_duration_seconds': max_query_duration,
                    'issues': issues
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database connection pool health check failed: {str(e)}")
            return HealthMetric(
                name="database_connection_pool",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection pool check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )
    
    async def check_query_performance(self, session: AsyncSession) -> HealthMetric:
        """Check database query performance that could cause timeouts"""
        start_time = time.time()
        
        try:
            # Test various query types with timing
            query_tests = []
            
            # Simple SELECT test
            simple_start = time.time()
            await session.execute(text("SELECT version()"))
            simple_time = (time.time() - simple_start) * 1000
            query_tests.append({'type': 'simple_select', 'time_ms': simple_time})
            
            # Table scan test (if tables exist)
            try:
                scan_start = time.time()
                result = await session.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                table_count = result.scalar()
                scan_time = (time.time() - scan_start) * 1000
                query_tests.append({'type': 'table_scan', 'time_ms': scan_time, 'tables_found': table_count})
            except Exception:
                query_tests.append({'type': 'table_scan', 'time_ms': None, 'error': 'Failed'})
            
            # Index usage test
            try:
                index_start = time.time()
                await session.execute(text("""
                    SELECT schemaname, indexname, idx_tup_read, idx_tup_fetch 
                    FROM pg_stat_user_indexes 
                    LIMIT 5
                """))
                index_time = (time.time() - index_start) * 1000
                query_tests.append({'type': 'index_stats', 'time_ms': index_time})
            except Exception:
                query_tests.append({'type': 'index_stats', 'time_ms': None, 'error': 'Failed'})
            
            # Get slow query stats
            slow_query_start = time.time()
            slow_queries = await session.execute(text("""
                SELECT query, calls, mean_time, total_time
                FROM pg_stat_statements 
                WHERE mean_time > 1000  -- queries averaging more than 1 second
                ORDER BY mean_time DESC 
                LIMIT 3
            """))
            slow_query_results = slow_queries.fetchall()
            slow_query_time = (time.time() - slow_query_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Analyze query performance
            total_query_time = sum(test['time_ms'] for test in query_tests if test['time_ms'])
            max_query_time = max((test['time_ms'] for test in query_tests if test['time_ms']), default=0)
            failed_queries = sum(1 for test in query_tests if test.get('error'))
            
            issues = []
            
            if max_query_time > 5000:  # Any single query over 5 seconds
                issues.append(f"Critical query time: {max_query_time:.1f}ms")
            elif max_query_time > 2000:
                issues.append(f"Slow query detected: {max_query_time:.1f}ms")
            
            if failed_queries > 0:
                issues.append(f"{failed_queries} query tests failed")
            
            if len(slow_query_results) > 0:
                avg_slow_time = sum(row.mean_time for row in slow_query_results) / len(slow_query_results)
                issues.append(f"{len(slow_query_results)} slow queries averaging {avg_slow_time:.1f}ms")
            
            # Determine health status
            if max_query_time > 5000 or failed_queries > 1:
                status = HealthStatus.CRITICAL
            elif issues:
                status = HealthStatus.DEGRADED
            elif max_query_time > 1000:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            message = "Query performance healthy" if status == HealthStatus.HEALTHY else f"Query performance issues: {', '.join(issues)}"
            
            return HealthMetric(
                name="database_query_performance",
                status=status,
                value=max_query_time,
                threshold_warning=2000,
                threshold_critical=5000,
                message=message,
                response_time_ms=response_time,
                details={
                    'query_tests': query_tests,
                    'total_query_time_ms': total_query_time,
                    'max_query_time_ms': max_query_time,
                    'slow_query_analysis_time_ms': slow_query_time,
                    'slow_queries_found': len(slow_query_results),
                    'failed_queries': failed_queries,
                    'issues': issues
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database query performance health check failed: {str(e)}")
            return HealthMetric(
                name="database_query_performance",
                status=HealthStatus.UNHEALTHY,
                message=f"Query performance check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )


class CacheMiddlewareHealthChecker:
    """Health checker for cache-related middleware components"""
    
    def __init__(self):
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client for health checks"""
        try:
            redis_url = getattr(settings, 'REDIS_URL', '')
            if redis_url:
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Redis client initialization failed for health check: {str(e)}")
    
    async def check_redis_cache_health(self) -> HealthMetric:
        """Check Redis cache middleware health and performance"""
        start_time = time.time()
        
        try:
            if not self.redis_client:
                return HealthMetric(
                    name="redis_cache",
                    status=HealthStatus.DEGRADED,
                    message="Redis not configured - using in-memory caching",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={'redis_configured': False}
                )
            
            # Test basic connectivity
            ping_start = time.time()
            self.redis_client.ping()
            ping_time = (time.time() - ping_start) * 1000
            
            # Test set/get operations
            ops_start = time.time()
            test_key = f"health_check_{int(time.time())}"
            test_value = f"health_test_value_{int(time.time())}"
            
            # SET operation
            set_start = time.time()
            self.redis_client.set(test_key, test_value, ex=60)
            set_time = (time.time() - set_start) * 1000
            
            # GET operation
            get_start = time.time()
            retrieved_value = self.redis_client.get(test_key)
            get_time = (time.time() - get_start) * 1000
            
            # DELETE operation
            del_start = time.time()
            self.redis_client.delete(test_key)
            del_time = (time.time() - del_start) * 1000
            
            total_ops_time = (time.time() - ops_start) * 1000
            
            # Get Redis info and stats
            info_start = time.time()
            info = self.redis_client.info()
            info_time = (time.time() - info_start) * 1000
            
            response_time = (time.time() - start_time) * 1000
            
            # Verify operation correctness
            if retrieved_value != test_value:
                return HealthMetric(
                    name="redis_cache",
                    status=HealthStatus.UNHEALTHY,
                    message="Redis set/get operation failed - data corruption",
                    response_time_ms=response_time,
                    details={
                        'expected_value': test_value,
                        'retrieved_value': retrieved_value,
                        'data_integrity': False
                    }
                )
            
            # Analyze Redis health
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            connected_clients = info.get('connected_clients', 0)
            total_commands_processed = info.get('total_commands_processed', 0)
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            
            # Calculate hit ratio
            hit_ratio = (keyspace_hits / (keyspace_hits + keyspace_misses)) * 100 if (keyspace_hits + keyspace_misses) > 0 else 0
            
            issues = []
            
            if ping_time > 1000:  # More than 1 second for ping
                issues.append(f"Critical Redis ping time: {ping_time:.1f}ms")
            elif ping_time > 500:
                issues.append(f"Slow Redis ping: {ping_time:.1f}ms")
            
            if total_ops_time > 2000:  # More than 2 seconds for basic operations
                issues.append(f"Critical Redis operations time: {total_ops_time:.1f}ms")
            elif total_ops_time > 1000:
                issues.append(f"Slow Redis operations: {total_ops_time:.1f}ms")
            
            if max_memory > 0 and (used_memory / max_memory) > 0.9:  # More than 90% memory usage
                issues.append(f"High Redis memory usage: {(used_memory / max_memory) * 100:.1f}%")
            
            if connected_clients > 100:  # High number of connections
                issues.append(f"High Redis connection count: {connected_clients}")
            
            if hit_ratio < 80 and (keyspace_hits + keyspace_misses) > 1000:  # Low hit ratio with significant traffic
                issues.append(f"Low cache hit ratio: {hit_ratio:.1f}%")
            
            # Determine health status
            if any("Critical" in issue for issue in issues):
                status = HealthStatus.CRITICAL
            elif issues:
                status = HealthStatus.DEGRADED
            elif ping_time > 100:  # More than 100ms is concerning for cache
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            message = "Redis cache healthy" if status == HealthStatus.HEALTHY else f"Redis issues: {', '.join(issues)}"
            
            return HealthMetric(
                name="redis_cache",
                status=status,
                value=ping_time,
                threshold_warning=500,
                threshold_critical=1000,
                message=message,
                response_time_ms=response_time,
                details={
                    'ping_time_ms': ping_time,
                    'set_time_ms': set_time,
                    'get_time_ms': get_time,
                    'delete_time_ms': del_time,
                    'total_ops_time_ms': total_ops_time,
                    'info_query_time_ms': info_time,
                    'redis_version': info.get('redis_version', 'unknown'),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                    'connected_clients': connected_clients,
                    'total_commands_processed': total_commands_processed,
                    'hit_ratio_percent': hit_ratio,
                    'keyspace_hits': keyspace_hits,
                    'keyspace_misses': keyspace_misses,
                    'data_integrity': True,
                    'issues': issues
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Redis cache health check failed: {str(e)}")
            return HealthMetric(
                name="redis_cache",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis cache check failed: {str(e)}",
                response_time_ms=response_time,
                details={'error': str(e)}
            )


# Global health checker instances
security_health_checker = SecurityMiddlewareHealthChecker()
database_health_checker = DatabaseMiddlewareHealthChecker()
cache_health_checker = CacheMiddlewareHealthChecker()
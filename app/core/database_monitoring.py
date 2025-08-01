"""
Database Connection Pooling and Query Optimization Monitoring
Provides comprehensive database performance monitoring, connection management, and query optimization
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
from sqlalchemy import event, text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.engine import Engine
# Remove invalid imports - these don't exist in current SQLAlchemy
from sqlalchemy.sql import sqltypes
import psutil
import threading
from collections import defaultdict, deque

from app.core.config import settings
# from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of database queries"""
    SELECT = "SELECT"
    INSERT = "INSERT" 
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    OTHER = "OTHER"


class SlowQuerySeverity(Enum):
    """Severity levels for slow queries"""
    WARNING = "warning"    # 1-5 seconds
    CRITICAL = "critical"  # 5+ seconds
    EMERGENCY = "emergency" # 10+ seconds


@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_id: str
    query_type: QueryType
    query_text: str
    execution_time: float
    start_time: datetime
    end_time: datetime
    rows_affected: Optional[int]
    connection_id: Optional[str]
    user_id: Optional[str]
    endpoint: Optional[str]
    severity: Optional[SlowQuerySeverity]
    parameters: Optional[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        data['query_type'] = self.query_type.value
        data['severity'] = self.severity.value if self.severity else None
        return data


@dataclass
class ConnectionPoolMetrics:
    """Connection pool performance metrics"""
    timestamp: datetime
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    invalidated: int
    total_connections: int
    active_connections: int
    idle_connections: int
    connection_errors: int
    pool_timeouts: int
    avg_checkout_time: float
    max_checkout_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class DatabaseQueryMonitor:
    """Monitors database query performance and connection usage"""
    
    def __init__(self):
        self.query_history: deque = deque(maxlen=1000)
        self.slow_queries: deque = deque(maxlen=100)
        self.query_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'max_time': 0.0,
            'min_time': float('inf')
        })
        self.connection_metrics: deque = deque(maxlen=100)
        self.lock = threading.Lock()
        
        # Configuration
        self.slow_query_threshold = 1.0  # seconds
        self.critical_query_threshold = 5.0  # seconds
        self.emergency_query_threshold = 10.0  # seconds
        
        # Start monitoring tasks
        asyncio.create_task(self._periodic_metrics_collection())
    
    def record_query(
        self,
        query_text: str,
        execution_time: float,
        rows_affected: Optional[int] = None,
        connection_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """Record query execution metrics"""
        try:
            with self.lock:
                # Determine query type
                query_type = self._get_query_type(query_text)
                
                # Determine severity
                severity = None
                if execution_time >= self.emergency_query_threshold:
                    severity = SlowQuerySeverity.EMERGENCY
                elif execution_time >= self.critical_query_threshold:
                    severity = SlowQuerySeverity.CRITICAL
                elif execution_time >= self.slow_query_threshold:
                    severity = SlowQuerySeverity.WARNING
                
                # Create query metrics
                query_metrics = QueryMetrics(
                    query_id=f"{int(time.time() * 1000)}_{id(query_text)}",
                    query_type=query_type,
                    query_text=self._sanitize_query(query_text),
                    execution_time=execution_time,
                    start_time=datetime.now() - timedelta(seconds=execution_time),
                    end_time=datetime.now(),
                    rows_affected=rows_affected,
                    connection_id=connection_id,
                    user_id=user_id,
                    endpoint=endpoint,
                    severity=severity,
                    parameters=self._sanitize_parameters(parameters) if parameters else None
                )
                
                # Store in history
                self.query_history.append(query_metrics)
                
                # Store slow queries separately
                if severity:
                    self.slow_queries.append(query_metrics)
                    logger.warning(
                        f"Slow query detected: {severity.value} - {execution_time:.3f}s",
                        extra={
                            'query_metrics': query_metrics.to_dict(),
                            'performance_impact': 'high' if execution_time > 5.0 else 'medium'
                        }
                    )
                
                # Update statistics
                query_pattern = self._get_query_pattern(query_text)
                stats = self.query_stats[query_pattern]
                stats['count'] += 1
                stats['total_time'] += execution_time
                stats['avg_time'] = stats['total_time'] / stats['count']
                stats['max_time'] = max(stats['max_time'], execution_time)
                stats['min_time'] = min(stats['min_time'], execution_time)
                
        except Exception as e:
            logger.error(f"Error recording query metrics: {str(e)}")
    
    def _get_query_type(self, query_text: str) -> QueryType:
        """Determine query type from SQL text"""
        query_upper = query_text.strip().upper()
        
        if query_upper.startswith('SELECT'):
            return QueryType.SELECT
        elif query_upper.startswith('INSERT'):
            return QueryType.INSERT
        elif query_upper.startswith('UPDATE'):
            return QueryType.UPDATE
        elif query_upper.startswith('DELETE'):
            return QueryType.DELETE
        elif query_upper.startswith('CREATE'):
            return QueryType.CREATE
        elif query_upper.startswith('DROP'):
            return QueryType.DROP
        elif query_upper.startswith('ALTER'):
            return QueryType.ALTER
        else:
            return QueryType.OTHER
    
    def _sanitize_query(self, query_text: str) -> str:
        """Sanitize query text for logging"""
        # Limit length and remove potentially sensitive data
        sanitized = query_text[:1000]
        
        # Replace potential sensitive values with placeholders
        import re
        sanitized = re.sub(r"'[^']*'", "'***'", sanitized)
        sanitized = re.sub(r'"[^"]*"', '"***"', sanitized)
        sanitized = re.sub(r'\b\d+\b', 'N', sanitized)
        
        return sanitized
    
    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize query parameters for logging"""
        sanitized = {}
        sensitive_keys = {'password', 'token', 'secret', 'key', 'auth'}
        
        for key, value in parameters.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                # Limit value size
                if isinstance(value, str) and len(value) > 100:
                    sanitized[key] = value[:100] + '...'
                else:
                    sanitized[key] = value
        
        return sanitized
    
    def _get_query_pattern(self, query_text: str) -> str:
        """Get normalized query pattern for statistics"""
        import re
        
        # Normalize the query to group similar queries
        pattern = query_text.strip().upper()
        
        # Replace values with placeholders
        pattern = re.sub(r"'[^']*'", '?', pattern)
        pattern = re.sub(r'"[^"]*"', '?', pattern)
        pattern = re.sub(r'\b\d+\b', '?', pattern)
        pattern = re.sub(r'\s+', ' ', pattern)
        
        # Limit length
        return pattern[:200]
    
    async def _periodic_metrics_collection(self):
        """Periodically collect connection pool metrics"""
        while True:
            try:
                await asyncio.sleep(30)  # Collect every 30 seconds
                await self._collect_pool_metrics()
            except Exception as e:
                logger.error(f"Error in periodic metrics collection: {str(e)}")
    
    async def _collect_pool_metrics(self):
        """Collect connection pool metrics"""
        try:
            # This would be implemented based on your database setup
            # For now, we'll create placeholder metrics
            
            metrics = ConnectionPoolMetrics(
                timestamp=datetime.now(),
                pool_size=10,  # These would come from actual pool
                checked_in=7,
                checked_out=3,
                overflow=0,
                invalidated=0,
                total_connections=10,
                active_connections=3,
                idle_connections=7,
                connection_errors=0,
                pool_timeouts=0,
                avg_checkout_time=0.05,
                max_checkout_time=0.2
            )
            
            with self.lock:
                self.connection_metrics.append(metrics)
                
        except Exception as e:
            logger.error(f"Error collecting pool metrics: {str(e)}")
    
    def get_query_statistics(self, limit: int = 10) -> Dict[str, Any]:
        """Get query performance statistics"""
        with self.lock:
            # Sort by total time to find most impactful queries
            sorted_stats = sorted(
                self.query_stats.items(),
                key=lambda x: x[1]['total_time'],
                reverse=True
            )
            
            return {
                'total_queries': sum(stats['count'] for stats in self.query_stats.values()),
                'unique_query_patterns': len(self.query_stats),
                'slowest_queries': [
                    {
                        'pattern': pattern,
                        'count': stats['count'],
                        'avg_time': round(stats['avg_time'], 3),
                        'max_time': round(stats['max_time'], 3),
                        'total_time': round(stats['total_time'], 3)
                    }
                    for pattern, stats in sorted_stats[:limit]
                ],
                'recent_slow_queries': [
                    query.to_dict() for query in list(self.slow_queries)[-limit:]
                ],
                'query_type_distribution': self._get_query_type_distribution()
            }
    
    def _get_query_type_distribution(self) -> Dict[str, int]:
        """Get distribution of query types"""
        distribution = defaultdict(int)
        
        for query in self.query_history:
            distribution[query.query_type.value] += 1
        
        return dict(distribution)
    
    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get connection pool metrics"""
        with self.lock:
            if not self.connection_metrics:
                return {}
            
            latest = self.connection_metrics[-1]
            return {
                'current_metrics': latest.to_dict(),
                'pool_utilization': (latest.checked_out / latest.pool_size) * 100 if latest.pool_size > 0 else 0,
                'connection_efficiency': (latest.active_connections / latest.total_connections) * 100 if latest.total_connections > 0 else 0,
                'health_status': self._assess_pool_health(latest)
            }
    
    def _assess_pool_health(self, metrics: ConnectionPoolMetrics) -> str:
        """Assess connection pool health"""
        utilization = (metrics.checked_out / metrics.pool_size) * 100 if metrics.pool_size > 0 else 0
        
        if metrics.connection_errors > 0 or metrics.pool_timeouts > 0:
            return 'critical'
        elif utilization > 80:
            return 'warning'
        elif utilization > 95:
            return 'critical'
        else:
            return 'healthy'


class OptimizedDatabaseEngine:
    """Enhanced database engine with monitoring and optimization"""
    
    def __init__(self):
        self.query_monitor = DatabaseQueryMonitor()
        self.engines: Dict[str, AsyncEngine] = {}
        self._setup_engines()
        self._setup_event_listeners()
    
    def _setup_engines(self):
        """Set up optimized database engines"""
        try:
            # Skip engine setup if DATABASE_URL is not configured
            if not settings.DATABASE_URL:
                logger.warning("DATABASE_URL not configured, skipping engine setup")
                return
                
            # FORCE asyncpg driver - direct URL conversion  
            database_url = settings.DATABASE_URL
            if database_url.startswith("postgresql://"):
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif "postgresql+psycopg2" in database_url:
                database_url = database_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
            
            # Primary database engine with optimized pool settings
            primary_engine = create_async_engine(
                database_url,
                # Connection pool settings
                poolclass=QueuePool,
                pool_size=20,  # Base pool size
                max_overflow=30,  # Additional connections when needed
                pool_timeout=30,  # Timeout for getting connection
                pool_recycle=3600,  # Recycle connections every hour
                pool_pre_ping=True,  # Validate connections before use
                
                # Query optimization settings
                echo=False,  # Set to True for SQL debugging
                echo_pool=False,  # Set to True for pool debugging
                
                # Connection settings
                connect_args={
                    "server_settings": {
                        "jit": "off",  # Disable JIT for consistent performance
                        "application_name": "mita_finance_app"
                    },
                    "command_timeout": 60,
                    "prepared_statement_cache_size": 100
                }
            )
            
            self.engines['primary'] = primary_engine
            
            # Read-only replica engine (if available)
            readonly_url = getattr(settings, 'READONLY_DATABASE_URL', None)
            if readonly_url:
                # Convert readonly URL to use asyncpg too
                if readonly_url.startswith("postgresql://"):
                    readonly_url = readonly_url.replace("postgresql://", "postgresql+asyncpg://", 1)
                elif readonly_url.startswith("postgres://"):
                    readonly_url = readonly_url.replace("postgres://", "postgresql+asyncpg://", 1)
                
                readonly_engine = create_async_engine(
                    readonly_url,
                    poolclass=QueuePool,
                    pool_size=15,
                    max_overflow=20,
                    pool_timeout=30,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    connect_args={
                        "server_settings": {
                            "default_transaction_read_only": "on",
                            "application_name": "mita_finance_readonly"
                        }
                    }
                )
                self.engines['readonly'] = readonly_engine
            
            logger.info("Database engines initialized with optimized settings")
            
        except Exception as e:
            logger.error(f"Error setting up database engines: {str(e)}")
            # Can't use async log_error in sync function
            logger.error(f"Critical database engine setup error: {str(e)}")
    
    def _setup_event_listeners(self):
        """Set up event listeners for monitoring"""
        try:
            for engine_name, engine in self.engines.items():
                # Query execution monitoring
                @event.listens_for(engine.sync_engine, "before_cursor_execute")
                def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    context._query_start_time = time.time()
                    context._query_statement = statement
                    context._query_parameters = parameters
                
                @event.listens_for(engine.sync_engine, "after_cursor_execute")
                def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    execution_time = time.time() - context._query_start_time
                    
                    # Record query metrics
                    self.query_monitor.record_query(
                        query_text=statement,
                        execution_time=execution_time,
                        rows_affected=cursor.rowcount if hasattr(cursor, 'rowcount') else None,
                        connection_id=str(id(conn)),
                        parameters=parameters
                    )
                
                # Connection pool monitoring
                @event.listens_for(engine.sync_engine.pool, "connect")
                def on_connect(dbapi_conn, connection_record):
                    logger.debug(f"New database connection established: {id(dbapi_conn)}")
                
                @event.listens_for(engine.sync_engine.pool, "checkout")
                def on_checkout(dbapi_conn, connection_record, connection_proxy):
                    connection_record.checkout_time = time.time()
                
                @event.listens_for(engine.sync_engine.pool, "checkin")
                def on_checkin(dbapi_conn, connection_record):
                    if hasattr(connection_record, 'checkout_time'):
                        checkout_duration = time.time() - connection_record.checkout_time
                        if checkout_duration > 10:  # Log long-running connections
                            logger.warning(f"Long connection checkout: {checkout_duration:.2f}s")
                
                logger.info(f"Event listeners set up for {engine_name} engine")
                
        except Exception as e:
            logger.error(f"Error setting up event listeners: {str(e)}")
    
    def get_engine(self, readonly: bool = False) -> AsyncEngine:
        """Get appropriate database engine"""
        if readonly and 'readonly' in self.engines:
            return self.engines['readonly']
        return self.engines['primary']
    
    @asynccontextmanager
    async def get_session(self, readonly: bool = False):
        """Get database session with monitoring"""
        engine = self.get_engine(readonly)
        async with AsyncSession(engine) as session:
            session_start_time = time.time()
            try:
                yield session
            finally:
                session_duration = time.time() - session_start_time
                if session_duration > 5:  # Log long sessions
                    logger.warning(
                        f"Long database session: {session_duration:.2f}s",
                        extra={'session_duration': session_duration, 'readonly': readonly}
                    )
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        try:
            stats = {
                'query_statistics': self.query_monitor.get_query_statistics(),
                'connection_metrics': self.query_monitor.get_connection_metrics(),
                'engine_info': {},
                'system_resources': await self._get_system_resources()
            }
            
            # Add engine information
            for name, engine in self.engines.items():
                pool = engine.pool if hasattr(engine, 'pool') else None
                if pool:
                    stats['engine_info'][name] = {
                        'pool_size': pool.size(),
                        'checked_in': pool.checkedin(),
                        'checked_out': pool.checkedout(),
                        'overflow': pool.overflow(),
                        'invalid': pool.invalid()
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {str(e)}")
            return {}
    
    async def _get_system_resources(self) -> Dict[str, Any]:
        """Get system resource usage"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'active_connections': len(psutil.net_connections())
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {str(e)}")
            return {}
    
    async def analyze_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Analyze slow queries and provide optimization suggestions"""
        try:
            with self.query_monitor.lock:
                slow_queries = list(self.query_monitor.slow_queries)[-limit:]
            
            analyzed_queries = []
            
            for query in slow_queries:
                analysis = {
                    'query': query.to_dict(),
                    'suggestions': self._generate_optimization_suggestions(query)
                }
                analyzed_queries.append(analysis)
            
            return analyzed_queries
            
        except Exception as e:
            logger.error(f"Error analyzing slow queries: {str(e)}")
            return []
    
    def _generate_optimization_suggestions(self, query: QueryMetrics) -> List[str]:
        """Generate optimization suggestions for slow queries"""
        suggestions = []
        query_text = query.query_text.upper()
        
        # Basic optimization suggestions
        if 'SELECT *' in query_text:
            suggestions.append("Consider selecting only required columns instead of using SELECT *")
        
        if 'ORDER BY' in query_text and 'LIMIT' not in query_text:
            suggestions.append("Consider adding LIMIT clause to ORDER BY queries")
        
        if query.execution_time > 5.0:
            suggestions.append("Query execution time is very high - consider adding database indexes")
        
        if 'JOIN' in query_text and query.execution_time > 2.0:
            suggestions.append("Complex joins detected - verify indexes on join columns")
        
        if 'WHERE' in query_text:
            suggestions.append("Ensure WHERE clause columns are properly indexed")
        
        if query.query_type == QueryType.SELECT and query.execution_time > 1.0:
            suggestions.append("Consider implementing query result caching")
        
        return suggestions


# Global database engine instance - initialized lazily
_db_engine = None

def get_db_engine():
    """Get or create the global database engine instance"""
    global _db_engine
    if _db_engine is None:
        _db_engine = OptimizedDatabaseEngine()
    return _db_engine

# For backward compatibility
class DBEngineProxy:
    def __getattr__(self, name):
        return getattr(get_db_engine(), name)

db_engine = DBEngineProxy()


async def get_optimized_db_session(readonly: bool = False):
    """Get optimized database session"""
    async with db_engine.get_session(readonly=readonly) as session:
        yield session


async def get_database_performance_stats() -> Dict[str, Any]:
    """Get database performance statistics"""
    return await db_engine.get_database_stats()


async def analyze_database_performance() -> Dict[str, Any]:
    """Analyze database performance and provide recommendations"""
    stats = await get_database_performance_stats()
    slow_queries = await db_engine.analyze_slow_queries()
    
    # Generate recommendations
    recommendations = []
    
    query_stats = stats.get('query_statistics', {})
    if query_stats.get('total_queries', 0) > 0:
        avg_query_time = sum(
            q['avg_time'] for q in query_stats.get('slowest_queries', [])
        ) / len(query_stats.get('slowest_queries', [1]))
        
        if avg_query_time > 1.0:
            recommendations.append("Consider optimizing frequently used queries")
        
        if len(query_stats.get('recent_slow_queries', [])) > 5:
            recommendations.append("High number of slow queries detected - review database indexes")
    
    connection_metrics = stats.get('connection_metrics', {})
    if connection_metrics.get('pool_utilization', 0) > 80:
        recommendations.append("High connection pool utilization - consider increasing pool size")
    
    return {
        'performance_stats': stats,
        'slow_query_analysis': slow_queries,
        'recommendations': recommendations,
        'health_score': _calculate_health_score(stats),
        'generated_at': datetime.now().isoformat()
    }


def _calculate_health_score(stats: Dict[str, Any]) -> int:
    """Calculate database health score (0-100)"""
    score = 100
    
    # Deduct points for performance issues
    query_stats = stats.get('query_statistics', {})
    if query_stats.get('slowest_queries'):
        avg_time = sum(q['avg_time'] for q in query_stats['slowest_queries']) / len(query_stats['slowest_queries'])
        if avg_time > 2.0:
            score -= 20
        elif avg_time > 1.0:
            score -= 10
    
    # Deduct points for connection issues
    connection_metrics = stats.get('connection_metrics', {})
    utilization = connection_metrics.get('pool_utilization', 0)
    if utilization > 90:
        score -= 20
    elif utilization > 80:
        score -= 10
    
    # Deduct points for system resources
    system_resources = stats.get('system_resources', {})
    if system_resources.get('memory_percent', 0) > 90:
        score -= 15
    if system_resources.get('cpu_percent', 0) > 80:
        score -= 10
    
    return max(0, score)
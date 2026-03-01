"""
Advanced Database Optimization System
Provides query optimization, indexing strategies, connection pooling,
and performance monitoring for MITA's PostgreSQL database
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text, Index, Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy.dialects.postgresql import UUID
# Note: Using SQLAlchemy for database operations instead of direct psycopg2
# This allows for better compatibility with asyncpg and the async architecture

from app.core.config import settings
from app.db.models import Base, User, Expense, Transaction, AIAnalysisSnapshot

logger = logging.getLogger(__name__)


class DatabasePerformanceMonitor:
    """Monitor database performance and identify slow queries"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.slow_query_threshold = 1.0  # seconds
        self.query_stats: Dict[str, Dict] = {}
    
    def log_query_performance(self, query: str, execution_time: float, params: Dict = None):
        """Log query performance metrics"""
        query_hash = hash(query)
        
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                'query': query[:200] + '...' if len(query) > 200 else query,
                'total_executions': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf'),
                'slow_executions': 0
            }
        
        stats = self.query_stats[query_hash]
        stats['total_executions'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['total_executions']
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['min_time'] = min(stats['min_time'], execution_time)
        
        if execution_time > self.slow_query_threshold:
            stats['slow_executions'] += 1
            logger.warning(f"Slow query detected ({execution_time:.3f}s): {query[:100]}...")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        total_queries = sum(stat['total_executions'] for stat in self.query_stats.values())
        total_slow_queries = sum(stat['slow_executions'] for stat in self.query_stats.values())
        
        slowest_queries = sorted(
            self.query_stats.values(),
            key=lambda x: x['avg_time'],
            reverse=True
        )[:5]
        
        return {
            'total_queries_monitored': total_queries,
            'total_slow_queries': total_slow_queries,
            'slow_query_percentage': (total_slow_queries / max(total_queries, 1)) * 100,
            'slowest_queries': slowest_queries,
            'monitoring_threshold': self.slow_query_threshold
        }


class OptimizedQueryBuilder:
    """Build optimized queries with performance considerations"""
    
    @staticmethod
    def build_user_expenses_query(user_id: int, start_date: datetime = None, 
                                end_date: datetime = None, limit: int = None) -> str:
        """Build optimized query for user expenses with proper indexing hints"""
        query = """
        SELECT e.id, e.amount, e.category, e.description, e.date, e.created_at
        FROM expenses e
        WHERE e.user_id = :user_id
        """
        
        if start_date:
            query += " AND e.date >= :start_date"
        
        if end_date:
            query += " AND e.date <= :end_date"
        
        # Order by date descending for better performance with limit
        query += " ORDER BY e.date DESC, e.id DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return query
    
    @staticmethod
    def build_category_totals_query(user_id: int, year: int, month: int) -> str:
        """Build optimized query for category totals"""
        return """
        SELECT 
            e.category,
            SUM(e.amount) as total_amount,
            COUNT(*) as transaction_count,
            AVG(e.amount) as avg_amount
        FROM expenses e
        WHERE e.user_id = :user_id
            AND EXTRACT(YEAR FROM e.date) = :year
            AND EXTRACT(MONTH FROM e.date) = :month
        GROUP BY e.category
        ORDER BY total_amount DESC
        """
    
    @staticmethod
    def build_spending_trends_query(user_id: int, months_back: int = 6) -> str:
        """Build optimized query for spending trends"""
        return """
        WITH monthly_totals AS (
            SELECT 
                DATE_TRUNC('month', e.date) as month,
                SUM(e.amount) as total_spending,
                COUNT(*) as transaction_count
            FROM expenses e
            WHERE e.user_id = :user_id
                AND e.date >= CURRENT_DATE - INTERVAL ':months_back months'
            GROUP BY DATE_TRUNC('month', e.date)
        )
        SELECT 
            month,
            total_spending,
            transaction_count,
            LAG(total_spending) OVER (ORDER BY month) as prev_month_spending,
            (total_spending - LAG(total_spending) OVER (ORDER BY month)) / 
                NULLIF(LAG(total_spending) OVER (ORDER BY month), 0) * 100 as growth_rate
        FROM monthly_totals
        ORDER BY month DESC
        """
    
    @staticmethod
    def build_user_analytics_query(user_id: int) -> str:
        """Build comprehensive user analytics query"""
        return """
        WITH user_stats AS (
            SELECT 
                COUNT(*) as total_expenses,
                SUM(amount) as total_spent,
                AVG(amount) as avg_expense,
                MIN(date) as first_expense_date,
                MAX(date) as last_expense_date,
                COUNT(DISTINCT category) as categories_used,
                COUNT(DISTINCT DATE_TRUNC('day', date)) as active_days
            FROM expenses
            WHERE user_id = :user_id
        ),
        category_breakdown AS (
            SELECT 
                category,
                SUM(amount) as category_total,
                COUNT(*) as category_count,
                ROW_NUMBER() OVER (ORDER BY SUM(amount) DESC) as category_rank
            FROM expenses
            WHERE user_id = :user_id
            GROUP BY category
        )
        SELECT 
            us.*,
            json_agg(
                json_build_object(
                    'category', cb.category,
                    'total', cb.category_total,
                    'count', cb.category_count,
                    'percentage', ROUND((cb.category_total / us.total_spent) * 100, 2)
                ) ORDER BY cb.category_rank
            ) as category_breakdown
        FROM user_stats us
        CROSS JOIN category_breakdown cb
        WHERE cb.category_rank <= 10
        GROUP BY us.total_expenses, us.total_spent, us.avg_expense, 
                us.first_expense_date, us.last_expense_date, 
                us.categories_used, us.active_days
        """


class DatabaseIndexManager:
    """Manage database indexes for optimal performance"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
    
    def create_performance_indexes(self):
        """Create indexes optimized for MITA's query patterns"""
        indexes_to_create = [
            # User expenses - most common queries
            {
                'table': 'expenses',
                'name': 'idx_expenses_user_date_desc',
                'columns': ['user_id', 'date DESC', 'id DESC'],
                'description': 'Optimizes user expense queries with date ordering'
            },
            {
                'table': 'expenses',
                'name': 'idx_expenses_user_category_date',
                'columns': ['user_id', 'category', 'date'],
                'description': 'Optimizes category-filtered queries'
            },
            {
                'table': 'expenses',
                'name': 'idx_expenses_user_amount_date',
                'columns': ['user_id', 'amount', 'date'],
                'description': 'Optimizes amount-based queries and anomaly detection'
            },
            {
                'table': 'expenses',
                'name': 'idx_expenses_date_month_year',
                'columns': ['user_id', 'EXTRACT(YEAR FROM date)', 'EXTRACT(MONTH FROM date)'],
                'description': 'Optimizes monthly/yearly aggregations'
            },
            
            # Transactions
            {
                'table': 'transactions',
                'name': 'idx_transactions_user_created_desc',
                'columns': ['user_id', 'created_at DESC'],
                'description': 'Optimizes transaction history queries'
            },
            {
                'table': 'transactions',
                'name': 'idx_transactions_user_category_created',
                'columns': ['user_id', 'category', 'created_at'],
                'description': 'Optimizes category-based transaction queries'
            },
            
            # AI Analysis Snapshots
            {
                'table': 'ai_analysis_snapshots',
                'name': 'idx_ai_snapshots_user_created_desc',
                'columns': ['user_id', 'created_at DESC'],
                'description': 'Optimizes latest AI snapshot queries'
            },
            
            # Users
            {
                'table': 'users',
                'name': 'idx_users_email_lower',
                'columns': ['LOWER(email)'],
                'description': 'Case-insensitive email lookups'
            },
            {
                'table': 'users',
                'name': 'idx_users_created_at',
                'columns': ['created_at'],
                'description': 'User registration analytics'
            },
            
            # Text search indexes
            {
                'table': 'expenses',
                'name': 'idx_expenses_description_gin',
                'columns': ['to_tsvector(\'english\', COALESCE(description, \'\'))'],
                'type': 'GIN',
                'description': 'Full-text search on expense descriptions'
            }
        ]
        
        with self.engine.connect() as conn:
            for idx in indexes_to_create:
                try:
                    self._create_index_if_not_exists(conn, idx)
                except Exception as e:
                    logger.error(f"Failed to create index {idx['name']}: {e}")
    
    def _create_index_if_not_exists(self, conn, index_config: Dict):
        """Create index if it doesn't already exist"""
        # Check if index exists
        check_query = text("""
            SELECT 1 FROM pg_indexes 
            WHERE tablename = :table_name AND indexname = :index_name
        """)
        
        result = conn.execute(check_query, {
            'table_name': index_config['table'],
            'index_name': index_config['name']
        }).fetchone()
        
        if result:
            logger.info(f"Index {index_config['name']} already exists")
            return
        
        # Create the index
        index_type = index_config.get('type', 'BTREE')
        columns_str = ', '.join(index_config['columns'])
        
        create_query = f"""
            CREATE INDEX CONCURRENTLY {index_config['name']} 
            ON {index_config['table']} 
            USING {index_type} ({columns_str})
        """
        
        logger.info(f"Creating index: {index_config['name']} - {index_config['description']}")
        conn.execute(text(create_query))
        conn.commit()
    
    def analyze_table_statistics(self):
        """Update table statistics for query planner"""
        tables = ['users', 'expenses', 'transactions', 'ai_analysis_snapshots']
        
        with self.engine.connect() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    logger.info(f"Updated statistics for table: {table}")
                except Exception as e:
                    logger.error(f"Failed to analyze table {table}: {e}")
            conn.commit()
    
    def get_index_usage_stats(self) -> List[Dict]:
        """Get index usage statistics"""
        query = text("""
        SELECT 
            schemaname,
            tablename,
            indexname,
            idx_tup_read,
            idx_tup_fetch,
            idx_scan,
            ROUND(
                CASE 
                    WHEN idx_tup_read + idx_tup_fetch = 0 THEN 0
                    ELSE (idx_tup_fetch::float / (idx_tup_read + idx_tup_fetch)) * 100
                END, 2
            ) as efficiency_percentage
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        ORDER BY idx_scan DESC, efficiency_percentage DESC
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query).fetchall()
            return [dict(row) for row in result]


class ConnectionPoolOptimizer:
    """Optimize database connection pooling"""
    
    @staticmethod
    def create_optimized_engine(database_url: str) -> Engine:
        """Create optimized database engine with proper connection pooling"""
        
        # Connection pool settings optimized for web application
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=20,              # Base connections
            max_overflow=30,           # Additional connections when needed
            pool_pre_ping=True,        # Validate connections before use
            pool_recycle=3600,         # Recycle connections every hour
            pool_timeout=30,           # Timeout waiting for connection
            echo=False,                # Set to True for query logging in development
            
            # PostgreSQL specific optimizations
            connect_args={
                "options": "-c search_path=public",
                "application_name": "mita_finance_app",
                "connect_timeout": 10,
                "command_timeout": 30,
                "server_settings": {
                    "jit": "off",  # Disable JIT for faster connection
                    "shared_preload_libraries": "pg_stat_statements"
                }
            }
        )
        
        # Configure engine events for monitoring
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            if total > 1.0:  # Log slow queries
                logger.warning(f"Slow query ({total:.3f}s): {statement[:200]}...")
        
        return engine


class QueryCache:
    """Simple query result caching system"""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self.cache: Dict[str, Dict] = {}
        self.default_ttl = default_ttl
    
    def _get_cache_key(self, query: str, params: Dict) -> str:
        """Generate cache key from query and parameters"""
        import hashlib
        key_string = f"{query}:{sorted(params.items()) if params else ''}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, query: str, params: Dict = None) -> Optional[Any]:
        """Get cached query result"""
        cache_key = self._get_cache_key(query, params or {})
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() < entry['expires_at']:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return entry['result']
            else:
                # Remove expired entry
                del self.cache[cache_key]
        
        return None
    
    def set(self, query: str, result: Any, params: Dict = None, ttl: int = None) -> None:
        """Cache query result"""
        cache_key = self._get_cache_key(query, params or {})
        expires_at = time.time() + (ttl or self.default_ttl)
        
        self.cache[cache_key] = {
            'result': result,
            'expires_at': expires_at,
            'created_at': time.time()
        }
        
        logger.debug(f"Cached result for query: {query[:50]}...")
    
    def clear(self) -> None:
        """Clear all cached results"""
        self.cache.clear()
        logger.info("Query cache cleared")
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time >= entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        return len(expired_keys)


class DatabaseOptimizer:
    """Main database optimization orchestrator"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.performance_monitor = DatabasePerformanceMonitor(engine)
        self.index_manager = DatabaseIndexManager(engine)
        self.query_cache = QueryCache()
        self.query_builder = OptimizedQueryBuilder()
    
    def initialize_optimizations(self):
        """Initialize all database optimizations"""
        logger.info("Initializing database optimizations...")
        
        try:
            # Create performance indexes
            self.index_manager.create_performance_indexes()
            
            # Update table statistics
            self.index_manager.analyze_table_statistics()
            
            # Configure query monitoring
            self._setup_query_monitoring()
            
            logger.info("Database optimizations initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database optimizations: {e}")
            raise
    
    def _setup_query_monitoring(self):
        """Set up query performance monitoring"""
        from sqlalchemy import event
        
        @event.listens_for(self.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
            context._query_statement = statement
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                execution_time = time.time() - context._query_start_time
                self.performance_monitor.log_query_performance(statement, execution_time, parameters)
    
    @contextmanager
    def optimized_session(self) -> Session:
        """Create database session with optimization features"""
        SessionLocal = sessionmaker(bind=self.engine)
        session = SessionLocal()
        
        try:
            # Configure session for performance
            session.execute(text("SET work_mem = '32MB'"))  # Increase work memory for complex queries
            session.execute(text("SET random_page_cost = 1.1"))  # Optimize for SSD storage
            
            yield session
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_cached_query(self, query: str, params: Dict = None, ttl: int = None) -> List[Dict]:
        """Execute query with caching"""
        # Check cache first
        cached_result = self.query_cache.get(query, params)
        if cached_result is not None:
            return cached_result
        
        # Execute query
        with self.optimized_session() as session:
            result = session.execute(text(query), params or {}).fetchall()
            result_dicts = [dict(row) for row in result]
            
            # Cache the result
            self.query_cache.set(query, result_dicts, params, ttl)
            
            return result_dicts
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        return {
            'performance_monitoring': self.performance_monitor.get_performance_report(),
            'index_usage': self.index_manager.get_index_usage_stats(),
            'cache_stats': {
                'cached_queries': len(self.query_cache.cache),
                'cache_size_mb': sum(
                    len(str(entry['result'])) for entry in self.query_cache.cache.values()
                ) / (1024 * 1024)
            },
            'recommendations': self._generate_optimization_recommendations()
        }
    
    def _generate_optimization_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on current performance"""
        recommendations = []
        
        # Check for slow queries
        perf_report = self.performance_monitor.get_performance_report()
        if perf_report['slow_query_percentage'] > 5:
            recommendations.append("High percentage of slow queries detected - consider adding indexes")
        
        # Check index usage
        index_stats = self.index_manager.get_index_usage_stats()
        unused_indexes = [idx for idx in index_stats if idx['idx_scan'] == 0]
        if len(unused_indexes) > 3:
            recommendations.append(f"{len(unused_indexes)} unused indexes found - consider dropping them")
        
        # Check cache hit rate
        cache_size = len(self.query_cache.cache)
        if cache_size < 10:
            recommendations.append("Low query cache utilization - consider increasing cache TTL")
        
        return recommendations or ["Database performance is optimal"]


# Singleton instance for application use
_db_optimizer: Optional[DatabaseOptimizer] = None

def get_database_optimizer(engine: Engine = None) -> DatabaseOptimizer:
    """Get or create database optimizer instance"""
    global _db_optimizer
    
    if _db_optimizer is None and engine:
        _db_optimizer = DatabaseOptimizer(engine)
        _db_optimizer.initialize_optimizations()
    
    return _db_optimizer


# SQL query templates for common operations
OPTIMIZED_QUERIES = {
    'user_monthly_spending': """
        SELECT 
            EXTRACT(YEAR FROM date) as year,
            EXTRACT(MONTH FROM date) as month,
            SUM(amount) as total_spending,
            COUNT(*) as transaction_count,
            AVG(amount) as avg_transaction
        FROM expenses
        WHERE user_id = :user_id
            AND date >= :start_date
            AND date <= :end_date
        GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
        ORDER BY year DESC, month DESC
    """,
    
    'category_spending_trends': """
        WITH monthly_category_totals AS (
            SELECT 
                category,
                DATE_TRUNC('month', date) as month,
                SUM(amount) as monthly_total
            FROM expenses
            WHERE user_id = :user_id
                AND date >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY category, DATE_TRUNC('month', date)
        )
        SELECT 
            category,
            month,
            monthly_total,
            LAG(monthly_total) OVER (PARTITION BY category ORDER BY month) as prev_month,
            CASE 
                WHEN LAG(monthly_total) OVER (PARTITION BY category ORDER BY month) IS NULL THEN 0
                ELSE ((monthly_total - LAG(monthly_total) OVER (PARTITION BY category ORDER BY month)) / 
                      LAG(monthly_total) OVER (PARTITION BY category ORDER BY month)) * 100
            END as growth_rate
        FROM monthly_category_totals
        ORDER BY category, month DESC
    """,
    
    'spending_anomaly_detection': """
        WITH category_stats AS (
            SELECT 
                category,
                AVG(amount) as avg_amount,
                STDDEV(amount) as stddev_amount,
                COUNT(*) as total_transactions
            FROM expenses
            WHERE user_id = :user_id
                AND date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY category
            HAVING COUNT(*) >= 5  -- Only categories with enough data
        )
        SELECT 
            e.id,
            e.amount,
            e.category,
            e.date,
            e.description,
            cs.avg_amount,
            ROUND((e.amount - cs.avg_amount) / NULLIF(cs.stddev_amount, 0), 2) as z_score,
            CASE 
                WHEN ABS((e.amount - cs.avg_amount) / NULLIF(cs.stddev_amount, 0)) > 2 THEN 'high'
                WHEN ABS((e.amount - cs.avg_amount) / NULLIF(cs.stddev_amount, 0)) > 1.5 THEN 'medium'
                ELSE 'low'
            END as anomaly_severity
        FROM expenses e
        JOIN category_stats cs ON e.category = cs.category
        WHERE e.user_id = :user_id
            AND e.date >= CURRENT_DATE - INTERVAL '30 days'
            AND ABS((e.amount - cs.avg_amount) / NULLIF(cs.stddev_amount, 0)) > 1.5
        ORDER BY ABS((e.amount - cs.avg_amount) / NULLIF(cs.stddev_amount, 0)) DESC
        LIMIT 10
    """
}
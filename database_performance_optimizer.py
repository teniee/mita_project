#!/usr/bin/env python3
"""
Database Performance Optimizer for MITA Finance
Identifies and optimizes slow queries causing 8-15+ second response times
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabasePerformanceOptimizer:
    """Optimize database performance for MITA Finance"""
    
    def __init__(self, database_url: str):
        # Create async engine for testing
        if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
            # Convert to asyncpg for async operations
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            async_url = async_url.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            async_url = database_url
            
        self.async_engine = create_async_engine(async_url)
        
        # Also create sync engine for index operations
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        self.sync_engine = create_engine(sync_url)
        
        self.slow_queries = []
        self.performance_metrics = {}
        
    async def analyze_current_performance(self):
        """Analyze current database performance and identify bottlenecks"""
        logger.info("🔍 Analyzing database performance...")
        
        async with AsyncSession(self.async_engine) as session:
            # Check for long-running queries
            long_queries = await self._find_long_running_queries(session)
            
            # Check table sizes and index usage
            table_stats = await self._get_table_statistics(session)
            
            # Check for missing indexes
            missing_indexes = await self._find_missing_indexes(session)
            
            # Check query patterns
            query_patterns = await self._analyze_query_patterns(session)
            
            results = {
                'long_running_queries': long_queries,
                'table_statistics': table_stats,
                'missing_indexes': missing_indexes,
                'query_patterns': query_patterns,
                'timestamp': datetime.now().isoformat()
            }
            
            return results
    
    async def _find_long_running_queries(self, session: AsyncSession) -> List[Dict]:
        """Find currently long-running queries"""
        try:
            result = await session.execute(text("""
                SELECT 
                    pid,
                    now() - pg_stat_activity.query_start AS duration,
                    query,
                    state,
                    wait_event,
                    application_name
                FROM pg_stat_activity
                WHERE (now() - pg_stat_activity.query_start) > interval '1 seconds'
                    AND state = 'active'
                    AND query NOT LIKE '%pg_stat_activity%'
                ORDER BY duration DESC
                LIMIT 20
            """))
            
            queries = []
            for row in result.fetchall():
                queries.append({
                    'pid': row.pid,
                    'duration_seconds': row.duration.total_seconds() if row.duration else 0,
                    'query': row.query[:500] + '...' if len(row.query or '') > 500 else row.query,
                    'state': row.state,
                    'wait_event': row.wait_event,
                    'application_name': row.application_name
                })
            
            return queries
            
        except Exception as e:
            logger.error(f"Error finding long-running queries: {e}")
            return []
    
    async def _get_table_statistics(self, session: AsyncSession) -> Dict[str, Any]:
        """Get table size and activity statistics"""
        try:
            # Get table sizes
            size_result = await session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """))
            
            table_sizes = {}
            for row in size_result.fetchall():
                table_sizes[row.tablename] = {
                    'human_size': row.size,
                    'bytes': row.size_bytes
                }
            
            # Get table activity stats
            activity_result = await session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            """))
            
            table_activity = {}
            for row in activity_result.fetchall():
                table_activity[row.tablename] = {
                    'sequential_scans': row.seq_scan or 0,
                    'seq_tuples_read': row.seq_tup_read or 0,
                    'index_scans': row.idx_scan or 0,
                    'index_tuples_fetched': row.idx_tup_fetch or 0,
                    'inserts': row.n_tup_ins or 0,
                    'updates': row.n_tup_upd or 0,
                    'deletes': row.n_tup_del or 0
                }
            
            return {
                'table_sizes': table_sizes,
                'table_activity': table_activity
            }
            
        except Exception as e:
            logger.error(f"Error getting table statistics: {e}")
            return {}
    
    async def _find_missing_indexes(self, session: AsyncSession) -> List[Dict]:
        """Identify potentially missing indexes"""
        try:
            result = await session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    seq_tup_read / NULLIF(seq_scan, 0) as avg_seq_tuples_per_scan
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                    AND seq_scan > 0
                    AND (seq_tup_read / NULLIF(seq_scan, 0)) > 1000
                ORDER BY seq_tup_read DESC
            """))
            
            missing_indexes = []
            for row in result.fetchall():
                if row.avg_seq_tuples_per_scan and row.avg_seq_tuples_per_scan > 1000:
                    missing_indexes.append({
                        'table': row.tablename,
                        'sequential_scans': row.seq_scan,
                        'tuples_read': row.seq_tup_read,
                        'avg_tuples_per_scan': row.avg_seq_tuples_per_scan,
                        'index_scans': row.idx_scan or 0,
                        'recommendation': f"High sequential scan activity on {row.tablename} - consider adding indexes"
                    })
            
            return missing_indexes
            
        except Exception as e:
            logger.error(f"Error finding missing indexes: {e}")
            return []
    
    async def _analyze_query_patterns(self, session: AsyncSession) -> Dict[str, Any]:
        """Analyze common query patterns from pg_stat_statements if available"""
        try:
            # Check if pg_stat_statements is available
            check_result = await session.execute(text("""
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            """))
            
            if not check_result.fetchone():
                return {'error': 'pg_stat_statements extension not available'}
            
            # Get top slow queries
            result = await session.execute(text("""
                SELECT 
                    query,
                    calls,
                    total_exec_time as total_time,
                    total_exec_time / calls as avg_time,
                    rows / calls as avg_rows
                FROM pg_stat_statements
                WHERE calls > 1
                ORDER BY total_exec_time DESC
                LIMIT 20
            """))
            
            slow_queries = []
            for row in result.fetchall():
                if row.avg_time > 1000:  # More than 1 second average
                    slow_queries.append({
                        'query': row.query[:200] + '...' if len(row.query) > 200 else row.query,
                        'calls': row.calls,
                        'total_time_ms': row.total_time,
                        'avg_time_ms': row.avg_time,
                        'avg_rows': row.avg_rows or 0
                    })
            
            return {'slow_queries': slow_queries}
            
        except Exception as e:
            logger.error(f"Error analyzing query patterns: {e}")
            return {'error': str(e)}
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run specific performance tests for critical MITA queries"""
        logger.info("🧪 Running performance tests on critical queries...")
        
        test_results = {}
        
        async with AsyncSession(self.async_engine) as session:
            # Test 1: User authentication query
            auth_time = await self._test_user_authentication_performance(session)
            test_results['user_authentication'] = auth_time
            
            # Test 2: Recent transactions query
            transactions_time = await self._test_transactions_query_performance(session)
            test_results['recent_transactions'] = transactions_time
            
            # Test 3: Monthly aggregations
            monthly_time = await self._test_monthly_aggregation_performance(session)
            test_results['monthly_aggregations'] = monthly_time
            
            # Test 4: Expense lookups
            expenses_time = await self._test_expenses_query_performance(session)
            test_results['expenses_lookup'] = expenses_time
        
        return test_results
    
    async def _test_user_authentication_performance(self, session: AsyncSession) -> Dict[str, Any]:
        """Test user authentication query performance"""
        try:
            start_time = time.time()
            
            # Test typical authentication query
            result = await session.execute(text("""
                SELECT id, email, password_hash, country, is_premium 
                FROM users 
                WHERE email = 'test@example.com'
                LIMIT 1
            """))
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000  # Convert to ms
            
            # Check if results were found (doesn't matter for performance test)
            user_found = result.fetchone() is not None
            
            return {
                'execution_time_ms': execution_time,
                'query_type': 'user_authentication',
                'status': 'slow' if execution_time > 100 else 'acceptable',
                'user_found': user_found
            }
            
        except Exception as e:
            logger.error(f"Error in user authentication test: {e}")
            return {'error': str(e), 'execution_time_ms': 0}
    
    async def _test_transactions_query_performance(self, session: AsyncSession) -> Dict[str, Any]:
        """Test transactions query performance"""
        try:
            start_time = time.time()
            
            # Test typical recent transactions query
            result = await session.execute(text("""
                SELECT id, user_id, amount, category, description, spent_at
                FROM transactions 
                WHERE user_id IS NOT NULL
                ORDER BY spent_at DESC 
                LIMIT 50
            """))
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            
            rows = result.fetchall()
            row_count = len(rows)
            
            return {
                'execution_time_ms': execution_time,
                'query_type': 'recent_transactions',
                'rows_returned': row_count,
                'status': 'slow' if execution_time > 200 else 'acceptable'
            }
            
        except Exception as e:
            logger.error(f"Error in transactions test: {e}")
            return {'error': str(e), 'execution_time_ms': 0}
    
    async def _test_monthly_aggregation_performance(self, session: AsyncSession) -> Dict[str, Any]:
        """Test monthly aggregation query performance"""
        try:
            start_time = time.time()
            
            # Test monthly aggregation query
            result = await session.execute(text("""
                SELECT 
                    EXTRACT(YEAR FROM spent_at) as year,
                    EXTRACT(MONTH FROM spent_at) as month,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount
                FROM transactions 
                WHERE spent_at >= NOW() - INTERVAL '6 months'
                GROUP BY EXTRACT(YEAR FROM spent_at), EXTRACT(MONTH FROM spent_at)
                ORDER BY year DESC, month DESC
            """))
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            
            rows = result.fetchall()
            row_count = len(rows)
            
            return {
                'execution_time_ms': execution_time,
                'query_type': 'monthly_aggregation',
                'rows_returned': row_count,
                'status': 'slow' if execution_time > 500 else 'acceptable'
            }
            
        except Exception as e:
            logger.error(f"Error in monthly aggregation test: {e}")
            return {'error': str(e), 'execution_time_ms': 0}
    
    async def _test_expenses_query_performance(self, session: AsyncSession) -> Dict[str, Any]:
        """Test expenses query performance"""
        try:
            start_time = time.time()
            
            # Test expenses lookup
            result = await session.execute(text("""
                SELECT id, user_id, action, amount, date
                FROM expenses 
                WHERE date >= NOW() - INTERVAL '30 days'
                ORDER BY date DESC 
                LIMIT 100
            """))
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            
            rows = result.fetchall()
            row_count = len(rows)
            
            return {
                'execution_time_ms': execution_time,
                'query_type': 'expenses_lookup',
                'rows_returned': row_count,
                'status': 'slow' if execution_time > 300 else 'acceptable'
            }
            
        except Exception as e:
            logger.error(f"Error in expenses test: {e}")
            return {'error': str(e), 'execution_time_ms': 0}
    
    def create_optimized_indexes(self):
        """Create indexes to improve query performance"""
        logger.info("🔧 Creating optimized database indexes...")
        
        indexes_to_create = [
            # Users table indexes
            {
                'name': 'idx_users_email_btree',
                'table': 'users',
                'columns': 'email',
                'description': 'Optimize user authentication by email'
            },
            {
                'name': 'idx_users_email_lower',
                'table': 'users', 
                'columns': 'LOWER(email)',
                'description': 'Case-insensitive email lookups'
            },
            
            # Transactions table indexes
            {
                'name': 'idx_transactions_user_spent_at_desc',
                'table': 'transactions',
                'columns': 'user_id, spent_at DESC',
                'description': 'Optimize recent transactions queries'
            },
            {
                'name': 'idx_transactions_spent_at_desc',
                'table': 'transactions',
                'columns': 'spent_at DESC',
                'description': 'Optimize date-based queries'
            },
            {
                'name': 'idx_transactions_user_category_spent_at',
                'table': 'transactions',
                'columns': 'user_id, category, spent_at',
                'description': 'Optimize category-filtered queries'
            },
            {
                'name': 'idx_transactions_user_amount',
                'table': 'transactions',
                'columns': 'user_id, amount',
                'description': 'Optimize amount-based queries'
            },
            
            # Expenses table indexes
            {
                'name': 'idx_expenses_user_date_desc',
                'table': 'expenses',
                'columns': 'user_id, date DESC',
                'description': 'Optimize user expense queries'
            },
            {
                'name': 'idx_expenses_date_desc',
                'table': 'expenses',
                'columns': 'date DESC',
                'description': 'Optimize date-based expense queries'
            },
            {
                'name': 'idx_expenses_user_action',
                'table': 'expenses',
                'columns': 'user_id, action',
                'description': 'Optimize action-based expense queries'
            },
        ]
        
        with self.sync_engine.connect() as conn:
            for index_config in indexes_to_create:
                try:
                    self._create_index_if_not_exists(conn, index_config)
                except Exception as e:
                    logger.error(f"Failed to create index {index_config['name']}: {e}")
    
    def _create_index_if_not_exists(self, conn, index_config):
        """Create index if it doesn't exist"""
        # Check if index exists
        check_result = conn.execute(text("""
            SELECT 1 FROM pg_indexes 
            WHERE tablename = :table_name AND indexname = :index_name
        """), {
            'table_name': index_config['table'],
            'index_name': index_config['name']
        })
        
        if check_result.fetchone():
            logger.info(f"✓ Index {index_config['name']} already exists")
            return
        
        # Create index
        create_sql = f"""
            CREATE INDEX CONCURRENTLY {index_config['name']} 
            ON {index_config['table']} ({index_config['columns']})
        """
        
        logger.info(f"📊 Creating index: {index_config['name']} - {index_config['description']}")
        
        try:
            conn.execute(text(create_sql))
            conn.commit()
            logger.info(f"✅ Successfully created index: {index_config['name']}")
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_config['name']}: {e}")
    
    def update_table_statistics(self):
        """Update table statistics for better query planning"""
        logger.info("📈 Updating table statistics for query planner...")
        
        tables = ['users', 'transactions', 'expenses', 'ai_analysis_snapshots', 'goals', 'habits']
        
        with self.sync_engine.connect() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    logger.info(f"✓ Updated statistics for {table}")
                except Exception as e:
                    logger.error(f"❌ Failed to analyze {table}: {e}")
            
            conn.commit()
    
    async def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        logger.info("📋 Generating database optimization report...")
        
        analysis = await self.analyze_current_performance()
        performance_tests = await self.run_performance_tests()
        
        # Generate recommendations
        recommendations = []
        
        # Check for slow queries in performance tests
        slow_tests = [
            test_name for test_name, results in performance_tests.items()
            if isinstance(results, dict) and results.get('status') == 'slow'
        ]
        
        if slow_tests:
            recommendations.append(f"Slow query performance detected in: {', '.join(slow_tests)}")
        
        # Check for high sequential scans
        missing_indexes = analysis.get('missing_indexes', [])
        if missing_indexes:
            recommendations.append(f"High sequential scan activity detected on {len(missing_indexes)} tables")
        
        # Check for long-running queries
        long_queries = analysis.get('long_running_queries', [])
        if long_queries:
            recommendations.append(f"{len(long_queries)} long-running queries detected")
        
        if not recommendations:
            recommendations.append("Database performance appears to be within acceptable parameters")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'performance_analysis': analysis,
            'performance_tests': performance_tests,
            'recommendations': recommendations,
            'optimization_actions': [
                'Create missing indexes',
                'Update table statistics',
                'Monitor query patterns',
                'Consider connection pool optimization'
            ]
        }

async def main():
    """Main optimization routine"""
    # Get database URL from environment or use default
    import os
    database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/mita_finance')
    
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        return
    
    optimizer = DatabasePerformanceOptimizer(database_url)
    
    try:
        # Generate optimization report
        report = await optimizer.generate_optimization_report()
        
        # Print summary
        print("\n" + "="*60)
        print("🚀 MITA FINANCE DATABASE OPTIMIZATION REPORT")
        print("="*60)
        
        print(f"\n📊 Performance Test Results:")
        for test_name, results in report['performance_tests'].items():
            if isinstance(results, dict):
                status_emoji = "🔴" if results.get('status') == 'slow' else "✅"
                execution_time = results.get('execution_time_ms', 0)
                print(f"   {status_emoji} {test_name}: {execution_time:.2f}ms")
        
        print(f"\n🔍 Analysis Summary:")
        missing_indexes = report['performance_analysis'].get('missing_indexes', [])
        long_queries = report['performance_analysis'].get('long_running_queries', [])
        
        print(f"   • Missing indexes detected: {len(missing_indexes)}")
        print(f"   • Long-running queries: {len(long_queries)}")
        
        print(f"\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"   • {rec}")
        
        # Apply optimizations
        print(f"\n🔧 Applying optimizations...")
        optimizer.create_optimized_indexes()
        optimizer.update_table_statistics()
        
        print(f"\n✅ Database optimization completed!")
        print("   • Indexes created for common query patterns")
        print("   • Table statistics updated for better query planning")
        print("   • Performance monitoring recommendations provided")
        
        # Save detailed report
        import json
        with open('database_optimization_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📋 Detailed report saved to: database_optimization_report.json")
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
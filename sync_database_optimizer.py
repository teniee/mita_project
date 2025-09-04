#!/usr/bin/env python3
"""
Synchronous Database Performance Optimizer for MITA Finance
Identifies and optimizes slow queries causing 8-15+ second response times
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extras import RealDictCursor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SyncDatabaseOptimizer:
    """Synchronous database optimizer for MITA Finance"""
    
    def __init__(self, database_url: str):
        # Create SQLAlchemy engine
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        self.engine = create_engine(sync_url)
        
        # Extract connection parameters for direct psycopg2 connection
        self.db_params = self._parse_database_url(database_url)
        
    def _parse_database_url(self, url: str) -> dict:
        """Parse database URL into connection parameters"""
        # Simple URL parsing - in production you'd use urllib.parse
        import re
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://"))
        if match:
            return {
                'user': match.group(1),
                'password': match.group(2), 
                'host': match.group(3),
                'port': int(match.group(4)),
                'database': match.group(5)
            }
        return {}
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze database performance"""
        logger.info("🔍 Analyzing database performance...")
        
        results = {}
        
        try:
            with self.engine.connect() as conn:
                # Check table sizes
                results['table_sizes'] = self._get_table_sizes(conn)
                
                # Check index usage
                results['index_usage'] = self._get_index_usage_stats(conn)
                
                # Check for sequential scans
                results['sequential_scans'] = self._find_high_sequential_scans(conn)
                
                # Get current active queries
                results['active_queries'] = self._get_active_queries(conn)
                
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
            results['error'] = str(e)
        
        return results
    
    def _get_table_sizes(self, conn) -> List[Dict]:
        """Get table sizes"""
        try:
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_relation_size(schemaname||'.'||tablename) as table_size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """))
            
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting table sizes: {e}")
            return []
    
    def _get_index_usage_stats(self, conn) -> List[Dict]:
        """Get index usage statistics"""
        try:
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as times_used,
                    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
                    pg_relation_size(indexname::regclass) as index_size_bytes
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """))
            
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting index usage stats: {e}")
            return []
    
    def _find_high_sequential_scans(self, conn) -> List[Dict]:
        """Find tables with high sequential scan activity"""
        try:
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch,
                    CASE 
                        WHEN seq_scan > 0 THEN (seq_tup_read::float / seq_scan)
                        ELSE 0
                    END as avg_seq_read
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                    AND seq_scan > 0
                ORDER BY seq_scan DESC, seq_tup_read DESC
            """))
            
            high_seq_scans = []
            for row in result.fetchall():
                row_dict = dict(row._mapping)
                if row_dict['avg_seq_read'] > 1000:  # More than 1000 rows per scan
                    row_dict['recommendation'] = 'Consider adding indexes - high sequential scan activity'
                    high_seq_scans.append(row_dict)
            
            return high_seq_scans
        except Exception as e:
            logger.error(f"Error finding sequential scans: {e}")
            return []
    
    def _get_active_queries(self, conn) -> List[Dict]:
        """Get currently active queries"""
        try:
            result = conn.execute(text("""
                SELECT 
                    pid,
                    state,
                    query_start,
                    NOW() - query_start as duration,
                    query,
                    application_name
                FROM pg_stat_activity
                WHERE state = 'active'
                    AND query NOT LIKE '%pg_stat_activity%'
                    AND pid <> pg_backend_pid()
                ORDER BY query_start
            """))
            
            active_queries = []
            for row in result.fetchall():
                row_dict = dict(row._mapping)
                # Truncate long queries
                if row_dict['query'] and len(row_dict['query']) > 200:
                    row_dict['query'] = row_dict['query'][:200] + '...'
                active_queries.append(row_dict)
            
            return active_queries
        except Exception as e:
            logger.error(f"Error getting active queries: {e}")
            return []
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance tests on critical queries"""
        logger.info("🧪 Running performance tests...")
        
        test_results = {}
        
        with self.engine.connect() as conn:
            # Test 1: User authentication query
            test_results['user_auth'] = self._test_user_auth_performance(conn)
            
            # Test 2: Recent transactions
            test_results['recent_transactions'] = self._test_transactions_performance(conn)
            
            # Test 3: Expenses query
            test_results['expenses_query'] = self._test_expenses_performance(conn)
            
            # Test 4: Monthly aggregations
            test_results['monthly_aggregations'] = self._test_monthly_agg_performance(conn)
        
        return test_results
    
    def _test_user_auth_performance(self, conn) -> Dict[str, Any]:
        """Test user authentication query performance"""
        try:
            query = "SELECT id, email, password_hash FROM users WHERE email = %s LIMIT 1"
            
            start_time = time.time()
            result = conn.execute(text("SELECT id, email, password_hash FROM users WHERE email = 'nonexistent@test.com' LIMIT 1"))
            end_time = time.time()
            
            execution_time_ms = (end_time - start_time) * 1000
            
            return {
                'execution_time_ms': execution_time_ms,
                'query_type': 'user_authentication',
                'status': 'slow' if execution_time_ms > 100 else 'acceptable',
                'target_ms': 50
            }
        except Exception as e:
            return {'error': str(e), 'execution_time_ms': 0}
    
    def _test_transactions_performance(self, conn) -> Dict[str, Any]:
        """Test transaction queries performance"""
        try:
            start_time = time.time()
            result = conn.execute(text("""
                SELECT id, user_id, amount, category, description, spent_at
                FROM transactions 
                ORDER BY spent_at DESC 
                LIMIT 50
            """))
            end_time = time.time()
            
            execution_time_ms = (end_time - start_time) * 1000
            row_count = result.rowcount if result.rowcount else 0
            
            return {
                'execution_time_ms': execution_time_ms,
                'query_type': 'recent_transactions',
                'rows_returned': row_count,
                'status': 'slow' if execution_time_ms > 200 else 'acceptable',
                'target_ms': 100
            }
        except Exception as e:
            return {'error': str(e), 'execution_time_ms': 0}
    
    def _test_expenses_performance(self, conn) -> Dict[str, Any]:
        """Test expenses query performance"""
        try:
            start_time = time.time()
            result = conn.execute(text("""
                SELECT id, user_id, action, amount, date
                FROM expenses 
                ORDER BY date DESC 
                LIMIT 100
            """))
            end_time = time.time()
            
            execution_time_ms = (end_time - start_time) * 1000
            row_count = result.rowcount if result.rowcount else 0
            
            return {
                'execution_time_ms': execution_time_ms,
                'query_type': 'expenses_lookup',
                'rows_returned': row_count,
                'status': 'slow' if execution_time_ms > 300 else 'acceptable',
                'target_ms': 150
            }
        except Exception as e:
            return {'error': str(e), 'execution_time_ms': 0}
    
    def _test_monthly_agg_performance(self, conn) -> Dict[str, Any]:
        """Test monthly aggregation performance"""
        try:
            start_time = time.time()
            result = conn.execute(text("""
                SELECT 
                    EXTRACT(YEAR FROM spent_at) as year,
                    EXTRACT(MONTH FROM spent_at) as month,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount
                FROM transactions 
                WHERE spent_at >= NOW() - INTERVAL '6 months'
                GROUP BY EXTRACT(YEAR FROM spent_at), EXTRACT(MONTH FROM spent_at)
                ORDER BY year DESC, month DESC
            """))
            end_time = time.time()
            
            execution_time_ms = (end_time - start_time) * 1000
            row_count = result.rowcount if result.rowcount else 0
            
            return {
                'execution_time_ms': execution_time_ms,
                'query_type': 'monthly_aggregation',
                'rows_returned': row_count,
                'status': 'slow' if execution_time_ms > 500 else 'acceptable',
                'target_ms': 250
            }
        except Exception as e:
            return {'error': str(e), 'execution_time_ms': 0}
    
    def create_performance_indexes(self):
        """Create indexes to improve performance"""
        logger.info("🔧 Creating performance indexes...")
        
        indexes = [
            # Users table
            {
                'name': 'idx_users_email_btree',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_btree ON users (email)'
            },
            {
                'name': 'idx_users_email_lower',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_lower ON users (LOWER(email))'
            },
            
            # Transactions table
            {
                'name': 'idx_transactions_spent_at_desc',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_spent_at_desc ON transactions (spent_at DESC)'
            },
            {
                'name': 'idx_transactions_user_spent_at_desc',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_spent_at_desc ON transactions (user_id, spent_at DESC)'
            },
            {
                'name': 'idx_transactions_user_category',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_category ON transactions (user_id, category)'
            },
            
            # Expenses table
            {
                'name': 'idx_expenses_date_desc',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_date_desc ON expenses (date DESC)'
            },
            {
                'name': 'idx_expenses_user_date_desc',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date_desc ON expenses (user_id, date DESC)'
            },
            {
                'name': 'idx_expenses_user_action',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_action ON expenses (user_id, action)'
            }
        ]
        
        created_count = 0
        failed_count = 0
        
        with self.engine.connect() as conn:
            for index in indexes:
                try:
                    # First check if index exists
                    check_result = conn.execute(text("""
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = :index_name
                    """), {'index_name': index['name']})
                    
                    if check_result.fetchone():
                        logger.info(f"✓ Index {index['name']} already exists")
                        continue
                    
                    # Create index
                    logger.info(f"📊 Creating index: {index['name']}")
                    conn.execute(text(index['sql']))
                    conn.commit()
                    created_count += 1
                    logger.info(f"✅ Successfully created index: {index['name']}")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Failed to create index {index['name']}: {e}")
        
        logger.info(f"Index creation summary: {created_count} created, {failed_count} failed")
    
    def update_table_statistics(self):
        """Update table statistics for query planner"""
        logger.info("📈 Updating table statistics...")
        
        tables = ['users', 'transactions', 'expenses', 'ai_analysis_snapshots', 'goals']
        updated_count = 0
        
        with self.engine.connect() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    conn.commit()
                    updated_count += 1
                    logger.info(f"✓ Updated statistics for {table}")
                except Exception as e:
                    logger.error(f"❌ Failed to analyze {table}: {e}")
        
        logger.info(f"Updated statistics for {updated_count} tables")
    
    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        logger.info("📋 Generating optimization report...")
        
        # Run analysis
        analysis = self.analyze_performance()
        performance_tests = self.run_performance_tests()
        
        # Generate recommendations
        recommendations = []
        
        # Check performance test results
        slow_tests = []
        for test_name, result in performance_tests.items():
            if isinstance(result, dict) and result.get('status') == 'slow':
                execution_time = result.get('execution_time_ms', 0)
                target = result.get('target_ms', 0)
                slow_tests.append(f"{test_name} ({execution_time:.1f}ms, target: {target}ms)")
        
        if slow_tests:
            recommendations.append(f"Slow queries detected: {', '.join(slow_tests)}")
        
        # Check sequential scans
        seq_scans = analysis.get('sequential_scans', [])
        high_seq_tables = [s['tablename'] for s in seq_scans if s.get('avg_seq_read', 0) > 5000]
        if high_seq_tables:
            recommendations.append(f"High sequential scan activity on tables: {', '.join(high_seq_tables)}")
        
        # Check table sizes
        table_sizes = analysis.get('table_sizes', [])
        large_tables = [t['tablename'] for t in table_sizes if t.get('size_bytes', 0) > 100 * 1024 * 1024]  # > 100MB
        if large_tables:
            recommendations.append(f"Large tables may benefit from partitioning: {', '.join(large_tables)}")
        
        if not recommendations:
            recommendations.append("Database performance appears to be within acceptable parameters")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'performance_analysis': analysis,
            'performance_tests': performance_tests,
            'recommendations': recommendations,
            'slow_query_count': len(slow_tests),
            'high_seq_scan_tables': len(seq_scans)
        }

def main():
    """Main optimization routine"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Try common development URLs
        possible_urls = [
            'postgresql://localhost/mita_finance',
            'postgresql://localhost/postgres',
            'postgresql://postgres:postgres@localhost/mita_finance'
        ]
        
        for url in possible_urls:
            try:
                optimizer = SyncDatabaseOptimizer(url)
                test_conn = optimizer.engine.connect()
                test_conn.close()
                database_url = url
                logger.info(f"✓ Connected to database: {url}")
                break
            except:
                continue
    
    if not database_url:
        logger.error("❌ Could not connect to any database. Please set DATABASE_URL environment variable.")
        return
    
    optimizer = SyncDatabaseOptimizer(database_url)
    
    try:
        # Generate report
        report = optimizer.generate_optimization_report()
        
        # Print results
        print("\n" + "="*70)
        print("🚀 MITA FINANCE DATABASE OPTIMIZATION REPORT")
        print("="*70)
        
        print(f"\n📊 Performance Test Results:")
        for test_name, results in report['performance_tests'].items():
            if isinstance(results, dict) and 'execution_time_ms' in results:
                status_emoji = "🔴" if results.get('status') == 'slow' else "✅"
                execution_time = results['execution_time_ms']
                target = results.get('target_ms', 0)
                print(f"   {status_emoji} {test_name}: {execution_time:.1f}ms (target: {target}ms)")
            elif isinstance(results, dict) and 'error' in results:
                print(f"   ❌ {test_name}: Error - {results['error']}")
        
        print(f"\n🔍 Database Analysis:")
        analysis = report['performance_analysis']
        
        # Table sizes
        table_sizes = analysis.get('table_sizes', [])
        if table_sizes:
            print(f"   📋 Largest tables:")
            for table in table_sizes[:5]:
                print(f"      • {table['tablename']}: {table['size']}")
        
        # Sequential scans
        seq_scans = analysis.get('sequential_scans', [])
        if seq_scans:
            print(f"   🔍 Tables with high sequential scan activity:")
            for table in seq_scans[:3]:
                print(f"      • {table['tablename']}: {table['seq_scan']} scans, {table['avg_seq_read']:.0f} avg rows/scan")
        
        print(f"\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"   • {rec}")
        
        # Apply optimizations
        print(f"\n🔧 Applying optimizations...")
        optimizer.create_performance_indexes()
        optimizer.update_table_statistics()
        
        print(f"\n✅ Database optimization completed!")
        
        # Save report
        import json
        with open('database_optimization_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📋 Detailed report saved: database_optimization_report.json")
        
    except Exception as e:
        logger.error(f"❌ Optimization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
"""
Database Indexing Strategy for MITA
Comprehensive indexing plan for optimal query performance
"""

from sqlalchemy import Index, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import logging

from app.core.async_session import get_async_db_context

logger = logging.getLogger(__name__)


class DatabaseIndexManager:
    """Manages database indexes for optimal performance"""
    
    def __init__(self):
        # Define critical indexes based on common query patterns
        self.critical_indexes = [
            # User table indexes
            {
                'name': 'idx_users_email_lower',
                'table': 'users',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_lower ON users (LOWER(email))',
                'description': 'Case-insensitive email lookup for authentication'
            },
            {
                'name': 'idx_users_is_premium',
                'table': 'users', 
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_is_premium ON users (is_premium)',
                'description': 'Filter premium users efficiently'
            },
            {
                'name': 'idx_users_premium_until',
                'table': 'users',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_premium_until ON users (premium_until) WHERE premium_until IS NOT NULL',
                'description': 'Find expiring premium subscriptions'
            },
            {
                'name': 'idx_users_created_at',
                'table': 'users',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at ON users (created_at)',
                'description': 'User registration date analysis'
            },
            
            # Transaction table indexes  
            {
                'name': 'idx_transactions_user_spent_at',
                'table': 'transactions',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_spent_at ON transactions (user_id, spent_at DESC)',
                'description': 'User transactions ordered by date (most common query)'
            },
            {
                'name': 'idx_transactions_user_category',
                'table': 'transactions', 
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_category ON transactions (user_id, category)',
                'description': 'Category-based transaction filtering'
            },
            {
                'name': 'idx_transactions_user_amount',
                'table': 'transactions',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_amount ON transactions (user_id, amount DESC)',
                'description': 'Largest transactions analysis'
            },
            {
                'name': 'idx_transactions_category_spent_at',
                'table': 'transactions',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_category_spent_at ON transactions (category, spent_at)',
                'description': 'Category trends over time'
            },
            
            # Expense table indexes
            {
                'name': 'idx_expenses_user_date',
                'table': 'expenses',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date ON expenses (user_id, date DESC)',
                'description': 'User expenses by date (primary query pattern)'
            },
            {
                'name': 'idx_expenses_user_action_date',
                'table': 'expenses',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_action_date ON expenses (user_id, action, date DESC)',
                'description': 'Expense action filtering with date ordering'
            },
            {
                'name': 'idx_expenses_date_amount',
                'table': 'expenses',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_date_amount ON expenses (date, amount DESC)',
                'description': 'Daily spending analysis'
            },
            
            # Goal table indexes
            {
                'name': 'idx_goals_user_status',
                'table': 'goals',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_status ON goals (user_id, status)',
                'description': 'Filter goals by status (active, completed, paused)'
            },
            {
                'name': 'idx_goals_user_target_date',
                'table': 'goals',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_target_date ON goals (user_id, target_date) WHERE status = \'active\'',
                'description': 'Find upcoming/overdue active goals'
            },
            {
                'name': 'idx_goals_user_category',
                'table': 'goals',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_category ON goals (user_id, category)',
                'description': 'Goals by category analysis'
            },
            {
                'name': 'idx_goals_user_progress',
                'table': 'goals',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_progress ON goals (user_id, progress DESC) WHERE status = \'active\'',
                'description': 'Near-completion goals identification'
            },
            
            # Budget Advice table indexes
            {
                'name': 'idx_budget_advice_user_date',
                'table': 'budget_advice',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_budget_advice_user_date ON budget_advice (user_id, date DESC)',
                'description': 'Recent advice retrieval'
            },
            {
                'name': 'idx_budget_advice_user_type',
                'table': 'budget_advice',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_budget_advice_user_type ON budget_advice (user_id, type)',
                'description': 'Advice filtering by type'
            },
            
            # Daily Plan table indexes
            {
                'name': 'idx_daily_plan_user_date',
                'table': 'daily_plan',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_plan_user_date ON daily_plan (user_id, date DESC)',
                'description': 'Daily plan retrieval by date'
            },
            
            # Mood table indexes
            {
                'name': 'idx_mood_user_date_unique',
                'table': 'mood',
                'sql': 'CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_mood_user_date_unique ON mood (user_id, date)',
                'description': 'Ensure one mood entry per user per date'
            },
            
            # Habit table indexes
            {
                'name': 'idx_habits_user_active',
                'table': 'habit',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_habits_user_active ON habit (user_id, is_active) WHERE is_active = true',
                'description': 'Active habits for daily tracking'
            },
            
            # AI Analysis Snapshot indexes
            {
                'name': 'idx_ai_snapshots_user_created_at',
                'table': 'ai_analysis_snapshots',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_snapshots_user_created_at ON ai_analysis_snapshots (user_id, created_at DESC)',
                'description': 'Recent AI analysis retrieval'
            },
            
            # Notification Log indexes
            {
                'name': 'idx_notification_log_user_sent_at',
                'table': 'notification_log',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_log_user_sent_at ON notification_log (user_id, sent_at DESC)',
                'description': 'Recent notifications tracking'
            },
            {
                'name': 'idx_notification_log_user_channel',
                'table': 'notification_log', 
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_log_user_channel ON notification_log (user_id, channel)',
                'description': 'Notification channel filtering'
            },
            
            # Push Token indexes
            {
                'name': 'idx_push_tokens_token_unique',
                'table': 'push_token',
                'sql': 'CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_push_tokens_token_unique ON push_token (token)',
                'description': 'Ensure unique push tokens'
            },
            
            # Subscription indexes
            {
                'name': 'idx_subscriptions_user_platform',
                'table': 'subscription',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_user_platform ON subscription (user_id, platform)',
                'description': 'User subscriptions by platform'
            },
            {
                'name': 'idx_subscriptions_user_active',
                'table': 'subscription',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_user_active ON subscription (user_id, is_active) WHERE is_active = true',
                'description': 'Active subscriptions only'
            }
        ]
        
        # Composite indexes for complex queries
        self.composite_indexes = [
            {
                'name': 'idx_transactions_user_date_category_amount',
                'table': 'transactions',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_date_category_amount ON transactions (user_id, spent_at, category, amount)',
                'description': 'Complex transaction analytics queries'
            },
            {
                'name': 'idx_expenses_user_date_action_amount',
                'table': 'expenses', 
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date_action_amount ON expenses (user_id, date, action, amount)',
                'description': 'Complex expense analytics queries'
            }
        ]
        
        # Full-text search indexes
        self.fulltext_indexes = [
            {
                'name': 'idx_transactions_description_fulltext',
                'table': 'transactions',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_description_fulltext ON transactions USING gin(to_tsvector(\'english\', COALESCE(description, \'\')))',
                'description': 'Full-text search on transaction descriptions'
            },
            {
                'name': 'idx_goals_title_description_fulltext',
                'table': 'goals',
                'sql': 'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_title_description_fulltext ON goals USING gin(to_tsvector(\'english\', COALESCE(title, \'\') || \' \' || COALESCE(description, \'\')))',
                'description': 'Full-text search on goal titles and descriptions'
            }
        ]
    
    async def create_all_indexes(self) -> Dict[str, Any]:
        """Create all recommended indexes"""
        results = {
            'critical_indexes': [],
            'composite_indexes': [],
            'fulltext_indexes': [],
            'errors': []
        }
        
        async with get_async_db_context() as db:
            # Create critical indexes
            for index in self.critical_indexes:
                try:
                    await db.execute(text(index['sql']))
                    await db.commit()
                    results['critical_indexes'].append({
                        'name': index['name'],
                        'status': 'created',
                        'description': index['description']
                    })
                    logger.info(f"Created index: {index['name']}")
                except Exception as e:
                    error_msg = f"Failed to create index {index['name']}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Create composite indexes
            for index in self.composite_indexes:
                try:
                    await db.execute(text(index['sql']))
                    await db.commit()
                    results['composite_indexes'].append({
                        'name': index['name'],
                        'status': 'created',
                        'description': index['description']
                    })
                    logger.info(f"Created composite index: {index['name']}")
                except Exception as e:
                    error_msg = f"Failed to create composite index {index['name']}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Create full-text indexes  
            for index in self.fulltext_indexes:
                try:
                    await db.execute(text(index['sql']))
                    await db.commit()
                    results['fulltext_indexes'].append({
                        'name': index['name'],
                        'status': 'created',
                        'description': index['description']
                    })
                    logger.info(f"Created full-text index: {index['name']}")
                except Exception as e:
                    error_msg = f"Failed to create full-text index {index['name']}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
        
        return results
    
    async def analyze_index_usage(self) -> Dict[str, Any]:
        """Analyze current index usage statistics"""
        async with get_async_db_context() as db:
            # Get index usage statistics
            usage_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes 
                ORDER BY idx_scan DESC;
            """)
            
            # Get index sizes
            size_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    pg_relation_size(indexrelid) as size_bytes
                FROM pg_stat_user_indexes
                ORDER BY pg_relation_size(indexrelid) DESC;
            """)
            
            # Get unused indexes
            unused_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes 
                WHERE idx_scan = 0
                ORDER BY pg_relation_size(indexrelid) DESC;
            """)
            
            try:
                usage_result = await db.execute(usage_query)
                size_result = await db.execute(size_query)
                unused_result = await db.execute(unused_query)
                
                return {
                    'index_usage': [dict(row._asdict()) for row in usage_result.fetchall()],
                    'index_sizes': [dict(row._asdict()) for row in size_result.fetchall()],
                    'unused_indexes': [dict(row._asdict()) for row in unused_result.fetchall()]
                }
            except Exception as e:
                logger.error(f"Error analyzing index usage: {str(e)}")
                return {'error': str(e)}
    
    async def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest queries for optimization"""
        async with get_async_db_context() as db:
            # Note: This requires pg_stat_statements extension
            query = text("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows,
                    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                FROM pg_stat_statements 
                WHERE query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_time DESC 
                LIMIT :limit;
            """)
            
            try:
                result = await db.execute(query, {'limit': limit})
                return [dict(row._asdict()) for row in result.fetchall()]
            except Exception as e:
                logger.warning(f"Could not retrieve slow queries (pg_stat_statements may not be enabled): {str(e)}")
                return []
    
    async def recommend_indexes(self) -> List[Dict[str, Any]]:
        """Generate index recommendations based on query patterns"""
        recommendations = []
        
        # Check for missing indexes on foreign key columns
        async with get_async_db_context() as db:
            fk_query = text("""
                SELECT 
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                WHERE constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public';
            """)
            
            try:
                result = await db.execute(fk_query)
                fk_columns = result.fetchall()
                
                for row in fk_columns:
                    # Check if index exists on this foreign key
                    index_check = text("""
                        SELECT COUNT(*) 
                        FROM pg_indexes 
                        WHERE tablename = :table_name 
                          AND indexdef LIKE '%' || :column_name || '%';
                    """)
                    
                    index_result = await db.execute(index_check, {
                        'table_name': row.table_name,
                        'column_name': row.column_name
                    })
                    
                    if index_result.scalar() == 0:
                        recommendations.append({
                            'type': 'foreign_key_index',
                            'table': row.table_name,
                            'column': row.column_name,
                            'priority': 'high',
                            'reason': f'Foreign key column {row.column_name} lacks index for efficient joins'
                        })
                
            except Exception as e:
                logger.error(f"Error checking foreign key indexes: {str(e)}")
        
        return recommendations


# Singleton instance
_index_manager: DatabaseIndexManager = None

def get_index_manager() -> DatabaseIndexManager:
    """Get singleton index manager instance"""
    global _index_manager
    if _index_manager is None:
        _index_manager = DatabaseIndexManager()
    return _index_manager
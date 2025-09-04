-- MITA Finance Database Performance Optimization
-- Critical Indexes for Query Performance
-- Run with: psql -d mita_finance -f create_indexes.sql

\timing on
\echo 'Creating performance indexes for MITA Finance...'

-- User authentication index (CRITICAL)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_btree 
ON users (email);

-- Case-insensitive email lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_lower 
ON users (LOWER(email));

-- Recent transactions (HIGH PRIORITY)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_spent_at_desc 
ON transactions (user_id, spent_at DESC);

-- Global transaction ordering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_spent_at_desc 
ON transactions (spent_at DESC);

-- User expense queries (HIGH PRIORITY)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date_desc 
ON expenses (user_id, date DESC);

-- Global expense date queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_date_desc 
ON expenses (date DESC);

-- AI analysis snapshots
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_snapshots_user_created_desc 
ON ai_analysis_snapshots (user_id, created_at DESC);

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_category_date 
ON transactions (user_id, category, spent_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_action_date 
ON expenses (user_id, action, date);

\echo 'Index creation completed!'
\echo 'Updating table statistics...'

-- Update table statistics for query planner
ANALYZE users;
ANALYZE transactions;
ANALYZE expenses;
ANALYZE ai_analysis_snapshots;
ANALYZE goals;
ANALYZE habits;

\echo 'Database optimization completed successfully!
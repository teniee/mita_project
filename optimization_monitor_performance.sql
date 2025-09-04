-- Performance Monitoring Queries
-- Use these to check optimization results

\echo 'Database Performance Report'
\echo '=========================='

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as times_used,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_stat_user_indexes 
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Check table sizes
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as total_size,
    pg_size_pretty(pg_relation_size(tablename::regclass)) as table_size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;

-- Check for slow queries (if pg_stat_statements is available)
SELECT 
    query,
    calls,
    total_exec_time / calls as avg_time_ms,
    total_exec_time,
    rows / calls as avg_rows
FROM pg_stat_statements 
WHERE calls > 1
ORDER BY total_exec_time DESC
LIMIT 10;
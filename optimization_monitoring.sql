-- MITA Finance Optimization Monitoring Queries
-- Run these to verify optimization effectiveness

\echo 'Database Optimization Effectiveness Report'
\echo '========================================'

-- 1. Check if critical indexes exist and are being used
\echo '1. Critical Index Usage:'
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as times_used,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_stat_user_indexes 
WHERE indexname IN (
    'idx_users_email_btree',
    'idx_transactions_user_spent_at_desc', 
    'idx_expenses_user_date_desc',
    'idx_ai_snapshots_user_created_desc'
)
ORDER BY times_used DESC;

-- 2. Check for tables with high sequential scan activity
\echo ''
\echo '2. Sequential Scan Activity (should be reduced):'
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    CASE WHEN seq_scan > 0 THEN seq_tup_read::float/seq_scan ELSE 0 END as avg_seq_read
FROM pg_stat_user_tables
WHERE schemaname = 'public' 
    AND seq_scan > 0
ORDER BY seq_scan DESC, avg_seq_read DESC
LIMIT 10;

-- 3. Check index hit ratio (should be >95%)
\echo ''
\echo '3. Index Hit Ratio (target: >95%):'
SELECT 
    'Index Hit Ratio' as metric,
    ROUND((sum(idx_blks_hit) / NULLIF(sum(idx_blks_hit + idx_blks_read), 0)) * 100, 2) as percentage
FROM pg_statio_user_indexes;

-- 4. Check table hit ratio (should be >95%)
\echo ''
\echo '4. Table Hit Ratio (target: >95%):'
SELECT 
    'Table Hit Ratio' as metric,
    ROUND((sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit + heap_blks_read), 0)) * 100, 2) as percentage
FROM pg_statio_user_tables;

\echo ''
\echo '✅ Monitoring report completed!'
\echo 'Expected improvements:'
\echo '  • Index usage should show significant activity'
\echo '  • Sequential scans should be reduced'
\echo '  • Hit ratios should be >95%'

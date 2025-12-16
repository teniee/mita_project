-- MITA Project - Migration Verification Script
-- © 2025 YAKOVLEV LTD - All Rights Reserved
--
-- Run this script in Supabase SQL Editor after applying migrations
-- to verify everything is correctly set up.

-- ============================================================================
-- 1. TABLE COUNT VERIFICATION
-- ============================================================================
SELECT
    'Table Count Check' as check_name,
    COUNT(*) as actual_count,
    27 as expected_count,
    CASE WHEN COUNT(*) = 27 THEN '✓ PASS' ELSE '✗ FAIL' END as status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';

-- ============================================================================
-- 2. LIST ALL TABLES
-- ============================================================================
SELECT
    'All Tables' as check_name,
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Expected tables:
-- ai_advice_templates, ai_analysis_snapshots, alembic_version, budget_advice,
-- challenge_participations, challenges, daily_plan, expenses,
-- feature_access_logs, feature_usage_logs, goals, habits,
-- installment_achievements, installment_calculations, installments,
-- moods, notification_logs, notifications, paywall_impression_logs,
-- push_tokens, subscriptions, transactions, user_answers,
-- user_financial_profiles, user_profiles, users

-- ============================================================================
-- 3. ALEMBIC VERSION CHECK
-- ============================================================================
SELECT
    'Migration Version' as check_name,
    version_num as current_version,
    CASE
        WHEN version_num = '0018_add_soft_deletes' THEN '✓ PASS - All migrations applied'
        ELSE '✗ FAIL - Incomplete migration'
    END as status
FROM alembic_version;

-- ============================================================================
-- 4. CRITICAL COLUMNS CHECK - USERS TABLE
-- ============================================================================
SELECT
    'Users Table Columns' as check_name,
    COUNT(*) as column_count,
    CASE WHEN COUNT(*) >= 25 THEN '✓ PASS' ELSE '✗ FAIL' END as status
FROM information_schema.columns
WHERE table_name = 'users'
  AND table_schema = 'public';

-- List all user columns
SELECT
    'Users Columns' as table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
  AND table_schema = 'public'
ORDER BY ordinal_position;

-- ============================================================================
-- 5. FINANCIAL PRECISION CHECK
-- ============================================================================
SELECT
    'Financial Precision' as check_name,
    table_name,
    column_name,
    data_type,
    numeric_precision,
    numeric_scale,
    CASE
        WHEN data_type = 'numeric' AND numeric_scale = 2 THEN '✓ PASS'
        WHEN data_type = 'numeric' AND numeric_scale IS NULL THEN '⚠ WARNING'
        ELSE '✗ FAIL'
    END as status
FROM information_schema.columns
WHERE table_name IN ('transactions', 'goals', 'expenses', 'installments', 'users')
  AND column_name LIKE '%amount%'
  AND table_schema = 'public'
ORDER BY table_name, column_name;

-- ============================================================================
-- 6. INDEX COUNT CHECK
-- ============================================================================
SELECT
    'Index Count' as check_name,
    COUNT(*) as index_count,
    CASE WHEN COUNT(*) >= 40 THEN '✓ PASS' ELSE '⚠ WARNING - Some indexes may be missing' END as status
FROM pg_indexes
WHERE schemaname = 'public';

-- List all indexes
SELECT
    'Indexes' as object_type,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ============================================================================
-- 7. FOREIGN KEY CONSTRAINTS CHECK
-- ============================================================================
SELECT
    'Foreign Key Count' as check_name,
    COUNT(*) as fk_count,
    CASE WHEN COUNT(*) >= 15 THEN '✓ PASS' ELSE '⚠ WARNING - Some foreign keys may be missing' END as status
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
  AND table_schema = 'public';

-- List all foreign keys
SELECT
    'Foreign Keys' as constraint_type,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.table_schema = tc.table_schema
LEFT JOIN information_schema.referential_constraints AS rc
  ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- ============================================================================
-- 8. TRIGGER CHECK
-- ============================================================================
SELECT
    'Trigger Count' as check_name,
    COUNT(*) as trigger_count,
    CASE WHEN COUNT(*) >= 2 THEN '✓ PASS' ELSE '⚠ WARNING - Triggers may be missing' END as status
FROM information_schema.triggers
WHERE trigger_schema = 'public';

-- List all triggers
SELECT
    'Triggers' as object_type,
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation,
    action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY event_object_table, trigger_name;

-- Expected triggers:
-- - update_users_updated_at on users (BEFORE UPDATE)
-- - update_transactions_updated_at on transactions (BEFORE UPDATE)

-- ============================================================================
-- 9. FUNCTION CHECK
-- ============================================================================
SELECT
    'Functions' as object_type,
    routine_name,
    routine_type,
    data_type as return_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_type = 'FUNCTION'
ORDER BY routine_name;

-- Expected functions:
-- - update_updated_at_column()

-- ============================================================================
-- 10. SAMPLE DATA CHECK (CHALLENGES)
-- ============================================================================
SELECT
    'Sample Challenges' as check_name,
    COUNT(*) as challenge_count,
    CASE
        WHEN COUNT(*) = 8 THEN '✓ PASS - All sample challenges inserted'
        WHEN COUNT(*) > 0 THEN '⚠ WARNING - Partial sample data'
        ELSE '✗ FAIL - No sample challenges'
    END as status
FROM challenges;

-- List all challenges
SELECT
    'Challenges' as table_name,
    id,
    name,
    type,
    difficulty,
    duration_days,
    reward_points
FROM challenges
ORDER BY difficulty, reward_points;

-- ============================================================================
-- 11. UUID COLUMN TYPE CHECK
-- ============================================================================
SELECT
    'UUID Columns' as check_name,
    table_name,
    column_name,
    data_type,
    CASE
        WHEN udt_name = 'uuid' THEN '✓ PASS'
        ELSE '✗ FAIL - Should be UUID'
    END as status
FROM information_schema.columns
WHERE column_name = 'id'
  AND table_name IN ('users', 'transactions', 'goals', 'moods', 'push_tokens')
  AND table_schema = 'public'
ORDER BY table_name;

-- ============================================================================
-- 12. SOFT DELETE COLUMNS CHECK
-- ============================================================================
SELECT
    'Soft Delete Support' as check_name,
    table_name,
    column_name,
    data_type,
    CASE
        WHEN column_name = 'deleted_at' THEN '✓ PASS'
        ELSE '✗ FAIL'
    END as status
FROM information_schema.columns
WHERE column_name = 'deleted_at'
  AND table_name IN ('transactions', 'goals', 'installments')
  AND table_schema = 'public'
ORDER BY table_name;

-- ============================================================================
-- 13. TIMESTAMP TIMEZONE CHECK
-- ============================================================================
SELECT
    'Timestamp with Timezone' as check_name,
    table_name,
    column_name,
    data_type,
    CASE
        WHEN data_type = 'timestamp with time zone' THEN '✓ PASS'
        WHEN data_type = 'timestamp without time zone' THEN '⚠ WARNING - Should have timezone'
        ELSE '✗ FAIL'
    END as status
FROM information_schema.columns
WHERE column_name IN ('created_at', 'updated_at', 'deleted_at')
  AND table_schema = 'public'
ORDER BY table_name, column_name;

-- ============================================================================
-- 14. UNIQUE CONSTRAINTS CHECK
-- ============================================================================
SELECT
    'Unique Constraints' as check_name,
    tc.table_name,
    kcu.column_name,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'UNIQUE'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- Expected unique constraints:
-- - users.email
-- - push_tokens.token
-- - user_profiles.user_id
-- - user_financial_profiles.user_id

-- ============================================================================
-- 15. DEFAULT VALUE CHECK
-- ============================================================================
SELECT
    'Default Values' as check_name,
    table_name,
    column_name,
    column_default
FROM information_schema.columns
WHERE column_default IS NOT NULL
  AND table_schema = 'public'
  AND table_name IN ('users', 'transactions', 'goals', 'challenges')
ORDER BY table_name, column_name;

-- ============================================================================
-- 16. EMPTY TABLE CHECK (Should all be empty on fresh DB)
-- ============================================================================
DO $$
DECLARE
    r RECORD;
    v_count INTEGER;
    v_output TEXT := '';
BEGIN
    FOR r IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name != 'alembic_version'
          AND table_name != 'challenges'
        ORDER BY table_name
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', r.table_name) INTO v_count;
        IF v_count > 0 THEN
            v_output := v_output || r.table_name || ': ' || v_count || ' rows' || E'\n';
        END IF;
    END LOOP;

    IF v_output = '' THEN
        RAISE NOTICE 'Empty Tables Check: ✓ PASS - All tables empty (except challenges and alembic_version)';
    ELSE
        RAISE NOTICE 'Empty Tables Check: ⚠ WARNING - Some tables have data:%', E'\n' || v_output;
    END IF;
END $$;

-- ============================================================================
-- 17. SUMMARY REPORT
-- ============================================================================
SELECT
    '=== MIGRATION VERIFICATION SUMMARY ===' as report_header;

SELECT
    'Total Tables' as metric,
    COUNT(*)::TEXT as value
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
UNION ALL
SELECT
    'Total Indexes',
    COUNT(*)::TEXT
FROM pg_indexes
WHERE schemaname = 'public'
UNION ALL
SELECT
    'Total Foreign Keys',
    COUNT(*)::TEXT
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public'
UNION ALL
SELECT
    'Total Triggers',
    COUNT(*)::TEXT
FROM information_schema.triggers
WHERE trigger_schema = 'public'
UNION ALL
SELECT
    'Migration Version',
    version_num
FROM alembic_version
UNION ALL
SELECT
    'Sample Challenges',
    COUNT(*)::TEXT
FROM challenges;

-- ============================================================================
-- 18. QUICK HEALTH CHECK
-- ============================================================================
SELECT
    '✓ Migration verification complete!' as status,
    'Review results above for any ✗ FAIL or ⚠ WARNING items' as next_steps;

-- If any checks failed, review:
-- 1. Check consolidated_migration.sql was applied completely
-- 2. Review error messages in Supabase logs
-- 3. Verify connection string and permissions
-- 4. Check for any conflicting existing tables

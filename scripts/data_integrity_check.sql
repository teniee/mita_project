-- ========================================
-- MITA Finance - Data Integrity Check SQL
-- Generated: 2026-01-06
-- Purpose: Comprehensive data consistency analysis
-- ========================================

\echo '========================================='
\echo 'MITA DATA INTEGRITY CHECK'
\echo 'Starting comprehensive analysis...'
\echo '========================================='
\echo ''

-- ========================================
-- 1. DATABASE OVERVIEW
-- ========================================
\echo '1. DATABASE OVERVIEW'
\echo '-------------------'

SELECT
    'Current Database' as metric,
    current_database() as value
UNION ALL
SELECT
    'PostgreSQL Version',
    version()
UNION ALL
SELECT
    'Current User',
    current_user::text
UNION ALL
SELECT
    'Current Timestamp',
    now()::text;

\echo ''

-- ========================================
-- 2. TABLE ROW COUNTS
-- ========================================
\echo '2. TABLE ROW COUNTS'
\echo '-------------------'

SELECT
    schemaname,
    tablename,
    n_live_tup as row_count,
    n_dead_tup as dead_rows,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

\echo ''

-- ========================================
-- 3. CHECK FOR NULL VALUES IN CRITICAL FIELDS
-- ========================================
\echo '3. NULL VALUES IN CRITICAL NON-NULLABLE FIELDS'
\echo '---------------------------------------------'

-- Users table
SELECT
    'users' as table_name,
    'email' as column_name,
    COUNT(*) as null_count
FROM users
WHERE email IS NULL
HAVING COUNT(*) > 0
UNION ALL
SELECT
    'users',
    'password_hash',
    COUNT(*)
FROM users
WHERE password_hash IS NULL
HAVING COUNT(*) > 0
UNION ALL

-- Transactions table
SELECT
    'transactions',
    'user_id',
    COUNT(*)
FROM transactions
WHERE user_id IS NULL
HAVING COUNT(*) > 0
UNION ALL
SELECT
    'transactions',
    'category',
    COUNT(*)
FROM transactions
WHERE category IS NULL
HAVING COUNT(*) > 0
UNION ALL
SELECT
    'transactions',
    'amount',
    COUNT(*)
FROM transactions
WHERE amount IS NULL
HAVING COUNT(*) > 0
UNION ALL

-- Goals table
SELECT
    'goals',
    'user_id',
    COUNT(*)
FROM goals
WHERE user_id IS NULL
HAVING COUNT(*) > 0
UNION ALL
SELECT
    'goals',
    'title',
    COUNT(*)
FROM goals
WHERE title IS NULL OR title = ''
HAVING COUNT(*) > 0
UNION ALL
SELECT
    'goals',
    'target_amount',
    COUNT(*)
FROM goals
WHERE target_amount IS NULL
HAVING COUNT(*) > 0
UNION ALL

-- Daily Plan table
SELECT
    'daily_plan',
    'user_id',
    COUNT(*)
FROM daily_plan
WHERE user_id IS NULL
HAVING COUNT(*) > 0;

\echo ''

-- ========================================
-- 4. FOREIGN KEY INTEGRITY - ORPHANED RECORDS
-- ========================================
\echo '4. FOREIGN KEY INTEGRITY - ORPHANED RECORDS'
\echo '-------------------------------------------'

-- Orphaned transactions (no user)
SELECT
    'Orphaned Transactions (no user)' as issue,
    COUNT(*) as count
FROM transactions t
LEFT JOIN users u ON t.user_id = u.id
WHERE u.id IS NULL;

-- Orphaned transactions (deleted users, if soft delete is used)
SELECT
    'Transactions with deleted users' as issue,
    COUNT(*) as count
FROM transactions t
JOIN users u ON t.user_id = u.id
WHERE t.deleted_at IS NULL
AND u.id IN (
    SELECT id FROM users WHERE email LIKE '%deleted%' OR email IS NULL
);

-- Orphaned goals (no user)
SELECT
    'Orphaned Goals (no user)' as issue,
    COUNT(*) as count
FROM goals g
LEFT JOIN users u ON g.user_id = u.id
WHERE u.id IS NULL;

-- Orphaned transactions with invalid goal_id
SELECT
    'Transactions with invalid goal_id' as issue,
    COUNT(*) as count
FROM transactions t
WHERE t.goal_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM goals g WHERE g.id = t.goal_id
);

-- Orphaned habit completions (if table exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'habit_completions'
    ) THEN
        RAISE NOTICE 'Checking habit_completions...';
    END IF;
END $$;

SELECT
    'Orphaned Habit Completions (no habit)' as issue,
    COUNT(*) as count
FROM habit_completions hc
LEFT JOIN habits h ON hc.habit_id = h.id
WHERE h.id IS NULL
AND EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'habit_completions'
);

\echo ''

-- ========================================
-- 5. DUPLICATE RECORDS CHECK
-- ========================================
\echo '5. DUPLICATE RECORDS CHECK'
\echo '-------------------------'

-- Duplicate user emails
SELECT
    'Duplicate user emails' as issue,
    email,
    COUNT(*) as count
FROM users
GROUP BY email
HAVING COUNT(*) > 1;

-- Duplicate daily plan entries (same user + date)
SELECT
    'Duplicate daily_plan entries' as issue,
    user_id,
    date,
    COUNT(*) as count
FROM daily_plan
GROUP BY user_id, date
HAVING COUNT(*) > 1;

-- Duplicate transactions (same user, amount, category, timestamp within 1 second)
SELECT
    'Potential duplicate transactions' as issue,
    user_id,
    category,
    amount,
    spent_at,
    COUNT(*) as count
FROM transactions
WHERE deleted_at IS NULL
GROUP BY user_id, category, amount, DATE_TRUNC('second', spent_at)
HAVING COUNT(*) > 1
LIMIT 10;

\echo ''

-- ========================================
-- 6. TIMESTAMP CONSISTENCY CHECKS
-- ========================================
\echo '6. TIMESTAMP CONSISTENCY CHECKS'
\echo '-------------------------------'

-- Transactions with created_at > updated_at
SELECT
    'Transactions: created_at > updated_at' as issue,
    COUNT(*) as count
FROM transactions
WHERE created_at > updated_at;

-- Goals with created_at > last_updated
SELECT
    'Goals: created_at > last_updated' as issue,
    COUNT(*) as count
FROM goals
WHERE created_at > last_updated;

-- Transactions with future spent_at dates
SELECT
    'Transactions with future dates' as issue,
    COUNT(*) as count
FROM transactions
WHERE spent_at > NOW() + INTERVAL '1 day'
AND deleted_at IS NULL;

-- Goals with completed_at before created_at
SELECT
    'Goals: completed_at < created_at' as issue,
    COUNT(*) as count
FROM goals
WHERE completed_at IS NOT NULL
AND completed_at < created_at;

-- Transactions with deleted_at before created_at
SELECT
    'Transactions: deleted_at < created_at' as issue,
    COUNT(*) as count
FROM transactions
WHERE deleted_at IS NOT NULL
AND deleted_at < created_at;

\echo ''

-- ========================================
-- 7. BUDGET VS TRANSACTION CONSISTENCY
-- ========================================
\echo '7. BUDGET VS TRANSACTION TOTALS'
\echo '-------------------------------'

-- Per-user transaction totals vs daily_plan spent_amount
WITH user_transaction_totals AS (
    SELECT
        user_id,
        DATE_TRUNC('day', spent_at) as day,
        category,
        SUM(amount) as total_spent
    FROM transactions
    WHERE deleted_at IS NULL
    AND spent_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id, DATE_TRUNC('day', spent_at), category
),
daily_plan_totals AS (
    SELECT
        user_id,
        DATE_TRUNC('day', date) as day,
        category,
        spent_amount
    FROM daily_plan
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    AND category IS NOT NULL
)
SELECT
    'Budget-Transaction Mismatches (last 30 days)' as issue,
    COUNT(*) as count
FROM user_transaction_totals utt
FULL OUTER JOIN daily_plan_totals dpt
    ON utt.user_id = dpt.user_id
    AND utt.day = dpt.day
    AND utt.category = dpt.category
WHERE ABS(COALESCE(utt.total_spent, 0) - COALESCE(dpt.spent_amount, 0)) > 0.01;

\echo ''

-- ========================================
-- 8. GOAL PROGRESS CALCULATION VERIFICATION
-- ========================================
\echo '8. GOAL PROGRESS CALCULATION VERIFICATION'
\echo '-----------------------------------------'

-- Goals where progress doesn't match saved_amount/target_amount
SELECT
    'Goals with incorrect progress calculation' as issue,
    COUNT(*) as count
FROM goals
WHERE target_amount > 0
AND deleted_at IS NULL
AND ABS(
    progress - (
        CASE
            WHEN saved_amount >= target_amount THEN 100
            ELSE (saved_amount / target_amount * 100)
        END
    )
) > 0.01;

-- Goals with progress > 100 but status != 'completed'
SELECT
    'Goals: progress > 100 but not completed' as issue,
    COUNT(*) as count
FROM goals
WHERE progress > 100
AND status != 'completed'
AND deleted_at IS NULL;

-- Goals with saved_amount > target_amount
SELECT
    'Goals: saved_amount > target_amount' as issue,
    COUNT(*) as count
FROM goals
WHERE saved_amount > target_amount
AND deleted_at IS NULL;

-- Goals with negative amounts
SELECT
    'Goals with negative saved_amount' as issue,
    COUNT(*) as count
FROM goals
WHERE saved_amount < 0
AND deleted_at IS NULL;

SELECT
    'Goals with negative target_amount' as issue,
    COUNT(*) as count
FROM goals
WHERE target_amount < 0;

\echo ''

-- ========================================
-- 9. DATA TYPE AND PRECISION CHECKS
-- ========================================
\echo '9. DATA TYPE AND PRECISION CHECKS'
\echo '---------------------------------'

-- Transactions with invalid currency codes
SELECT
    'Transactions with invalid currency' as issue,
    currency,
    COUNT(*) as count
FROM transactions
WHERE currency NOT IN ('USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'BRL')
AND deleted_at IS NULL
GROUP BY currency;

-- Transactions with zero or negative amounts (if unexpected)
SELECT
    'Transactions with zero amount' as issue,
    COUNT(*) as count
FROM transactions
WHERE amount = 0
AND deleted_at IS NULL;

SELECT
    'Transactions with negative amount' as issue,
    COUNT(*) as count
FROM transactions
WHERE amount < 0
AND deleted_at IS NULL
AND category NOT IN ('income', 'refund', 'transfer');

-- Daily plan with negative amounts
SELECT
    'Daily plan with negative planned_amount' as issue,
    COUNT(*) as count
FROM daily_plan
WHERE planned_amount < 0;

\echo ''

-- ========================================
-- 10. SOFT DELETE CONSISTENCY
-- ========================================
\echo '10. SOFT DELETE CONSISTENCY'
\echo '---------------------------'

-- Count of soft-deleted records
SELECT
    'Soft-deleted transactions' as category,
    COUNT(*) as count
FROM transactions
WHERE deleted_at IS NOT NULL;

SELECT
    'Soft-deleted goals' as category,
    COUNT(*) as count
FROM goals
WHERE deleted_at IS NOT NULL;

-- Transactions soft-deleted but still referenced in daily_plan
SELECT
    'Soft-deleted transactions still in use' as issue,
    COUNT(DISTINCT t.id) as count
FROM transactions t
WHERE t.deleted_at IS NOT NULL
AND EXISTS (
    SELECT 1 FROM daily_plan dp
    WHERE dp.user_id = t.user_id
    AND DATE_TRUNC('day', dp.date) = DATE_TRUNC('day', t.spent_at)
);

\echo ''

-- ========================================
-- 11. INDEX AND CONSTRAINT STATUS
-- ========================================
\echo '11. INDEX AND CONSTRAINT STATUS'
\echo '-------------------------------'

-- List all foreign keys
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name;

\echo ''

-- ========================================
-- 12. USER DATA COMPLETENESS
-- ========================================
\echo '12. USER DATA COMPLETENESS'
\echo '-------------------------'

-- Users missing critical onboarding data
SELECT
    'Users without monthly_income' as issue,
    COUNT(*) as count
FROM users
WHERE (monthly_income IS NULL OR monthly_income = 0)
AND has_onboarded = true;

SELECT
    'Users without annual_income' as issue,
    COUNT(*) as count
FROM users
WHERE (annual_income IS NULL OR annual_income = 0)
AND has_onboarded = true;

SELECT
    'Users marked onboarded but no transactions' as issue,
    COUNT(*) as count
FROM users u
WHERE u.has_onboarded = true
AND NOT EXISTS (
    SELECT 1 FROM transactions t
    WHERE t.user_id = u.id
    AND t.deleted_at IS NULL
);

\echo ''

-- ========================================
-- 13. RECENT PROBLEMATIC RECORDS
-- ========================================
\echo '13. RECENT PROBLEMATIC RECORDS (Last 7 Days)'
\echo '--------------------------------------------'

-- Recently created transactions with issues
SELECT
    'Recent transactions missing category' as issue,
    COUNT(*) as count
FROM transactions
WHERE created_at >= NOW() - INTERVAL '7 days'
AND (category IS NULL OR category = '');

SELECT
    'Recent transactions missing spent_at' as issue,
    COUNT(*) as count
FROM transactions
WHERE created_at >= NOW() - INTERVAL '7 days'
AND spent_at IS NULL;

-- Recent goals with issues
SELECT
    'Recent goals with invalid status' as issue,
    COUNT(*) as count
FROM goals
WHERE created_at >= NOW() - INTERVAL '7 days'
AND status NOT IN ('active', 'completed', 'paused', 'cancelled');

\echo ''

-- ========================================
-- 14. CALENDAR DATA INTEGRITY
-- ========================================
\echo '14. CALENDAR DATA INTEGRITY'
\echo '-------------------------'

-- Daily plans with missing required fields
SELECT
    'Daily plans without date' as issue,
    COUNT(*) as count
FROM daily_plan
WHERE date IS NULL;

SELECT
    'Daily plans without user_id' as issue,
    COUNT(*) as count
FROM daily_plan
WHERE user_id IS NULL;

-- Daily plans with inconsistent spent vs planned
SELECT
    'Daily plans: spent > planned (by category)' as issue,
    COUNT(*) as count
FROM daily_plan
WHERE spent_amount > planned_amount
AND planned_amount > 0;

\echo ''

-- ========================================
-- SUMMARY
-- ========================================
\echo '========================================='
\echo 'DATA INTEGRITY CHECK COMPLETE'
\echo 'Review results above for any issues.'
\echo 'Run fix scripts if inconsistencies found.'
\echo '========================================='

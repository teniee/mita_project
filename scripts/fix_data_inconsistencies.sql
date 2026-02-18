-- ========================================
-- MITA Finance - Data Inconsistency Fixes
-- Generated: 2026-01-06
-- WARNING: Review carefully before executing!
-- ========================================

-- IMPORTANT: This script contains fixes for common data inconsistencies.
-- Review each section and uncomment only the fixes you want to apply.
-- Always backup your database before running any fix scripts!

\echo '========================================='
\echo 'MITA DATA INCONSISTENCY FIXES'
\echo 'WARNING: Review before executing!'
\echo '========================================='
\echo ''

-- ========================================
-- 1. FIX NULL VALUES IN CRITICAL FIELDS
-- ========================================
\echo '1. Fixing NULL values in critical fields...'

-- Fix transactions with NULL category (assign 'uncategorized')
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET category = 'uncategorized'
-- WHERE category IS NULL;

-- Fix transactions with NULL spent_at (use created_at)
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET spent_at = created_at
-- WHERE spent_at IS NULL;

-- Fix goals with empty titles
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET title = 'Untitled Goal'
-- WHERE title IS NULL OR title = '';

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 2. REMOVE ORPHANED RECORDS
-- ========================================
\echo '2. Removing orphaned records...'

-- Soft delete orphaned transactions (no user exists)
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET deleted_at = NOW()
-- WHERE user_id NOT IN (SELECT id FROM users)
-- AND deleted_at IS NULL;

-- Soft delete orphaned goals (no user exists)
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET deleted_at = NOW()
-- WHERE user_id NOT IN (SELECT id FROM users)
-- AND deleted_at IS NULL;

-- Fix transactions with invalid goal_id (set to NULL)
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET goal_id = NULL
-- WHERE goal_id IS NOT NULL
-- AND goal_id NOT IN (SELECT id FROM goals);

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 3. FIX DUPLICATE RECORDS
-- ========================================
\echo '3. Fixing duplicate records...'

-- Remove duplicate daily_plan entries (keep most recent)
-- UNCOMMENT TO EXECUTE:
-- DELETE FROM daily_plan
-- WHERE id IN (
--     SELECT id
--     FROM (
--         SELECT id,
--                ROW_NUMBER() OVER (PARTITION BY user_id, date ORDER BY created_at DESC) as rn
--         FROM daily_plan
--     ) t
--     WHERE rn > 1
-- );

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 4. FIX TIMESTAMP INCONSISTENCIES
-- ========================================
\echo '4. Fixing timestamp inconsistencies...'

-- Fix transactions where created_at > updated_at
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET updated_at = created_at
-- WHERE created_at > updated_at;

-- Fix goals where created_at > last_updated
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET last_updated = created_at
-- WHERE created_at > last_updated;

-- Mark future transactions as invalid (soft delete)
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET deleted_at = NOW()
-- WHERE spent_at > NOW() + INTERVAL '1 day'
-- AND deleted_at IS NULL;

-- Fix goals completed before created (set completed_at = created_at)
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET completed_at = created_at
-- WHERE completed_at IS NOT NULL
-- AND completed_at < created_at;

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 5. FIX GOAL PROGRESS CALCULATIONS
-- ========================================
\echo '5. Fixing goal progress calculations...'

-- Recalculate progress for all active goals
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET progress = LEAST(
--     CASE
--         WHEN target_amount > 0 THEN (saved_amount / target_amount * 100)
--         ELSE 0
--     END,
--     100
-- )
-- WHERE deleted_at IS NULL;

-- Auto-complete goals that reached 100% but status != 'completed'
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET
--     status = 'completed',
--     completed_at = NOW()
-- WHERE progress >= 100
-- AND status = 'active'
-- AND deleted_at IS NULL;

-- Fix goals with saved_amount > target_amount (cap at target)
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET saved_amount = target_amount
-- WHERE saved_amount > target_amount
-- AND deleted_at IS NULL;

-- Fix goals with negative saved_amount
-- UNCOMMENT TO EXECUTE:
-- UPDATE goals
-- SET saved_amount = 0
-- WHERE saved_amount < 0
-- AND deleted_at IS NULL;

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 6. FIX DATA TYPE INCONSISTENCIES
-- ========================================
\echo '6. Fixing data type inconsistencies...'

-- Fix invalid currency codes (default to USD)
-- UNCOMMENT TO EXECUTE:
-- UPDATE transactions
-- SET currency = 'USD'
-- WHERE currency NOT IN ('USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'BRL')
-- AND deleted_at IS NULL;

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 7. FIX USER DATA COMPLETENESS
-- ========================================
\echo '7. Fixing user data completeness...'

-- Set default monthly_income for onboarded users without it
-- UNCOMMENT TO EXECUTE:
-- UPDATE users
-- SET monthly_income = COALESCE(annual_income / 12, 0)
-- WHERE has_onboarded = true
-- AND (monthly_income IS NULL OR monthly_income = 0)
-- AND annual_income > 0;

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- 8. VACUUM AND ANALYZE AFTER FIXES
-- ========================================
\echo '8. Cleanup and optimization...'

-- After applying fixes, run VACUUM and ANALYZE
-- UNCOMMENT TO EXECUTE:
-- VACUUM ANALYZE transactions;
-- VACUUM ANALYZE goals;
-- VACUUM ANALYZE daily_plan;
-- VACUUM ANALYZE users;

\echo '  (Review and uncomment commands to execute)'
\echo ''

-- ========================================
-- VERIFICATION QUERIES
-- ========================================
\echo '========================================='
\echo 'VERIFICATION QUERIES'
\echo 'Run these after applying fixes to verify'
\echo '========================================='

-- Check remaining orphaned transactions
SELECT
    'Orphaned transactions remaining' as check_name,
    COUNT(*) as count
FROM transactions t
LEFT JOIN users u ON t.user_id = u.id
WHERE u.id IS NULL;

-- Check remaining orphaned goals
SELECT
    'Orphaned goals remaining' as check_name,
    COUNT(*) as count
FROM goals g
LEFT JOIN users u ON g.user_id = u.id
WHERE u.id IS NULL;

-- Check goals with incorrect progress
SELECT
    'Goals with incorrect progress' as check_name,
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

-- Check timestamp inconsistencies
SELECT
    'Transactions: created > updated' as check_name,
    COUNT(*) as count
FROM transactions
WHERE created_at > updated_at;

\echo ''
\echo '========================================='
\echo 'FIX SCRIPT COMPLETE'
\echo 'Review results above before proceeding'
\echo '========================================='

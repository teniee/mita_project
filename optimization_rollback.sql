-- MITA Finance Database Optimization Rollback
-- Generated: 2025-09-03T01:23:31.623251
-- Use only if optimization causes issues (unlikely with CONCURRENTLY)

\echo '⚠️  Rolling back MITA Finance database optimizations...'

-- Remove idx_users_email_btree
DROP INDEX IF EXISTS idx_users_email_btree;
\echo 'Removed index: idx_users_email_btree'

-- Remove idx_users_email_lower
DROP INDEX IF EXISTS idx_users_email_lower;
\echo 'Removed index: idx_users_email_lower'

-- Remove idx_transactions_user_spent_at_desc
DROP INDEX IF EXISTS idx_transactions_user_spent_at_desc;
\echo 'Removed index: idx_transactions_user_spent_at_desc'

-- Remove idx_transactions_spent_at_desc
DROP INDEX IF EXISTS idx_transactions_spent_at_desc;
\echo 'Removed index: idx_transactions_spent_at_desc'

-- Remove idx_expenses_user_date_desc
DROP INDEX IF EXISTS idx_expenses_user_date_desc;
\echo 'Removed index: idx_expenses_user_date_desc'

-- Remove idx_expenses_date_desc
DROP INDEX IF EXISTS idx_expenses_date_desc;
\echo 'Removed index: idx_expenses_date_desc'

-- Remove idx_ai_snapshots_user_created_desc
DROP INDEX IF EXISTS idx_ai_snapshots_user_created_desc;
\echo 'Removed index: idx_ai_snapshots_user_created_desc'

\echo '⚠️  Rollback completed. Performance will return to previous state.'

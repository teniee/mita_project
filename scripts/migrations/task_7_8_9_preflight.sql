-- TASK-7/8/9 migration preflight — READ-ONLY.
--
-- Run this against PRODUCTION (read replica is fine) BEFORE the owner
-- applies migrations 0036/0037/0038 in a maintenance window. It changes
-- nothing; it reports exactly which production rows the migrations would
-- delete, round, or reject.
--
--   psql "$DATABASE_URL" -f scripts/migrations/task_7_8_9_preflight.sql
--
-- Interpretation:
--   * TASK-7 orphan counts  -> rows migration 0036 will DELETE.
--   * TASK-8 rounding counts -> rows migration 0037 will ROUND to the cent.
--   * TASK-9 duplicate list  -> groups that make migration 0038 FAIL until
--     reconciled by hand (0038 never deletes subscription rows).

\echo '=== TASK-7: orphaned rows that migration 0036 will DELETE ==='
SELECT 'moods'            AS table_name, count(*) AS orphan_rows
  FROM moods t            LEFT JOIN users u ON u.id = t.user_id
  WHERE t.user_id IS NOT NULL AND u.id IS NULL
UNION ALL
SELECT 'budget_advice',    count(*)
  FROM budget_advice t     LEFT JOIN users u ON u.id = t.user_id
  WHERE t.user_id IS NOT NULL AND u.id IS NULL
UNION ALL
SELECT 'notification_logs', count(*)
  FROM notification_logs t LEFT JOIN users u ON u.id = t.user_id
  WHERE t.user_id IS NOT NULL AND u.id IS NULL
UNION ALL
SELECT 'push_tokens',       count(*)
  FROM push_tokens t       LEFT JOIN users u ON u.id = t.user_id
  WHERE t.user_id IS NOT NULL AND u.id IS NULL
UNION ALL
SELECT 'ignored_alerts',    count(*)
  FROM ignored_alerts t    LEFT JOIN users u ON u.id = t.user_id
  WHERE t.user_id IS NOT NULL AND u.id IS NULL;

\echo '=== TASK-8: rows that migration 0037 will ROUND to 2 decimal places ==='
SELECT 'users.monthly_income' AS column_name,
       count(*) AS rows_to_round
  FROM users
  WHERE monthly_income IS NOT NULL
    AND round(monthly_income::numeric, 2) <> monthly_income::numeric
UNION ALL
SELECT 'users.savings_goal',
       count(*)
  FROM users
  WHERE savings_goal IS NOT NULL
    AND round(savings_goal::numeric, 2) <> savings_goal::numeric
UNION ALL
SELECT 'expenses.amount',
       count(*)
  FROM expenses
  WHERE amount IS NOT NULL
    AND round(amount::numeric, 2) <> amount::numeric;

\echo '=== TASK-9: duplicate (platform, original_transaction_id) that will BLOCK migration 0038 ==='
SELECT platform,
       original_transaction_id,
       count(*) AS duplicate_rows,
       array_agg(id) AS subscription_ids
  FROM subscriptions
  WHERE original_transaction_id IS NOT NULL
  GROUP BY platform, original_transaction_id
  HAVING count(*) > 1
  ORDER BY count(*) DESC;

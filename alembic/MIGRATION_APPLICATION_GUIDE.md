# MITA Project - Database Migration Application Guide

**Generated:** 2025-12-14
**Target:** Supabase PostgreSQL 15.8
**© 2025 YAKOVLEV LTD - All Rights Reserved**

## Overview

This guide provides instructions for applying all Alembic migrations to your Supabase database. Since the `mcp__supabase__apply_migration` tool is not available, migrations must be applied manually via SQL.

## Migration Files Summary

Total migrations: **19 files**
Dependency chain complexity: **Multiple branches from f8e0108e3527**

### Complete Migration Chain

```
0001_initial (base)
  └─ 0002_mood
      └─ 0003_goals
          └─ 0004_user_premium_until
              └─ 0005_push_tokens
                  └─ a0d5ecc53667_sync_models
                      └─ 0006_fix_financial_data_types
                          └─ 0007_email_password_reset_fields
                              └─ f8e0108e3527_add_missing_user_fields
                                  ├─ 0008_add_user_profile_fields
                                  ├─ 0009_add_transaction_extended_fields
                                  │   └─ 0010_enhance_goals
                                  │       └─ 0011_add_goal_id
                                  │           └─ 0012_add_challenges
                                  │               └─ 0013_add_analytics_tables
                                  │                   └─ 0014_add_notifications_table
                                  ├─ 0015_add_installments_module
                                  └─ 0017_add_account_security_fields
                                      └─ 0018_add_soft_deletes
```

## Method 1: Apply Consolidated SQL Script (RECOMMENDED)

This is the fastest and most reliable method for a fresh database.

### Steps:

1. **Backup Current Database** (if not fresh):
   ```bash
   # Use Supabase backup feature or pg_dump
   ```

2. **Open Supabase SQL Editor**:
   - Navigate to your Supabase project
   - Go to SQL Editor tab
   - Create a new query

3. **Apply Consolidated Migration**:
   - Copy contents of `/Users/mikhail/StudioProjects/mita_project/alembic/consolidated_migration.sql`
   - Paste into Supabase SQL Editor
   - Execute the query

4. **Verify Migration**:
   ```sql
   -- Check all tables were created
   SELECT table_name
   FROM information_schema.tables
   WHERE table_schema = 'public'
   ORDER BY table_name;

   -- Expected tables (27 total):
   -- ai_advice_templates, ai_analysis_snapshots, budget_advice,
   -- challenge_participations, challenges, daily_plan, expenses,
   -- feature_access_logs, feature_usage_logs, goals, habits,
   -- installment_achievements, installment_calculations, installments,
   -- moods, notification_logs, notifications, paywall_impression_logs,
   -- push_tokens, subscriptions, transactions, user_answers,
   -- user_financial_profiles, user_profiles, users

   -- Check migration version
   SELECT * FROM alembic_version;
   -- Expected: version_num = '0018_add_soft_deletes'
   ```

## Method 2: Apply Individual Migrations (Alternative)

Use this if you need granular control or are applying to an existing database.

### Migration Order:

1. `0001_initial.py` - Base schema
2. `0002_mood.py` - Moods table
3. `0003_goals.py` - Goals table
4. `0004_user_premium_until.py` - Premium field
5. `0005_push_tokens.py` - Push tokens
6. `a0d5ecc53667_sync_models.py` - Model sync
7. `0006_fix_financial_data_types.py` - Financial precision fixes
8. `0007_email_password_reset_fields.py` - Email verification
9. `f8e0108e3527_add_missing_user_fields.py` - User fields
10. `0008_add_user_profile_fields.py` - User profile
11. `0009_add_transaction_extended_fields.py` - Transaction fields
12. `0010_enhance_goals_table.py` - Enhanced goals
13. `0011_add_goal_id_to_transactions.py` - Goal linking
14. `0012_add_challenges_tables.py` - Challenges
15. `0013_add_analytics_tables.py` - Analytics
16. `0014_add_notifications_table.py` - Notifications
17. `0015_add_installments_module.py` - Installments
18. `add_account_security_fields.py` (0017) - Security
19. `0018_add_soft_deletes.py` - Soft deletes

### For each migration:
1. Convert Alembic operations to raw SQL
2. Apply via Supabase SQL Editor
3. Update alembic_version table

## Method 3: Use Alembic CLI (Local to Supabase)

If you have direct database access credentials:

### Steps:

1. **Update alembic.ini**:
   ```ini
   sqlalchemy.url = postgresql://[user]:[password]@[host]:[port]/[database]
   ```

   Get connection string from Supabase:
   - Project Settings → Database → Connection String → URI

2. **Run Alembic**:
   ```bash
   cd /Users/mikhail/StudioProjects/mita_project
   alembic upgrade head
   ```

3. **Verify**:
   ```bash
   alembic current
   # Should show: 0018_add_soft_deletes (head)
   ```

## Database Schema Overview

### Core Tables (27 total)

#### User Management (1 table)
- `users` - User accounts, authentication, profile, preferences, security

#### Financial Data (4 tables)
- `transactions` - Income/expenses with OCR support
- `expenses` - Legacy expense tracking
- `goals` - Savings goals with progress tracking
- `installments` - BNPL payment tracking

#### Planning & Habits (2 tables)
- `daily_plan` - Daily budget calendar
- `habits` - Habit tracking

#### Social & Engagement (3 tables)
- `moods` - Daily mood tracking
- `challenges` - Challenge definitions
- `challenge_participations` - User challenge progress

#### AI & Intelligence (2 tables)
- `ai_analysis_snapshots` - AI financial analysis
- `ai_advice_templates` - AI advice templates
- `budget_advice` - AI budget recommendations

#### Notifications (3 tables)
- `notifications` - Rich notifications system
- `notification_logs` - Notification delivery logs
- `push_tokens` - FCM push token management

#### Analytics (3 tables)
- `feature_usage_logs` - Feature engagement
- `feature_access_logs` - Premium feature access
- `paywall_impression_logs` - Paywall conversion tracking

#### Installments Module (4 tables)
- `user_financial_profiles` - Financial risk assessment
- `installment_calculations` - BNPL calculations
- `installment_achievements` - Gamification

#### Subscriptions (1 table)
- `subscriptions` - Premium subscription management

#### Legacy/Support (3 tables)
- `user_profiles` - User profile data
- `user_answers` - Onboarding answers
- `alembic_version` - Migration tracking

## Key Features Enabled by Schema

### 1. Revolutionary Budget Redistribution
- Tables: `daily_plan`, `transactions`, `expenses`
- Daily category-based budgets with auto-rebalancing

### 2. AI-Powered OCR
- Tables: `transactions` (receipt_url, confidence_score)
- Google Cloud Vision integration

### 3. Behavioral Intelligence
- Tables: `moods`, `habits`, `ai_analysis_snapshots`
- Spending pattern analysis with mood correlation

### 4. Predictive Alerts
- Tables: `notifications`, `budget_advice`
- AI-powered budget warnings before overspending

### 5. Gamification
- Tables: `challenges`, `challenge_participations`, `installment_achievements`
- Streaks, points, achievements

### 6. Smart Installments
- Tables: `installments`, `installment_calculations`, `user_financial_profiles`
- BNPL risk assessment and tracking

### 7. Premium Analytics
- Tables: `feature_usage_logs`, `feature_access_logs`, `paywall_impression_logs`
- Conversion tracking and usage analytics

## Post-Migration Verification Checklist

Run these queries in Supabase SQL Editor:

```sql
-- 1. Verify all tables exist (should return 27 rows)
SELECT COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public';

-- 2. Verify critical indexes exist
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 3. Verify foreign key constraints
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name;

-- 4. Verify triggers exist
SELECT trigger_name, event_object_table, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public';

-- Expected triggers:
-- - update_users_updated_at on users table
-- - update_transactions_updated_at on transactions table

-- 5. Check migration version
SELECT * FROM alembic_version;
-- Expected: version_num = '0018_add_soft_deletes'

-- 6. Verify sample data (challenges)
SELECT COUNT(*) FROM challenges;
-- Expected: 8 sample challenges

-- 7. Verify column types for financial precision
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name IN ('transactions', 'goals', 'expenses', 'installments', 'users')
  AND column_name LIKE '%amount%'
ORDER BY table_name, column_name;
-- All financial amounts should be NUMERIC(12,2) or NUMERIC(10,2)
```

## Troubleshooting

### Issue: Foreign Key Constraint Fails
**Cause:** Tables created out of order
**Solution:** Drop and recreate tables in correct order or use consolidated script

### Issue: Column Already Exists
**Cause:** Partial migration applied
**Solution:** Check which migrations are already applied:
```sql
SELECT * FROM alembic_version;
```
Then apply only remaining migrations

### Issue: Data Type Mismatch
**Cause:** Migration 0006 not applied correctly
**Solution:** Manually fix data types:
```sql
ALTER TABLE expenses ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
ALTER TABLE expenses ALTER COLUMN user_id TYPE UUID USING user_id::UUID;
```

### Issue: Trigger Function Missing
**Cause:** Migration f8e0108e3527 not applied
**Solution:** Create trigger function:
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
```

## Security Considerations

### Sensitive Columns
- `users.password_hash` - BCrypt hashed passwords
- `users.email` - PII data
- `users.password_reset_token` - Secure tokens
- `users.email_verification_token` - Secure tokens

### Recommended Supabase RLS Policies

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
-- ... (apply to all tables)

-- Example: Users can only see their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own transactions" ON transactions
  FOR SELECT USING (auth.uid() = user_id);

-- Add similar policies for all user-scoped tables
```

## Performance Optimization

### Recommended Supabase Settings

1. **Connection Pooling**: Enable in Supabase settings
2. **Indexes**: All critical indexes included in migration
3. **Partitioning**: Consider for `transactions` table if >10M rows
4. **Vacuum**: Supabase handles automatically

### Query Performance Tips

```sql
-- Use partial indexes for soft-deleted data
-- Already included in migration 0018

-- Add composite indexes for common queries
CREATE INDEX idx_transactions_user_category_date
ON transactions(user_id, category, spent_at)
WHERE deleted_at IS NULL;

CREATE INDEX idx_goals_user_status
ON goals(user_id, status)
WHERE deleted_at IS NULL;
```

## Rollback Instructions

### Full Rollback (Nuclear Option)
```sql
-- WARNING: This deletes ALL data
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
```

### Targeted Rollback
Use the `downgrade()` functions in each migration file, applying in reverse order.

## Next Steps

After successful migration:

1. **Configure Supabase Auth**
   - Enable email/password auth
   - Set up email templates for verification/reset
   - Configure JWT expiration

2. **Set Up Storage Buckets**
   - Create `receipts` bucket for OCR images
   - Configure RLS policies

3. **Enable Realtime**
   - Enable for `notifications` table
   - Enable for `transactions` table

4. **Configure Edge Functions**
   - Deploy OCR processing function
   - Deploy AI insights function

5. **Set Up Monitoring**
   - Enable Supabase logging
   - Configure alerts for errors

6. **Test API Endpoints**
   - Update backend connection string
   - Run integration tests
   - Verify CRUD operations

## Support

For issues or questions:
- Email: mikhail@mita.finance
- Company: YAKOVLEV LTD (207808591)

## License

Proprietary Software License
© 2025 YAKOVLEV LTD - All Rights Reserved

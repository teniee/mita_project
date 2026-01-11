# MITA Database Integrity - Action Checklist
**Date:** 2026-01-11
**Priority:** IMMEDIATE

---

## 🔴 CRITICAL - Execute Today

### 1. Run Diagnostic Scripts on Production ⏱️ 15 minutes

```bash
# Set database URL (use actual password)
export DATABASE_URL="postgresql://postgres.atdcxppfflmiwjwjuqyl:YOUR_PASSWORD@aws-0-us-east-2.pooler.supabase.com:5432/postgres?prepared_statement_cache_size=0"

# Run SQL diagnostic script
cd /Users/mikhail/mita_project
psql $DATABASE_URL -f scripts/data_integrity_check.sql > reports/integrity_report_$(date +%Y%m%d_%H%M).txt

# Run Python diagnostic script
python3 scripts/run_data_integrity_check.py

# Review results
cat reports/integrity_report_*.txt | less
```

**Expected Output:**
- Text report with 14 categories of checks
- JSON report with issue counts by severity
- List of orphaned records (if any)

---

### 2. Review Critical Issues ⏱️ 10 minutes

**Key Questions:**
- [ ] How many orphaned daily_plan records exist?
- [ ] How many orphaned subscriptions exist?
- [ ] Are there any orphaned transactions or goals?
- [ ] What is the count of duplicate records?
- [ ] Are there any budget-transaction mismatches?

**Action:** Document findings in Slack/email to team

---

### 3. Test Migration 0022 Locally ⏱️ 20 minutes

```bash
# Option 1: Use local PostgreSQL
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/mita_test"

# Create test database
createdb mita_test

# Run all migrations including 0022
cd /Users/mikhail/mita_project
alembic upgrade head

# Verify FK constraints exist
psql $DATABASE_URL -c "
SELECT table_name, constraint_name, column_name
FROM information_schema.key_column_usage
WHERE constraint_name IN ('fk_daily_plan_user_id', 'fk_subscriptions_user_id')
ORDER BY table_name;
"
```

**Expected Output:**
```
 table_name   | constraint_name           | column_name
--------------+---------------------------+-------------
 daily_plan   | fk_daily_plan_user_id    | user_id
 subscriptions| fk_subscriptions_user_id | user_id
(2 rows)
```

---

## 🟡 HIGH PRIORITY - Execute This Week

### 4. Deploy Migration 0022 to Staging ⏱️ 30 minutes

```bash
# Option 1: Railway staging environment
railway link
railway environment --environment staging
railway run alembic upgrade head

# Option 2: Manual deployment
export DATABASE_URL="your-staging-database-url"
alembic upgrade head

# Verify deployment
railway run python3 scripts/run_data_integrity_check.py
```

**Checklist:**
- [ ] Backup staging database before migration
- [ ] Run migration with verbose logging
- [ ] Verify FK constraints created
- [ ] Run integrity check after migration
- [ ] Test creating new users/transactions/subscriptions
- [ ] Verify CASCADE delete behavior

---

### 5. Deploy Migration 0022 to Production ⏱️ 45 minutes

**Pre-deployment:**
- [ ] Review staging test results
- [ ] Schedule maintenance window (or deploy during low traffic)
- [ ] Notify team in Slack
- [ ] Backup production database

**Deployment:**
```bash
# Production deployment (Railway auto-migrates on push)
git add alembic/versions/0022_add_missing_fk_constraints.py
git commit -m "feat(db): Add missing FK constraints to daily_plan and subscriptions

- Adds foreign key constraints to ensure data integrity
- Cleans up orphaned records before adding constraints
- Adds deleted_at column to subscriptions for soft delete support
- Includes idempotency checks to prevent duplicate constraints

Fixes: data integrity violations, orphaned records
Migration: 0022_add_missing_fk_constraints
Tested: staging environment"

git push origin main
```

**Post-deployment:**
- [ ] Monitor Railway deployment logs
- [ ] Verify migration completed successfully
- [ ] Run integrity check on production
- [ ] Test user deletion (verify CASCADE works)
- [ ] Monitor Sentry for any errors
- [ ] Update team in Slack

---

### 6. Add Unique Constraint to daily_plan ⏱️ 30 minutes

**Create Migration 0023:**
```bash
cd /Users/mikhail/mita_project
alembic revision -m "add_unique_constraint_daily_plan"
```

**Edit migration file:**
```python
def upgrade():
    # Remove duplicates first
    op.execute("""
        DELETE FROM daily_plan
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, date, category
                    ORDER BY created_at DESC
                ) as rn
                FROM daily_plan
            ) t WHERE rn > 1
        );
    """)

    # Add unique constraint
    op.create_unique_constraint(
        'uq_daily_plan_user_date_category',
        'daily_plan',
        ['user_id', 'date', 'category']
    )
```

**Test and deploy following same process as migration 0022**

---

## 🟢 MEDIUM PRIORITY - Execute This Month

### 7. Add Database Check Constraints ⏱️ 1 hour

**Create Migration 0024:**
- Goals: saved_amount <= target_amount
- Goals: progress <= 100
- Goals: target_amount > 0
- Transactions: amount >= 0 (except refunds)
- Daily plan: planned_amount >= 0

**Template available in comprehensive report**

---

### 8. Implement Database Triggers ⏱️ 2 hours

**Create Migration 0025:**
- Auto-update daily_plan.spent_amount when transactions change
- Trigger function: `update_daily_plan_spent()`
- Handles INSERT, UPDATE, DELETE on transactions table

**Template available in comprehensive report**

---

### 9. Set Up Automated Integrity Checks ⏱️ 1 hour

**Railway cron job:**
```yaml
# railway.yml
cron:
  - name: data-integrity-check
    schedule: "0 2 * * *"
    command: python3 scripts/run_data_integrity_check.py
```

**Configure alerts:**
- Sentry for critical issues
- Email to mikhail@mita.finance
- Slack #alerts-production channel

---

## 📊 SUCCESS METRICS

### After Migration 0022
- [ ] Zero orphaned daily_plan records
- [ ] Zero orphaned subscriptions
- [ ] FK constraints verified in production
- [ ] CASCADE delete tested and working

### After Migration 0023
- [ ] Zero duplicate calendar entries
- [ ] Unique constraint enforced
- [ ] New duplicates prevented

### After All Actions
- [ ] 100% referential integrity
- [ ] Automated daily checks running
- [ ] All check constraints enforced
- [ ] Database triggers active

---

## 🚨 ROLLBACK PLAN

**If Migration 0022 Fails:**
```bash
# Rollback to previous version
alembic downgrade -1

# Or rollback to specific version
alembic downgrade 0021_add_habit_completions_table

# Verify rollback
alembic current
```

**If Production Issues After Deployment:**
```bash
# Emergency rollback via Railway
railway rollback

# Or manual rollback
export DATABASE_URL="production-url"
alembic downgrade -1
```

---

## 📞 CONTACTS

**Technical Issues:**
- Mikhail Yakovlev - mikhail@mita.finance
- Claude Code AI - Available 24/7

**Supabase Support:**
- Dashboard: https://supabase.com/dashboard
- Project: atdcxppfflmiwjwjuqyl

**Railway Support:**
- Dashboard: https://railway.app
- Project: mita-finance-production

---

## 📚 RELATED DOCUMENTS

1. **Comprehensive Report:** `/Users/mikhail/mita_project/DATABASE_INTEGRITY_COMPREHENSIVE_REPORT_2026-01-11.md` (901 lines)
2. **Migration 0022:** `/Users/mikhail/mita_project/alembic/versions/0022_add_missing_fk_constraints.py`
3. **SQL Diagnostic Script:** `/Users/mikhail/mita_project/scripts/data_integrity_check.sql`
4. **Python Diagnostic Script:** `/Users/mikhail/mita_project/scripts/run_data_integrity_check.py`
5. **Fix Script:** `/Users/mikhail/mita_project/scripts/fix_data_inconsistencies.sql`
6. **Previous Investigation:** `/Users/mikhail/mita_project/DATA_INTEGRITY_INVESTIGATION_REPORT_2026-01-06.md`

---

**Last Updated:** 2026-01-11
**Status:** Ready for execution
**Estimated Total Time:** 4-6 hours over 1 week

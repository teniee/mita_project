# MITA Database Migration - Quick Start Guide

**© 2025 YAKOVLEV LTD - All Rights Reserved**

## 🚀 Apply Migrations in 5 Minutes

### Prerequisites
- Supabase project created
- Access to Supabase SQL Editor
- Fresh database OR backup of existing data

### Step 1: Open Supabase SQL Editor (30 seconds)

1. Go to https://app.supabase.com
2. Select your project
3. Click "SQL Editor" in left sidebar
4. Click "+ New query"

### Step 2: Apply Consolidated Migration (2 minutes)

1. **Copy the SQL script:**
   - Open: `/Users/mikhail/StudioProjects/mita_project/alembic/consolidated_migration.sql`
   - Select all (Cmd+A)
   - Copy (Cmd+C)

2. **Paste into Supabase:**
   - Paste into SQL Editor
   - Click "Run" button (or Cmd+Enter)

3. **Wait for completion:**
   - Should complete in ~10-30 seconds
   - Watch for any error messages

### Step 3: Verify Migration (2 minutes)

1. **Run verification script:**
   - Open: `/Users/mikhail/StudioProjects/mita_project/alembic/verify_migration.sql`
   - Copy all
   - Paste into new SQL Editor tab
   - Run the query

2. **Check results:**
   - Look for "✓ PASS" markers
   - If you see "✗ FAIL" - check error details
   - All tables should be created (27 total)

### Step 4: Update Backend Connection (30 seconds)

1. **Get Supabase connection string:**
   - Supabase → Project Settings → Database
   - Copy "Connection string" (URI format)

2. **Update backend .env:**
   ```env
   DATABASE_URL=postgresql://[user]:[password]@[host]:[port]/[database]
   ```

### That's It! ✅

Your database is now ready with:
- ✓ 27 tables created
- ✓ 40+ indexes for performance
- ✓ 15+ foreign key constraints
- ✓ 2 auto-update triggers
- ✓ 8 sample challenges
- ✓ Soft delete support
- ✓ Financial precision (NUMERIC 12,2)

## Next Steps

### 1. Test API Connection

```bash
cd /Users/mikhail/StudioProjects/mita_project
uvicorn app.main:app --reload
```

Then test an endpoint:
```bash
curl http://localhost:8000/api/v1/health
```

### 2. Enable Supabase Features

#### Row Level Security (RLS)
```sql
-- Run in SQL Editor
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
-- Add for other tables as needed

-- Example policy: Users can only see their own data
CREATE POLICY "Users view own transactions"
ON transactions FOR SELECT
USING (auth.uid() = user_id);
```

#### Storage Bucket for Receipts
1. Go to Storage in Supabase
2. Create new bucket: `receipts`
3. Set as Public or Private (based on requirements)
4. Add RLS policies:
```sql
CREATE POLICY "Users upload own receipts"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'receipts' AND auth.uid()::text = (storage.foldername(name))[1]);
```

#### Realtime for Notifications
1. Go to Database → Replication
2. Enable for tables:
   - `notifications`
   - `transactions`
   - `goals`

### 3. Run Integration Tests

```bash
# From project root
pytest tests/ -v

# Or specific test suites
pytest tests/test_budgets.py -v
pytest tests/test_transactions.py -v
pytest tests/test_goals.py -v
```

### 4. Seed Development Data (Optional)

Create test user and data:
```sql
-- Run in Supabase SQL Editor
INSERT INTO users (
    id,
    email,
    password_hash,
    country,
    is_premium,
    email_verified,
    has_onboarded,
    created_at
) VALUES (
    gen_random_uuid(),
    'test@mita.finance',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5zyouFP6p6B5e', -- "password123"
    'US',
    TRUE,
    TRUE,
    TRUE,
    NOW()
) RETURNING id;

-- Copy the returned UUID and use it for test transactions:
INSERT INTO transactions (
    id,
    user_id,
    category,
    amount,
    currency,
    spent_at,
    created_at
) VALUES (
    gen_random_uuid(),
    '<paste-user-uuid-here>',
    'Food & Dining',
    25.50,
    'USD',
    NOW(),
    NOW()
);
```

## Troubleshooting

### ❌ Error: "relation already exists"
**Solution:** You have partial migration. Either:
1. Drop all tables and re-run consolidated script
2. Or skip already-created tables (not recommended)

```sql
-- Nuclear option (deletes everything):
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
-- Then re-run consolidated_migration.sql
```

### ❌ Error: "foreign key constraint fails"
**Solution:** Tables created out of order. Use consolidated script which handles dependencies.

### ❌ Error: "function update_updated_at_column() does not exist"
**Solution:** Trigger function not created. Run this first:
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';
```

### ⚠️ Warning: Some indexes missing
**Solution:** Non-critical. Backend will still work. Review verify_migration.sql output for details.

### ⚠️ Warning: Partial sample data
**Solution:** Sample challenges not inserted. Not critical for functionality.

## Quick Reference

### File Locations
```
/Users/mikhail/StudioProjects/mita_project/alembic/
├── consolidated_migration.sql       # ← Apply this to Supabase
├── verify_migration.sql            # ← Run this to verify
├── MIGRATION_APPLICATION_GUIDE.md  # ← Full detailed guide
└── QUICK_START.md                  # ← This file
```

### Migration Stats
- **Total migrations:** 19 files
- **Total tables:** 27
- **Total indexes:** 40+
- **Total foreign keys:** 15+
- **Lines of SQL:** ~1,500
- **Estimated execution time:** 10-30 seconds

### Database Size Estimates
- **Fresh database:** ~5 MB
- **With 1K users:** ~50 MB
- **With 10K users + transactions:** ~500 MB - 1 GB
- **With 100K users:** 5-10 GB

### Support

**Issues?** Check:
1. Supabase logs (Logs & Reports section)
2. verify_migration.sql output
3. Full guide: MIGRATION_APPLICATION_GUIDE.md

**Contact:**
- mikhail@mita.finance
- YAKOVLEV LTD (207808591)

---

**Ready to build the next generation of personal finance management!** 🚀

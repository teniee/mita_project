-- ============================================================================
-- SUPABASE MIGRATION: Add User Profile Fields
-- ============================================================================
-- Revision: 0008_add_user_profile_fields
-- Date: 2025-10-22
-- Description: Adds comprehensive user profile fields to the users table
-- ============================================================================

-- This migration adds:
-- - name: User's full name
-- - savings_goal: Monthly savings target
-- - budget_method: Budgeting methodology (e.g., 50/30/20 Rule)
-- - currency: User's preferred currency (e.g., USD, EUR)
-- - region: User's region/location
-- - notifications_enabled: Push notifications preference
-- - dark_mode_enabled: Dark mode UI preference
-- - monthly_income: Monthly income (if not exists)
-- - has_onboarded: Onboarding completion status (if not exists)

-- ============================================================================
-- STEP 1: Add Profile Fields
-- ============================================================================

-- Add name field
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR NULL;

-- Add savings_goal field with default value
ALTER TABLE users ADD COLUMN IF NOT EXISTS savings_goal NUMERIC NOT NULL DEFAULT 0;

-- Add budget_method field with default value
ALTER TABLE users ADD COLUMN IF NOT EXISTS budget_method VARCHAR NOT NULL DEFAULT '50/30/20 Rule';

-- Add currency field with default value (3-character ISO code)
ALTER TABLE users ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD';

-- Add region field
ALTER TABLE users ADD COLUMN IF NOT EXISTS region VARCHAR NULL;

-- ============================================================================
-- STEP 2: Add Preference Fields
-- ============================================================================

-- Add notifications_enabled field
ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT true;

-- Add dark_mode_enabled field
ALTER TABLE users ADD COLUMN IF NOT EXISTS dark_mode_enabled BOOLEAN NOT NULL DEFAULT false;

-- ============================================================================
-- STEP 3: Add Income and Onboarding Fields (if not exist)
-- ============================================================================

-- Add monthly_income field (may already exist in some deployments)
ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_income NUMERIC DEFAULT 0;

-- Add has_onboarded field (may already exist in some deployments)
ALTER TABLE users ADD COLUMN IF NOT EXISTS has_onboarded BOOLEAN NOT NULL DEFAULT false;

-- ============================================================================
-- STEP 4: Create Indexes for Performance
-- ============================================================================

-- Index for currency filtering (e.g., get all users with USD)
CREATE INDEX IF NOT EXISTS idx_users_currency ON users(currency);

-- Index for region filtering
CREATE INDEX IF NOT EXISTS idx_users_region ON users(region) WHERE region IS NOT NULL;

-- Index for onboarding status
CREATE INDEX IF NOT EXISTS idx_users_has_onboarded ON users(has_onboarded);

-- ============================================================================
-- STEP 5: Add Comments for Documentation
-- ============================================================================

COMMENT ON COLUMN users.name IS 'User full name';
COMMENT ON COLUMN users.savings_goal IS 'Monthly savings target amount';
COMMENT ON COLUMN users.budget_method IS 'Preferred budgeting methodology (e.g., 50/30/20 Rule, Zero-Based)';
COMMENT ON COLUMN users.currency IS 'User preferred currency (ISO 4217 code)';
COMMENT ON COLUMN users.region IS 'User geographic region';
COMMENT ON COLUMN users.notifications_enabled IS 'Push notifications enabled/disabled';
COMMENT ON COLUMN users.dark_mode_enabled IS 'Dark mode theme enabled/disabled';
COMMENT ON COLUMN users.monthly_income IS 'User monthly income';
COMMENT ON COLUMN users.has_onboarded IS 'User has completed onboarding process';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all columns were added successfully
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN (
    'name',
    'savings_goal',
    'budget_method',
    'currency',
    'region',
    'notifications_enabled',
    'dark_mode_enabled',
    'monthly_income',
    'has_onboarded'
)
ORDER BY column_name;

-- ============================================================================
-- ROLLBACK SCRIPT (if needed)
-- ============================================================================
-- UNCOMMENT ONLY IF YOU NEED TO ROLLBACK THIS MIGRATION

-- DROP INDEX IF EXISTS idx_users_has_onboarded;
-- DROP INDEX IF EXISTS idx_users_region;
-- DROP INDEX IF EXISTS idx_users_currency;
--
-- ALTER TABLE users DROP COLUMN IF EXISTS dark_mode_enabled;
-- ALTER TABLE users DROP COLUMN IF EXISTS notifications_enabled;
-- ALTER TABLE users DROP COLUMN IF EXISTS region;
-- ALTER TABLE users DROP COLUMN IF EXISTS currency;
-- ALTER TABLE users DROP COLUMN IF EXISTS budget_method;
-- ALTER TABLE users DROP COLUMN IF EXISTS savings_goal;
-- ALTER TABLE users DROP COLUMN IF EXISTS name;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

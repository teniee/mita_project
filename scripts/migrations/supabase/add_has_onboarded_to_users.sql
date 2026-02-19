-- Migration: Add has_onboarded field to users table
-- Date: 2025-10-21
-- Description: Adds has_onboarded boolean field to track onboarding completion

-- Add the has_onboarded column with default value of false
ALTER TABLE users
ADD COLUMN IF NOT EXISTS has_onboarded BOOLEAN NOT NULL DEFAULT false;

-- Update existing users who have monthly_income set to be marked as onboarded
-- This handles users who completed onboarding before this migration
UPDATE users
SET has_onboarded = true
WHERE monthly_income > 0;

-- Add a comment to document the column
COMMENT ON COLUMN users.has_onboarded IS 'Tracks whether user has completed the onboarding process';

-- Create an index for better query performance (optional but recommended)
CREATE INDEX IF NOT EXISTS idx_users_has_onboarded ON users(has_onboarded);

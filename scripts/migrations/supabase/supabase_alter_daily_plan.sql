-- Migration: Add budget tracking columns to existing daily_plan table
-- Run this in Supabase SQL Editor

-- Add category column with index
ALTER TABLE daily_plan ADD COLUMN IF NOT EXISTS category VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_daily_plan_category ON daily_plan(category);

-- Add planned_amount column
ALTER TABLE daily_plan ADD COLUMN IF NOT EXISTS planned_amount NUMERIC(12, 2) DEFAULT 0.00;

-- Add spent_amount column
ALTER TABLE daily_plan ADD COLUMN IF NOT EXISTS spent_amount NUMERIC(12, 2) DEFAULT 0.00;

-- Add daily_budget column
ALTER TABLE daily_plan ADD COLUMN IF NOT EXISTS daily_budget NUMERIC(12, 2);

-- Add status column
ALTER TABLE daily_plan ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'green';

-- Make plan_json nullable (if it's NOT NULL currently)
ALTER TABLE daily_plan ALTER COLUMN plan_json DROP NOT NULL;

-- Create composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_daily_plan_user_date_category ON daily_plan(user_id, date, category);

-- Verify changes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'daily_plan'
ORDER BY ordinal_position;

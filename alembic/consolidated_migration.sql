-- MITA Project - Consolidated Database Migration Script
-- Generated: 2025-12-14
-- Target: Supabase PostgreSQL 15.8
-- © 2025 YAKOVLEV LTD - All Rights Reserved

-- This script consolidates ALL Alembic migrations into a single executable SQL file
-- Apply this to a fresh Supabase database to create the complete schema

-- ============================================================================
-- MIGRATION 0001_initial: Initial unified migration
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    country VARCHAR(2) DEFAULT 'US',
    annual_income NUMERIC DEFAULT 0,
    is_premium BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    category VARCHAR NOT NULL,
    amount NUMERIC NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    spent_at TIMESTAMP,
    created_at TIMESTAMP
);
CREATE INDEX ON transactions(user_id);
CREATE INDEX ON transactions(spent_at);

CREATE TABLE daily_plan (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    date TIMESTAMP NOT NULL,
    plan_json JSONB NOT NULL,
    created_at TIMESTAMP
);
CREATE INDEX ON daily_plan(user_id);
CREATE INDEX ON daily_plan(date);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    platform VARCHAR NOT NULL,
    receipt JSONB NOT NULL,
    status VARCHAR DEFAULT 'active',
    current_period_end TIMESTAMP,
    created_at TIMESTAMP
);
CREATE INDEX ON subscriptions(user_id);

CREATE TABLE ai_analysis_snapshots (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    rating VARCHAR,
    risk VARCHAR,
    summary VARCHAR,
    full_profile JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- MIGRATION 0002_mood: Add moods table
-- ============================================================================

CREATE TABLE moods (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    date DATE NOT NULL,
    mood VARCHAR NOT NULL
);
CREATE INDEX ON moods(user_id);
CREATE INDEX ON moods(date);

-- ============================================================================
-- MIGRATION 0003_goals: Add goals table
-- ============================================================================

CREATE TABLE goals (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR NOT NULL,
    target_amount NUMERIC NOT NULL,
    saved_amount NUMERIC NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON goals(user_id);

-- ============================================================================
-- MIGRATION 0004_user_premium_until: Add premium_until field to user
-- ============================================================================

ALTER TABLE users ADD COLUMN premium_until TIMESTAMP;

-- ============================================================================
-- MIGRATION 0005_push_tokens: Add push tokens table
-- ============================================================================

CREATE TABLE push_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    token VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON push_tokens(user_id);

-- ============================================================================
-- MIGRATION a0d5ecc53667_sync_models: Sync models
-- ============================================================================

CREATE TABLE ai_advice_templates (
    id UUID PRIMARY KEY,
    key VARCHAR NOT NULL,
    text VARCHAR NOT NULL
);
CREATE UNIQUE INDEX ix_ai_advice_templates_key ON ai_advice_templates(key);

CREATE TABLE budget_advice (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    date TIMESTAMP WITH TIME ZONE,
    type VARCHAR NOT NULL,
    text VARCHAR NOT NULL
);
CREATE INDEX ix_budget_advice_date ON budget_advice(date);
CREATE INDEX ix_budget_advice_user_id ON budget_advice(user_id);

CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    amount FLOAT NOT NULL,
    date DATE NOT NULL
);
CREATE INDEX ix_expenses_id ON expenses(id);
CREATE INDEX ix_expenses_user_id ON expenses(user_id);

CREATE TABLE habits (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP
);
CREATE INDEX ix_habits_user_id ON habits(user_id);

CREATE TABLE notification_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    channel VARCHAR NOT NULL,
    message VARCHAR NOT NULL,
    success BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_notification_logs_user_id ON notification_logs(user_id);

CREATE TABLE user_answers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    question_key VARCHAR NOT NULL,
    answer_json VARCHAR
);

CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL UNIQUE,
    data VARCHAR
);

-- Update ai_analysis_snapshots
ALTER TABLE ai_analysis_snapshots
    ALTER COLUMN full_profile TYPE JSON USING full_profile::JSON;
CREATE INDEX ix_ai_analysis_snapshots_id ON ai_analysis_snapshots(id);
ALTER TABLE ai_analysis_snapshots
    ADD CONSTRAINT fk_ai_analysis_snapshots_user_id FOREIGN KEY (user_id) REFERENCES users(id);

-- Update daily_plan timestamps
ALTER TABLE daily_plan
    ALTER COLUMN date TYPE TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;

-- Update push_tokens
ALTER TABLE push_tokens ADD COLUMN platform VARCHAR NOT NULL DEFAULT 'ios';

-- Update subscriptions
ALTER TABLE subscriptions
    ADD COLUMN plan VARCHAR,
    ADD COLUMN starts_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE,
    DROP COLUMN current_period_end;

-- Update transactions
ALTER TABLE transactions
    ALTER COLUMN spent_at TYPE TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;

-- Update users
ALTER TABLE users
    ADD COLUMN timezone VARCHAR,
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;

-- ============================================================================
-- MIGRATION 0006_fix_financial_data_types: Fix critical financial data types
-- ============================================================================

-- Create backup table
CREATE TEMP TABLE expenses_backup AS SELECT * FROM expenses;

-- Fix expenses table
ALTER TABLE expenses
    ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2),
    ALTER COLUMN user_id TYPE UUID USING user_id::UUID;

-- Add foreign key constraints
ALTER TABLE expenses
    ADD CONSTRAINT fk_expenses_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Fix goals table
ALTER TABLE goals
    ALTER COLUMN target_amount TYPE NUMERIC(12,2),
    ALTER COLUMN saved_amount TYPE NUMERIC(12,2);

ALTER TABLE goals
    ADD CONSTRAINT fk_goals_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Fix users table
ALTER TABLE users
    ALTER COLUMN annual_income TYPE NUMERIC(12,2);

-- Fix user_answers table
ALTER TABLE user_answers
    ALTER COLUMN user_id TYPE UUID USING user_id::UUID;

ALTER TABLE user_answers
    ADD CONSTRAINT fk_user_answers_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Fix user_profiles table
ALTER TABLE user_profiles
    ALTER COLUMN user_id TYPE UUID USING user_id::UUID;

ALTER TABLE user_profiles
    ADD CONSTRAINT fk_user_profiles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Add critical indexes
CREATE INDEX ix_expenses_user_id_date ON expenses(user_id, date);
CREATE INDEX ix_transactions_user_id_spent_at ON transactions(user_id, spent_at);

-- ============================================================================
-- MIGRATION 0007_email_password_reset_fields: Add email verification and password reset
-- ============================================================================

ALTER TABLE users
    ADD COLUMN password_reset_token VARCHAR,
    ADD COLUMN password_reset_expires TIMESTAMP WITH TIME ZONE,
    ADD COLUMN password_reset_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN email_verification_token VARCHAR,
    ADD COLUMN email_verification_expires TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_users_password_reset_token ON users(password_reset_token);
CREATE INDEX idx_users_email_verification_token ON users(email_verification_token);
CREATE INDEX idx_users_email_verified ON users(email_verified);

-- ============================================================================
-- MIGRATION f8e0108e3527: Add missing user fields (updated_at, token_version)
-- ============================================================================

-- Create trigger function for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

ALTER TABLE users
    ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1;

CREATE INDEX idx_users_updated_at ON users(updated_at);
CREATE INDEX idx_users_token_version ON users(token_version);

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- MIGRATION 0008_add_user_profile_fields: Add user profile fields
-- ============================================================================

ALTER TABLE users
    ADD COLUMN name VARCHAR,
    ADD COLUMN savings_goal NUMERIC NOT NULL DEFAULT 0,
    ADD COLUMN budget_method VARCHAR NOT NULL DEFAULT '50/30/20 Rule',
    ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    ADD COLUMN region VARCHAR,
    ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN dark_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- Add monthly_income if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='monthly_income'
    ) THEN
        ALTER TABLE users ADD COLUMN monthly_income NUMERIC DEFAULT 0;
    END IF;
END $$;

-- Add has_onboarded if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='has_onboarded'
    ) THEN
        ALTER TABLE users ADD COLUMN has_onboarded BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

CREATE INDEX idx_users_currency ON users(currency);
CREATE INDEX idx_users_region ON users(region);
CREATE INDEX idx_users_has_onboarded ON users(has_onboarded);

-- ============================================================================
-- MIGRATION 0009_add_transaction_extended_fields: Add extended transaction fields
-- ============================================================================

ALTER TABLE transactions
    ADD COLUMN merchant VARCHAR(200),
    ADD COLUMN location VARCHAR(200),
    ADD COLUMN tags VARCHAR[],
    ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN confidence_score FLOAT,
    ADD COLUMN receipt_url VARCHAR(500),
    ADD COLUMN notes TEXT,
    ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

CREATE INDEX idx_transactions_merchant ON transactions(merchant);
CREATE INDEX idx_transactions_is_recurring ON transactions(is_recurring);
CREATE INDEX idx_transactions_updated_at ON transactions(updated_at);

CREATE TRIGGER update_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- MIGRATION 0010_enhance_goals: Enhance goals table
-- ============================================================================

ALTER TABLE goals
    ADD COLUMN description TEXT,
    ADD COLUMN category VARCHAR(50),
    ADD COLUMN monthly_contribution NUMERIC(10,2),
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active',
    ADD COLUMN progress NUMERIC(5,2) NOT NULL DEFAULT 0,
    ADD COLUMN target_date DATE,
    ADD COLUMN last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    ADD COLUMN completed_at TIMESTAMP,
    ADD COLUMN priority VARCHAR(10) DEFAULT 'medium',
    ALTER COLUMN target_amount TYPE NUMERIC(10,2),
    ALTER COLUMN saved_amount TYPE NUMERIC(10,2),
    ALTER COLUMN title TYPE VARCHAR(200);

CREATE INDEX ix_goals_category ON goals(category);
CREATE INDEX ix_goals_status ON goals(status);

-- ============================================================================
-- MIGRATION 0011_add_goal_id: Add goal_id to transactions
-- ============================================================================

ALTER TABLE transactions
    ADD COLUMN goal_id UUID;

ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_goal_id FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE SET NULL;

CREATE INDEX ix_transactions_goal_id ON transactions(goal_id);

-- ============================================================================
-- MIGRATION 0012_add_challenges: Add challenges tables
-- ============================================================================

CREATE TABLE challenges (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    duration_days INTEGER NOT NULL,
    reward_points INTEGER DEFAULT 0,
    difficulty VARCHAR(20) NOT NULL,
    start_month VARCHAR(7) NOT NULL,
    end_month VARCHAR(7) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE challenge_participations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    challenge_id VARCHAR NOT NULL,
    month VARCHAR(7) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    progress_percentage INTEGER DEFAULT 0,
    days_completed INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE
);

CREATE INDEX ix_challenge_participations_user_id ON challenge_participations(user_id);
CREATE INDEX ix_challenge_participations_challenge_id ON challenge_participations(challenge_id);
CREATE INDEX ix_challenge_participations_month ON challenge_participations(month);
CREATE INDEX ix_challenge_participations_status ON challenge_participations(status);

-- Insert sample challenges
INSERT INTO challenges (id, name, description, type, duration_days, reward_points, difficulty, start_month, end_month)
VALUES
    ('savings_streak_7', '7-Day Savings Streak', 'Save money every day for 7 consecutive days', 'streak', 7, 100, 'easy', '2025-01', '2025-12'),
    ('savings_streak_30', '30-Day Savings Challenge', 'Build a monthly savings habit by saving every day', 'streak', 30, 500, 'medium', '2025-01', '2025-12'),
    ('no_coffee_challenge', 'Skip the Coffee', 'Reduce coffee shop expenses for 14 days', 'category_restriction', 14, 200, 'medium', '2025-01', '2025-12'),
    ('dining_reduction', 'Cook at Home Challenge', 'Reduce dining out expenses by 50% this month', 'category_reduction', 30, 300, 'medium', '2025-01', '2025-12'),
    ('transportation_saver', 'Commute Smart', 'Save on transportation costs for 21 days', 'category_reduction', 21, 250, 'easy', '2025-01', '2025-12'),
    ('budget_master', 'Budget Master', 'Stay within budget for all categories for 30 days', 'streak', 30, 1000, 'hard', '2025-01', '2025-12'),
    ('impulse_free', 'Impulse-Free Zone', 'Avoid impulse purchases for 14 days', 'category_restriction', 14, 300, 'medium', '2025-01', '2025-12'),
    ('weekly_saver', 'Weekly Savings Goal', 'Save a specific amount every week for 4 weeks', 'streak', 28, 400, 'medium', '2025-01', '2025-12');

-- ============================================================================
-- MIGRATION 0013_add_analytics_tables: Add analytics tables
-- ============================================================================

CREATE TABLE feature_usage_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    feature VARCHAR(100) NOT NULL,
    screen VARCHAR(100),
    action VARCHAR(100),
    extra_data JSON,
    session_id VARCHAR(100),
    platform VARCHAR(20),
    app_version VARCHAR(20),
    timestamp TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX ix_feature_usage_logs_user_id ON feature_usage_logs(user_id);
CREATE INDEX ix_feature_usage_logs_feature ON feature_usage_logs(feature);
CREATE INDEX ix_feature_usage_logs_screen ON feature_usage_logs(screen);
CREATE INDEX ix_feature_usage_logs_session_id ON feature_usage_logs(session_id);
CREATE INDEX ix_feature_usage_logs_timestamp ON feature_usage_logs(timestamp);

CREATE TABLE feature_access_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    feature VARCHAR(100) NOT NULL,
    has_access BOOLEAN NOT NULL DEFAULT FALSE,
    is_premium_feature BOOLEAN NOT NULL DEFAULT FALSE,
    converted_to_premium BOOLEAN DEFAULT FALSE,
    converted_at TIMESTAMP WITH TIME ZONE,
    screen VARCHAR(100),
    extra_data JSON,
    timestamp TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX ix_feature_access_logs_user_id ON feature_access_logs(user_id);
CREATE INDEX ix_feature_access_logs_feature ON feature_access_logs(feature);
CREATE INDEX ix_feature_access_logs_timestamp ON feature_access_logs(timestamp);

CREATE TABLE paywall_impression_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    screen VARCHAR(100) NOT NULL,
    feature VARCHAR(100),
    resulted_in_purchase BOOLEAN DEFAULT FALSE,
    purchase_timestamp TIMESTAMP WITH TIME ZONE,
    impression_context VARCHAR(200),
    extra_data JSON,
    timestamp TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX ix_paywall_impression_logs_user_id ON paywall_impression_logs(user_id);
CREATE INDEX ix_paywall_impression_logs_screen ON paywall_impression_logs(screen);
CREATE INDEX ix_paywall_impression_logs_timestamp ON paywall_impression_logs(timestamp);

-- ============================================================================
-- MIGRATION 0014_add_notifications_table: Add notifications table
-- ============================================================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'info',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    image_url VARCHAR(500),
    action_url VARCHAR(500),
    data JSON,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    channel VARCHAR(20),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count VARCHAR NOT NULL DEFAULT '0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    category VARCHAR(50),
    group_key VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_id ON notifications(user_id);
CREATE INDEX ix_notifications_is_read ON notifications(is_read);
CREATE INDEX ix_notifications_scheduled_for ON notifications(scheduled_for);
CREATE INDEX ix_notifications_created_at ON notifications(created_at);
CREATE INDEX ix_notifications_group_key ON notifications(group_key);
CREATE INDEX ix_notifications_user_id_is_read_created_at ON notifications(user_id, is_read, created_at);

-- ============================================================================
-- MIGRATION 0015_add_installments_module: Add installments module
-- ============================================================================

CREATE TABLE user_financial_profiles (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    monthly_income NUMERIC(12,2) NOT NULL,
    current_balance NUMERIC(12,2) NOT NULL,
    age_group VARCHAR(10) NOT NULL DEFAULT '25-34',
    credit_card_debt BOOLEAN NOT NULL DEFAULT FALSE,
    credit_card_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
    other_loans_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
    rent_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
    subscriptions_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
    planning_mortgage BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX ix_user_financial_profiles_user_id ON user_financial_profiles(user_id);

CREATE TABLE installments (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    item_name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'other',
    total_amount NUMERIC(12,2) NOT NULL,
    payment_amount NUMERIC(12,2) NOT NULL,
    interest_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    total_payments INTEGER NOT NULL,
    payments_made INTEGER NOT NULL DEFAULT 0,
    payment_frequency VARCHAR(20) NOT NULL DEFAULT 'monthly',
    first_payment_date TIMESTAMP WITH TIME ZONE NOT NULL,
    next_payment_date TIMESTAMP WITH TIME ZONE NOT NULL,
    final_payment_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX ix_installments_user_id ON installments(user_id);
CREATE INDEX ix_installments_created_at ON installments(created_at);

CREATE TABLE installment_calculations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    installment_id UUID,
    purchase_amount NUMERIC(12,2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    num_payments INTEGER NOT NULL,
    interest_rate NUMERIC(5,2) NOT NULL,
    monthly_payment NUMERIC(12,2) NOT NULL,
    total_interest NUMERIC(12,2) NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    dti_ratio NUMERIC(5,2) NOT NULL,
    payment_to_income_ratio NUMERIC(5,2) NOT NULL,
    remaining_balance NUMERIC(12,2) NOT NULL,
    risk_factors TEXT,
    user_proceeded BOOLEAN NOT NULL DEFAULT FALSE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (installment_id) REFERENCES installments(id) ON DELETE SET NULL
);
CREATE INDEX ix_installment_calculations_user_id ON installment_calculations(user_id);
CREATE INDEX ix_installment_calculations_installment_id ON installment_calculations(installment_id);
CREATE INDEX ix_installment_calculations_calculated_at ON installment_calculations(calculated_at);

CREATE TABLE installment_achievements (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    installments_completed INTEGER NOT NULL DEFAULT 0,
    calculations_performed INTEGER NOT NULL DEFAULT 0,
    calculations_declined INTEGER NOT NULL DEFAULT 0,
    days_without_new_installment INTEGER NOT NULL DEFAULT 0,
    max_days_streak INTEGER NOT NULL DEFAULT 0,
    interest_saved NUMERIC(12,2) NOT NULL DEFAULT 0,
    achievement_level VARCHAR(20) NOT NULL DEFAULT 'beginner',
    last_calculation_date TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX ix_installment_achievements_user_id ON installment_achievements(user_id);

-- ============================================================================
-- MIGRATION 0017_add_account_security_fields: Add account security fields
-- ============================================================================

ALTER TABLE users
    ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN account_locked_until TIMESTAMP WITH TIME ZONE;

-- ============================================================================
-- MIGRATION 0018_add_soft_deletes: Add soft delete support
-- ============================================================================

ALTER TABLE transactions
    ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE goals
    ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE installments
    ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_transactions_deleted_at ON transactions(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_goals_deleted_at ON goals(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_installments_deleted_at ON installments(deleted_at) WHERE deleted_at IS NULL;

-- ============================================================================
-- ALEMBIC VERSION TRACKING
-- ============================================================================

-- Create alembic_version table if it doesn't exist
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

-- Insert the final migration version
-- Use the latest migration in the chain
INSERT INTO alembic_version (version_num) VALUES ('0018_add_soft_deletes')
ON CONFLICT (version_num) DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Uncomment these to verify the migration was successful:
-- SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public';
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
-- SELECT * FROM alembic_version;

-- ============================================================================
-- END OF MIGRATION SCRIPT
-- ============================================================================

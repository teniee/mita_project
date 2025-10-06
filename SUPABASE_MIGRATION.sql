-- MITA Backend - New Tables Migration
-- Run this in Supabase SQL Editor

-- 1. Challenges table
CREATE TABLE IF NOT EXISTS challenges (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    duration_days INTEGER NOT NULL,
    reward_points INTEGER DEFAULT 0,
    difficulty VARCHAR(20) DEFAULT 'medium',
    start_month VARCHAR(7) NOT NULL,
    end_month VARCHAR(7) NOT NULL,
    icon_name VARCHAR(50),
    color VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_challenges_type ON challenges(type);
CREATE INDEX IF NOT EXISTS idx_challenges_active ON challenges(is_active);
CREATE INDEX IF NOT EXISTS idx_challenges_dates ON challenges(start_month, end_month);

-- 2. Challenge Participations table
CREATE TABLE IF NOT EXISTS challenge_participations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    challenge_id VARCHAR(100) NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active',
    progress_percentage NUMERIC(5, 2) DEFAULT 0,
    days_completed INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    points_earned INTEGER DEFAULT 0,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    extra_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_challenge_participations_user ON challenge_participations(user_id);
CREATE INDEX IF NOT EXISTS idx_challenge_participations_challenge ON challenge_participations(challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_participations_status ON challenge_participations(status);
CREATE INDEX IF NOT EXISTS idx_challenge_participations_user_status ON challenge_participations(user_id, status);

-- 3. OCR Jobs table
CREATE TABLE IF NOT EXISTS ocr_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    extracted_text TEXT,
    merchant_name VARCHAR(200),
    total_amount NUMERIC(15, 2),
    transaction_date DATE,
    category VARCHAR(100),
    confidence_score NUMERIC(3, 2),
    error_message TEXT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ocr_jobs_user ON ocr_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status ON ocr_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_created ON ocr_jobs(created_at DESC);

-- 4. Feature Usage Logs table
CREATE TABLE IF NOT EXISTS feature_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    feature VARCHAR(100) NOT NULL,
    screen VARCHAR(100),
    action VARCHAR(100),
    extra_data JSONB,
    session_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feature_usage_user ON feature_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_feature_usage_feature ON feature_usage_logs(feature);
CREATE INDEX IF NOT EXISTS idx_feature_usage_screen ON feature_usage_logs(screen);
CREATE INDEX IF NOT EXISTS idx_feature_usage_timestamp ON feature_usage_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feature_usage_session ON feature_usage_logs(session_id);

-- 5. Feature Access Logs table (Premium features tracking)
CREATE TABLE IF NOT EXISTS feature_access_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    feature VARCHAR(100) NOT NULL,
    access_granted BOOLEAN NOT NULL,
    user_plan VARCHAR(50),
    extra_data JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feature_access_user ON feature_access_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_feature_access_feature ON feature_access_logs(feature);
CREATE INDEX IF NOT EXISTS idx_feature_access_granted ON feature_access_logs(access_granted);
CREATE INDEX IF NOT EXISTS idx_feature_access_timestamp ON feature_access_logs(timestamp DESC);

-- 6. Paywall Impression Logs table
CREATE TABLE IF NOT EXISTS paywall_impression_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    paywall_type VARCHAR(50) NOT NULL,
    trigger_context VARCHAR(100),
    action_taken VARCHAR(50),
    extra_data JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paywall_impression_user ON paywall_impression_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_paywall_impression_type ON paywall_impression_logs(paywall_type);
CREATE INDEX IF NOT EXISTS idx_paywall_impression_action ON paywall_impression_logs(action_taken);
CREATE INDEX IF NOT EXISTS idx_paywall_impression_timestamp ON paywall_impression_logs(timestamp DESC);

-- 7. User Preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    behavioral_enabled BOOLEAN DEFAULT true,
    behavioral_savings_target NUMERIC(5, 2) DEFAULT 20.0,
    behavioral_risk_tolerance VARCHAR(20) DEFAULT 'moderate',
    notification_budget_alert BOOLEAN DEFAULT true,
    notification_daily_summary BOOLEAN DEFAULT false,
    notification_challenge_reminder BOOLEAN DEFAULT true,
    notification_goal_milestone BOOLEAN DEFAULT true,
    budget_auto_rollover BOOLEAN DEFAULT true,
    budget_weekly_reset BOOLEAN DEFAULT false,
    preferred_currency VARCHAR(3) DEFAULT 'USD',
    theme VARCHAR(20) DEFAULT 'system',
    language VARCHAR(10) DEFAULT 'en',
    extra_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);

-- 8. Habit Completions table
CREATE TABLE IF NOT EXISTS habit_completions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    habit_id UUID NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_habit_completions_habit ON habit_completions(habit_id);
CREATE INDEX IF NOT EXISTS idx_habit_completions_user ON habit_completions(user_id);
CREATE INDEX IF NOT EXISTS idx_habit_completions_date ON habit_completions(completed_at DESC);

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully! All 8 new tables created.';
END $$;

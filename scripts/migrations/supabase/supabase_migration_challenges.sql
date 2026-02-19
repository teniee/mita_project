-- =====================================================
-- MODULE 5: CHALLENGES SYSTEM - SUPABASE MIGRATION
-- =====================================================
-- Run this SQL in Supabase SQL Editor
-- https://app.supabase.com/project/YOUR_PROJECT/sql

-- =====================================================
-- 1. CREATE CHALLENGES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS challenges (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,  -- streak, category_restriction, category_reduction
    duration_days INTEGER NOT NULL,
    reward_points INTEGER DEFAULT 0,
    difficulty VARCHAR(20) NOT NULL,  -- easy, medium, hard
    start_month VARCHAR(7) NOT NULL,  -- "2025-01"
    end_month VARCHAR(7) NOT NULL,    -- "2025-12"
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. CREATE CHALLENGE_PARTICIPATIONS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS challenge_participations (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    challenge_id VARCHAR NOT NULL,
    month VARCHAR(7) NOT NULL,  -- "2025-10"
    status VARCHAR(20) DEFAULT 'active',  -- active, completed, failed, abandoned
    progress_percentage INTEGER DEFAULT 0,
    days_completed INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    CONSTRAINT fk_challenge_participations_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_challenge_participations_challenge
        FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE
);

-- =====================================================
-- 3. CREATE INDEXES FOR PERFORMANCE
-- =====================================================

CREATE INDEX IF NOT EXISTS ix_challenge_participations_user_id
    ON challenge_participations(user_id);

CREATE INDEX IF NOT EXISTS ix_challenge_participations_challenge_id
    ON challenge_participations(challenge_id);

CREATE INDEX IF NOT EXISTS ix_challenge_participations_month
    ON challenge_participations(month);

CREATE INDEX IF NOT EXISTS ix_challenge_participations_status
    ON challenge_participations(status);

-- =====================================================
-- 4. CREATE TRIGGER FOR AUTO-UPDATE TIMESTAMPS
-- =====================================================

-- Trigger function for challenges table
CREATE OR REPLACE FUNCTION update_challenges_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_challenges_updated_at
    BEFORE UPDATE ON challenges
    FOR EACH ROW
    EXECUTE FUNCTION update_challenges_updated_at();

-- Trigger function for challenge_participations table
CREATE OR REPLACE FUNCTION update_challenge_participations_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_challenge_participations_last_updated
    BEFORE UPDATE ON challenge_participations
    FOR EACH ROW
    EXECUTE FUNCTION update_challenge_participations_last_updated();

-- =====================================================
-- 5. INSERT SAMPLE CHALLENGES (8 CHALLENGES)
-- =====================================================

INSERT INTO challenges (id, name, description, type, duration_days, reward_points, difficulty, start_month, end_month)
VALUES
    -- Easy Challenges
    ('savings_streak_7',
     '7-Day Savings Streak',
     'Save money every day for 7 consecutive days',
     'streak', 7, 100, 'easy', '2025-01', '2025-12'),

    ('transportation_saver',
     'Commute Smart',
     'Save on transportation costs for 21 days',
     'category_reduction', 21, 250, 'easy', '2025-01', '2025-12'),

    -- Medium Challenges
    ('savings_streak_30',
     '30-Day Savings Challenge',
     'Build a monthly savings habit by saving every day',
     'streak', 30, 500, 'medium', '2025-01', '2025-12'),

    ('no_coffee_challenge',
     'Skip the Coffee',
     'Reduce coffee shop expenses for 14 days',
     'category_restriction', 14, 200, 'medium', '2025-01', '2025-12'),

    ('dining_reduction',
     'Cook at Home Challenge',
     'Reduce dining out expenses by 50% this month',
     'category_reduction', 30, 300, 'medium', '2025-01', '2025-12'),

    ('impulse_free',
     'Impulse-Free Zone',
     'Avoid impulse purchases for 14 days',
     'category_restriction', 14, 300, 'medium', '2025-01', '2025-12'),

    ('weekly_saver',
     'Weekly Savings Goal',
     'Save a specific amount every week for 4 weeks',
     'streak', 28, 400, 'medium', '2025-01', '2025-12'),

    -- Hard Challenges
    ('budget_master',
     'Budget Master',
     'Stay within budget for all categories for 30 days',
     'streak', 30, 1000, 'hard', '2025-01', '2025-12')
ON CONFLICT (id) DO NOTHING;  -- Skip if already exists

-- =====================================================
-- 6. VERIFY MIGRATION
-- =====================================================

-- Check challenges table
SELECT 'Challenges table' as table_name, COUNT(*) as row_count FROM challenges;

-- Check challenge_participations table
SELECT 'Challenge participations table' as table_name, COUNT(*) as row_count FROM challenge_participations;

-- List all challenges
SELECT id, name, difficulty, reward_points FROM challenges ORDER BY difficulty, reward_points;

-- Check indexes
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('challenges', 'challenge_participations')
ORDER BY tablename, indexname;

-- =====================================================
-- MIGRATION COMPLETE!
-- =====================================================
--
-- Next steps:
-- 1. Verify row counts above
-- 2. You should see 8 challenges
-- 3. You should see 4 indexes on challenge_participations
-- 4. You're ready to use the Challenges feature!
--
-- =====================================================

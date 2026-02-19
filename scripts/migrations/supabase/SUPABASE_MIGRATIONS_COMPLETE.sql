-- ============================================================================
-- MITA PROJECT: COMPLETE DATABASE MIGRATIONS FOR SUPABASE
-- ============================================================================
-- This script applies ALL pending migrations (0008 through 0018)
-- Safe to run multiple times - includes existence checks for all objects
--
-- CRITICAL MIGRATIONS:
--   0008: User profile fields (name, savings_goal, currency, etc.)
--   0009: Transaction extended fields (merchant, location, tags, etc.)
--   0010: Enhanced goals table (description, category, status, etc.)
--   0011: Link transactions to goals (goal_id foreign key)
--   0012: Challenges tables (gamification features)
--   0013: Analytics tables (feature usage tracking)
--   0014: Notifications table (push notification system)
--   0015: Installments module (BNPL payment tracking)
--   0017: Account security fields (failed login attempts, account lockout)
--   0018: Soft deletes (deleted_at for financial compliance)
--
-- INSTRUCTIONS:
--   1. Go to Supabase Dashboard → SQL Editor
--   2. Copy and paste this entire script
--   3. Click "Run" to execute
--   4. Verify success messages in output
-- ============================================================================

BEGIN;

RAISE NOTICE '============================================================================';
RAISE NOTICE 'MITA DATABASE MIGRATION - STARTING';
RAISE NOTICE 'Timestamp: %', NOW();
RAISE NOTICE '============================================================================';

-- ============================================================================
-- MIGRATION 0008: Add User Profile Fields
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0008] Adding user profile fields...';

DO $$
BEGIN
    -- name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='name') THEN
        ALTER TABLE users ADD COLUMN name VARCHAR;
        RAISE NOTICE '  ✓ Added column: users.name';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.name';
    END IF;

    -- savings_goal
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='savings_goal') THEN
        ALTER TABLE users ADD COLUMN savings_goal NUMERIC NOT NULL DEFAULT 0;
        RAISE NOTICE '  ✓ Added column: users.savings_goal';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.savings_goal';
    END IF;

    -- budget_method
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='budget_method') THEN
        ALTER TABLE users ADD COLUMN budget_method VARCHAR NOT NULL DEFAULT '50/30/20 Rule';
        RAISE NOTICE '  ✓ Added column: users.budget_method';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.budget_method';
    END IF;

    -- currency
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='currency') THEN
        ALTER TABLE users ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'USD';
        RAISE NOTICE '  ✓ Added column: users.currency';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.currency';
    END IF;

    -- region
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='region') THEN
        ALTER TABLE users ADD COLUMN region VARCHAR;
        RAISE NOTICE '  ✓ Added column: users.region';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.region';
    END IF;

    -- notifications_enabled
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='notifications_enabled') THEN
        ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT true;
        RAISE NOTICE '  ✓ Added column: users.notifications_enabled';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.notifications_enabled';
    END IF;

    -- dark_mode_enabled
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='dark_mode_enabled') THEN
        ALTER TABLE users ADD COLUMN dark_mode_enabled BOOLEAN NOT NULL DEFAULT false;
        RAISE NOTICE '  ✓ Added column: users.dark_mode_enabled';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.dark_mode_enabled';
    END IF;

    -- monthly_income (conditional - may exist from other migrations)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='monthly_income') THEN
        ALTER TABLE users ADD COLUMN monthly_income NUMERIC DEFAULT 0;
        RAISE NOTICE '  ✓ Added column: users.monthly_income';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.monthly_income';
    END IF;

    -- has_onboarded (conditional)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='has_onboarded') THEN
        ALTER TABLE users ADD COLUMN has_onboarded BOOLEAN NOT NULL DEFAULT false;
        RAISE NOTICE '  ✓ Added column: users.has_onboarded';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.has_onboarded';
    END IF;

    -- Create indexes
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_currency') THEN
        CREATE INDEX idx_users_currency ON users(currency);
        RAISE NOTICE '  ✓ Created index: idx_users_currency';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_region') THEN
        CREATE INDEX idx_users_region ON users(region);
        RAISE NOTICE '  ✓ Created index: idx_users_region';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_has_onboarded') THEN
        CREATE INDEX idx_users_has_onboarded ON users(has_onboarded);
        RAISE NOTICE '  ✓ Created index: idx_users_has_onboarded';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0009: Add Transaction Extended Fields
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0009] Adding transaction extended fields...';

DO $$
BEGIN
    -- merchant
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='merchant') THEN
        ALTER TABLE transactions ADD COLUMN merchant VARCHAR(200);
        RAISE NOTICE '  ✓ Added column: transactions.merchant';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.merchant';
    END IF;

    -- location
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='location') THEN
        ALTER TABLE transactions ADD COLUMN location VARCHAR(200);
        RAISE NOTICE '  ✓ Added column: transactions.location';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.location';
    END IF;

    -- tags
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='tags') THEN
        ALTER TABLE transactions ADD COLUMN tags VARCHAR[];
        RAISE NOTICE '  ✓ Added column: transactions.tags';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.tags';
    END IF;

    -- is_recurring
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='is_recurring') THEN
        ALTER TABLE transactions ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT false;
        RAISE NOTICE '  ✓ Added column: transactions.is_recurring';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.is_recurring';
    END IF;

    -- confidence_score
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='confidence_score') THEN
        ALTER TABLE transactions ADD COLUMN confidence_score FLOAT;
        RAISE NOTICE '  ✓ Added column: transactions.confidence_score';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.confidence_score';
    END IF;

    -- receipt_url
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='receipt_url') THEN
        ALTER TABLE transactions ADD COLUMN receipt_url VARCHAR(500);
        RAISE NOTICE '  ✓ Added column: transactions.receipt_url';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.receipt_url';
    END IF;

    -- notes
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='notes') THEN
        ALTER TABLE transactions ADD COLUMN notes TEXT;
        RAISE NOTICE '  ✓ Added column: transactions.notes';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.notes';
    END IF;

    -- updated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='updated_at') THEN
        ALTER TABLE transactions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();
        RAISE NOTICE '  ✓ Added column: transactions.updated_at';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.updated_at';
    END IF;

    -- Create indexes
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_transactions_merchant') THEN
        CREATE INDEX idx_transactions_merchant ON transactions(merchant);
        RAISE NOTICE '  ✓ Created index: idx_transactions_merchant';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_transactions_is_recurring') THEN
        CREATE INDEX idx_transactions_is_recurring ON transactions(is_recurring);
        RAISE NOTICE '  ✓ Created index: idx_transactions_is_recurring';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_transactions_updated_at') THEN
        CREATE INDEX idx_transactions_updated_at ON transactions(updated_at);
        RAISE NOTICE '  ✓ Created index: idx_transactions_updated_at';
    END IF;

    -- Create trigger for auto-updating updated_at
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_transactions_updated_at') THEN
        CREATE TRIGGER update_transactions_updated_at
        BEFORE UPDATE ON transactions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '  ✓ Created trigger: update_transactions_updated_at';
    ELSE
        RAISE NOTICE '  ⊙ Trigger already exists: update_transactions_updated_at';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0010: Enhance Goals Table
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0010] Enhancing goals table...';

DO $$
BEGIN
    -- description
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='description') THEN
        ALTER TABLE goals ADD COLUMN description TEXT;
        RAISE NOTICE '  ✓ Added column: goals.description';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.description';
    END IF;

    -- category
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='category') THEN
        ALTER TABLE goals ADD COLUMN category VARCHAR(50);
        CREATE INDEX ix_goals_category ON goals(category);
        RAISE NOTICE '  ✓ Added column: goals.category (with index)';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.category';
    END IF;

    -- monthly_contribution
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='monthly_contribution') THEN
        ALTER TABLE goals ADD COLUMN monthly_contribution NUMERIC(10,2);
        RAISE NOTICE '  ✓ Added column: goals.monthly_contribution';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.monthly_contribution';
    END IF;

    -- status
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='status') THEN
        ALTER TABLE goals ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
        CREATE INDEX ix_goals_status ON goals(status);
        RAISE NOTICE '  ✓ Added column: goals.status (with index)';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.status';
    END IF;

    -- progress
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='progress') THEN
        ALTER TABLE goals ADD COLUMN progress NUMERIC(5,2) NOT NULL DEFAULT 0;
        RAISE NOTICE '  ✓ Added column: goals.progress';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.progress';
    END IF;

    -- target_date
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='target_date') THEN
        ALTER TABLE goals ADD COLUMN target_date DATE;
        RAISE NOTICE '  ✓ Added column: goals.target_date';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.target_date';
    END IF;

    -- last_updated
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='last_updated') THEN
        ALTER TABLE goals ADD COLUMN last_updated TIMESTAMP NOT NULL DEFAULT NOW();
        RAISE NOTICE '  ✓ Added column: goals.last_updated';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.last_updated';
    END IF;

    -- completed_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='completed_at') THEN
        ALTER TABLE goals ADD COLUMN completed_at TIMESTAMP;
        RAISE NOTICE '  ✓ Added column: goals.completed_at';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.completed_at';
    END IF;

    -- priority
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='priority') THEN
        ALTER TABLE goals ADD COLUMN priority VARCHAR(10) DEFAULT 'medium';
        RAISE NOTICE '  ✓ Added column: goals.priority';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.priority';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0011: Add goal_id to Transactions
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0011] Linking transactions to goals...';

DO $$
BEGIN
    -- goal_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='goal_id') THEN
        ALTER TABLE transactions ADD COLUMN goal_id UUID;
        RAISE NOTICE '  ✓ Added column: transactions.goal_id';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.goal_id';
    END IF;

    -- Foreign key constraint
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_transactions_goal_id' AND table_name = 'transactions'
    ) THEN
        ALTER TABLE transactions
        ADD CONSTRAINT fk_transactions_goal_id
        FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE SET NULL;
        RAISE NOTICE '  ✓ Created foreign key: fk_transactions_goal_id';
    ELSE
        RAISE NOTICE '  ⊙ Foreign key already exists: fk_transactions_goal_id';
    END IF;

    -- Index
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_transactions_goal_id') THEN
        CREATE INDEX ix_transactions_goal_id ON transactions(goal_id);
        RAISE NOTICE '  ✓ Created index: ix_transactions_goal_id';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0012: Add Challenges Tables
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0012] Creating challenges tables...';

DO $$
BEGIN
    -- Create challenges table
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'challenges') THEN
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
        RAISE NOTICE '  ✓ Created table: challenges';

        -- Insert sample challenges
        INSERT INTO challenges (id, name, description, type, duration_days, reward_points, difficulty, start_month, end_month) VALUES
        ('savings_streak_7', '7-Day Savings Streak', 'Save money every day for 7 consecutive days', 'streak', 7, 100, 'easy', '2025-01', '2025-12'),
        ('savings_streak_30', '30-Day Savings Challenge', 'Build a monthly savings habit by saving every day', 'streak', 30, 500, 'medium', '2025-01', '2025-12'),
        ('no_coffee_challenge', 'Skip the Coffee', 'Reduce coffee shop expenses for 14 days', 'category_restriction', 14, 200, 'medium', '2025-01', '2025-12'),
        ('dining_reduction', 'Cook at Home Challenge', 'Reduce dining out expenses by 50% this month', 'category_reduction', 30, 300, 'medium', '2025-01', '2025-12'),
        ('transportation_saver', 'Commute Smart', 'Save on transportation costs for 21 days', 'category_reduction', 21, 250, 'easy', '2025-01', '2025-12'),
        ('budget_master', 'Budget Master', 'Stay within budget for all categories for 30 days', 'streak', 30, 1000, 'hard', '2025-01', '2025-12'),
        ('impulse_free', 'Impulse-Free Zone', 'Avoid impulse purchases for 14 days', 'category_restriction', 14, 300, 'medium', '2025-01', '2025-12'),
        ('weekly_saver', 'Weekly Savings Goal', 'Save a specific amount every week for 4 weeks', 'streak', 28, 400, 'medium', '2025-01', '2025-12');
        RAISE NOTICE '  ✓ Inserted 8 sample challenges';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: challenges';
    END IF;

    -- Create challenge_participations table
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'challenge_participations') THEN
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

        RAISE NOTICE '  ✓ Created table: challenge_participations (with indexes)';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: challenge_participations';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0013: Add Analytics Tables
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0013] Creating analytics tables...';

DO $$
BEGIN
    -- feature_usage_logs
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feature_usage_logs') THEN
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

        RAISE NOTICE '  ✓ Created table: feature_usage_logs (with 5 indexes)';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: feature_usage_logs';
    END IF;

    -- feature_access_logs
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feature_access_logs') THEN
        CREATE TABLE feature_access_logs (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            feature VARCHAR(100) NOT NULL,
            has_access BOOLEAN NOT NULL DEFAULT false,
            is_premium_feature BOOLEAN NOT NULL DEFAULT false,
            converted_to_premium BOOLEAN DEFAULT false,
            converted_at TIMESTAMP WITH TIME ZONE,
            screen VARCHAR(100),
            extra_data JSON,
            timestamp TIMESTAMP WITH TIME ZONE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX ix_feature_access_logs_user_id ON feature_access_logs(user_id);
        CREATE INDEX ix_feature_access_logs_feature ON feature_access_logs(feature);
        CREATE INDEX ix_feature_access_logs_timestamp ON feature_access_logs(timestamp);

        RAISE NOTICE '  ✓ Created table: feature_access_logs (with 3 indexes)';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: feature_access_logs';
    END IF;

    -- paywall_impression_logs
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'paywall_impression_logs') THEN
        CREATE TABLE paywall_impression_logs (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            screen VARCHAR(100) NOT NULL,
            feature VARCHAR(100),
            resulted_in_purchase BOOLEAN DEFAULT false,
            purchase_timestamp TIMESTAMP WITH TIME ZONE,
            impression_context VARCHAR(200),
            extra_data JSON,
            timestamp TIMESTAMP WITH TIME ZONE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX ix_paywall_impression_logs_user_id ON paywall_impression_logs(user_id);
        CREATE INDEX ix_paywall_impression_logs_screen ON paywall_impression_logs(screen);
        CREATE INDEX ix_paywall_impression_logs_timestamp ON paywall_impression_logs(timestamp);

        RAISE NOTICE '  ✓ Created table: paywall_impression_logs (with 3 indexes)';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: paywall_impression_logs';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0014: Add Notifications Table
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0014] Creating notifications table...';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications') THEN
        CREATE TABLE notifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            -- Content
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(50) NOT NULL DEFAULT 'info',
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            -- Rich content
            image_url VARCHAR(500),
            action_url VARCHAR(500),
            data JSON,
            -- Delivery tracking
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            channel VARCHAR(20),
            -- Read tracking
            is_read BOOLEAN NOT NULL DEFAULT false,
            read_at TIMESTAMP WITH TIME ZONE,
            -- Scheduling
            scheduled_for TIMESTAMP WITH TIME ZONE,
            sent_at TIMESTAMP WITH TIME ZONE,
            delivered_at TIMESTAMP WITH TIME ZONE,
            -- Error tracking
            error_message TEXT,
            retry_count VARCHAR NOT NULL DEFAULT '0',
            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE,
            -- Grouping
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

        RAISE NOTICE '  ✓ Created table: notifications (with 6 indexes)';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: notifications';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0015: Add Installments Module (BNPL)
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0015] Creating installments module tables...';

DO $$
BEGIN
    -- user_financial_profiles
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_financial_profiles') THEN
        CREATE TABLE user_financial_profiles (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE,
            monthly_income NUMERIC(12,2) NOT NULL,
            current_balance NUMERIC(12,2) NOT NULL,
            age_group VARCHAR(10) NOT NULL DEFAULT '25-34',
            credit_card_debt BOOLEAN NOT NULL DEFAULT false,
            credit_card_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
            other_loans_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
            rent_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
            subscriptions_payment NUMERIC(12,2) NOT NULL DEFAULT 0,
            planning_mortgage BOOLEAN NOT NULL DEFAULT false,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX ix_user_financial_profiles_user_id ON user_financial_profiles(user_id);
        RAISE NOTICE '  ✓ Created table: user_financial_profiles';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: user_financial_profiles';
    END IF;

    -- installments
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'installments') THEN
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
        RAISE NOTICE '  ✓ Created table: installments';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: installments';
    END IF;

    -- installment_calculations
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'installment_calculations') THEN
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
            user_proceeded BOOLEAN NOT NULL DEFAULT false,
            calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (installment_id) REFERENCES installments(id) ON DELETE SET NULL
        );
        CREATE INDEX ix_installment_calculations_user_id ON installment_calculations(user_id);
        CREATE INDEX ix_installment_calculations_installment_id ON installment_calculations(installment_id);
        CREATE INDEX ix_installment_calculations_calculated_at ON installment_calculations(calculated_at);
        RAISE NOTICE '  ✓ Created table: installment_calculations';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: installment_calculations';
    END IF;

    -- installment_achievements
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'installment_achievements') THEN
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
        RAISE NOTICE '  ✓ Created table: installment_achievements';
    ELSE
        RAISE NOTICE '  ⊙ Table already exists: installment_achievements';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0017: Add Account Security Fields
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0017] Adding account security fields...';

DO $$
BEGIN
    -- failed_login_attempts
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='failed_login_attempts') THEN
        ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;
        RAISE NOTICE '  ✓ Added column: users.failed_login_attempts';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.failed_login_attempts';
    END IF;

    -- account_locked_until
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='account_locked_until') THEN
        ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '  ✓ Added column: users.account_locked_until';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: users.account_locked_until';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION 0018: Add Soft Deletes
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '[0018] Adding soft delete support...';

DO $$
BEGIN
    -- transactions.deleted_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='transactions' AND column_name='deleted_at') THEN
        ALTER TABLE transactions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '  ✓ Added column: transactions.deleted_at';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: transactions.deleted_at';
    END IF;

    -- goals.deleted_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='goals' AND column_name='deleted_at') THEN
        ALTER TABLE goals ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '  ✓ Added column: goals.deleted_at';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: goals.deleted_at';
    END IF;

    -- installments.deleted_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='installments' AND column_name='deleted_at') THEN
        ALTER TABLE installments ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '  ✓ Added column: installments.deleted_at';
    ELSE
        RAISE NOTICE '  ⊙ Column already exists: installments.deleted_at';
    END IF;

    -- Partial indexes for performance (only index non-deleted records)
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_transactions_deleted_at') THEN
        CREATE INDEX idx_transactions_deleted_at ON transactions(deleted_at) WHERE deleted_at IS NULL;
        RAISE NOTICE '  ✓ Created partial index: idx_transactions_deleted_at';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_goals_deleted_at') THEN
        CREATE INDEX idx_goals_deleted_at ON goals(deleted_at) WHERE deleted_at IS NULL;
        RAISE NOTICE '  ✓ Created partial index: idx_goals_deleted_at';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_installments_deleted_at') THEN
        CREATE INDEX idx_installments_deleted_at ON installments(deleted_at) WHERE deleted_at IS NULL;
        RAISE NOTICE '  ✓ Created partial index: idx_installments_deleted_at';
    END IF;
END $$;

-- ============================================================================
-- Update Alembic Version Tracking
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE 'Updating alembic_version tracking...';

-- Clear old version and set latest
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('0018_add_soft_deletes');

RAISE NOTICE '  ✓ Set alembic_version to: 0018_add_soft_deletes';

-- ============================================================================
-- VERIFICATION & SUMMARY
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '============================================================================';
RAISE NOTICE 'MIGRATION VERIFICATION';
RAISE NOTICE '============================================================================';

DO $$
DECLARE
    users_cols INTEGER;
    transactions_cols INTEGER;
    goals_cols INTEGER;
    new_tables INTEGER;
BEGIN
    -- Count new columns in users table
    SELECT COUNT(*) INTO users_cols
    FROM information_schema.columns
    WHERE table_name = 'users'
    AND column_name IN ('name', 'savings_goal', 'currency', 'region', 'notifications_enabled',
                        'dark_mode_enabled', 'failed_login_attempts', 'account_locked_until');

    -- Count new columns in transactions table
    SELECT COUNT(*) INTO transactions_cols
    FROM information_schema.columns
    WHERE table_name = 'transactions'
    AND column_name IN ('merchant', 'location', 'tags', 'is_recurring', 'confidence_score',
                        'receipt_url', 'notes', 'updated_at', 'goal_id', 'deleted_at');

    -- Count new columns in goals table
    SELECT COUNT(*) INTO goals_cols
    FROM information_schema.columns
    WHERE table_name = 'goals'
    AND column_name IN ('description', 'category', 'monthly_contribution', 'status',
                        'progress', 'target_date', 'priority', 'deleted_at');

    -- Count new tables
    SELECT COUNT(*) INTO new_tables
    FROM information_schema.tables
    WHERE table_name IN ('challenges', 'challenge_participations', 'feature_usage_logs',
                         'feature_access_logs', 'paywall_impression_logs', 'notifications',
                         'user_financial_profiles', 'installments', 'installment_calculations',
                         'installment_achievements');

    RAISE NOTICE 'Users table: % new columns (expected: 8)', users_cols;
    RAISE NOTICE 'Transactions table: % new columns (expected: 10)', transactions_cols;
    RAISE NOTICE 'Goals table: % new columns (expected: 8)', goals_cols;
    RAISE NOTICE 'New tables created: % (expected: 10)', new_tables;
    RAISE NOTICE '';

    IF users_cols >= 8 AND transactions_cols >= 10 AND goals_cols >= 8 AND new_tables >= 10 THEN
        RAISE NOTICE '✅ MIGRATION SUCCESSFUL - All changes applied!';
    ELSE
        RAISE WARNING '⚠️  MIGRATION INCOMPLETE - Some changes may be missing';
    END IF;
END $$;

RAISE NOTICE '';
RAISE NOTICE '============================================================================';
RAISE NOTICE 'MIGRATION COMPLETE';
RAISE NOTICE 'Timestamp: %', NOW();
RAISE NOTICE 'Alembic version: 0018_add_soft_deletes';
RAISE NOTICE '============================================================================';

COMMIT;

-- Show alembic_version
SELECT 'Current alembic version:' as status, version_num FROM alembic_version;

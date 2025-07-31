-- Database Performance Indexes for MITA
-- Add critical indexes for optimal query performance
-- Run with: psql -d mita_db -f migrations/add_performance_indexes.sql

-- Users table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_is_premium ON users (is_premium);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_premium_until ON users (premium_until) WHERE premium_until IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at ON users (created_at);

-- Transaction table indexes (most critical for performance)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_spent_at ON transactions (user_id, spent_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_category ON transactions (user_id, category);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_amount ON transactions (user_id, amount DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_category_spent_at ON transactions (category, spent_at);

-- Expense table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date ON expenses (user_id, date DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_action_date ON expenses (user_id, action, date DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_date_amount ON expenses (date, amount DESC);

-- Goal table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_status ON goals (user_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_target_date ON goals (user_id, target_date) WHERE status = 'active';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_category ON goals (user_id, category);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_user_progress ON goals (user_id, progress DESC) WHERE status = 'active';

-- Budget Advice table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_budget_advice_user_date ON budget_advice (user_id, date DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_budget_advice_user_type ON budget_advice (user_id, type);

-- Daily Plan table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_daily_plan_user_date ON daily_plan (user_id, date DESC);

-- Mood table indexes (unique constraint)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_mood_user_date_unique ON mood (user_id, date);

-- Habit table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_habits_user_active ON habit (user_id, is_active) WHERE is_active = true;

-- AI Analysis Snapshot indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_snapshots_user_created_at ON ai_analysis_snapshots (user_id, created_at DESC);

-- Notification Log indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_log_user_sent_at ON notification_log (user_id, sent_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_log_user_channel ON notification_log (user_id, channel);

-- Push Token indexes
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_push_tokens_token_unique ON push_token (token);

-- Subscription indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_user_platform ON subscription (user_id, platform);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_user_active ON subscription (user_id, is_active) WHERE is_active = true;

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_date_category_amount ON transactions (user_id, spent_at, category, amount);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expenses_user_date_action_amount ON expenses (user_id, date, action, amount);

-- Full-text search indexes (requires PostgreSQL with full-text search)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_description_fulltext ON transactions USING gin(to_tsvector('english', COALESCE(description, '')));
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_goals_title_description_fulltext ON goals USING gin(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(description, '')));

-- Analyze tables after creating indexes to update statistics
ANALYZE users;
ANALYZE transactions;
ANALYZE expenses;
ANALYZE goals;
ANALYZE budget_advice;
ANALYZE daily_plan;
ANALYZE mood;
ANALYZE habit;
ANALYZE ai_analysis_snapshots;
ANALYZE notification_log;
ANALYZE push_token;
ANALYZE subscription;
-- =====================================================================
-- MITA Subscription Management Database Schema
-- =====================================================================
-- This schema supports comprehensive subscription management for the MITA
-- financial application, including receipt validation, premium features,
-- and audit logging for compliance.

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =====================================================================
-- User Subscriptions Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('ios', 'android')),
    subscription_id VARCHAR(255) NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN (
        'active', 'expired', 'cancelled', 'refunded', 
        'grace_period', 'billing_retry', 'pending_renewal'
    )),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_renew BOOLEAN DEFAULT true,
    receipt_data TEXT NOT NULL,
    receipt_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for deduplication
    last_verified TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    trial_period BOOLEAN DEFAULT false,
    grace_period_expires_at TIMESTAMP WITH TIME ZONE,
    billing_retry_until TIMESTAMP WITH TIME ZONE,
    original_transaction_id VARCHAR(255),
    web_order_line_item_id VARCHAR(255),
    cancellation_reason VARCHAR(100),
    country_code VARCHAR(2),
    price_amount DECIMAL(10,2),
    price_currency_code VARCHAR(3),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_user_subscription UNIQUE (user_id, subscription_id, platform),
    CONSTRAINT unique_receipt_hash UNIQUE (receipt_hash),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires_at ON user_subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_last_verified ON user_subscriptions(last_verified);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_platform ON user_subscriptions(platform);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_verification_needed ON user_subscriptions(status, last_verified) 
    WHERE status IN ('active', 'grace_period', 'billing_retry');

-- =====================================================================
-- Premium Feature Flags Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS user_feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    feature_name VARCHAR(100) NOT NULL CHECK (feature_name IN (
        'advanced_ocr', 'batch_receipt_processing', 'premium_insights',
        'enhanced_analytics', 'unlimited_transactions', 'priority_support',
        'custom_categories', 'export_data'
    )),
    is_enabled BOOLEAN DEFAULT true,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    granted_by VARCHAR(50) DEFAULT 'subscription_system',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_user_feature UNIQUE (user_id, feature_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for feature flag lookups
CREATE INDEX IF NOT EXISTS idx_user_feature_flags_user_id ON user_feature_flags(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feature_flags_feature_name ON user_feature_flags(feature_name);
CREATE INDEX IF NOT EXISTS idx_user_feature_flags_active ON user_feature_flags(user_id, is_enabled) 
    WHERE is_enabled = true AND (expires_at IS NULL OR expires_at > NOW());

-- =====================================================================
-- Subscription Audit Log
-- =====================================================================
CREATE TABLE IF NOT EXISTS subscription_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    user_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    subscription_id VARCHAR(255) NOT NULL,
    details JSONB DEFAULT '{}',
    script_version VARCHAR(20),
    ip_address INET,
    user_agent TEXT,
    archived BOOLEAN DEFAULT false,
    
    -- Constraints
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_subscription_audit_log_timestamp ON subscription_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_subscription_audit_log_user_id ON subscription_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_audit_log_action ON subscription_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_subscription_audit_log_subscription_id ON subscription_audit_log(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_audit_log_active ON subscription_audit_log(timestamp, archived) 
    WHERE archived = false;

-- =====================================================================
-- Premium Feature Usage Tracking
-- =====================================================================
CREATE TABLE IF NOT EXISTS premium_feature_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    usage_count INTEGER DEFAULT 1,
    api_calls_made INTEGER DEFAULT 0,
    processing_time_ms INTEGER,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_daily_feature_usage UNIQUE (user_id, feature_name, usage_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for usage analytics
CREATE INDEX IF NOT EXISTS idx_premium_feature_usage_user_date ON premium_feature_usage(user_id, usage_date);
CREATE INDEX IF NOT EXISTS idx_premium_feature_usage_feature_date ON premium_feature_usage(feature_name, usage_date);

-- =====================================================================
-- Subscription Metrics Summary
-- =====================================================================
CREATE TABLE IF NOT EXISTS subscription_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    platform VARCHAR(20) NOT NULL,
    total_subscriptions INTEGER DEFAULT 0,
    active_subscriptions INTEGER DEFAULT 0,
    expired_subscriptions INTEGER DEFAULT 0,
    cancelled_subscriptions INTEGER DEFAULT 0,
    grace_period_subscriptions INTEGER DEFAULT 0,
    new_subscriptions INTEGER DEFAULT 0,
    renewals INTEGER DEFAULT 0,
    refunds INTEGER DEFAULT 0,
    revenue_usd DECIMAL(12,2) DEFAULT 0,
    api_calls_apple INTEGER DEFAULT 0,
    api_calls_google INTEGER DEFAULT 0,
    processing_errors INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_daily_platform_metrics UNIQUE (date, platform)
);

-- Index for metrics queries
CREATE INDEX IF NOT EXISTS idx_subscription_metrics_date ON subscription_metrics(date);
CREATE INDEX IF NOT EXISTS idx_subscription_metrics_platform ON subscription_metrics(platform);

-- =====================================================================
-- Update Users Table for Premium Status
-- =====================================================================
-- Add premium-related columns to existing users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_tier VARCHAR(50) DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_platform VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_premium_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS lifetime_premium_months INTEGER DEFAULT 0;

-- Index for premium user queries
CREATE INDEX IF NOT EXISTS idx_users_premium_status ON users(is_premium, premium_expires_at) 
    WHERE is_premium = true;

-- =====================================================================
-- User Preferences for Premium Features
-- =====================================================================
CREATE TABLE IF NOT EXISTS user_premium_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    advanced_ocr_enabled BOOLEAN DEFAULT true,
    batch_processing_enabled BOOLEAN DEFAULT true,
    premium_insights_enabled BOOLEAN DEFAULT true,
    enhanced_analytics_enabled BOOLEAN DEFAULT true,
    export_formats_enabled TEXT[] DEFAULT ARRAY['pdf', 'csv', 'excel'],
    notification_preferences JSONB DEFAULT '{"renewal_reminders": true, "feature_updates": true}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_user_premium_preferences UNIQUE (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================================
-- Triggers for Automatic Updates
-- =====================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_user_subscriptions_updated_at 
    BEFORE UPDATE ON user_subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_premium_feature_usage_updated_at 
    BEFORE UPDATE ON premium_feature_usage 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_premium_preferences_updated_at 
    BEFORE UPDATE ON user_premium_preferences 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to generate receipt hash
CREATE OR REPLACE FUNCTION generate_receipt_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.receipt_hash = encode(digest(NEW.receipt_data, 'sha256'), 'hex');
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply receipt hash trigger
CREATE TRIGGER generate_user_subscription_receipt_hash 
    BEFORE INSERT OR UPDATE ON user_subscriptions 
    FOR EACH ROW EXECUTE FUNCTION generate_receipt_hash();

-- Function to update premium feature usage metrics
CREATE OR REPLACE FUNCTION update_feature_usage_metrics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO premium_feature_usage (user_id, feature_name, usage_date, usage_count)
    VALUES (NEW.user_id, TG_ARGV[0], CURRENT_DATE, 1)
    ON CONFLICT (user_id, feature_name, usage_date)
    DO UPDATE SET 
        usage_count = premium_feature_usage.usage_count + 1,
        updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- =====================================================================
-- Views for Common Queries
-- =====================================================================

-- Active premium users view
CREATE OR REPLACE VIEW active_premium_users AS
SELECT 
    u.id,
    u.email,
    u.is_premium,
    u.premium_expires_at,
    u.premium_tier,
    us.platform,
    us.subscription_id,
    us.status,
    us.auto_renew,
    us.expires_at as subscription_expires_at
FROM users u
JOIN user_subscriptions us ON u.id = us.user_id
WHERE u.is_premium = true 
    AND us.status IN ('active', 'grace_period')
    AND (us.expires_at > NOW() OR us.grace_period_expires_at > NOW());

-- Subscription health dashboard view
CREATE OR REPLACE VIEW subscription_health_dashboard AS
SELECT 
    platform,
    status,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days') as expiring_soon,
    COUNT(*) FILTER (WHERE last_verified < NOW() - INTERVAL '1 hour') as needs_verification,
    AVG(EXTRACT(EPOCH FROM (NOW() - last_verified))/3600) as avg_hours_since_verification
FROM user_subscriptions 
GROUP BY platform, status;

-- Premium feature utilization view
CREATE OR REPLACE VIEW premium_feature_utilization AS
SELECT 
    pfu.feature_name,
    COUNT(DISTINCT pfu.user_id) as unique_users,
    SUM(pfu.usage_count) as total_usage,
    AVG(pfu.usage_count) as avg_daily_usage,
    SUM(pfu.api_calls_made) as total_api_calls,
    AVG(pfu.processing_time_ms) as avg_processing_time_ms,
    (SUM(pfu.success_count)::float / NULLIF(SUM(pfu.success_count + pfu.error_count), 0) * 100) as success_rate
FROM premium_feature_usage pfu
WHERE pfu.usage_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY pfu.feature_name
ORDER BY total_usage DESC;

-- =====================================================================
-- Data Retention Policies
-- =====================================================================

-- Function to archive old audit logs
CREATE OR REPLACE FUNCTION archive_old_audit_logs()
RETURNS void AS $$
BEGIN
    -- Archive audit logs older than 7 years (financial compliance requirement)
    UPDATE subscription_audit_log 
    SET archived = true 
    WHERE timestamp < NOW() - INTERVAL '7 years' 
        AND archived = false;
    
    -- Delete very old usage metrics (keep 2 years)
    DELETE FROM premium_feature_usage 
    WHERE usage_date < CURRENT_DATE - INTERVAL '2 years';
    
    -- Delete old subscription metrics (keep 5 years)
    DELETE FROM subscription_metrics 
    WHERE date < CURRENT_DATE - INTERVAL '5 years';
END;
$$ language 'plpgsql';

-- =====================================================================
-- Sample Data for Testing (Development Only)
-- =====================================================================
-- Note: This should only be used in development environments

-- Insert sample premium features for testing
INSERT INTO user_feature_flags (user_id, feature_name, is_enabled, expires_at)
SELECT 
    id as user_id,
    unnest(ARRAY['advanced_ocr', 'batch_receipt_processing', 'premium_insights']) as feature_name,
    true as is_enabled,
    NOW() + INTERVAL '30 days' as expires_at
FROM users 
WHERE email LIKE '%@test.com' -- Only for test users
ON CONFLICT (user_id, feature_name) DO NOTHING;

-- =====================================================================
-- Security Policies (Row Level Security)
-- =====================================================================

-- Enable RLS on sensitive tables
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE premium_feature_usage ENABLE ROW LEVEL SECURITY;

-- Policy for users to only see their own subscription data
CREATE POLICY user_subscription_policy ON user_subscriptions
    FOR ALL USING (user_id = current_setting('app.user_id')::uuid);

-- Policy for audit log access (admin only)
CREATE POLICY audit_log_admin_policy ON subscription_audit_log
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE id = current_setting('app.user_id')::uuid 
            AND role = 'admin'
        )
    );

-- Policy for feature flags (users can see their own)
CREATE POLICY user_feature_flags_policy ON user_feature_flags
    FOR ALL USING (user_id = current_setting('app.user_id')::uuid);

-- Policy for usage tracking (users can see their own)
CREATE POLICY premium_usage_policy ON premium_feature_usage
    FOR ALL USING (user_id = current_setting('app.user_id')::uuid);

-- =====================================================================
-- Performance Optimization
-- =====================================================================

-- Partial indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_active_expiring 
ON user_subscriptions (expires_at) 
WHERE status = 'active' AND expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_verification_queue
ON user_subscriptions (last_verified, status) 
WHERE status IN ('active', 'grace_period', 'billing_retry') 
    AND last_verified < NOW() - INTERVAL '1 hour';

-- Statistics collection
ANALYZE user_subscriptions;
ANALYZE subscription_audit_log;
ANALYZE user_feature_flags;
ANALYZE premium_feature_usage;

-- =====================================================================
-- Database Functions for API Integration
-- =====================================================================

-- Function to check if user has specific premium feature
CREATE OR REPLACE FUNCTION user_has_premium_feature(p_user_id UUID, p_feature_name VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    has_feature BOOLEAN := false;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM user_feature_flags uff
        JOIN users u ON uff.user_id = u.id
        WHERE uff.user_id = p_user_id
            AND uff.feature_name = p_feature_name
            AND uff.is_enabled = true
            AND u.is_premium = true
            AND (uff.expires_at IS NULL OR uff.expires_at > NOW())
            AND (u.premium_expires_at IS NULL OR u.premium_expires_at > NOW())
    ) INTO has_feature;
    
    RETURN has_feature;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's premium status summary
CREATE OR REPLACE FUNCTION get_user_premium_status(p_user_id UUID)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'is_premium', COALESCE(u.is_premium, false),
        'expires_at', u.premium_expires_at,
        'tier', COALESCE(u.premium_tier, 'free'),
        'subscription_platform', u.subscription_platform,
        'active_features', (
            SELECT array_agg(uff.feature_name)
            FROM user_feature_flags uff
            WHERE uff.user_id = p_user_id
                AND uff.is_enabled = true
                AND (uff.expires_at IS NULL OR uff.expires_at > NOW())
        ),
        'subscription_details', (
            SELECT json_build_object(
                'status', us.status,
                'expires_at', us.expires_at,
                'auto_renew', us.auto_renew,
                'platform', us.platform
            )
            FROM user_subscriptions us
            WHERE us.user_id = p_user_id
                AND us.status IN ('active', 'grace_period')
            ORDER BY us.expires_at DESC
            LIMIT 1
        )
    ) INTO result
    FROM users u
    WHERE u.id = p_user_id;
    
    RETURN COALESCE(result, '{}'::json);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION user_has_premium_feature(UUID, VARCHAR) TO app_role;
GRANT EXECUTE ON FUNCTION get_user_premium_status(UUID) TO app_role;
GRANT EXECUTE ON FUNCTION archive_old_audit_logs() TO maintenance_role;
-- ============================================================================
-- MИТА АНАЛИТИКА - СОЗДАНИЕ ТАБЛИЦ
-- ============================================================================
-- ИНСТРУКЦИЯ:
-- 1. Открой Supabase Dashboard → SQL Editor
-- 2. Создай New Query
-- 3. СКОПИРУЙ ВЕСЬ ЭТОТ ФАЙЛ ПОЛНОСТЬЮ (от начала до конца)
-- 4. Вставь в SQL Editor
-- 5. Нажми RUN (или Ctrl+Enter)
-- ============================================================================

-- Таблица 1: Логи использования функций
CREATE TABLE IF NOT EXISTS feature_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature VARCHAR(100) NOT NULL,
    screen VARCHAR(100),
    action VARCHAR(100),
    extra_data JSONB,
    session_id VARCHAR(100),
    platform VARCHAR(20),
    app_version VARCHAR(20),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_user_id ON feature_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_feature ON feature_usage_logs(feature);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_screen ON feature_usage_logs(screen);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_session_id ON feature_usage_logs(session_id);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_timestamp ON feature_usage_logs(timestamp);

-- Таблица 2: Логи доступа к премиум функциям
CREATE TABLE IF NOT EXISTS feature_access_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature VARCHAR(100) NOT NULL,
    has_access BOOLEAN NOT NULL DEFAULT FALSE,
    is_premium_feature BOOLEAN NOT NULL DEFAULT FALSE,
    converted_to_premium BOOLEAN DEFAULT FALSE,
    converted_at TIMESTAMPTZ,
    screen VARCHAR(100),
    extra_data JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feature_access_logs_user_id ON feature_access_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_feature_access_logs_feature ON feature_access_logs(feature);
CREATE INDEX IF NOT EXISTS ix_feature_access_logs_timestamp ON feature_access_logs(timestamp);

-- Таблица 3: Логи показов paywall
CREATE TABLE IF NOT EXISTS paywall_impression_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    screen VARCHAR(100) NOT NULL,
    feature VARCHAR(100),
    resulted_in_purchase BOOLEAN DEFAULT FALSE,
    purchase_timestamp TIMESTAMPTZ,
    impression_context VARCHAR(200),
    extra_data JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_user_id ON paywall_impression_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_screen ON paywall_impression_logs(screen);
CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_timestamp ON paywall_impression_logs(timestamp);

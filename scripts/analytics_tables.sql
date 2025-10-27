-- ============================================================================
-- MITA Analytics Module - Database Tables
-- ============================================================================
-- Просто скопируй этот SQL и выполни в Supabase SQL Editor!
-- Это создаст все таблицы для модуля аналитики
-- ============================================================================

-- 1. Таблица для логирования использования функций
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

-- Индексы для быстрых запросов
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_user_id ON feature_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_feature ON feature_usage_logs(feature);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_screen ON feature_usage_logs(screen);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_session_id ON feature_usage_logs(session_id);
CREATE INDEX IF NOT EXISTS ix_feature_usage_logs_timestamp ON feature_usage_logs(timestamp);

-- ============================================================================

-- 2. Таблица для отслеживания попыток доступа к премиум функциям
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

-- Индексы для анализа конверсии
CREATE INDEX IF NOT EXISTS ix_feature_access_logs_user_id ON feature_access_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_feature_access_logs_feature ON feature_access_logs(feature);
CREATE INDEX IF NOT EXISTS ix_feature_access_logs_timestamp ON feature_access_logs(timestamp);

-- ============================================================================

-- 3. Таблица для логирования показов paywall (conversion funnel)
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

-- Индексы для анализа конверсии
CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_user_id ON paywall_impression_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_screen ON paywall_impression_logs(screen);
CREATE INDEX IF NOT EXISTS ix_paywall_impression_logs_timestamp ON paywall_impression_logs(timestamp);

-- ============================================================================
-- ГОТОВО! Проверьте что таблицы созданы:
-- ============================================================================

-- Выполните этот запрос для проверки:
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
AND table_name IN ('feature_usage_logs', 'feature_access_logs', 'paywall_impression_logs')
ORDER BY table_name;

-- Должно вернуть 3 строки с названиями таблиц

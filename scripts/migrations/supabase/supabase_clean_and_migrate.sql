-- =====================================================
-- РЕШЕНИЕ ПРОБЛЕМЫ: Полная очистка и миграция
-- =====================================================
-- Используй этот скрипт если получаешь ошибки про существующие объекты

-- =====================================================
-- ШАГ 1: ПОЛНАЯ ОЧИСТКА (если таблицы уже существуют)
-- =====================================================

-- Удалить триггеры (если существуют)
DROP TRIGGER IF EXISTS trigger_challenges_updated_at ON challenges CASCADE;
DROP TRIGGER IF EXISTS trigger_challenge_participations_last_updated ON challenge_participations CASCADE;

-- Удалить функции (если существуют)
DROP FUNCTION IF EXISTS update_challenges_updated_at() CASCADE;
DROP FUNCTION IF EXISTS update_challenge_participations_last_updated() CASCADE;

-- Удалить таблицы (если существуют) - CASCADE удалит и зависимости
DROP TABLE IF EXISTS challenge_participations CASCADE;
DROP TABLE IF EXISTS challenges CASCADE;

-- =====================================================
-- ШАГ 2: СОЗДАТЬ ТАБЛИЦЫ ЗАНОВО
-- =====================================================

-- Создать таблицу challenges
CREATE TABLE challenges (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    duration_days INTEGER NOT NULL,
    reward_points INTEGER DEFAULT 0,
    difficulty VARCHAR(20) NOT NULL,
    start_month VARCHAR(7) NOT NULL,
    end_month VARCHAR(7) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Создать таблицу challenge_participations
CREATE TABLE challenge_participations (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    challenge_id VARCHAR NOT NULL,
    month VARCHAR(7) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
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
-- ШАГ 3: СОЗДАТЬ ИНДЕКСЫ
-- =====================================================

CREATE INDEX ix_challenge_participations_user_id
    ON challenge_participations(user_id);

CREATE INDEX ix_challenge_participations_challenge_id
    ON challenge_participations(challenge_id);

CREATE INDEX ix_challenge_participations_month
    ON challenge_participations(month);

CREATE INDEX ix_challenge_participations_status
    ON challenge_participations(status);

-- =====================================================
-- ШАГ 4: СОЗДАТЬ ТРИГГЕРЫ ДЛЯ AUTO-UPDATE
-- =====================================================

-- Функция для challenges
CREATE FUNCTION update_challenges_updated_at()
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

-- Функция для challenge_participations
CREATE FUNCTION update_challenge_participations_last_updated()
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
-- ШАГ 5: ЗАГРУЗИТЬ SAMPLE CHALLENGES
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
     'streak', 30, 1000, 'hard', '2025-01', '2025-12');

-- =====================================================
-- ШАГ 6: НАСТРОИТЬ RLS (Row Level Security)
-- =====================================================

-- Включить RLS
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenge_participations ENABLE ROW LEVEL SECURITY;

-- Политики для challenges (все могут читать)
CREATE POLICY "Users can view all challenges"
ON challenges FOR SELECT
TO authenticated
USING (true);

-- Политики для challenge_participations (только свои данные)
CREATE POLICY "Users can view own participations"
ON challenge_participations FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can create own participations"
ON challenge_participations FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own participations"
ON challenge_participations FOR UPDATE
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own participations"
ON challenge_participations FOR DELETE
TO authenticated
USING (auth.uid() = user_id);

-- =====================================================
-- ШАГ 7: ПРОВЕРКА
-- =====================================================

-- Проверить количество challenges
SELECT 'Challenges created' as status, COUNT(*) as count FROM challenges;

-- Показать все challenges
SELECT id, name, difficulty, reward_points
FROM challenges
ORDER BY difficulty, reward_points;

-- Проверить структуру таблиц
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('challenges', 'challenge_participations')
ORDER BY table_name, ordinal_position;

-- Проверить индексы
SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('challenges', 'challenge_participations')
ORDER BY tablename;

-- =====================================================
-- ГОТОВО! ✅
-- =====================================================
-- Должно быть:
-- ✅ 2 таблицы созданы
-- ✅ 8 challenges загружены
-- ✅ 4 индекса созданы
-- ✅ 2 триггера созданы
-- ✅ 5 RLS политик создано
-- =====================================================

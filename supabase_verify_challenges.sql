-- =====================================================
-- ФИНАЛЬНАЯ ПРОВЕРКА: Challenges загружены?
-- =====================================================

-- 1. Сколько challenges создано?
SELECT 'Total challenges' as check_name, COUNT(*) as result
FROM challenges;

-- 2. Показать все challenges
SELECT
    id,
    name,
    difficulty,
    reward_points,
    duration_days
FROM challenges
ORDER BY
    CASE difficulty
        WHEN 'easy' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'hard' THEN 3
    END,
    reward_points;

-- 3. Проверить что таблица participations пустая (это нормально)
SELECT 'Total participations' as check_name, COUNT(*) as result
FROM challenge_participations;

-- 4. Проверить структуру таблицы challenges
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'challenges'
ORDER BY ordinal_position;

-- 5. Проверить структуру таблицы challenge_participations
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'challenge_participations'
ORDER BY ordinal_position;

-- =====================================================
-- Ожидаемый результат:
-- ✅ Total challenges: 8
-- ✅ Challenges listed: savings_streak_7, transportation_saver, etc.
-- ✅ Total participations: 0 (это нормально!)
-- ✅ Все колонки на месте
-- =====================================================

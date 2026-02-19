-- =====================================================
-- ДИАГНОСТИКА: Проверка существующих таблиц
-- =====================================================
-- Запусти это СНАЧАЛА чтобы понять что уже есть

-- 1. Проверить существуют ли таблицы
SELECT
    tablename,
    schemaname
FROM pg_tables
WHERE tablename IN ('challenges', 'challenge_participations')
ORDER BY tablename;

-- 2. Если таблицы существуют, посмотреть их структуру
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name IN ('challenges', 'challenge_participations')
ORDER BY table_name, ordinal_position;

-- 3. Проверить индексы
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('challenges', 'challenge_participations')
ORDER BY tablename, indexname;

-- 4. Проверить foreign keys
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name IN ('challenges', 'challenge_participations');

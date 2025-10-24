# 🚀 Supabase Migration Guide - MODULE 5 Challenges

## ⚠️ ВАЖНО: Выбери правильный способ миграции

### 🔴 Если получаешь ошибку "column month does not exist"
**Используй**: `supabase_clean_and_migrate.sql` (см. Вариант B ниже)

### 🟢 Если это первая миграция
**Используй**: `supabase_migration_challenges.sql` (см. Вариант A ниже)

---

## 📋 Вариант A: Первая миграция (чистая БД)

### Шаг 1: Открыть Supabase SQL Editor

1. Перейти на https://app.supabase.com
2. Выбрать ваш проект MITA
3. В левом меню: **SQL Editor**
4. Нажать **New Query**

### Шаг 2: Скопировать SQL скрипт

Откройте файл: `supabase_migration_challenges.sql`

```bash
cat supabase_migration_challenges.sql
```

### Шаг 3: Вставить и запустить

1. Вставить скопированный SQL в редактор
2. Нажать **Run** (или Ctrl+Enter)
3. Дождаться завершения (~5-10 секунд)

---

## 🔧 Вариант B: Исправление проблем (если есть ошибки)

### Когда использовать:
- ❌ Получаешь ошибку "column month does not exist"
- ❌ Получаешь ошибку "table already exists"
- ❌ Таблицы созданы но данных нет
- ❌ Нужно пересоздать таблицы с нуля

### ⚠️ ВНИМАНИЕ: Этот скрипт удалит существующие таблицы challenges!

### Шаг 1: Открыть Supabase SQL Editor
(так же как в Варианте A)

### Шаг 2: Скопировать ИСПРАВЛЕННЫЙ скрипт

Откройте файл: `supabase_clean_and_migrate.sql`

```bash
cat supabase_clean_and_migrate.sql
```

### Шаг 3: Вставить и запустить

1. Вставить скопированный SQL в редактор
2. Нажать **Run** (или Ctrl+Enter)
3. Дождаться завершения (~10-15 секунд)

**Этот скрипт:**
- ✅ Удалит старые таблицы (если есть)
- ✅ Создаст таблицы заново
- ✅ Загрузит 8 challenges
- ✅ Настроит RLS политики
- ✅ Создаст все индексы и триггеры

---

## 🔍 Диагностика (опционально)

Если хочешь сначала проверить что есть в БД:

```bash
cat supabase_check_existing.sql
```

Запусти этот скрипт чтобы увидеть:
- Существуют ли таблицы
- Какие колонки есть
- Какие индексы созданы

## Шаг 4: Проверить результат

В выводе вы должны увидеть:

```
✅ Challenges table: 8 rows
✅ Challenge participations table: 0 rows (это норма)
✅ 8 challenges listed with names and difficulties
✅ 4 indexes created
```

### Ожидаемый вывод:

```sql
-- Table: challenges
-- Row count: 8

-- Table: challenge_participations
-- Row count: 0

-- Challenges list:
| id                    | name                      | difficulty | reward_points |
|-----------------------|---------------------------|------------|---------------|
| savings_streak_7      | 7-Day Savings Streak      | easy       | 100           |
| transportation_saver  | Commute Smart             | easy       | 250           |
| savings_streak_30     | 30-Day Savings Challenge  | medium     | 500           |
| no_coffee_challenge   | Skip the Coffee           | medium     | 200           |
| dining_reduction      | Cook at Home Challenge    | medium     | 300           |
| impulse_free          | Impulse-Free Zone         | medium     | 300           |
| weekly_saver          | Weekly Savings Goal       | medium     | 400           |
| budget_master         | Budget Master             | hard       | 1000          |

-- Indexes created:
✅ ix_challenge_participations_user_id
✅ ix_challenge_participations_challenge_id
✅ ix_challenge_participations_month
✅ ix_challenge_participations_status
```

## Шаг 5: Проверка через UI

### Проверка таблиц:
1. В Supabase: **Table Editor**
2. Найти таблицы:
   - `challenges` - должна содержать 8 записей
   - `challenge_participations` - должна быть пустой

### Проверка структуры:
```sql
-- Запустить в SQL Editor:
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'challenges'
ORDER BY ordinal_position;
```

## Шаг 6: Тестирование API

После миграции проверьте endpoints:

```bash
# 1. Get available challenges
curl https://your-api.com/api/challenge/available \
  -H "Authorization: Bearer YOUR_TOKEN"

# Ожидаемый результат: массив из 8 challenges

# 2. Get stats (пока пустые)
curl https://your-api.com/api/challenge/stats \
  -H "Authorization: Bearer YOUR_TOKEN"

# Ожидаемый результат:
{
  "data": {
    "total_points": 0,
    "active_challenges": 0,
    "completed_challenges": 0,
    "current_streak": 0
  }
}
```

## Что создает миграция:

### 📊 Таблицы:
1. **challenges** - справочник доступных челленджей
   - 8 предзагруженных челленджей
   - Легкие (easy): 2 шт.
   - Средние (medium): 5 шт.
   - Сложные (hard): 1 шт.

2. **challenge_participations** - участие пользователей
   - Связь с users через user_id
   - Связь с challenges через challenge_id
   - Отслеживание прогресса, streaks, статуса

### 🔧 Функции:
- Auto-update timestamps triggers для обеих таблиц

### 🚀 Индексы:
- Оптимизация запросов по user_id, challenge_id, month, status

## Откат миграции (если нужно)

Если что-то пошло не так:

```sql
-- Удалить триггеры
DROP TRIGGER IF EXISTS trigger_challenges_updated_at ON challenges;
DROP TRIGGER IF EXISTS trigger_challenge_participations_last_updated ON challenge_participations;

-- Удалить функции
DROP FUNCTION IF EXISTS update_challenges_updated_at();
DROP FUNCTION IF EXISTS update_challenge_participations_last_updated();

-- Удалить таблицы (будут удалены и все данные!)
DROP TABLE IF EXISTS challenge_participations CASCADE;
DROP TABLE IF EXISTS challenges CASCADE;
```

## ❗ Частые проблемы и решения

### ❌ Ошибка: "column month does not exist"
**Причина**: Таблица уже существует но создана с другой структурой

**Решение**: Используй `supabase_clean_and_migrate.sql` вместо обычного скрипта.

```bash
# Скопируй этот файл вместо обычного:
cat supabase_clean_and_migrate.sql
```

### ❌ Ошибка: "table already exists"
**Причина**: Таблицы уже созданы ранее

**Решение 1** (если хочешь сохранить данные):
```sql
-- Просто загрузи challenges:
INSERT INTO challenges (id, name, description, type, duration_days, reward_points, difficulty, start_month, end_month)
VALUES (...) ON CONFLICT (id) DO NOTHING;
```

**Решение 2** (если можно удалить):
Используй `supabase_clean_and_migrate.sql`

### ❌ Ошибка: "relation users does not exist"
**Причина**: Таблица `users` не создана

**Решение**: Убедитесь что таблица `users` существует. Проверь:
```sql
SELECT * FROM users LIMIT 1;
```

### ❌ Ошибка: "permission denied"
**Причина**: Недостаточно прав

**Решение**: Убедитесь что вы project owner или admin.

## Проверка RLS (Row Level Security)

Supabase автоматически включает RLS. Нужно создать политики:

```sql
-- Политика: Users can read all challenges
CREATE POLICY "Users can view all challenges"
ON challenges FOR SELECT
TO authenticated
USING (true);

-- Политика: Users can view only their participations
CREATE POLICY "Users can view own participations"
ON challenge_participations FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Политика: Users can insert own participations
CREATE POLICY "Users can create own participations"
ON challenge_participations FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Политика: Users can update own participations
CREATE POLICY "Users can update own participations"
ON challenge_participations FOR UPDATE
TO authenticated
USING (auth.uid() = user_id);

-- Политика: Users can delete own participations
CREATE POLICY "Users can delete own participations"
ON challenge_participations FOR DELETE
TO authenticated
USING (auth.uid() = user_id);
```

## Следующие шаги

После успешной миграции:

1. ✅ Проверить что challenges загрузились (8 шт.)
2. ✅ Перезапустить backend (если нужно)
3. ✅ Открыть mobile app
4. ✅ Проверить что экран Challenges загружается
5. ✅ Попробовать Join challenge
6. ✅ Проверить что challenge появился на Main Screen

## Готово! 🎉

После выполнения миграции:
- ✅ DATABASE готова
- ✅ BACKEND API готов (уже реализован)
- ✅ MOBILE APP готов (уже реализован)
- ✅ Можно использовать функцию Challenges!

---

**Need help?**
- Проверь `MODULE_5_CHALLENGES_COMPLETE.md` для полной документации
- Проверь `MODULE_5_CHALLENGES_AUDIT.md` для отчета о проверке

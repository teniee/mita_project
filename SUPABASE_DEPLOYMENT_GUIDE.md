# 🚀 Supabase Deployment Guide - User Profile Module

## Обзор

Этот гайд поможет вам применить миграцию User Profile Module к вашей Supabase базе данных.

---

## 📋 Что нужно сделать в Supabase

### Вариант 1: Через Supabase Dashboard (РЕКОМЕНДУЕТСЯ)

Это самый простой и безопасный способ.

#### Шаг 1: Откройте SQL Editor

1. Зайдите в ваш Supabase проект: https://app.supabase.com
2. Выберите ваш проект
3. В левом меню нажмите на **SQL Editor**

#### Шаг 2: Создайте новый запрос

1. Нажмите **New query**
2. Дайте запросу имя: `Add User Profile Fields`

#### Шаг 3: Скопируйте и выполните SQL скрипт

1. Откройте файл `SUPABASE_PROFILE_MIGRATION.sql` из вашего проекта
2. Скопируйте **весь** SQL код
3. Вставьте в SQL Editor
4. Нажмите **Run** (или Ctrl/Cmd + Enter)

#### Шаг 4: Проверьте результат

В конце скрипта есть verification запрос, который покажет все добавленные колонки:

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN (
    'name',
    'savings_goal',
    'budget_method',
    'currency',
    'region',
    'notifications_enabled',
    'dark_mode_enabled',
    'monthly_income',
    'has_onboarded'
)
ORDER BY column_name;
```

**Ожидаемый результат:** Должны увидеть 9 строк с колонками профиля.

---

### Вариант 2: Через Supabase CLI (для продвинутых)

#### Шаг 1: Установите Supabase CLI

```bash
npm install -g supabase
```

#### Шаг 2: Подключитесь к проекту

```bash
supabase link --project-ref YOUR_PROJECT_REF
```

#### Шаг 3: Создайте миграцию

```bash
supabase migration new add_user_profile_fields
```

#### Шаг 4: Скопируйте SQL код

Скопируйте содержимое `SUPABASE_PROFILE_MIGRATION.sql` в созданный файл миграции.

#### Шаг 5: Примените миграцию

```bash
supabase db push
```

---

## 🔍 Проверка после применения миграции

### 1. Проверьте структуру таблицы

В Supabase Dashboard:
1. Перейдите в **Table Editor**
2. Выберите таблицу `users`
3. Проверьте, что добавились новые колонки:
   - ✅ name
   - ✅ savings_goal
   - ✅ budget_method
   - ✅ currency
   - ✅ region
   - ✅ notifications_enabled
   - ✅ dark_mode_enabled
   - ✅ monthly_income
   - ✅ has_onboarded

### 2. Проверьте индексы

В SQL Editor выполните:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'users'
AND indexname LIKE 'idx_users_%';
```

Должны увидеть индексы:
- `idx_users_currency`
- `idx_users_region`
- `idx_users_has_onboarded`

### 3. Протестируйте API

Проверьте что API эндпоинт работает:

```bash
curl -X GET https://YOUR_PROJECT.supabase.co/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Должен вернуть все новые поля профиля.

---

## 🔙 Откат миграции (Rollback)

Если что-то пошло не так, вы можете откатить изменения.

**⚠️ ВНИМАНИЕ:** Откат удалит все данные в новых колонках!

В SQL Editor выполните:

```sql
-- ROLLBACK SCRIPT
DROP INDEX IF EXISTS idx_users_has_onboarded;
DROP INDEX IF EXISTS idx_users_region;
DROP INDEX IF EXISTS idx_users_currency;

ALTER TABLE users DROP COLUMN IF EXISTS dark_mode_enabled;
ALTER TABLE users DROP COLUMN IF EXISTS notifications_enabled;
ALTER TABLE users DROP COLUMN IF EXISTS region;
ALTER TABLE users DROP COLUMN IF EXISTS currency;
ALTER TABLE users DROP COLUMN IF EXISTS budget_method;
ALTER TABLE users DROP COLUMN IF EXISTS savings_goal;
ALTER TABLE users DROP COLUMN IF EXISTS name;
```

---

## ⚙️ Настройка Row Level Security (RLS)

После миграции рекомендуется настроить RLS политики для новых полей.

### Политика: Пользователи могут читать свой профиль

```sql
CREATE POLICY "Users can view own profile"
ON users
FOR SELECT
USING (auth.uid() = id);
```

### Политика: Пользователи могут обновлять свой профиль

```sql
CREATE POLICY "Users can update own profile"
ON users
FOR UPDATE
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);
```

---

## 🧪 Тестирование в Supabase

### Тест 1: Создание тестового пользователя

```sql
-- Вставьте тестовые данные
UPDATE users
SET
    name = 'Test User',
    savings_goal = 1000,
    budget_method = '50/30/20 Rule',
    currency = 'USD',
    region = 'US',
    notifications_enabled = true,
    dark_mode_enabled = false,
    monthly_income = 5000,
    has_onboarded = true
WHERE email = 'test@example.com';
```

### Тест 2: Проверка данных

```sql
SELECT
    name,
    savings_goal,
    budget_method,
    currency,
    region,
    notifications_enabled,
    dark_mode_enabled,
    monthly_income,
    has_onboarded
FROM users
WHERE email = 'test@example.com';
```

---

## 📊 Мониторинг производительности

После применения миграции проверьте производительность:

```sql
-- Проверьте использование индексов
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'users'
ORDER BY idx_scan DESC;
```

---

## 🔧 Troubleshooting

### Проблема: "column already exists"

**Решение:** Это нормально! Скрипт использует `IF NOT EXISTS`, поэтому просто пропускает уже существующие колонки.

### Проблема: "permission denied"

**Решение:** Убедитесь что вы используете аккаунт с правами администратора в Supabase.

### Проблема: API не возвращает новые поля

**Решение:**
1. Проверьте что миграция применена: запустите verification запрос
2. Перезапустите ваш backend сервер
3. Очистите кеш API

---

## 📝 Checklist перед deployment

- [ ] Создан backup базы данных в Supabase
- [ ] SQL скрипт протестирован на dev окружении
- [ ] Все новые колонки добавлены успешно
- [ ] Индексы созданы и работают
- [ ] RLS политики настроены
- [ ] API эндпоинт `/users/me` возвращает новые поля
- [ ] Flutter приложение обновлено (field names исправлены)
- [ ] Протестирована работа профиля в мобильном приложении

---

## 🎯 Следующие шаги

После успешного применения миграции:

1. **Обновите Flutter приложение:**
   - Убедитесь что изменения в `profile_settings_screen.dart` задеплоены
   - Протестируйте обновление профиля

2. **Настройте мониторинг:**
   - Следите за performance метриками в Supabase Dashboard
   - Проверьте логи на ошибки

3. **Документируйте для команды:**
   - Уведомите команду о новых полях профиля
   - Обновите API документацию

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте Supabase logs в Dashboard
2. Запустите verification запросы из SQL скрипта
3. Проверьте что используете последнюю версию кода

---

**Дата создания:** 2025-10-22
**Версия миграции:** 0008_add_user_profile_fields
**Статус:** ✅ Ready for Production

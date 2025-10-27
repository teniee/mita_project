# 📊 Руководство по применению миграции Analytics Module в Supabase

## Обзор

Это руководство поможет вам применить миграцию базы данных для модуля аналитики MITA в вашей Supabase базе данных.

### Что будет создано:

1. **feature_usage_logs** - таблица для отслеживания использования функций
2. **feature_access_logs** - таблица для отслеживания попыток доступа к премиум функциям
3. **paywall_impression_logs** - таблица для аналитики показов paywall

## 🔐 Предварительные требования

### 1. Получите строку подключения к Supabase

В вашем Supabase проекте:

1. Откройте **Settings** > **Database**
2. Найдите секцию **Connection string**
3. Выберите **URI** формат
4. Скопируйте строку подключения

Она будет выглядеть примерно так:
```
postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxxx.supabase.co:5432/postgres
```

### 2. Создайте backup базы данных

⚠️ **ВАЖНО: Всегда создавайте backup перед применением миграций!**

В Supabase Dashboard:
1. Перейдите в **Database** > **Backups**
2. Нажмите **Create backup**
3. Дождитесь завершения создания backup

## 🚀 Метод 1: Автоматическое применение (Рекомендуется)

### Шаг 1: Установите DATABASE_URL

```bash
# Замените [YOUR-PASSWORD] на ваш реальный пароль
export DATABASE_URL='postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres'
```

**Пример:**
```bash
export DATABASE_URL='postgresql://postgres:MySecurePassword123@db.abcdefghij.supabase.co:5432/postgres'
```

### Шаг 2: Проверьте подключение

```bash
./scripts/verify_analytics_tables.py
```

Вы должны увидеть:
- ✅ Successfully connected to database
- ❌ Table 'feature_usage_logs' does NOT exist (это нормально, мы их еще не создали)

### Шаг 3: Примените миграцию

```bash
./scripts/apply_analytics_migration.sh
```

Скрипт:
1. Проверит подключение к базе
2. Покажет текущий статус миграций
3. Попросит подтверждение
4. Применит миграцию
5. Проверит что таблицы созданы

### Шаг 4: Проверьте результат

```bash
./scripts/verify_analytics_tables.py
```

Вы должны увидеть:
- ✅ Table 'feature_usage_logs' exists
- ✅ Table 'feature_access_logs' exists
- ✅ Table 'paywall_impression_logs' exists
- ✅ All analytics tables are properly configured!

## 🔧 Метод 2: Ручное применение

### Шаг 1: Установите зависимости

```bash
pip install alembic psycopg2-binary
```

### Шаг 2: Установите DATABASE_URL

```bash
export DATABASE_URL='postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres'
```

### Шаг 3: Проверьте текущий статус миграций

```bash
alembic current
```

### Шаг 4: Примените миграцию

```bash
alembic upgrade head
```

### Шаг 5: Проверьте что миграция применилась

```bash
alembic current
```

Вы должны увидеть:
```
0013_add_analytics_tables (head)
```

## 🔍 Проверка в Supabase Dashboard

После применения миграции, проверьте в Supabase Dashboard:

1. Откройте **Table Editor**
2. Вы должны увидеть новые таблицы:
   - `feature_usage_logs`
   - `feature_access_logs`
   - `paywall_impression_logs`

### Структура таблиц

#### feature_usage_logs
```sql
- id (uuid, primary key)
- user_id (uuid, foreign key -> users.id)
- feature (varchar(100))
- screen (varchar(100))
- action (varchar(100))
- extra_data (jsonb)
- session_id (varchar(100))
- platform (varchar(20))
- app_version (varchar(20))
- timestamp (timestamptz)
```

#### feature_access_logs
```sql
- id (uuid, primary key)
- user_id (uuid, foreign key -> users.id)
- feature (varchar(100))
- has_access (boolean)
- is_premium_feature (boolean)
- converted_to_premium (boolean)
- converted_at (timestamptz)
- screen (varchar(100))
- extra_data (jsonb)
- timestamp (timestamptz)
```

#### paywall_impression_logs
```sql
- id (uuid, primary key)
- user_id (uuid, foreign key -> users.id)
- screen (varchar(100))
- feature (varchar(100))
- resulted_in_purchase (boolean)
- purchase_timestamp (timestamptz)
- impression_context (varchar(200))
- extra_data (jsonb)
- timestamp (timestamptz)
```

## 🧪 Тестирование

### Тест 1: Проверка таблиц через SQL

В Supabase SQL Editor выполните:

```sql
-- Проверка что таблицы существуют
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE '%_logs';

-- Проверка индексов
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('feature_usage_logs', 'feature_access_logs', 'paywall_impression_logs');
```

### Тест 2: Вставка тестовых данных

```sql
-- Тестовая запись в feature_usage_logs
INSERT INTO feature_usage_logs (
    id, user_id, feature, screen, action, timestamp
) VALUES (
    gen_random_uuid(),
    (SELECT id FROM users LIMIT 1),
    'test_feature',
    'TestScreen',
    'test_action',
    NOW()
);

-- Проверка
SELECT * FROM feature_usage_logs WHERE feature = 'test_feature';

-- Очистка тестовых данных
DELETE FROM feature_usage_logs WHERE feature = 'test_feature';
```

## ❓ Troubleshooting

### Проблема: "DATABASE_URL environment variable is not set"

**Решение:**
```bash
export DATABASE_URL='postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres'
```

### Проблема: "password authentication failed"

**Решение:**
1. Проверьте что пароль правильный
2. Убедитесь что в строке подключения нет лишних пробелов
3. Попробуйте сбросить пароль в Supabase Dashboard > Settings > Database > Reset database password

### Проблема: "could not connect to server"

**Решение:**
1. Проверьте что у вас есть доступ к интернету
2. Проверьте что Supabase проект активен
3. Проверьте что вы используете правильный host из Supabase Dashboard

### Проблема: "relation already exists"

**Решение:**
Таблицы уже существуют. Проверьте:
```bash
./scripts/verify_analytics_tables.py
```

Если таблицы существуют и работают корректно - всё в порядке!

### Проблема: Миграция не применяется

**Решение:**
```bash
# Проверьте текущую версию
alembic current

# Посмотрите историю миграций
alembic history

# Если нужно, откатите на предыдущую версию
alembic downgrade -1

# Примените миграцию заново
alembic upgrade head
```

## 🔄 Откат миграции

Если что-то пошло не так, вы можете откатить миграцию:

### Откат на одну версию назад:
```bash
export DATABASE_URL='your-database-url'
alembic downgrade -1
```

### Откат на конкретную версию:
```bash
alembic downgrade 0012_add_challenges_tables
```

### Полная очистка таблиц аналитики (⚠️ ОСТОРОЖНО!):

```sql
-- В Supabase SQL Editor
DROP TABLE IF EXISTS paywall_impression_logs CASCADE;
DROP TABLE IF EXISTS feature_access_logs CASCADE;
DROP TABLE IF EXISTS feature_usage_logs CASCADE;
```

## 📝 Следующие шаги

После успешного применения миграции:

1. **Обновите backend:**
   - Перезапустите FastAPI сервер
   - Убедитесь что endpoints `/analytics/*` работают

2. **Обновите Flutter приложение:**
   - Интегрируйте `AnalyticsService` (см. `docs/module-5-analytics.md`)
   - Добавьте вызовы аналитики в ключевые места приложения

3. **Мониторинг:**
   - Проверяйте логи на ошибки
   - Следите за ростом таблиц в Supabase Dashboard

4. **Тестирование:**
   - Протестируйте логирование использования функций
   - Проверьте отслеживание показов paywall
   - Убедитесь что данные корректно сохраняются

## 🆘 Получение помощи

Если у вас возникли проблемы:

1. Проверьте логи:
   ```bash
   # Backend логи
   tail -f logs/app.log

   # Alembic логи
   alembic history -v
   ```

2. Проверьте Supabase Logs:
   - Dashboard > Logs > Database

3. Создайте issue в репозитории с описанием проблемы и логами

## ✅ Checklist

- [ ] Создан backup базы данных
- [ ] Установлен DATABASE_URL
- [ ] Проверено подключение к базе
- [ ] Применена миграция
- [ ] Проверено что таблицы созданы
- [ ] Протестированы API endpoints
- [ ] Обновлен Flutter код
- [ ] Протестирована работа аналитики

---

**Создано:** 2025-10-27
**Версия миграции:** 0013_add_analytics_tables
**Модуль:** Analytics Module (Module 5)

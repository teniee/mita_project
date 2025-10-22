# ⚡ Supabase Quick Start - 5 минут

## Что нужно сделать ПРЯМО СЕЙЧАС:

### 1️⃣ Откройте Supabase Dashboard
👉 https://app.supabase.com → Ваш проект → **SQL Editor**

### 2️⃣ Скопируйте и выполните SQL
1. Откройте файл `SUPABASE_PROFILE_MIGRATION.sql`
2. Скопируйте **весь код**
3. Вставьте в SQL Editor
4. Нажмите **RUN** ▶️

### 3️⃣ Проверьте результат
Должны увидеть таблицу с 9 новыми колонками:
- name
- savings_goal
- budget_method
- currency
- region
- notifications_enabled
- dark_mode_enabled
- monthly_income
- has_onboarded

## ✅ Готово!

Миграция применена. Теперь ваш User Profile модуль полностью работает.

---

## 🧪 Быстрый тест

Выполните в SQL Editor:

```sql
-- Проверка что колонки добавились
SELECT column_name FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('name', 'currency', 'notifications_enabled');
```

Должны увидеть 3 строки.

---

## 📖 Полная документация
См. `SUPABASE_DEPLOYMENT_GUIDE.md` для деталей.

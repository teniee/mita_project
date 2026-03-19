# MITA Budget System — Problem Audit & Fix Status

**Audit Date:** 2026-03-19
**Audited By:** Claude Code (deep codebase analysis)
**Scope:** Full budget distribution pipeline — from income input to daily redistribution

---

## Core Vision (что должно работать)

> Пользователь вводит доходы и расходы → приложение само считает, сколько тратить каждый день по категориям → в конце месяца деньги остаются, цели выполняются.

Четыре шага цикла:
1. **Вход** — доход + фиксированные расходы + цели накоплений
2. **Расчёт** — сколько тратить в день по каждой категории
3. **Трекинг** — пользователь логирует трату → бюджет обновляется мгновенно
4. **Корректировка** — перерасход в одной категории → автоматически урезаем другие

---

## Что работало до аудита ✅

| Компонент | Файл | Статус |
|-----------|------|--------|
| Классификация дохода (5 тиров) | `income_classification_service.py` | ✅ Работает |
| Генерация бюджета из анкеты | `budget_logic.py` | ✅ Работает |
| Распределение по дням (FIXED/SPREAD/CLUSTERED) | `calendar_engine.py` | ✅ Работает |
| Логирование транзакции → DailyPlan | `expense_tracker.py` | ✅ Работает |
| Мгновенное обновление spent_amount | `services.py` (transactions) | ✅ Синхронно |
| Pre-transaction affordability check | `POST /transactions/check-affordability` | ✅ Работает |
| Дашборд дня green/yellow/red | `GET /budget/daily` | ✅ Работает |
| Трекинг целей (goal progress) | `goal_transaction_service.py` | ✅ Работает |
| Алгоритм перераспределения | `budget_redistributor.py` | ✅ Написан |

---

## Проблемы — полный список

---

### ПРОБЛЕМА 1 — Авто-перераспределение не вызывалось ❌ → ✅ ИСПРАВЛЕНО

**Файлы:** `expense_tracker.py`, `realtime_rebalancer.py`

**Что было:**
Алгоритм перераспределения (`rebalance_after_overspend`) был написан и работал корректно, но нигде не вызывался автоматически. При перерасходе день просто становился "red" — и всё. Ничего не происходило.

**Два дополнительных бага в `realtime_rebalancer.py`:**
1. `entry.planned_amount = float(available - cut)` — финансовые суммы конвертировались в `float`, теряя точность (например, $3.33 → $3.3300000001)
2. Функция брала деньги у доноров, но **не добавляла** покрытую сумму к перерасходованному дню. День оставался "red" вечно, даже после успешного ребаланса.

**Что сделано:**
- Исправлен баг с `float` → везде `Decimal`
- Добавлен шаг 5: после трансферов кредитуем `planned_amount` перерасходованного entry
- В `expense_tracker.py` добавлен вызов `check_and_rebalance()` после каждой транзакции
- После ребаланса повторно вызывается `update_day_status()` — статус пересчитывается и может переключиться RED → GREEN

**Полный поток теперь:**
```
Пользователь тратит $35 на dining_out (план $25, дефицит $10)
  → apply_transaction_to_plan() → spent = 35, статус RED
  → check_and_rebalance() → дефицит $10 обнаружен
      → ищет future days с surplus в non-SACRED категориях
      → берёт $10 у entertainment (DISCRETIONARY — первый приоритет)
      → кредитует dining_out planned → planned = 35
      → db.commit()
  → update_day_status() → planned=35, spent=35 → статус GREEN ✅
```

**Приоритет доноров:**
```
DISCRETIONARY (3) — gaming, entertainment, dining, delivery  → берём первыми
FLEXIBLE (2)      — coffee, clothing, personal_care          → вторые
PROTECTED (1)     — groceries, transport_public              → только если нет других
SACRED (0)        — rent, mortgage, savings_goal, utilities  → НИКОГДА не трогаем
```

**Защиты:**
- 50% cap: максимум 50% бюджета одной категории за один ребаланс
- Только future days (≥ txn_date): прошлые дни не меняются
- dry_run режим: расчёт без записи в БД (для preview)

**Тесты написаны:**
- `tests/test_realtime_rebalancer.py` — 18 unit тестов (mock DB)
- `tests/test_rebalancer_integration.py` — 10 integration тестов (SQLite in-memory, реальные SQL запросы)
- Все 28 тестов проходят ✅

---

### ПРОБЛЕМА 2 — Audit log хранится в памяти, теряется при рестарте ⚠️ ОТКРЫТА

**Файл:** `app/services/redistribution_audit_log.py`

**Что есть:**
```python
_audit_log: Dict[str, List[Dict]] = {}  # in-memory dict!
```

**Проблема:**
История перераспределений хранится в Python-словаре в памяти процесса. При каждом деплое на Railway (а их много), при каждом рестарте контейнера — вся история теряется. `GET /budget/redistribution_history` возвращает пустой список после рестарта.

**Что нужно сделать:**
- Создать таблицу `redistribution_events` в PostgreSQL
- Alembic миграция
- Переписать `record_redistribution_event()` и `get_redistribution_history()` на работу с БД
- Индексы: `(user_id, created_at DESC)` для быстрой выборки истории

**Схема таблицы:**
```sql
CREATE TABLE redistribution_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_category VARCHAR(100) NOT NULL,
    to_category VARCHAR(100) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    reason VARCHAR(50) NOT NULL,  -- 'realtime_rebalance' | 'budget_redistribution'
    from_day DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX ix_redistribution_events_user_created
    ON redistribution_events(user_id, created_at DESC);
```

---

### ПРОБЛЕМА 3 — Нет forward projection (приложение не думает вперёд) ⚠️ ОТКРЫТА

**Файлы:** нет — функциональность отсутствует полностью

**Проблема:**
Пользователь не видит ничего о том, что будет к концу месяца при текущем темпе трат. Нет ни одного эндпоинта который считает:
- "При текущем темпе ты потратишь весь бюджет на еду к 18-му числу"
- "В конце месяца у тебя останется X рублей / ты уйдёшь в минус на Y"
- "Безопасный дневной лимит с сегодня: $64/день"
- "Цель на отпуск: ты отстаёшь на $120, нужно урезать развлечения"

**Что нужно сделать:**
Новый эндпоинт `GET /budget/forecast`:

```json
{
  "days_elapsed": 10,
  "days_remaining": 21,
  "current_daily_pace": 87.50,
  "safe_daily_limit": 64.20,
  "projected_month_end_balance": -278.00,
  "status": "danger",
  "categories_at_risk": [
    {
      "category": "dining_out",
      "pace": 12.50,
      "budget_per_day": 8.30,
      "days_until_exhausted": 6
    }
  ],
  "goal_forecast": {
    "target": 500.00,
    "on_track": false,
    "projected_saved": 320.00,
    "shortfall": 180.00
  }
}
```

**Формулы:**
```python
days_remaining = days_in_month - today.day
total_spent = sum(daily_plan.spent_amount for month)
monthly_budget = sum(daily_plan.planned_amount for month)
remaining_budget = monthly_budget - total_spent
safe_daily_limit = remaining_budget / days_remaining
current_pace = total_spent / today.day
projected_end = total_spent + (current_pace * days_remaining)
projected_balance = monthly_budget - projected_end
```

---

### ПРОБЛЕМА 4 — Цели не связаны с дневным бюджетом ⚠️ ОТКРЫТА

**Файлы:** `app/db/models/goal.py`, `app/db/models/daily_plan.py`

**Проблема:**
Цели и DailyPlan живут в параллельных мирах. Если пользователь создаёт цель "накопить $500 к июню" — это никак не влияет на то, сколько приложение разрешает тратить каждый день. Накопление не вычитается из discretionary автоматически.

**Пример:**
```
Доход: $3000/мес
Цель: накопить $600 к June 30 (нужно откладывать $200/мес)
Текущая ситуация: приложение даёт тратить $3000 — цель полностью игнорируется
Должно быть: приложение даёт тратить $2800, $200 помечены как SACRED для цели
```

**Что нужно сделать:**
- При создании цели с `target_date` — вычислять `required_monthly_savings`
- Автоматически добавлять в DailyPlan SACRED запись для этой суммы
- При обновлении прогресса цели — пересчитывать оставшуюся сумму

---

### ПРОБЛЕМА 5 — Нет проактивных алертов по velocity ⚠️ ОТКРЫТА

**Файлы:** нет — функциональность отсутствует

**Проблема:**
`POST /transactions/check-affordability` работает только когда пользователь **сам спрашивает** перед тратой. Приложение никогда не пишет первым:
- "Ты уже потратил 80% бюджета на развлечения, хотя месяц прошёл лишь на 40%"
- "При текущем темпе бюджет на еду закончится через 5 дней"
- "Сегодня хорошо — ты потратил меньше нормы, +$12 к запасу"

**Что нужно сделать:**
- Фоновый воркер запускается раз в день (или триггер при транзакции)
- Считает velocity по каждой категории: `spent_so_far / days_elapsed` vs `monthly_budget / days_in_month`
- Если категория сжигается > 1.5x быстрее нормы → push notification
- Firebase Cloud Messaging уже интегрирован — нужна только логика триггеров

---

### ПРОБЛЕМА 6 — Нет запланированных будущих расходов ⚠️ ОТКРЫТА

**Файлы:** нет — функциональность отсутствует

**Проблема:**
Пользователь знает что 25-го числа придёт счёт за страховку $300. Он не может сказать об этом приложению заранее, и оно не корректирует дневной бюджет. В итоге 25-го происходит "неожиданный" перерасход.

**Что нужно сделать:**
- `POST /transactions/scheduled` — запланировать будущую трату
- При создании: сразу пересчитать `safe_daily_limit` для оставшихся дней
- За 3 дня до — push reminder
- В день наступления — автоматически создать транзакцию

---

## Сводная таблица

| # | Проблема | Критичность | Статус |
|---|----------|-------------|--------|
| 1 | Авто-перераспределение не вызывалось + 2 бага в алгоритме | 🔴 Критично | ✅ **ИСПРАВЛЕНО** |
| 2 | Audit log в памяти — теряется при рестарте | 🟡 Важно | ⚠️ Открыта |
| 3 | Нет forward projection / прогноза конца месяца | 🟡 Важно | ⚠️ Открыта |
| 4 | Цели не связаны с дневным бюджетом | 🟡 Важно | ⚠️ Открыта |
| 5 | Нет проактивных алертов по velocity трат | 🟢 Улучшение | ⚠️ Открыта |
| 6 | Нет запланированных будущих расходов | 🟢 Улучшение | ⚠️ Открыта |

---

## Что изменено в коде (Problem 1)

### `app/services/core/engine/realtime_rebalancer.py`
- Исправлен `float` → `Decimal` при обновлении `planned_amount` (строка ~168)
- Добавлен шаг 5: кредитование перерасходованного entry после трансферов (строки ~197–231)

### `app/services/core/engine/expense_tracker.py`
- Добавлен import `check_and_rebalance`
- Добавлен вызов после `update_day_status` (строки ~54–74)
- Повторный `update_day_status` после ребаланса для актуального статуса

### `tests/test_realtime_rebalancer.py` ← новый файл
- 18 unit тестов с mock DB
- Покрытие: fast path, SACRED protection, 50% cap, priority order, partial coverage, dry_run, Decimal precision, credit to overspent entry

### `tests/test_rebalancer_integration.py` ← новый файл
- 10 integration тестов с SQLite in-memory (реальные SQL запросы)
- Покрытие: full flow, past days не трогаются, DB precision, multiple donors

**Итого тестов:** было 44 passing → стало 72 passing (+28 новых, все ✅)

---

*Документ обновлять при закрытии каждой проблемы.*

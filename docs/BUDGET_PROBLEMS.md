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

### ПРОБЛЕМА 2 — Audit log хранился в памяти, терялся при рестарте ✅ ИСПРАВЛЕНО

**Файл:** `app/services/redistribution_audit_log.py`

**Что было:**
```python
_audit_log: Dict[str, List[Dict]] = {}  # in-memory dict!
```
История перераспределений хранилась в Python-словаре. При каждом деплое на Railway — вся история терялась. `GET /budget/redistribution_history` возвращал пустой список после рестарта.

**Что сделано:**
- Создана модель `RedistributionEvent` (`app/db/models/redistribution_event.py`)
- Alembic миграция `0025_add_redistribution_events_table.py`
- Два индекса: `(user_id, created_at DESC)` для history queries, `(user_id, from_day)` для monthly reports
- `redistribution_audit_log.py` полностью переписан — `record_redistribution_event()` пишет в PostgreSQL через savepoint (`db.begin_nested()`)
- Savepoint защищает основную транзакцию: если audit write упадёт, ребаланс не откатывается
- `GET /budget/redistribution_history` теперь делает реальный SQL-запрос к `redistribution_events`
- `budget_redistributor.py` обновлён — передаёт `db=db` и `from_day=donor_entry.date`
- `realtime_rebalancer.py` обновлён — передаёт `db=db` в `record_redistribution_event()`

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
CREATE INDEX ix_redistribution_events_user_day
    ON redistribution_events(user_id, from_day);
```

**Тесты:**
- `tests/test_redistribution_audit_log.py` — 17 тестов (SQLite in-memory): write to DB, survives session restart, from_day as date/datetime/str/None, precision, ordering, user isolation, limit, clear
- `tests/test_rebalancer_integration.py` — 10 integration тестов обновлены (оба теста создают обе таблицы)
- Все 45 тестов проходят ✅

---

### ПРОБЛЕМА 2.5 — DateTime vs date в WHERE запросах к DailyPlan ✅ ИСПРАВЛЕНО

**Файлы:** `expense_tracker.py` (×2), `calendar_updater.py`, `calendar_service_real.py`, `expense_tracker.py` (services)

**Что было:**
`DailyPlan.date` — колонка `DateTime(timezone=True)`. Все запросы использовали:
```python
.filter_by(date=python_date_object)
```
Это генерирует SQL:
```sql
WHERE date = '2026-03-19 00:00:00+00'
```
Запись хранящаяся как `2026-03-19 12:00:00+00` (полдень UTC) **не находилась**. В результате `apply_transaction_to_plan()` создавал новый `DailyPlan` ряд с `planned_amount=0` вместо обновления существующего → `spent_amount` накапливался в дублирующей строке, а оригинальный бюджет оставался нетронутым.

**Что сделано:**
- Создан хелпер `app/core/date_utils.py::day_to_range(d: date)` → возвращает `(00:00:00, 23:59:59)` datetime границы
- Во всех 4 файлах заменены `filter_by(date=day)` на явный range-фильтр:
```python
day_start, day_end = day_to_range(day)
.filter(
    DailyPlan.date >= day_start,
    DailyPlan.date <= day_end,
)
```

**Затронутые файлы:**
- `app/core/date_utils.py` ← новый файл
- `app/services/core/engine/expense_tracker.py` — `apply_transaction_to_plan()` + `record_expense()`
- `app/services/core/engine/calendar_updater.py` — `update_day_status()`
- `app/services/calendar_service_real.py` — `update_day_entry()`
- `app/services/expense_tracker.py` — `record_expense()`

---

### ПРОБЛЕМА 3 — Нет forward projection (приложение не думает вперёд) ✅ ИСПРАВЛЕНО

**Файлы:** `app/services/core/engine/budget_forecast_engine.py`, `app/api/budget/routes.py`

**Что было:**
Пользователь не видел ничего о том, что будет к концу месяца при текущем темпе трат.

**Что сделано:**
- Создан чистый движок `budget_forecast_engine.py` — pure computation, никакого DB доступа внутри
- `DailyPlanData`, `GoalData` — входные dataclass'ы (route предварительно тянет данные из БД)
- `ForecastResult`, `CategoryForecast`, `GoalForecast` — выходные dataclass'ы с `to_dict()`
- `compute_forecast()` — публичный API движка
- Добавлен `GET /budget/forecast` в `app/api/budget/routes.py`
- Все расчёты через `Decimal`, float только в `to_dict()` при отдаче JSON

**Эндпоинт `GET /budget/forecast`:**
```json
{
  "year": 2026, "month": 3,
  "days_in_month": 31, "days_elapsed": 10, "days_remaining": 21,
  "total_planned": 3100.00, "total_spent": 1500.00,
  "remaining_budget": 1600.00,
  "current_daily_pace": 150.00,
  "safe_daily_limit": 76.19,
  "projected_month_end_spend": 4650.00,
  "projected_month_end_balance": -1550.00,
  "status": "danger",
  "categories_at_risk": [
    {
      "category": "dining_out",
      "monthly_planned": 930.00,
      "monthly_spent": 600.00,
      "pace": 60.00,
      "budget_per_day": 30.00,
      "overspend_ratio": 2.0,
      "days_until_exhausted": 6
    }
  ],
  "all_categories": [...],
  "goals": [
    {
      "goal_id": "...", "title": "Vacation",
      "target": 500.00, "saved": 50.00, "remaining": 450.00,
      "target_date": "2026-06-01",
      "months_remaining": 2.53,
      "required_monthly_contribution": 177.87,
      "projected_saved": 176.50,
      "on_track": false,
      "shortfall": 323.50
    }
  ]
}
```

**Статусы:**
- `"on_track"` → projected_balance >= 0
- `"warning"` → projected overspend < 10% от total_planned
- `"danger"` → projected overspend >= 10% от total_planned
- `"no_data"` → нет DailyPlan строк или days_elapsed == 0

**Категории at_risk:** темп трат > 120% от планового дневного лимита
**Цели:** проекция через `monthly_contribution * months_remaining` (30.44 дней/мес)

**Тесты:**
- `tests/test_budget_forecast_engine.py` — 35 unit тестов (pure engine, без DB)
- Все 35 проходят ✅

**Тест-классы:**
- `TestNoData` — пустые планы, будущий месяц, первый день, прошлый месяц, to_dict()
- `TestStatusThresholds` — on_track / warning / danger пороги
- `TestGlobalMetrics` — safe_daily_limit, pace, projected_balance формулы
- `TestCategoryForecasts` — at_risk пороги, сортировка, агрегация по категории
- `TestDaysUntilExhausted` — normal, zero-pace, already-exhausted
- `TestGoalForecasts` — on_track, not_on_track, no deadline, overdue, fully funded
- `TestDecimalPrecision` — Decimal внутри, float в to_dict(), 2 знака
- `TestFullScenario` — реалистичные сценарии (danger + goals, all green)

---

### ПРОБЛЕМА 4 — Цели не связаны с дневным бюджетом ✅ ИСПРАВЛЕНО

**Файлы:** `app/db/models/daily_plan.py`, `app/core/category_priority.py`,
`app/services/core/engine/goal_budget_sync.py`, `app/api/goals/routes.py`,
`alembic/versions/0026_add_goal_id_to_daily_plan.py`

**Что было:**
Цели и DailyPlan жили в параллельных мирах. Пользователь создавал цель "накопить $500 к июню" — это никак не влияло на то, сколько приложение разрешает тратить каждый день. Накопление не вычиталось из discretionary автоматически.

**Пример (что было vs что стало):**
```
Доход: $3000/мес
Цель: накопить $600 к June 30 (нужно откладывать $200/мес = $6.45/день)

БЫЛО:  приложение даёт тратить $3000 — цель полностью игнорируется
СТАЛО: 13 SACRED строк в DailyPlan (19-31 марта), по $6.45/день
       Реблансёр никогда не трогает эти строки
       Пользователь видит реальный "safe daily limit" → $2800/мес
```

**Что сделано:**

**1. Миграция 0026** — добавлена колонка `goal_id` в `daily_plan`:
```sql
ALTER TABLE daily_plan ADD COLUMN goal_id UUID REFERENCES goals(id) ON DELETE SET NULL;
CREATE INDEX ix_daily_plan_goal_id ON daily_plan(goal_id);
CREATE INDEX ix_daily_plan_user_goal_date ON daily_plan(user_id, goal_id, date);
```

**2. `DailyPlan` модель** — новое nullable FK поле `goal_id`.

**3. `category_priority.py`** — добавлена категория `goal_savings` в SACRED:
```python
"goal_savings": CategoryLevel.SACRED,  # Реблансёр никогда не трогает
```

**4. `goal_budget_sync.py`** (новый файл) — чистый движок синхронизации:
- `calculate_required_monthly_contribution(goal, today)` — сколько нужно откладывать в месяц
- `calculate_daily_savings_amount(monthly, year, month)` — ежедневная сумма = monthly / days_in_month
- `sync_goal_to_daily_plan(db, goal, user_id)` — upsert SACRED строк для оставшихся дней месяца
- `remove_goal_daily_plan_rows(db, goal_id, user_id, from_date)` — освобождает бюджет при деактивации

**Ключевые принципы:**
- Только будущие дни создаются/обновляются (прошлое нетронуто)
- Idempotent: вызов дважды даёт тот же результат
- `daily = monthly / days_in_month` — равномерное распределение, честный shortfall при создании mid-month
- `months` floor = 1 — нет деления на 0 при deadlines < 30 дней

**5. `goals/routes.py`** — хуки в 6 endpoints (non-blocking, try/except):
| Endpoint | Действие |
|----------|----------|
| `POST /goals/` | Создать SACRED строки |
| `PATCH /goals/{id}` | Пересчитать при изменении target/date/status |
| `DELETE /goals/{id}` | Удалить будущие строки ДО удаления цели |
| `POST /goals/{id}/pause` | Освободить будущий бюджет |
| `POST /goals/{id}/resume` | Восстановить SACRED строки |
| `POST /goals/{id}/complete` | Освободить будущий бюджет |

**Тесты:**
- `tests/test_goal_budget_sync.py` — 41 тест (unit + mock-based):
  - 12 тестов: `calculate_required_monthly_contribution`
  - 6 тестов: `calculate_daily_savings_amount`
  - 11 тестов: `sync_goal_to_daily_plan`
  - 4 теста: `remove_goal_daily_plan_rows`
  - 3 теста: SACRED category validation
  - 5 тестов: edge cases (precision, multiple goals, leap year)
- `tests/test_rebalancer_integration.py` — обновлён DDL (добавлен `goal_id` в SQLite schema)
- Все 121 тест проходят ✅

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
| 2 | Audit log в памяти — теряется при рестарте | 🟡 Важно | ✅ **ИСПРАВЛЕНО** |
| 3 | Нет forward projection / прогноза конца месяца | 🟡 Важно | ✅ **ИСПРАВЛЕНО** |
| 4 | Цели не связаны с дневным бюджетом | 🟡 Важно | ✅ **ИСПРАВЛЕНО** |
| 5 | Нет проактивных алертов по velocity трат | 🟢 Улучшение | ⚠️ Открыта |
| 6 | Нет запланированных будущих расходов | 🟢 Улучшение | ⚠️ Открыта |

---

## Что изменено в коде

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

### Problem 2 — `app/services/redistribution_audit_log.py`
- Полностью переписан с in-memory dict → PostgreSQL
- `record_redistribution_event()` пишет через savepoint (`db.begin_nested()`)
- `get_redistribution_history()` / `clear_user_audit_log()` — реальные SQL запросы

### `app/db/models/redistribution_event.py` ← новый файл
- SQLAlchemy модель `RedistributionEvent`

### `alembic/versions/0025_add_redistribution_events_table.py` ← новая миграция
- Таблица + 2 индекса: `(user_id, created_at DESC)`, `(user_id, from_day)`

### `app/api/budget/routes.py`
- `GET /budget/redistribution_history` — реальный SQL вместо эвристического хака

### `tests/test_redistribution_audit_log.py` ← новый файл
- 17 тестов: write, session restart, from_day типы, precision, ordering, isolation, limit, clear

---

### Problem 2.5 (DateTime баг) — `app/core/date_utils.py` ← новый файл
- `day_to_range(d)` — единственный источник правды для datetime границ дня
- Исправлены 4 файла: оба `expense_tracker.py`, `calendar_updater.py`, `calendar_service_real.py`

---

**Итого тестов сейчас:** 45 passing ✅

---

### Problem 3 — `app/services/core/engine/budget_forecast_engine.py` ← новый файл
- Pure computation engine, zero DB access
- `DailyPlanData`, `GoalData` — frozen dataclass'ы для входных данных
- `CategoryForecast`, `GoalForecast`, `ForecastResult` — выходные dataclass'ы с `to_dict()`
- `compute_forecast()` — публичный API, принимает pre-fetched данные от роута
- Все расчёты в Decimal, ROUND_HALF_UP, 2 знака везде

### `app/api/budget/routes.py`
- Добавлен `GET /budget/forecast` эндпоинт
- Async SQLAlchemy запросы: DailyPlan за месяц + активные Goals
- Конвертация ORM объектов → DailyPlanData / GoalData перед вызовом движка
- Валидация year/month (2020–2030, 1–12) с HTTP 422

### `tests/test_budget_forecast_engine.py` ← новый файл
- 35 unit тестов, все без DB (движок чистый)
- 8 групп: NoData, Status, GlobalMetrics, CategoryForecasts, DaysUntilExhausted,
  GoalForecasts, DecimalPrecision, FullScenario

**Итого тестов после Problem 3:** 80 passing ✅ (45 предыдущих + 35 новых)

---

### Problem 4 — `app/services/core/engine/goal_budget_sync.py` ← новый файл
- `calculate_required_monthly_contribution()` — pure, synchronous
- `calculate_daily_savings_amount()` — pure, synchronous
- `sync_goal_to_daily_plan()` — async, idempotent upsert
- `remove_goal_daily_plan_rows()` — async, bulk DELETE

### `app/db/models/daily_plan.py`
- Добавлен `goal_id` nullable FK → `goals.id` ON DELETE SET NULL

### `app/core/category_priority.py`
- Добавлен `"goal_savings": CategoryLevel.SACRED`

### `alembic/versions/0026_add_goal_id_to_daily_plan.py` ← новая миграция
- `goal_id` column + 2 индекса: `ix_daily_plan_goal_id`, `ix_daily_plan_user_goal_date`

### `app/api/goals/routes.py`
- Хуки в 6 endpoints: create, update, delete, pause, resume, complete
- Non-blocking: try/except, sync failure не ломает goal CRUD

### `tests/test_goal_budget_sync.py` ← новый файл
- 41 тест: unit + mock-based AsyncSession

### `tests/test_rebalancer_integration.py`
- DDL обновлён: добавлен `goal_id TEXT` в CREATE TABLE

**Итого тестов после Problem 4:** 121 passing ✅ (80 предыдущих + 41 новый)

---

*Документ обновлять при закрытии каждой проблемы.*

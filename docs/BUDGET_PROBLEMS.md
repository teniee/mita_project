# BUDGET PROBLEMS — ПОЛНЫЙ АУДИТ И СТАТУС ИСПРАВЛЕНИЙ
**Создан:** 2026-03-13
**Обновлён:** 2026-03-20
**Источник:** Deep analysis of all 32 budget-related files + code verification

---

## КРИТИЧЕСКИЕ НЕСООТВЕТСТВИЯ

### ПРОБЛЕМА 1 — Главный API эндпоинт игнорирует движок
**Файл:** `app/api/budget/routes.py` строки 476–556

**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

Эндпоинт `POST /budget/monthly` корректно вызывает реальный движок:
- Если `user_answers` содержит `monthly_income` → вызывает `generate_budget_from_answers(user_answers)` → персонализированный бюджет
- Иначе → `IncomeClassificationService.classify_income()` → `get_budget_weights(tier)` → tier-специфичные веса
- Захардкоженные `0.30/0.15/0.10/0.20` присутствуют только как `except`-fallback при крэше движка — это нормальная архитектура

---

### ПРОБЛЕМА 2 — Real-time rebalancing не был реализован
**Файл:** `app/services/core/engine/realtime_rebalancer.py`, `app/services/core/engine/expense_tracker.py`

**Статус: ✅ ИСПРАВЛЕНО (март 2026)**

**Что было:** Алгоритм перераспределения был написан, но нигде не вызывался. При перерасходе день просто становился RED — ничего не происходило. Дополнительно: два бага — `float` вместо `Decimal` теряло точность, и перерасходованный день не кредитировался после ребаланса (оставался RED навсегда).

**Что сделано:**
- `realtime_rebalancer.py` — исправлен `float` → `Decimal`, добавлен шаг кредитования перерасходованного entry
- `expense_tracker.py` — после каждой транзакции вызывается `check_and_rebalance()` + повторный `update_day_status()`
- Приоритет доноров: DISCRETIONARY(3) → FLEXIBLE(2) → PROTECTED(1), SACRED(0) никогда не трогается
- 50% cap на один ребаланс, только future days

**Полный поток:**
```
Потратил $35 на dining_out (план $25, дефицит $10)
  → spent = 35, статус RED
  → check_and_rebalance() → берёт $10 у entertainment (DISCRETIONARY)
  → dining_out planned = 35
  → update_day_status() → GREEN ✅
```

**Тесты:** 28 тестов (`test_realtime_rebalancer.py` + `test_rebalancer_integration.py`) — все проходят ✅

---

### ПРОБЛЕМА 3 — Cron перераспределял прошлый месяц
**Файл:** `app/services/core/engine/cron_task_budget_redistribution.py` строка 16

**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

Cron использует `year = now.year`, `month = now.month` — текущий месяц. `prev_month = month - 1` встречается только в блоке `if now.day == 1` для rollover savings — это правильная логика, а не баг.

---

### ПРОБЛЕМА 4 — Savings не были защищены от перераспределения
**Файл:** `app/services/budget_redistributor.py` строки 41–52

**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

`is_sacred()` из `category_priority.py` применяется: `not is_sacred(d_cat)` как фильтр доноров. `savings_goal`, `savings_emergency`, `rent`, `mortgage`, `utilities` никогда не выступают донорами.

---

### ПРОБЛЕМА 5 — Behavioral allocator сломан (возвращал `user_context_applied: True` — ложь)
**Файл:** `app/services/core/behavior/behavioral_budget_allocator.py` строки 103–147

**Статус: ⚠️ ЧАСТИЧНО ИСПРАВЛЕНО — нужна проверка**

`user_context_applied` теперь честный boolean: `True` только при успешном применении контекста (строка 131), `False` при fallback (строка 140).

**Что остаётся под вопросом:** Насколько часто реальный пользователь попадает в ветку `user_context_applied=True`. Нужно проверить, какой процент вызовов реально использует `dynamic_threshold_service` vs жёсткие константы `food=30%, savings=20%`.

**Нужно сделать:** Добавить логирование/метрику — сколько % запросов используют реальный контекст, сколько — fallback константы.

---

### ПРОБЛЕМА 6 — Порог статуса дня одинаков для всех доходов
**Файл:** `app/services/core/engine/calendar_updater.py` строка 26

**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

Порог динамический: `yellow_threshold = max(Decimal("2.00"), min(Decimal("25.00"), planned * Decimal("0.05")))` — 5% от planned, от $2 до $25. `$10 flat` для всех больше не используется.

---

### ПРОБЛЕМА 7 — CLUSTERED распределение случайное (без seed)
**Файл:** `app/services/core/engine/calendar_engine.py` строки 127–146

**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

Детерминированный RNG: `seed = hashlib.md5(f"{year}{month}{category}".encode())` → `random.Random(seed_int)`. При одинаковых входных данных — одинаковое распределение по дням. Пользователь может планировать.

---

### ПРОБЛЕМА 8 — Два механизма перераспределения несовместимы
**Файл A:** `app/engine/budget_redistributor.py` — дневное, не сохраняет в БД
**Файл B:** `app/services/budget_redistributor.py` — категорийное, сохраняет в БД

**Статус: ❌ НЕ ИСПРАВЛЕНО**

Оба файла существуют, используются в разных контекстах, разные форматы данных. Алгоритм A (app/engine/) не записывает результат в `DailyPlan`. Нет единого пути для всех ребалансов.

**Что нужно сделать:** Выбрать один — скорее всего `app/services/budget_redistributor.py` (он пишет в БД) + `realtime_rebalancer.py` для real-time. `app/engine/budget_redistributor.py` — устаревший, нужно проверить все вызовы и удалить.

---

### ПРОБЛЕМА 9 — Цели изолированы от бюджета
**Файл:** `app/services/core/engine/goal_budget_sync.py`, `app/api/goals/routes.py`

**Статус: ✅ ИСПРАВЛЕНО (март 2026)**

**Что было:** Цели жили отдельно. "Накопить $500 к июню" не влияло на daily spending limit.

**Что сделано:**
- `goal_budget_sync.py` — при создании цели создаются SACRED строки в `DailyPlan` (category `goal_savings`)
- Alembic миграция `0026` — добавлена колонка `goal_id` в `daily_plan`
- Хуки в 6 endpoints goals: create, update, delete, pause, resume, complete
- Реблансёр никогда не трогает `goal_savings` категорию (SACRED)
- Пример: доход $3000, цель $600 к June 30 → 13 SACRED строк по $6.45/день → реальный safe_daily_limit = $2800/мес

**Тесты:** 41 тест (`test_goal_budget_sync.py`) — все проходят ✅

---

### ПРОБЛЕМА 10 — Уведомления не знают о целях пользователя
**Файл:** `app/services/budget_alert_service.py`, `app/services/spending_prevention_service.py`

**Статус: ❌ НЕ ИСПРАВЛЕНО**

Сообщения безличные: "Consider reducing this category". Не упоминают имя, не говорят о влиянии на цель.

**Что нужно:** Каждый alert должен включать:
- Имя пользователя
- Категорию и сумму перерасхода
- Влияние на цель (сдвиг в днях/сумме)
- Конкретное предложение откуда взять
- Кнопки: [Принять] [Настроить] [Игнорировать]

**Пример:**
```
"Марина, ты потратила на $250 больше на одежду.
Твоя цель [Отпуск в Барселоне] сдвинулась на 5 дней.
Хочешь скорректировать бюджет?"
```

---

### ПРОБЛЕМА 11 — Нет напоминаний через 3 дня
**Статус: ❌ НЕ СДЕЛАНО**

Когда пользователь нажал [Игнорировать] на предупреждении → через 3 дня напоминание о последствиях.

**Что нужно:** Cron task + поле `ignored_at` в `Notification`. При ignore → записать дату. Cron утром проверяет: `ignored_at + 3 days <= today` → push напоминание с обновлённым impact (цель сдвинулась ещё на N дней).

---

### ПРОБЛЕМА 12 — Несоответствие порогов между сервисами
**Файл A:** `app/services/budget_alert_service.py:24–25` — WARNING=80%, DANGER=100%
**Файл B:** `app/services/spending_prevention_service.py:24–27` — CAUTION=70%, DANGER=90%

**Статус: ❌ НЕ ИСПРАВЛЕНО**

Два разных порога в двух сервисах — пользователь получает разные сигналы в зависимости от того, какой путь сработал.

**Что нужно:** Вынести все пороги в `budget_thresholds.py` (там уже есть velocity константы — добавить туда же). Оба сервиса импортируют из одного источника.

---

### ПРОБЛЕМА 13 — История перераспределений — эвристика, не лог
**Файл:** `app/api/budget/routes.py` строки 261–280

**Статус: ✅ ИСПРАВЛЕНО (март 2026)**

**Что было:** `GET /budget/redistribution_history` сравнивал соседние DailyPlan записи и угадывал причину изменения по размеру diff.

**Что сделано:**
- Модель `RedistributionEvent` (`app/db/models/redistribution_event.py`)
- Alembic миграция `0025` — таблица `redistribution_events` + 2 индекса
- `redistribution_audit_log.py` переписан — пишет в PostgreSQL через savepoint
- `GET /budget/redistribution_history` — реальный SQL запрос к таблице

**Тесты:** 17 тестов (`test_redistribution_audit_log.py`) — все проходят ✅

---

### ПРОБЛЕМА 14 — Потеря излишков savings между месяцами
**Статус: ✅ УЖЕ ИСПРАВЛЕНО**

`savings_surplus_service.rollover_month_savings()` вызывается в cron каждое 1-е число: берёт surplus прошлого месяца и добавляет к цели текущего. Логика уже в `cron_task_budget_redistribution.py`.

---

### ПРОБЛЕМА 15 — Нет положительных уведомлений (wins)
**Файл:** `app/services/core/engine/velocity_alert_engine.py`

**Статус: ⚠️ ЧАСТИЧНО СДЕЛАНО — нужна проверка delivery**

`velocity_alert_engine.py` содержит win detection: consecutive good days (7/14/30-day streaks). `notify_spending_win` добавлен в `NotificationIntegration`. Шаблон `spending_win` есть в `NotificationTemplates`.

**Что нужно проверить:** Реально ли отправляются push при streak. Проверить через тест или лог после 7 consecutive green days.

---

## ОТСУТСТВУЮЩИЕ КОМПОНЕНТЫ (уже построены)

### ✅ СДЕЛАНО A — Real-time rebalancing engine
`app/services/core/engine/realtime_rebalancer.py` — полный цикл от транзакции до GREEN статуса.

### ✅ СДЕЛАНО B — Goal-aware budget sync
`app/services/core/engine/goal_budget_sync.py` — SACRED строки в DailyPlan при создании цели.

### ✅ СДЕЛАНО C — Категорийная иерархия (единый реестр)
`app/core/category_priority.py` — SACRED(0) / PROTECTED(1) / FLEXIBLE(2) / DISCRETIONARY(3).

### ✅ СДЕЛАНО D — Velocity alerts + win notifications
`app/services/core/engine/velocity_alert_engine.py` + `velocity_alert_service.py` + cron.

### ✅ СДЕЛАНО E — Scheduled future expenses
`app/services/core/engine/scheduled_expense_engine.py`, модель `ScheduledExpense`, миграция 0027, API `/api/scheduled-expenses/`.

### ✅ СДЕЛАНО F — Savings surplus rollover
`app/services/savings_surplus_service.py` — автоматический перенос на 1-е число.

### ❌ НЕ СДЕЛАНО D (из оригинального плана) — 3-day reminder cron
Cron для напоминаний при игнорировании предупреждений — ещё не создан.

---

## АРХИТЕКТУРНЫЕ ПРИНЦИПЫ

- Savings СВЯЩЕННЫ — никогда не доноры при ребалансе
- MITA — советник, не судья. Конечный выбор всегда за пользователем
- Каждое уведомление = имя + категория + цель + предложение + действие
- Пороги всегда из `budget_thresholds.py` (единый источник)
- Все финансовые расчёты через `Decimal`, `float` только при отдаче JSON

---

## ИТОГОВЫЙ СТАТУС

| # | Проблема | Приоритет | Статус |
|---|----------|-----------|--------|
| 1 | `/budget/monthly` игнорировал движок | 🔴 Критично | ✅ Было неверно описано — уже работало |
| 2 | Real-time rebalancing не вызывался | 🔴 Критично | ✅ **ИСПРАВЛЕНО** |
| 3 | Cron брал прошлый месяц | 🔴 Критично | ✅ Было неверно описано — уже работало |
| 4 | Savings не защищены | 🔴 Критично | ✅ Было неверно описано — уже работало |
| 5 | Behavioral allocator врал | 🟡 Важно | ⚠️ Частично — нужна проверка % использования |
| 6 | Порог $10 для всех | 🟡 Важно | ✅ Было неверно описано — уже динамический |
| 7 | CLUSTERED без seed | 🟡 Важно | ✅ Было неверно описано — уже детерминирован |
| 8 | Два несовместимых redistributor | 🟡 Важно | ❌ **НУЖНО ИСПРАВИТЬ** |
| 9 | Цели не в DailyPlan | 🟡 Важно | ✅ **ИСПРАВЛЕНО** |
| 10 | Безличные уведомления | 🟢 Улучшение | ❌ **НУЖНО СДЕЛАТЬ** |
| 11 | Нет 3-day reminder | 🟢 Улучшение | ❌ **НУЖНО СДЕЛАТЬ** |
| 12 | Разные пороги в разных сервисах | 🟢 Улучшение | ❌ **НУЖНО ИСПРАВИТЬ** |
| 13 | Audit log эвристика | 🟡 Важно | ✅ **ИСПРАВЛЕНО** |
| 14 | Потеря savings surplus | 🟢 Улучшение | ✅ Было неверно описано — уже работало |
| 15 | Нет позитивных wins | 🟢 Улучшение | ⚠️ Частично — нужна проверка delivery |

**Тесты:** 287 passing, 7 failing (`test_category_mapping_fix.py`, `test_income_location_budget_allocation.py` — не связаны с бюджетными проблемами).

---

## ПОРЯДОК ОСТАВШЕЙСЯ РАБОТЫ

1. **Проблема 8** — Убрать `app/engine/budget_redistributor.py`, все вызовы направить на `app/services/budget_redistributor.py` + `realtime_rebalancer.py`
2. **Проблема 12** — Унифицировать пороги: вынести WARNING/DANGER/CAUTION в `budget_thresholds.py`, убрать дублирование
3. **Проблема 5** — Добавить метрику: % запросов с реальным user_context vs fallback
4. **Проблема 15** — Проверить delivery push для wins streak
5. **Проблема 10** — Goal-aware текст в уведомлениях (имя + цель + сдвиг в днях)
6. **Проблема 11** — 3-day reminder cron при игнорировании алерта

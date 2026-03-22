# BUDGET PROBLEMS — ПОЛНЫЙ АУДИТ И СТАТУС ИСПРАВЛЕНИЙ
**Создан:** 2026-03-13
**Обновлён:** 2026-03-23
**Источник:** Прямой аудит кода — 13 файлов проверено построчно

---

## ЛЕГЕНДА СТАТУСОВ
- ✅ **ИСПРАВЛЕНО** — подтверждено кодом
- ⚠️ **ЧАСТИЧНО** — исправлено не полностью, нужна доработка
- ❌ **НЕ ИСПРАВЛЕНО** — проблема реальная, код не менялся
- 🆕 **НОВЫЙ БАГ** — обнаружен при аудите, в оригинальном списке отсутствовал

---

## ПРОБЛЕМЫ И СТАТУСЫ

### ПРОБЛЕМА 1 — Главный API эндпоинт игнорирует движок
**Файл:** `app/api/budget/routes.py`
**Статус: ✅ ИСПРАВЛЕНО**

`POST /budget/monthly` корректно вызывает движок:
- Если `user_answers.monthly_income` → `generate_budget_from_answers(user_answers)`
- Иначе → `IncomeClassificationService.classify_income()` → `get_budget_weights(tier)` → tier-специфичные веса
- Захардкоженные проценты — только в `except`-fallback при краше движка (корректная архитектура)

---

### ПРОБЛЕМА 2 — Real-time rebalancing не был реализован
**Файл:** `app/services/core/engine/expense_tracker.py`, `app/services/expense_tracker.py`
**Статус: ✅ ИСПРАВЛЕНО**

**Что исправлено:**
- `realtime_rebalancer.py` — полная реализация: `Decimal` везде, 50% cap, кредитование перерасходованного дня, запись в audit log
- `app/services/core/engine/expense_tracker.py` — добавлен `check_and_rebalance()` + второй `update_day_status()` в `record_expense()` ✅
- `app/services/expense_tracker.py` (legacy, используется OCR-путём через `receipt_orchestrator.py`) — добавлены `update_day_status()` и `check_and_rebalance()` с обработкой ошибок ✅

Оба файла теперь следуют одному pipeline: запись транзакции → `update_day_status()` → `check_and_rebalance()` → `update_day_status()` повторно при rebalance.

---

### ПРОБЛЕМА 3 — Cron перераспределял прошлый месяц
**Файл:** `app/services/core/engine/cron_task_budget_redistribution.py`
**Статус: ✅ ИСПРАВЛЕНО**

`year = now.year`, `month = now.month` — текущий месяц. `prev_month` используется только в блоке `if now.day == 1` для rollover savings — это правильная логика.

---

### ПРОБЛЕМА 4 — Savings не были защищены от перераспределения
**Файл:** `app/services/budget_redistributor.py`
**Статус: ✅ ИСПРАВЛЕНО**

`not is_sacred(d_cat)` фильтрует доноров. `realtime_rebalancer.py` также пропускает SACRED через `is_sacred(cat)`.

---

### ПРОБЛЕМА 5 — Behavioral allocator возвращал `user_context_applied: True` — ложь
**Файл:** `app/services/core/behavior/behavioral_budget_allocator.py`
**Статус: ✅ ИСПРАВЛЕНО**

`user_context_applied` честный: `True` только если `DynamicThresholdService` вернул непустой словарь, `False` при fallback.
Добавлено: `logger.info("behavioral_allocator: context_applied=%s", user_context_applied)` — % реальной персонализации виден в логах.

---

### ПРОБЛЕМА 6 — Порог статуса дня одинаков для всех доходов
**Файл:** `app/services/core/engine/calendar_updater.py`
**Статус: ✅ ИСПРАВЛЕНО**

```python
yellow_threshold = max(Decimal("2.00"), min(Decimal("25.00"), total_planned * Decimal("0.05")))
```
5% от planned, от $2 до $25. `$10 flat` больше не используется.

---

### ПРОБЛЕМА 7 — CLUSTERED распределение случайное (без seed)
**Файл:** `app/services/core/engine/calendar_engine.py`
**Статус: ✅ ИСПРАВЛЕНО**

```python
seed_str = f"{year_val}{month_val}{category}"
seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2 ** 31)
rng = random.Random(seed_int)
```
Детерминированный RNG. Одинаковые входные данные → одинаковое распределение.

---

### ПРОБЛЕМА 8 — Два механизма перераспределения несовместимы
**Файл A:** `app/engine/budget_redistributor.py`
**Файл B:** `app/services/budget_redistributor.py`
**Статус: ✅ ИСПРАВЛЕНО — намеренная архитектура, не конфликт**

`app/engine/budget_redistributor.py` имеет явный docstring:
```
In-memory budget redistributor — DISPLAY ONLY.
Used by the calendar API to show a visual representation...
does NOT write to the database.
For DB-backed real-time rebalancing, use:
  - app.services.core.engine.realtime_rebalancer.check_and_rebalance()
  - app.services.budget_redistributor.redistribute_budget_for_user()
```
Два файла — два разных назначения: UI preview (in-memory) и реальные изменения в БД. Конфликта нет.

---

### ПРОБЛЕМА 9 — Цели изолированы от бюджета
**Файл:** `app/services/core/engine/goal_budget_sync.py`
**Статус: ✅ ИСПРАВЛЕНО**

Полная async реализация: SACRED строки `goal_savings` в `DailyPlan` при создании цели. Идемпотентно. При pause/cancel/complete — future rows удаляются. Реблансёр никогда не трогает `goal_savings`.

---

### ПРОБЛЕМА 10 — Уведомления не знают о целях пользователя
**Файл:** `app/services/budget_alert_service.py`, `app/services/spending_prevention_service.py`
**Статус: ✅ ИСПРАВЛЕНО**

Оба сервиса теперь имеют goal context:
- `budget_alert_service.py` — `_get_user_goal_context()` уже был ✅
- `spending_prevention_service.py` — добавлен `_get_user_goal_context()` (тот же паттерн: активная цель, `delay_days = overspend / (monthly_contribution / 30)`), вызов в `check_affordability()`, результат передаётся в `_generate_impact_message()`, все уровни предупреждений включают goal suffix ✅

---

### ПРОБЛЕМА 11 — Нет напоминаний через 3 дня
**Статус: ✅ ИСПРАВЛЕНО**

`app/api/budget/routes.py` содержит `POST /alert/ignored` → `record_ignored_alert()` ✅

`cron_task_followup_reminder.run_followup_reminders()` проверен и дополнен — теперь реально отправляет push через `notifier.send_custom_notification()` с `notification_type="reminder"` при `ignored_at + 3 days <= today` ✅

Ограничение: `_ignored_alerts` хранится in-memory (сбрасывается при рестарте). Задокументировано как known limitation — миграция на DB-таблицу в следующей итерации.

---

### ПРОБЛЕМА 12 — Несоответствие порогов между сервисами
**Статус: ✅ ИСПРАВЛЕНО**

Оба сервиса импортируют из `app/core/budget_thresholds.py`:
```python
# budget_alert_service.py
from app.core.budget_thresholds import THRESHOLD_WARNING, THRESHOLD_DANGER, THRESHOLD_EXCEEDED

# spending_prevention_service.py
from app.core.budget_thresholds import THRESHOLD_SAFE, THRESHOLD_WARNING, THRESHOLD_DANGER, THRESHOLD_EXCEEDED
```
Единый источник правды: SAFE=0.70, WARNING=0.80, DANGER=0.90, EXCEEDED=1.00.

---

### ПРОБЛЕМА 13 — История перераспределений — эвристика, не лог
**Статус: ✅ ИСПРАВЛЕНО**

`GET /budget/redistribution_history` — реальный SQL к таблице `redistribution_events`. `record_redistribution_event()` вызывается в обоих redistributor-ах с reason, amount, from_category, to_category.

---

### ПРОБЛЕМА 14 — Потеря излишков savings между месяцами
**Статус: ✅ ИСПРАВЛЕНО**

`cron_task_budget_redistribution.py` вызывает `rollover_month_savings()` на первый день каждого месяца.

---

### ПРОБЛЕМА 15 — Нет положительных уведомлений (wins)
**Файл:** `app/services/core/engine/velocity_alert_engine.py`, `app/services/velocity_alert_service.py`
**Статус: ✅ ИСПРАВЛЕНО — полностью работает**

`velocity_alert_engine._detect_wins()` — считает consecutive green days (7/14/30 streak).
`velocity_alert_service._maybe_send_win_notification()` — дедупликация через таблицу Notification (cooldown 7 дней), вызывает `notifier.notify_spending_win()`.
Wins отправляются через ежедневный cron (full scan) — правильная архитектура.

---

## 🆕 НОВЫЙ БАГ — обнаружен при аудите

### `record_expense()` не вызывает rebalancer
**Файл:** `app/services/core/engine/expense_tracker.py`
**Приоритет: 🔴 ВЫСОКИЙ**

**Статус: ✅ ИСПРАВЛЕНО**

Найдено два файла с `record_expense()`:
1. `app/services/core/engine/expense_tracker.py` — добавлены `check_and_rebalance()` + повторный `update_day_status()` ✅
2. `app/services/expense_tracker.py` (legacy, используется через OCR-путь `async_tasks → receipt_orchestrator`) — добавлены `update_day_status()`, `check_and_rebalance()`, импорты и логирование ✅

Оба файла теперь гарантируют полный pipeline после каждой транзакции.

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
| 1 | `/budget/monthly` игнорировал движок | 🔴 Критично | ✅ Исправлено |
| 2 | Real-time rebalancing не вызывался | 🔴 Критично | ✅ Исправлено (оба expense_tracker) |
| 3 | Cron брал прошлый месяц | 🔴 Критично | ✅ Исправлено |
| 4 | Savings не защищены | 🔴 Критично | ✅ Исправлено |
| 5 | Behavioral allocator врал | 🟡 Важно | ✅ Исправлено + логирование добавлено |
| 6 | Порог $10 для всех | 🟡 Важно | ✅ Исправлено |
| 7 | CLUSTERED без seed | 🟡 Важно | ✅ Исправлено |
| 8 | Два redistributor конфликтуют | 🟡 Важно | ✅ Намеренная архитектура, не баг |
| 9 | Цели не в DailyPlan | 🟡 Важно | ✅ Исправлено |
| 10 | Безличные уведомления | 🟢 Улучшение | ✅ Исправлено (оба сервиса имеют goal context) |
| 11 | Нет 3-day reminder | 🟢 Улучшение | ✅ Исправлено (push отправляется реально) |
| 12 | Разные пороги в сервисах | 🟢 Улучшение | ✅ Единый budget_thresholds.py |
| 13 | Audit log эвристика | 🟡 Важно | ✅ Исправлено |
| 14 | Потеря savings surplus | 🟢 Улучшение | ✅ Исправлено |
| 15 | Нет позитивных wins | 🟢 Улучшение | ✅ Полностью работает |
| 🆕 | `record_expense()` без rebalancer | 🔴 Критично | ✅ Исправлено (оба expense_tracker) |

---

## ПОРЯДОК ОСТАВШЕЙСЯ РАБОТЫ

✅ Все задачи выполнены. Оставшиеся улучшения (known limitations):

- `_ignored_alerts` в `cron_task_followup_reminder.py` хранится in-memory — при рестарте сбрасывается. Рекомендуется мигрировать на DB-таблицу в следующей итерации.

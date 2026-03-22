# BUDGET PROBLEMS — ПОЛНЫЙ АУДИТ И СТАТУС ИСПРАВЛЕНИЙ
**Создан:** 2026-03-13
**Обновлён:** 2026-03-22
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
**Файл:** `app/services/core/engine/realtime_rebalancer.py`, `app/services/core/engine/expense_tracker.py`
**Статус: ⚠️ ЧАСТИЧНО — основной путь работает, legacy-функция пропускает rebalancer**

**Что исправлено:**
- `realtime_rebalancer.py` — полная реализация: `Decimal` везде, 50% cap, кредитование перерасходованного дня, запись в audit log
- `expense_tracker.apply_transaction_to_plan()` — вызывает `check_and_rebalance()` после каждой транзакции ✅

**Что остаётся проблемой:**
`expense_tracker.record_expense()` — НЕ вызывает `check_and_rebalance()`:
```python
# record_expense() — только update_day_status(), rebalancing пропускается ❌
db.commit()
update_day_status(db, user_id, day)
return {...}  # check_and_rebalance() отсутствует
```
Если любой API использует `record_expense()` — транзакция записывается, день краснеет, но будущие дни не пересчитываются.

**Что нужно сделать:** Проверить все вызовы `record_expense()` в транзакционном API. Добавить `check_and_rebalance()` или заменить на `apply_transaction_to_plan()`.

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
**Статус: ⚠️ ЧАСТИЧНО — boolean честный, метрика персонализации отсутствует**

`user_context_applied` теперь честный: `True` только если `DynamicThresholdService` вернул непустой словарь, `False` при fallback.

**Что нужно:** Добавить `logger.info("behavioral_allocator: context_applied=%s", user_context_applied)` и проверить в логах, какой % запросов реально персонализирован.

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
**Статус: ⚠️ ЧАСТИЧНО — budget_alert имеет goal context, spending_prevention — нет**

**Что реализовано:**
`budget_alert_service.py` содержит `_get_user_goal_context()`: берёт активную цель, считает `delay_days = overspend / (monthly_contribution / 30)`, добавляет `goal_context_message` в результат и передаёт в notifier.

**Что отсутствует:**
`spending_prevention_service.py` (проактивная проверка ДО транзакции) — только generic сообщения без имени пользователя и цели:
```python
return f"✅ Safe to spend. You'll have ${remaining:.2f} left in {category} today."
```

**Что нужно:** Добавить `_get_user_goal_context()` в `SpendingPreventionService`, включить goal impact в `impact_message`.

---

### ПРОБЛЕМА 11 — Нет напоминаний через 3 дня
**Статус: ⚠️ ЧАСТИЧНО — endpoint и запись игнора реализованы, сам cron не проверен**

`app/api/budget/routes.py` содержит `POST /alert/ignored`:
```python
from app.services.core.engine.cron_task_followup_reminder import record_ignored_alert
record_ignored_alert(user_id, category, overspend_amount, goal_title)
```

**Что не проверено:** `cron_task_followup_reminder.py` — реально ли cron отправляет push при `ignored_at + 3 days <= today` или только записывает событие.

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

В `expense_tracker.py` два пути записи расхода:

1. `apply_transaction_to_plan()` — полный pipeline: alerts + velocity + **`check_and_rebalance()`** ✅
2. `record_expense()` — только `update_day_status()`, **rebalancing отсутствует** ❌

Если любой API использует `record_expense()` — транзакция записывается, день краснеет, но будущие дни не пересчитываются. Core promise продукта нарушается молча.

**Что нужно:**
1. `grep -r "record_expense" app/` — найти все вызовы
2. Добавить `check_and_rebalance()` в `record_expense()` или заменить вызовы на `apply_transaction_to_plan()`

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
| 2 | Real-time rebalancing не вызывался | 🔴 Критично | ⚠️ apply_transaction ✅, record_expense ❌ |
| 3 | Cron брал прошлый месяц | 🔴 Критично | ✅ Исправлено |
| 4 | Savings не защищены | 🔴 Критично | ✅ Исправлено |
| 5 | Behavioral allocator врал | 🟡 Важно | ⚠️ Boolean честный, % персонализации неизвестен |
| 6 | Порог $10 для всех | 🟡 Важно | ✅ Исправлено |
| 7 | CLUSTERED без seed | 🟡 Важно | ✅ Исправлено |
| 8 | Два redistributor конфликтуют | 🟡 Важно | ✅ Намеренная архитектура, не баг |
| 9 | Цели не в DailyPlan | 🟡 Важно | ✅ Исправлено |
| 10 | Безличные уведомления | 🟢 Улучшение | ⚠️ budget_alert ✅, spending_prevention ❌ |
| 11 | Нет 3-day reminder | 🟢 Улучшение | ⚠️ Endpoint есть, cron не проверен |
| 12 | Разные пороги в сервисах | 🟢 Улучшение | ✅ Единый budget_thresholds.py |
| 13 | Audit log эвристика | 🟡 Важно | ✅ Исправлено |
| 14 | Потеря savings surplus | 🟢 Улучшение | ✅ Исправлено |
| 15 | Нет позитивных wins | 🟢 Улучшение | ✅ Полностью работает |
| 🆕 | `record_expense()` без rebalancer | 🔴 Критично | ❌ Новый баг, требует исправления |

---

## ПОРЯДОК ОСТАВШЕЙСЯ РАБОТЫ

1. **🆕 NEW BUG** — Найти все вызовы `record_expense()`, добавить `check_and_rebalance()` или заменить на `apply_transaction_to_plan()`
2. **P2** — Убедиться что весь транзакционный API идёт через `apply_transaction_to_plan()`
3. **P10** — Добавить goal context в `spending_prevention_service.py`
4. **P11** — Прочитать `cron_task_followup_reminder.py`, убедиться что 3-day push реально отправляется
5. **P5** — Добавить логирование % реальной персонализации в `behavioral_budget_allocator.py`

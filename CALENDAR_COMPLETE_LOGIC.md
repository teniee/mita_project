# MITA Календарь - Полная документация логики

> Детальное описание всей логики календаря и бюджета для переноса в новый проект.

---

## Содержание

1. [Обзор системы](#1-обзор-системы)
2. [Поток данных](#2-поток-данных)
3. [Генерация бюджета из онбординга](#3-генерация-бюджета-из-онбординга)
4. [Классификация дохода](#4-классификация-дохода)
5. [Распределение по дням](#5-распределение-по-дням)
6. [Шаблоны поведения категорий](#6-шаблоны-поведения-категорий)
7. [Перераспределение бюджета](#7-перераспределение-бюджета)
8. [База данных](#8-база-данных)
9. [API Endpoints](#9-api-endpoints)
10. [Flutter клиент](#10-flutter-клиент)
11. [Полный пример расчёта](#11-полный-пример-расчёта)

---

# 1. Обзор системы

## 1.1 Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CALENDAR SYSTEM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────────┐     ┌────────────────┐  │
│  │  ONBOARDING  │────▶│  BUDGET PLANNER  │────▶│ CALENDAR ENGINE│  │
│  │   (answers)  │     │  (budget_logic)  │     │  (distribution)│  │
│  └──────────────┘     └──────────────────┘     └───────┬────────┘  │
│                                                        │           │
│  ┌──────────────┐     ┌──────────────────┐            │           │
│  │   INCOME     │────▶│  COUNTRY PROFILE │────────────┘           │
│  │   SERVICE    │     │   (thresholds)   │                        │
│  └──────────────┘     └──────────────────┘                        │
│                                                        │           │
│                       ┌──────────────────┐            ▼           │
│                       │   DAILY PLAN     │◀───────────────────────│
│                       │   (PostgreSQL)   │                        │
│                       └──────────────────┘                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 1.2 Ключевые файлы

| Файл | Назначение |
|------|------------|
| `app/services/core/engine/budget_logic.py` | Генерация бюджета из ответов онбординга |
| `app/services/core/engine/calendar_engine.py` | Распределение бюджета по дням |
| `app/services/core/engine/monthly_budget_engine.py` | Построение месячного плана |
| `app/services/core/income_classification_service.py` | Классификация дохода (5 уровней) |
| `app/engine/budget_redistributor.py` | Перераспределение при перерасходе |
| `app/services/calendar_service_real.py` | Сохранение/чтение из БД |
| `app/api/calendar/routes.py` | API endpoints |
| `app/db/models/daily_plan.py` | Модель базы данных |
| `app/config/country_profiles_loader.py` | Загрузка региональных профилей |

---

# 2. Поток данных

## 2.1 От онбординга к календарю

```
ОНБОРДИНГ ЗАВЕРШЁН
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ generate_budget_from_answers(answers)                             │
│   файл: app/services/core/engine/budget_logic.py                  │
│                                                                   │
│   ВХОДНЫЕ ДАННЫЕ (answers):                                       │
│   {                                                               │
│     "region": "US-CA",                                           │
│     "income": {"monthly_income": 5000, "additional_income": 500},│
│     "fixed_expenses": {"rent": 1500, "utilities": 150, ...},     │
│     "goals": {"savings_goal_amount_per_month": 500},             │
│     "spending_habits": {                                          │
│       "coffee_per_week": 3,                                       │
│       "dining_out_per_month": 8,                                  │
│       "entertainment_per_month": 4,                               │
│       "clothing_per_month": 2,                                    │
│       "transport_per_month": 200,                                 │
│       "travel_per_year": 6                                        │
│     }                                                             │
│   }                                                               │
│                                                                   │
│   ВЫХОДНЫЕ ДАННЫЕ (budget_plan):                                  │
│   {                                                               │
│     "user_class": "middle",                                       │
│     "total_income": 5500.00,                                      │
│     "fixed_expenses_total": 1850.00,                              │
│     "discretionary_total": 3150.00,                               │
│     "savings_goal": 500.00,                                       │
│     "discretionary_breakdown": {                                  │
│       "dining out": 111.25,                                       │
│       "entertainment events": 55.75,                              │
│       "clothing": 27.72,                                          │
│       "travel": 6.93,                                             │
│       "coffee": 166.95,                                           │
│       "transport": 2780.45                                        │
│     }                                                             │
│   }                                                               │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ build_monthly_budget(user_answers, year, month)                   │
│   файл: app/services/core/engine/monthly_budget_engine.py         │
│                                                                   │
│   1. Объединить fixed_expenses + discretionary_breakdown          │
│   2. Создать CalendarDay для каждого дня месяца                   │
│   3. Для каждой категории:                                        │
│      - Получить user_frequency из spending_habits                 │
│      - Вызвать distribute_budget_over_days()                      │
│   4. Вернуть List[CalendarDay]                                    │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ save_calendar_for_user(db, user_id, calendar)                     │
│   файл: app/services/calendar_service_real.py                     │
│                                                                   │
│   Для каждого дня и категории:                                    │
│     INSERT INTO daily_plan (user_id, date, category, planned_amount)│
└───────────────────────────────────────────────────────────────────┘
```

---

# 3. Генерация бюджета из онбординга

## 3.1 Алгоритм (5 шагов)

**Файл:** `app/services/core/engine/budget_logic.py`

```python
def generate_budget_from_answers(answers: dict) -> dict:
```

### Шаг 1: Получение данных

```python
region = answers.get("region", "US")  # Регион для классификации
income_data = answers.get("income", {})
monthly_income = income_data.get("monthly_income", 0)
additional_income = income_data.get("additional_income", 0)
income = monthly_income + additional_income  # Общий доход
```

### Шаг 2: Классификация дохода

```python
from app.services.core.income_classification_service import classify_income, get_tier_string

income_tier = classify_income(income, region)  # IncomeTier.MIDDLE
user_class = get_tier_string(income_tier)      # "middle"
```

### Шаг 3: Расчёт дискреционного бюджета

```python
fixed = answers.get("fixed_expenses", {})
fixed_total = sum(fixed.values())  # Сумма фиксированных расходов

if fixed_total > income:
    raise ValueError("Fixed expenses exceed income")

discretionary = income - fixed_total  # Гибкий бюджет

# Вычитаем цель сбережений
savings_goal = answers.get("goals", {}).get("savings_goal_amount_per_month", 0)
discretionary -= savings_goal

if discretionary < 0:
    savings_goal = max(0, savings_goal + discretionary)
    discretionary = 0
```

### Шаг 4: Вычисление весов из привычек

```python
freq = answers.get("spending_habits", {})

# Преобразование частот в месячные значения
freq_weights = {
    "dining out": freq.get("dining_out_per_month", 0),           # как есть
    "entertainment events": freq.get("entertainment_per_month", 0),
    "clothing": freq.get("clothing_per_month", 0),
    "travel": freq.get("travel_per_year", 0) / 12,               # год → месяц
    "coffee": freq.get("coffee_per_week", 0) * 4,                # неделя → месяц
    "transport": freq.get("transport_per_month", 0),
}

# Нормализация весов
total_freq = sum(freq_weights.values())
if total_freq == 0:
    weights = {k: 1 / len(freq_weights) for k in freq_weights}  # равномерно
else:
    weights = {k: v / total_freq for k, v in freq_weights.items()}
```

### Шаг 5: Распределение дискреционного бюджета

```python
return {
    "savings_goal": round(savings_goal, 2),
    "user_class": user_class,
    "total_income": round(income, 2),
    "fixed_expenses_total": round(fixed_total, 2),
    "discretionary_total": round(discretionary, 2),
    "discretionary_breakdown": {
        k: round(discretionary * w, 2) for k, w in weights.items()
    },
}
```

## 3.2 Пример расчёта

**Входные данные:**
```
monthly_income: $5,000
additional_income: $500
fixed_expenses: $1,850 (rent $1,500 + utilities $150 + insurance $200)
savings_goal: $500

spending_habits:
  coffee_per_week: 3
  dining_out_per_month: 8
  entertainment_per_month: 4
  clothing_per_month: 2
  transport_per_month: 12
  travel_per_year: 6
```

**Расчёт:**
```
total_income = 5000 + 500 = $5,500
fixed_total = $1,850
discretionary = 5500 - 1850 - 500 = $3,150

freq_weights:
  coffee: 3 * 4 = 12
  dining_out: 8
  entertainment: 4
  clothing: 2
  transport: 12
  travel: 6 / 12 = 0.5

total_freq = 12 + 8 + 4 + 2 + 12 + 0.5 = 38.5

weights:
  coffee: 12 / 38.5 = 0.312 (31.2%)
  dining_out: 8 / 38.5 = 0.208 (20.8%)
  entertainment: 4 / 38.5 = 0.104 (10.4%)
  clothing: 2 / 38.5 = 0.052 (5.2%)
  transport: 12 / 38.5 = 0.312 (31.2%)
  travel: 0.5 / 38.5 = 0.013 (1.3%)

discretionary_breakdown:
  coffee: 3150 * 0.312 = $982.80
  dining_out: 3150 * 0.208 = $655.20
  entertainment: 3150 * 0.104 = $327.60
  clothing: 3150 * 0.052 = $163.80
  transport: 3150 * 0.312 = $982.80
  travel: 3150 * 0.013 = $40.95
```

---

# 4. Классификация дохода

## 4.1 5-уровневая система

**Файл:** `app/services/core/income_classification_service.py`

```python
class IncomeTier(Enum):
    LOW = "low"
    LOWER_MIDDLE = "lower_middle"
    MIDDLE = "middle"
    UPPER_MIDDLE = "upper_middle"
    HIGH = "high"
```

## 4.2 Пороги (годовой доход)

| Класс | US (национальный) | US-CA (Калифорния) |
|-------|------------------|-------------------|
| LOW | < $36,000 | < $44,935 |
| LOWER_MIDDLE | $36,001 - $57,600 | $44,936 - $71,896 |
| MIDDLE | $57,601 - $86,400 | $71,897 - $107,844 |
| UPPER_MIDDLE | $86,401 - $144,000 | $107,845 - $179,740 |
| HIGH | > $144,000 | > $179,740 |

**Калифорния дороже на ~25%** - пороги выше.

## 4.3 Алгоритм классификации

```python
def classify_income(monthly_income: float, region: str = "US") -> IncomeTier:
    # Получить региональные пороги
    profile = get_profile(region)
    thresholds = profile.get("class_thresholds", {})

    # Конвертировать в годовой
    annual_income = monthly_income * 12

    if annual_income <= thresholds.get("low", 36000):
        return IncomeTier.LOW
    elif annual_income <= thresholds.get("lower_middle", 57600):
        return IncomeTier.LOWER_MIDDLE
    elif annual_income <= thresholds.get("middle", 86400):
        return IncomeTier.MIDDLE
    elif annual_income <= thresholds.get("upper_middle", 144000):
        return IncomeTier.UPPER_MIDDLE
    else:
        return IncomeTier.HIGH
```

## 4.4 Рекомендуемое распределение по классам

```python
# LOW income
{
    "housing": 0.40,      # 40% на жильё
    "food": 0.15,
    "transport": 0.15,
    "utilities": 0.10,
    "healthcare": 0.08,
    "savings": 0.05,      # 5% сбережений
    "entertainment": 0.04,
    "miscellaneous": 0.03
}

# MIDDLE income
{
    "housing": 0.30,      # 30% на жильё (меньше)
    "food": 0.12,
    "transport": 0.15,
    "utilities": 0.07,
    "healthcare": 0.06,
    "savings": 0.12,      # 12% сбережений (больше)
    "entertainment": 0.08,
    "miscellaneous": 0.10
}

# HIGH income
{
    "housing": 0.25,
    "food": 0.08,
    "transport": 0.10,
    "utilities": 0.04,
    "healthcare": 0.04,
    "savings": 0.12,
    "entertainment": 0.10,
    "investments": 0.20,  # 20% инвестиции
    "luxury": 0.07
}
```

## 4.5 Поведенческие паттерны по классам

```python
patterns = {
    IncomeTier.LOW: {
        "decision_time": "immediate",           # Решения сразу
        "planning_horizon": "weekly",           # Планируют на неделю
        "risk_tolerance": "very_low",
        "mental_accounting_buckets": 2,         # 2 бакета: essential/non-essential
        "savings_rate_target": 0.05,            # 5%
        "housing_ratio_target": 0.40            # До 40% на жильё
    },
    IncomeTier.MIDDLE: {
        "decision_time": "days_to_weeks",
        "planning_horizon": "quarterly",
        "risk_tolerance": "moderate",
        "mental_accounting_buckets": 6,
        "savings_rate_target": 0.12,
        "housing_ratio_target": 0.30
    },
    IncomeTier.HIGH: {
        "decision_time": "months_to_years",
        "planning_horizon": "multi_year",
        "risk_tolerance": "high",
        "mental_accounting_buckets": 10,
        "savings_rate_target": 0.25,
        "housing_ratio_target": 0.25
    }
}
```

---

# 5. Распределение по дням

## 5.1 Структура CalendarDay

**Файл:** `app/services/core/engine/calendar_engine.py`

```python
class CalendarDay:
    def __init__(self, date: datetime.date):
        self.date: datetime.date = date
        self.day_type: str = "weekend" if date.weekday() >= 5 else "weekday"
        self.planned_budget: Dict[str, float] = {}  # {"food": 50, "transport": 20}
        self.actual_spending: Dict[str, float] = {}
        self.recommendations: List[str] = []
        self.status: str = "green"  # green/yellow/red
        self.total: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day_type": self.day_type,
            "planned_budget": self.planned_budget,
            "actual_spending": self.actual_spending,
            "recommendations": self.recommendations,
            "status": self.status,
            "total": self.total,
        }
```

## 5.2 Основная функция распределения

**Файл:** `app/services/core/engine/monthly_budget_engine.py`

```python
def build_monthly_budget(user_answers: dict, year: int, month: int) -> List[Dict]:
    # 1. Получить региональный профиль
    region = user_answers.get("region", "US-CA")
    profile = COUNTRY_PROFILES.get(region, {})

    # 2. Извлечь данные
    income = Decimal(str(user_answers.get("monthly_income", 3000)))
    fixed = user_answers.get("fixed_expenses", {})
    savings_goal = user_answers.get("goals", {}).get("savings_goal_amount_per_month", 0)

    # 3. Расчёт дискреционного бюджета
    fixed_total = sum(Decimal(str(v)) for v in fixed.values())
    discretionary = income - fixed_total - Decimal(str(savings_goal))

    if discretionary < 0:
        raise ValueError("Fixed expenses + goal exceed income")

    # 4. Получить персонализированное распределение (из онбординга)
    discretionary_breakdown = user_answers.get("discretionary_breakdown")

    # 5. Объединить в полный месячный план
    full_month_plan = {}
    full_month_plan.update(fixed)              # Фиксированные расходы
    full_month_plan.update(discretionary_breakdown)  # Гибкие расходы

    # 6. Извлечь частоты трат пользователя
    spending_habits = user_answers.get("spending_habits", {})
    category_frequencies = {
        "coffee": spending_habits.get("coffee_per_week", 0) * 4,
        "transport": spending_habits.get("transport_per_month", 0),
        "dining out": spending_habits.get("dining_out_per_month", 0),
        "entertainment events": spending_habits.get("entertainment_per_month", 0),
        "clothing": spending_habits.get("clothing_per_month", 0),
        "travel": spending_habits.get("travel_per_year", 0) / 12,
    }

    # 7. Создать дни месяца
    num_days = calendar.monthrange(year, month)[1]
    days = [CalendarDay(datetime.date(year, month, day)) for day in range(1, num_days + 1)]

    # 8. Распределить каждую категорию
    for category, monthly_amount in full_month_plan.items():
        user_frequency = category_frequencies.get(category)
        distribute_budget_over_days(days, category, float(monthly_amount), user_frequency)

    # 9. Рассчитать total для каждого дня
    for day in days:
        day.total = round(sum(day.planned_budget.values()), 2)

    return [day.to_dict() for day in days]
```

---

# 6. Шаблоны поведения категорий

## 6.1 Три шаблона распределения

**Файл:** `app/services/core/engine/calendar_engine.py`

```python
CATEGORY_BEHAVIOR: Dict[str, str] = {
    # FIXED - один платёж в начале месяца
    "rent": "fixed",
    "mortgage": "fixed",
    "utilities": "fixed",
    "subscriptions software": "fixed",
    "media streaming": "fixed",
    "insurance medical": "fixed",
    "gym fitness": "fixed",
    "flights": "fixed",
    "hotels": "fixed",
    "courses online": "fixed",
    "school fees": "fixed",
    "debt repayment": "fixed",
    "investment contribution": "fixed",

    # SPREAD - равномерно по рабочим дням
    "groceries": "spread",
    "transport public": "spread",
    "local transport": "spread",
    "savings emergency": "spread",
    "savings goal based": "spread",

    # CLUSTERED - сконцентрировано на выходных
    "dining out": "clustered",
    "delivery": "clustered",
    "home repairs": "clustered",
    "transport gas": "clustered",
    "taxi ridehailing": "clustered",
    "car maintenance": "clustered",
    "clothing": "clustered",
    "tech gadgets": "clustered",
    "home goods": "clustered",
    "out of pocket medical": "clustered",
    "entertainment events": "clustered",
    "gaming": "clustered",
    "hobbies": "clustered",
    "books": "clustered",
}
```

## 6.2 Алгоритм distribute_budget_over_days

```python
def distribute_budget_over_days(
    days: List[CalendarDay],
    category: str,
    total: float,
    user_frequency: int = None  # Частота из онбординга
) -> None:
    behavior = CATEGORY_BEHAVIOR.get(category, "spread")
    num_days = len(days)
```

### Шаблон FIXED

```python
if behavior == "fixed":
    # Определить день платежа
    if category in ["rent", "mortgage", "school fees"]:
        index = 0  # 1-й день месяца
    else:
        index = min(4, num_days - 1)  # 5-й день или последний

    # Вся сумма в один день
    days[index].planned_budget[category] = round(total, 2)
```

**Пример:**
```
rent: $1,500 → День 1: $1,500
utilities: $150 → День 5: $150
```

### Шаблон SPREAD

```python
elif behavior == "spread":
    # Отфильтровать рабочие дни
    weekday_days = [d for d in days if d.day_type == "weekday"]

    if user_frequency and user_frequency > 0:
        # Использовать частоту пользователя
        num_spread_days = min(int(user_frequency), len(weekday_days))
        spread_days = weekday_days[:num_spread_days]
    else:
        # Fallback: все рабочие дни
        spread_days = weekday_days if weekday_days else days

    if len(spread_days) == 0:
        spread_days = days

    # Равномерно распределить
    per_day = round(total / len(spread_days), 2)
    for day in spread_days:
        day.planned_budget[category] = per_day
```

**Пример:**
```
coffee: $168/месяц, coffee_per_week: 3 → 12 дней
per_day = 168 / 12 = $14
Дни 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23: $14 каждый
```

### Шаблон CLUSTERED

```python
elif behavior == "clustered":
    # Определить количество дней
    if user_frequency and user_frequency > 0:
        num_cluster_days = min(int(user_frequency), num_days)
    else:
        num_cluster_days = 4  # По умолчанию

    # Предпочтение выходным
    candidate_days = [d for d in days if d.day_type == "weekend"]

    if len(candidate_days) < num_cluster_days:
        # Добавить рабочие дни если не хватает выходных
        remaining_needed = num_cluster_days - len(candidate_days)
        weekday_candidates = [d for d in days if d.day_type == "weekday"]
        if weekday_candidates:
            candidate_days += random.sample(
                weekday_candidates,
                min(remaining_needed, len(weekday_candidates))
            )

    # Случайно выбрать дни
    selected_days = random.sample(candidate_days, min(num_cluster_days, len(candidate_days)))

    # Распределить равномерно по выбранным дням
    chunk = round(total / len(selected_days), 2)
    for day in selected_days:
        day.planned_budget[category] = chunk
```

**Пример:**
```
entertainment: $200/месяц, entertainment_per_month: 4
→ Выбрать 4 выходных дня (субботы)
→ chunk = 200 / 4 = $50
→ Суббота 1: $50, Суббота 2: $50, Суббота 3: $50, Суббота 4: $50
```

## 6.3 Важные принципы

1. **user_frequency приоритетнее дефолтов** - если пользователь указал частоту, она используется
2. **Выходные приоритетнее для clustered** - развлечения и шопинг на выходных
3. **Рабочие дни для spread** - ежедневные траты в рабочие дни
4. **random.sample создаёт вариативность** - не одни и те же дни каждый месяц

---

# 7. Перераспределение бюджета

## 7.1 Назначение

Когда пользователь перерасходовал в один день, система может перенести "экономию" из других дней для компенсации.

**Файл:** `app/engine/budget_redistributor.py`

## 7.2 Входные данные

```python
calendar = {
    "1": {"total": 45, "limit": 30},  # Перерасход: потратил 45 при лимите 30
    "2": {"total": 10, "limit": 30},  # Экономия: потратил 10 при лимите 30
    "3": {"total": 30, "limit": 30},  # В норме
    ...
}
```

## 7.3 Алгоритм

```python
class BudgetRedistributor:
    def __init__(self, calendar: Dict[str, Dict]):
        # Конвертировать в Decimal для точности
        self.calendar = {
            day: {
                "total": Decimal(str(data["total"])),
                "limit": Decimal(str(data.get("limit", 0))),
            }
            for day, data in calendar.items()
        }

    def redistribute_budget(self) -> Tuple[Dict, List[Tuple]]:
        # 1. Найти дни с перерасходом (доноры денег НЕ нужны, нужно покрыть)
        over_days = [day for day in self.calendar if self._overage(day) > 0]

        # 2. Найти дни с экономией (доноры - откуда возьмём деньги)
        under_days = [day for day in self.calendar if self._shortfall(day) > 0]

        # 3. Отсортировать по размеру (большие первыми)
        over_days.sort(key=self._overage, reverse=True)
        under_days.sort(key=self._shortfall, reverse=True)

        transfers = []

        # 4. Жадный алгоритм переноса
        for src in over_days:  # src = день с перерасходом
            src_over = self._overage(src)
            if src_over <= 0:
                continue

            for dst in under_days:  # dst = день с экономией
                dst_need = self._shortfall(dst)
                if dst_need <= 0:
                    continue

                amount = min(src_over, dst_need)
                if amount == 0:
                    continue

                # Перенести
                self._apply_transfer(src, dst, amount)
                transfers.append((src, dst, amount))
                src_over -= amount

                if src_over == 0:
                    break

        return self.calendar, transfers

    def _overage(self, day: str) -> Decimal:
        """Насколько потрачено больше лимита"""
        return self.calendar[day]["total"] - self.calendar[day]["limit"]

    def _shortfall(self, day: str) -> Decimal:
        """Насколько потрачено меньше лимита (экономия)"""
        return self.calendar[day]["limit"] - self.calendar[day]["total"]

    def _apply_transfer(self, src: str, dst: str, amount: Decimal):
        """Перенос: уменьшить total у src, увеличить у dst"""
        self.calendar[src]["total"] -= amount
        self.calendar[dst]["total"] += amount
```

## 7.4 Пример

```
ДО:
День 1: total=45, limit=30 (перерасход 15)
День 2: total=10, limit=30 (экономия 20)
День 3: total=25, limit=30 (экономия 5)

АЛГОРИТМ:
- over_days = [1] (перерасход 15)
- under_days = [2, 3] (экономия 20, 5)

Перенос 1: День 1 → День 2, amount = min(15, 20) = 15
  День 1: total = 45 - 15 = 30 ✓
  День 2: total = 10 + 15 = 25

ПОСЛЕ:
День 1: total=30, limit=30 (норма)
День 2: total=25, limit=30 (экономия 5)
День 3: total=25, limit=30 (экономия 5)

Трансферы: [(1, 2, 15)]
```

---

# 8. База данных

## 8.1 Модель DailyPlan

**Файл:** `app/db/models/daily_plan.py`

```python
class DailyPlan(Base):
    __tablename__ = "daily_plan"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    category = Column(String(100), nullable=True, index=True)
    planned_amount = Column(Numeric(12, 2), default=Decimal("0.00"))
    spent_amount = Column(Numeric(12, 2), default=Decimal("0.00"))
    daily_budget = Column(Numeric(12, 2), nullable=True)
    status = Column(String(20), default="green")  # green/yellow/red

    plan_json = Column(JSONB, nullable=True)  # Дополнительные данные
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
```

## 8.2 Структура записей

Для каждого дня создаётся **несколько записей** - по одной на категорию:

```
user_id | date       | category      | planned_amount | spent_amount | status
--------|------------|---------------|----------------|--------------|-------
abc123  | 2025-02-01 | rent          | 1500.00        | 1500.00      | green
abc123  | 2025-02-01 | utilities     | 150.00         | 0.00         | green
abc123  | 2025-02-02 | coffee        | 14.00          | 12.50        | green
abc123  | 2025-02-02 | transport     | 8.00           | 8.00         | green
abc123  | 2025-02-03 | dining out    | 50.00          | 65.00        | red
...
```

## 8.3 Сохранение календаря

**Файл:** `app/services/calendar_service_real.py`

```python
def save_calendar_for_user(db: Session, user_id: UUID, calendar: List[Dict]):
    # Конвертировать List формат в Dict
    calendar_dict = {}
    for day_entry in calendar:
        date_str = day_entry.get("date")
        planned_budget = day_entry.get("planned_budget", {})
        if date_str and planned_budget:
            calendar_dict[date_str] = planned_budget

    # Сохранить каждую категорию каждого дня
    for day_str, categories in calendar_dict.items():
        day_date = date.fromisoformat(day_str)
        for category, amount in categories.items():
            db_plan = DailyPlan(
                id=uuid.uuid4(),
                user_id=user_id,
                date=day_date,
                category=category,
                planned_amount=Decimal(amount),
                spent_amount=Decimal("0.00"),
            )
            db.add(db_plan)

    db.commit()
```

## 8.4 Чтение календаря

```python
def fetch_calendar(db: Session, user_id: UUID, year: int, month: int) -> Dict:
    results = db.query(DailyPlan).filter(
        DailyPlan.user_id == user_id,
        DailyPlan.date >= date(year, month, 1),
        DailyPlan.date < date(year + (month // 12), ((month % 12) + 1), 1)
    ).all()

    calendar = {}
    for plan in results:
        key = plan.date.isoformat()
        if key not in calendar:
            calendar[key] = {}
        calendar[key][plan.category] = float(plan.planned_amount)

    return calendar
```

---

# 9. API Endpoints

## 9.1 Список endpoints

**Файл:** `app/api/calendar/routes.py`

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/calendar/generate` | Генерация нового календаря |
| GET | `/calendar/day/{year}/{month}/{day}` | Получить один день |
| PATCH | `/calendar/day/{year}/{month}/{day}` | Редактировать день |
| POST | `/calendar/day_state` | Получить состояние дня |
| POST | `/calendar/redistribute` | Перераспределить бюджет |
| POST | `/calendar/shell` | Быстрое превью календаря |
| GET | `/calendar/current-month` | Текущий месяц |
| GET | `/calendar/saved/{year}/{month}` | Сохранённый календарь |

## 9.2 GET /calendar/saved/{year}/{month}

**Основной endpoint для получения календаря мобильным приложением.**

```python
@router.get("/saved/{year}/{month}")
async def get_saved_calendar(year: int, month: int, user=Depends(get_current_user)):
    """Получить сохранённый календарь из БД"""

    rows = db.query(DailyPlan).filter(
        DailyPlan.user_id == user.id,
        extract('year', DailyPlan.date) == year,
        extract('month', DailyPlan.date) == month,
    ).order_by(DailyPlan.date).all()

    # Агрегировать по дням
    days_data = defaultdict(lambda: {
        'date': None,
        'day': 0,
        'total_budget': 0,
        'total_planned': 0,
        'total_spent': 0,
        'categories': {}
    })

    for row in rows:
        day_key = row.date.isoformat()
        day_data = days_data[day_key]

        if day_data['date'] is None:
            day_data['date'] = row.date.isoformat()
            day_data['day'] = row.date.day

        day_data['total_planned'] += (row.planned_amount or 0)
        day_data['total_spent'] += (row.spent_amount or 0)

        day_data['categories'][row.category] = {
            'planned': float(row.planned_amount or 0),
            'spent': float(row.spent_amount or 0),
            'status': row.status or 'pending'
        }

    # Конвертировать в список
    calendar_days = []
    for day_data in days_data.values():
        calendar_days.append({
            'date': day_data['date'],
            'day': day_data['day'],
            'planned_budget': day_data['categories'],
            'limit': float(day_data['total_budget']),
            'total': float(day_data['total_planned']),
            'spent': float(day_data['total_spent']),
            'status': 'active' if day_data['total_spent'] > 0 else 'pending'
        })

    calendar_days.sort(key=lambda x: x['date'])

    return {"data": {"calendar": calendar_days}}
```

**Формат ответа:**
```json
{
  "data": {
    "calendar": [
      {
        "date": "2025-02-01",
        "day": 1,
        "planned_budget": {
          "rent": {"planned": 1500, "spent": 1500, "status": "green"},
          "utilities": {"planned": 150, "spent": 0, "status": "pending"}
        },
        "limit": 1650,
        "total": 1650,
        "spent": 1500,
        "status": "active"
      },
      {
        "date": "2025-02-02",
        "day": 2,
        "planned_budget": {
          "coffee": {"planned": 14, "spent": 12.5, "status": "green"},
          "transport": {"planned": 8, "spent": 8, "status": "green"}
        },
        "limit": 22,
        "total": 22,
        "spent": 20.5,
        "status": "active"
      }
    ]
  }
}
```

## 9.3 POST /calendar/redistribute

```python
@router.post("/redistribute")
async def redistribute(payload: RedistributeInput):
    """
    Перераспределить бюджет между днями.

    Request:
    {
      "calendar": {
        "1": {"total": 45, "limit": 30},
        "2": {"total": 10, "limit": 30}
      },
      "strategy": "balance"
    }

    Response:
    {
      "data": {
        "updated_calendar": {
          "1": {"total": 30, "limit": 30},
          "2": {"total": 25, "limit": 30}
        }
      }
    }
    """
    updated_calendar = redistribute_calendar_budget(payload.calendar)
    return {"data": {"updated_calendar": updated_calendar}}
```

## 9.4 Schemas

**Файл:** `app/api/calendar/schemas.py`

```python
class GenerateCalendarRequest(BaseModel):
    calendar_id: str
    start_date: date
    num_days: int
    budget_plan: Dict[str, float]

class ShellConfig(BaseModel):
    savings_target: float
    income: float
    fixed: Dict[str, float]
    weights: Dict[str, float]
    year: int
    month: int

class RedistributeInput(BaseModel):
    calendar: dict
    strategy: str = "balance"
```

---

# 10. Flutter клиент

## 10.1 BudgetProvider

**Файл:** `mobile_app/lib/providers/budget_provider.dart`

```dart
class BudgetProvider extends ChangeNotifier {
  List<dynamic> _calendarData = [];

  List<dynamic> get calendarData => _calendarData;

  /// Загрузить данные календаря
  Future<void> loadCalendarData({int? year, int? month}) async {
    final now = DateTime.now();
    final targetYear = year ?? now.year;
    final targetMonth = month ?? now.month;

    try {
      // 1. Попробовать production budget engine
      final productionData = await _budgetService.getCalendarData();
      _calendarData = productionData;
    } catch (e) {
      try {
        // 2. Fallback: behavioral calendar
        final behavioralCalendar = await _apiService.getBehaviorCalendar(
          year: targetYear,
          month: targetMonth,
        );
        _calendarData = _convertBehavioralCalendarData(behavioralCalendar);
      } catch (e) {
        // 3. Fallback: standard API
        final data = await _apiService.getCalendar();
        _calendarData = data;
      }
    }
    notifyListeners();
  }
}
```

## 10.2 CalendarScreen

**Файл:** `mobile_app/lib/screens/calendar_screen.dart`

**Структура экрана:**
```
┌─────────────────────────────────────────┐
│  AppBar: "Calendar - February 2025"     │
│  [Settings] [Refresh]                   │
├─────────────────────────────────────────┤
│  Month Overview Card                    │
│  Total Budget: $5,500                   │
│  Spent: $2,150 | Remaining: $3,350      │
│  [====== 39% =======              ]     │
│  On Track: 15 | Warning: 3 | Over: 2    │
├─────────────────────────────────────────┤
│  Daily Spending Status (Legend)         │
│  🟢 On Track  🟡 Warning  🔴 Over       │
├─────────────────────────────────────────┤
│  Calendar Grid                          │
│   S   M   T   W   T   F   S             │
│  [ ] [🟢] [🟢] [🟢] [🟡] [🟢] [🟢]      │
│  [🟢] [🟢] [🟢] [🔴] [🟢] [🟢] [🟢]      │
│  [🟢] ...                               │
├─────────────────────────────────────────┤
│  FAB: [+ Add Expense]                   │
└─────────────────────────────────────────┘
```

## 10.3 Цвета статуса дня

```dart
Color _getSimpleDayColor(String status, bool isToday) {
  if (isToday) {
    switch (status.toLowerCase()) {
      case 'over':
        return Colors.red.shade100;
      case 'warning':
        return Colors.orange.shade100;
      default:
        return Colors.blue.shade100;
    }
  }

  switch (status.toLowerCase()) {
    case 'over':
      return Colors.red.shade50;
    case 'warning':
      return Colors.orange.shade50;
    default:
      return Colors.green.shade50;
  }
}
```

## 10.4 Определение статуса

```dart
// В бэкенде или фронтенде:
String getStatus(double spent, double limit) {
  if (limit == 0) return 'neutral';

  double ratio = spent / limit;

  if (ratio > 1.0) return 'over';      // Перерасход
  if (ratio >= 0.8) return 'warning';  // Предупреждение (80%+)
  if (ratio > 0) return 'good';        // В норме
  return 'neutral';                     // Нет трат
}
```

---

# 11. Полный пример расчёта

## Входные данные (из онбординга)

```json
{
  "region": "US-CA",
  "income": {
    "monthly_income": 6000,
    "additional_income": 0
  },
  "fixed_expenses": {
    "rent": 1800,
    "utilities": 200,
    "insurance": 150,
    "subscriptions": 50
  },
  "goals": {
    "savings_goal_amount_per_month": 600
  },
  "spending_habits": {
    "coffee_per_week": 4,
    "dining_out_per_month": 8,
    "entertainment_per_month": 4,
    "clothing_per_month": 2,
    "transport_per_month": 15,
    "travel_per_year": 3
  }
}
```

## Шаг 1: Классификация дохода

```
Годовой доход: $6,000 × 12 = $72,000
Регион: US-CA
Пороги CA: low=44935, lower_middle=71896, middle=107844

$72,000 > $71,896 → MIDDLE класс (Strategic Achiever)
```

## Шаг 2: Расчёт бюджета

```
Всего доход: $6,000
Фиксированные: $1,800 + $200 + $150 + $50 = $2,200
Сбережения: $600
Дискреционный: $6,000 - $2,200 - $600 = $3,200
```

## Шаг 3: Вычисление весов

```
freq_weights:
  coffee: 4 * 4 = 16
  dining_out: 8
  entertainment: 4
  clothing: 2
  transport: 15
  travel: 3 / 12 = 0.25

total_freq = 16 + 8 + 4 + 2 + 15 + 0.25 = 45.25

weights:
  coffee: 16 / 45.25 = 0.354 (35.4%)
  dining_out: 8 / 45.25 = 0.177 (17.7%)
  entertainment: 4 / 45.25 = 0.088 (8.8%)
  clothing: 2 / 45.25 = 0.044 (4.4%)
  transport: 15 / 45.25 = 0.332 (33.2%)
  travel: 0.25 / 45.25 = 0.006 (0.6%)
```

## Шаг 4: Распределение дискреционного

```
discretionary_breakdown:
  coffee: $3,200 × 0.354 = $1,132.80
  dining_out: $3,200 × 0.177 = $566.40
  entertainment: $3,200 × 0.088 = $281.60
  clothing: $3,200 × 0.044 = $140.80
  transport: $3,200 × 0.332 = $1,062.40
  travel: $3,200 × 0.006 = $19.20
```

## Шаг 5: Распределение по дням (Февраль 2025, 28 дней)

### Фиксированные (FIXED pattern):
```
День 1:
  rent: $1,800
  utilities: $200 (на 5-й день)
  insurance: $150
  subscriptions: $50

День 5:
  utilities: $200
```

### Coffee (SPREAD pattern, 16 дней):
```
$1,132.80 / 16 = $70.80 на день
Дни: 1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 14, 15, 17, 18, 21, 24
(первые 16 рабочих дней)
```

### Dining out (CLUSTERED pattern, 8 дней):
```
$566.40 / 8 = $70.80 на день
Дни: выходные + несколько будней
Сб 1, Вс 2, Сб 8, Вс 9, Сб 15, Вс 16, Сб 22, Вс 23
```

### Entertainment (CLUSTERED pattern, 4 дня):
```
$281.60 / 4 = $70.40 на день
Дни: 4 субботы
Сб 1, Сб 8, Сб 15, Сб 22
```

### Clothing (CLUSTERED pattern, 2 дня):
```
$140.80 / 2 = $70.40 на день
Дни: 2 выходных
Сб 8, Сб 22
```

### Transport (SPREAD pattern, 15 дней):
```
$1,062.40 / 15 = $70.83 на день
Дни: 15 рабочих дней
```

### Travel (CLUSTERED pattern, ~0.25 = 1 день):
```
$19.20 / 1 = $19.20
День: Сб 15 (один день)
```

## Итоговый календарь (упрощённо):

```
День 1 (Сб):  $1,800 (rent) + $150 (ins) + $50 (subs) + $70.80 (coffee) + $70.80 (dining) + $70.40 (ent) = $2,212
День 2 (Вс):  $70.80 (dining) = $70.80
День 3 (Пн):  $70.80 (coffee) + $70.83 (transport) = $141.63
День 4 (Вт):  $70.80 (coffee) + $70.83 (transport) = $141.63
День 5 (Ср):  $200 (utilities) + $70.80 (coffee) + $70.83 (transport) = $341.63
...
День 8 (Сб):  $70.80 (dining) + $70.40 (ent) + $70.40 (clothing) = $211.60
...
День 15 (Сб): $70.80 (dining) + $70.40 (ent) + $19.20 (travel) = $160.40
...
День 22 (Сб): $70.80 (dining) + $70.40 (ent) + $70.40 (clothing) = $211.60
...
```

---

# Ключевые выводы

## Что делает систему "умной":

1. **Персонализация через онбординг** - частота трат определяет распределение
2. **Региональная адаптация** - CA дороже TX, пороги разные
3. **5 классов дохода** - разные рекомендации для разных уровней
4. **3 шаблона распределения** - fixed/spread/clustered
5. **Приоритет выходных** - развлечения и шопинг на выходных
6. **Перераспределение** - компенсация перерасхода из экономии

## Принципы НЕ равномерного распределения:

1. **coffee_per_week: 4** → 16 дней в месяц, не 30
2. **dining_out_per_month: 8** → 8 дней на выходных
3. **rent** → 1 день (1-е число)
4. **Нет покупок одежды 2 дня подряд** - clustered с random выбором

## Данные необходимые для работы:

1. `monthly_income` - месячный доход
2. `region` - регион для классификации
3. `fixed_expenses` - фиксированные расходы
4. `savings_goal_amount_per_month` - цель сбережений
5. `spending_habits` - частоты трат по категориям

---

*Документ создан для переноса логики MITA Calendar в новый проект.*

"""app/services/calendar_service.py
Простейшая in‑memory / stub‑реализация календарного сервиса.

‼  Это *рабочие* функции, которых достаточно, чтобы backend поднялся
    и эндпоинты Swagger отдавали корректные ответы.

Постоянного хранения в БД здесь нет — данные создаются «на лету».
В production‑варианте вы замените эти функции реальным доступом к
таблице DailyPlan / Redis‑кэшу.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any

###############################################################################
#                        ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
###############################################################################


def _date_range(start: date, num_days: int) -> List[date]:
    """Генерирует список дат начиная со start (вкл.) длиной num_days."""
    return [start + timedelta(days=i) for i in range(num_days)]


def _iso(d: date) -> str:
    return d.isoformat()


###############################################################################
#                        ОСНОВНОЕ API  (используется в роутерах)
###############################################################################

# ------------------------------------------------------------------ generate_calendar


def generate_calendar(
    calendar_id: str,
    start_date: date,
    num_days: int,
    budget_plan: Dict[str, float | int],
) -> List[Dict[str, Any]]:
    """
    Строит календарь с плановым бюджетом на каждый день.

    • budget_plan — месячные суммы по категориям.
    • Лимит дня == сумма категорий / num_days  (равномерно).

    Возвращает список словарей вида:
        {
          "date": "2025-05-01",
          "planned_budget": {"groceries": 10.0, ...},
          "limit": 30.0,
          "total": 0.0,
        }
    """
    days = _date_range(start_date, num_days)
    per_day_budget = {
        cat: round(Decimal(str(total)) / Decimal(num_days), 2)
        for cat, total in budget_plan.items()
    }
    day_limit = round(sum(per_day_budget.values()), 2)

    return [
        {
            "calendar_id": calendar_id,
            "date": _iso(d),
            "planned_budget": per_day_budget,
            "limit": day_limit,
            "total": Decimal("0.0"),
        }
        for d in days
    ]


# ------------------------------------------------------------------ fetch_calendar


def fetch_calendar(user_id: str, year: int, month: int) -> Dict[int, Dict[str, Any]]:
    """
    Возвращает упрощённый «календарь месяца» для пользователя.
    Здесь это просто рыба‑данные (свободные дни).
    Ключ — день месяца, значение — словарь про день.
    """
    first_day = date(year, month, 1)
    num_days = (date(year + month // 12, month % 12 + 1, 1) - first_day).days
    return {
        day: {
            "date": _iso(first_day + timedelta(days=day - 1)),
            "total": Decimal("0.0"),
            "limit": Decimal("0.0"),
            "status": "free",
        }
        for day in range(1, num_days + 1)
    }


# ------------------------------------------------------------------ update_day


def update_day(calendar: Dict[int, Dict[str, Any]], day: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обновляет запись дня внутри переданного календаря.
    Возвращает обновлённый словарь дня.
    """
    if day not in calendar:
        raise KeyError("day not in calendar")

    calendar[day].update(updates)
    return calendar[day]


# ------------------------------------------------------------------ fetch_day_state


def fetch_day_state(user_id: str, year: int, month: int, day: int) -> Dict[str, Any]:
    """
    Заготовка для получения «состояния дня».
    Сейчас возвращает статичный набор задач.
    """
    return {
        "user_id": user_id,
        "date": f"{year}-{month:02d}-{day:02d}",
        "status": "planned",
        "tasks": ["Review budget", "Log expenses"],
    }


# ------------------------------------------------------------------ generate_shell_calendar


def generate_shell_calendar(user_id: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Используется на шаге онбординга: строит «скорлупу» календаря, чтобы
    фронтенд показал пользователю пример бюджета, *не* сохраняя его.

    payload ожидает ключи:
        start_date: str (ISO, 'YYYY-MM-DD')
        num_days:   int
        budget_plan: dict[cat, amount]
    """
    start_date = date.fromisoformat(payload["start_date"])
    num_days = int(payload["num_days"])
    budget_plan = payload["budget_plan"]

    # просто переиспользуем generate_calendar (calendar_id не нужен)
    return generate_calendar("__shell__", start_date, num_days, budget_plan)

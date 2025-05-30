from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, List, Tuple

# ‑‑‑ предпочитаем финансовую точность ‑‑‑
getcontext().prec = 28          # 28 — стандарт IEEE 754 decimal64
getcontext().rounding = ROUND_HALF_UP


class BudgetRedistributor:
    """
    Переносит «неистраченный остаток» дней‑доноров на дни‑получатели,
    чтобы погасить перерасход и сохранить общий monthly‑лимит.

    calendar =
        {
            "1": {"total": 45, "limit": 30},
            "2": {"total": 10, "limit": 30},
            ...
        }

    *   over‑day  →  total  > limit   (перерасход)
    *   under‑day →  total  < limit   (экономия)

    Алгоритм проходит по донорам (по убыванию размера перерасхода) и
    погашает самый «дорогой» долг самым «богатым» донором, пока
    или все долги не погашены, или у доноров не кончились деньги.
    """

    def __init__(self, calendar: Dict[str, Dict[str, float | int | Decimal]]):
        # храним календарь в Decimal для точной математики
        self.calendar: Dict[str, Dict[str, Decimal]] = {
            day: {
                "total": Decimal(str(data["total"])),
                "limit": Decimal(str(data.get("limit", 0))),
            }
            for day, data in calendar.items()
        }

    # ----------------- публичный метод -----------------
    def redistribute_budget(self) -> Tuple[Dict[str, Dict[str, Decimal]],
                                           List[Tuple[str, str, Decimal]]]:
        """Возвращает (обновлённый календарь, список трансферов)."""
        over_days = [
            day for day in self.calendar if self._overage(day) > 0
        ]
        under_days = [
            day for day in self.calendar if self._shortfall(day) > 0
        ]

        # сортируем: сначала самые большие проблемы/ресурсы
        over_days.sort(key=self._overage, reverse=True)
        under_days.sort(key=self._shortfall, reverse=True)

        transfers: List[Tuple[str, str, Decimal]] = []

        for src in over_days:
            src_over = self._overage(src)
            if src_over <= 0:
                continue

            for dst in under_days:
                dst_need = self._shortfall(dst)
                if dst_need <= 0:
                    continue

                amount = min(src_over, dst_need)
                if amount == 0:
                    continue

                self._apply_transfer(src, dst, amount)
                transfers.append((src, dst, amount))
                src_over -= amount

                if src_over == 0:  # донор «опустошён»
                    break

        return self.calendar, transfers

    # ----------------- вспомогательные -----------------
    def _overage(self, day: str) -> Decimal:
        data = self.calendar[day]
        return data["total"] - data["limit"]

    def _shortfall(self, day: str) -> Decimal:
        data = self.calendar[day]
        return data["limit"] - data["total"]

    def _apply_transfer(self, src: str, dst: str, amount: Decimal) -> None:
        self.calendar[src]["total"] -= amount
        self.calendar[dst]["total"] += amount


# ===  external API ===

def redistribute_budget(
    calendar_dict: Dict[str, Dict[str, float | int | Decimal]]
) -> Dict[str, Dict[str, Decimal]]:
    """
    Тонкая обёртка под использование в сервисах API.

    Возвращает обновлённый календарь (с уже перенесёнными суммами).
    Список трансферов при необходимости можно получить так:

        updated, transfers = BudgetRedistributor(calendar_dict).redistribute_budget()
    """
    updated_calendar, _ = BudgetRedistributor(calendar_dict).redistribute_budget()
    return updated_calendar

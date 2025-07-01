from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, List, Tuple

# --- prefer financial precision ---
getcontext().prec = 28          # 28 is IEEE 754 decimal64 standard
getcontext().rounding = ROUND_HALF_UP


class BudgetRedistributor:
    """
    Move leftover amounts from surplus days to deficit days
    to cover overspending while keeping the monthly limit.

    calendar =
        {
            "1": {"total": 45, "limit": 30},
            "2": {"total": 10, "limit": 30},
            ...
        }

    *   over-day  →  total  > limit   (overspent)
    *   under-day →  total  < limit   (surplus)

    The algorithm processes donors in descending order of overspend
    and uses the largest donor to cover the largest deficit until
    debts are paid or donors run out of funds.
    """

    def __init__(self, calendar: Dict[str, Dict[str, float | int | Decimal]]):
        # store the calendar using Decimal for precise math
        self.calendar: Dict[str, Dict[str, Decimal]] = {
            day: {
                "total": Decimal(str(data["total"])),
                "limit": Decimal(str(data.get("limit", 0))),
            }
            for day, data in calendar.items()
        }

    # ----------------- public method -----------------
    def redistribute_budget(self) -> Tuple[Dict[str, Dict[str, Decimal]],
                                           List[Tuple[str, str, Decimal]]]:
        """Return the updated calendar and the list of transfers."""
        over_days = [
            day for day in self.calendar if self._overage(day) > 0
        ]
        under_days = [
            day for day in self.calendar if self._shortfall(day) > 0
        ]

        # sort donors and receivers by largest amounts first
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

                if src_over == 0:  # donor depleted
                    break

        return self.calendar, transfers

    # ----------------- helper methods -----------------
    def _overage(self, day: str) -> Decimal:
        data = self.calendar[day]
        return data["total"] - data["limit"]

    def _shortfall(self, day: str) -> Decimal:
        data = self.calendar[day]
        return data["limit"] - data["total"]

    def _apply_transfer(self, src: str, dst: str, amount: Decimal) -> None:
        self.calendar[src]["total"] -= amount
        self.calendar[dst]["total"] += amount


# === external API ===

def redistribute_budget(
    calendar_dict: Dict[str, Dict[str, float | int | Decimal]]
) -> Dict[str, Dict[str, Decimal]]:
    """
    Thin wrapper for use in API services.

    Returns the updated calendar (with transfers already applied).
    To retrieve the transfer list, call::

        updated, transfers = BudgetRedistributor(calendar_dict).redistribute_budget()
    """
    updated_calendar, _ = BudgetRedistributor(calendar_dict).redistribute_budget()
    return updated_calendar

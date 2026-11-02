"""A bill's money stays on its own line, whenever the bill is paid (F-8).

Owner decision 2026-11-02 (docs/chatgpt-app/bill-due-dates.md): a fixed
obligation is planned in full on its due date, and paying it — on time,
early, late or in parts — is never overspending in itself.

The rule, for the month's bill lines only (``budget_forecast_engine
.commitment_expectations``: the recordable categories of the user's saved
payments that count in the month, and the rent / mortgage / utilities lines
— the same bills R3 holds out of the safe daily amount):

* the line's monthly plan is the bill's money; its dated rows say when it
  is due;
* what is recorded under the line is matched to those rows in date order
  (``settle``): a payment uses the line's money due on its own date, then
  money due earlier and still unpaid (a late payment, oldest first), then
  money due later (an early payment, nearest first);
* the matched money moves to the date the payment was recorded on
  (``retime_bill_lines``). Nothing crosses lines, so the month's totals, the
  reserve for bills and the safe daily amount do not change;
* only spending beyond the line's whole month is overspending, which the
  established rebalancer then covers from other lines as before; a bill line
  is never a donor (``realtime_rebalancer``, ``protected``).

Everyday lines keep the per-date rebalancing exactly as it was.

Each move is written into the rows' ``plan_json`` under ``BILL_TIMING_KEY``
(a signed delta). ``rebuild_month_plan`` backs it out before every replay,
like the real-time adjustment, and ``monthly_plan_service`` reads through it
to the reviewed (base) plan. It is not redistribution: no
``redistribution_events`` row, no "redistributed" note, no mobile banner.

Matching is by category and date, never by amount and never to a particular
saved payment: MITA's data cannot say which bill an expense paid (no link
between an expense and a saved payment). ``settle`` is also what the
calendar uses to say what is recorded against each bill date.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import (
    AbstractSet,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Sequence,
    Tuple,
)

ZERO = Decimal("0.00")
BILL_TIMING_KEY = "_mita_bill_timing_v1"


@dataclass
class Settlement:
    """``settle``'s answer, index-aligned with the dues it was given."""

    covered: List[Decimal]
    # per due: (date the paying expense was recorded on, amount), in order
    paid: List[List[Tuple[date, Decimal]]]
    # per recorded date: what no due of the line covered (beyond its month)
    beyond: Dict[date, Decimal] = field(default_factory=dict)


def settle(
    dues: Sequence[Tuple[date, Decimal]],
    payments: Iterable[Tuple[date, Decimal]],
) -> Settlement:
    """Match one line's recorded spending to its dues in date order.

    ``dues``: ``(due date, amount)``, several may share a date (two bills of
    one category on one day stay two). ``payments``: ``(recorded date,
    amount)``, summed per date here. Deterministic: dates ascending, and dues
    on one date in the order given.
    """
    remaining = [max(ZERO, Decimal(amount)) for _, amount in dues]
    covered = [ZERO for _ in dues]
    paid: List[List[Tuple[date, Decimal]]] = [[] for _ in dues]
    by_day: Dict[date, Decimal] = defaultdict(lambda: ZERO)
    for day, amount in payments:
        if Decimal(amount) > ZERO:
            by_day[day] += Decimal(amount)
    order = sorted(range(len(dues)), key=lambda i: (dues[i][0], i))
    beyond: Dict[date, Decimal] = {}
    for day in sorted(by_day):
        need = by_day[day]
        same = [i for i in order if dues[i][0] == day]
        earlier = [i for i in order if dues[i][0] < day]
        later = [i for i in order if dues[i][0] > day]
        for i in same + earlier + later:
            if need <= ZERO:
                break
            take = min(need, remaining[i])
            if take <= ZERO:
                continue
            remaining[i] -= take
            covered[i] += take
            paid[i].append((day, take))
            need -= take
        if need > ZERO:
            beyond[day] = need
    return Settlement(covered=covered, paid=paid, beyond=beyond)


def _record(entry, delta: Decimal) -> None:
    metadata = dict(entry.plan_json) if isinstance(entry.plan_json, dict) else {}
    current = Decimal(str(metadata.get(BILL_TIMING_KEY, "0")))
    total = current + delta
    if total == 0:
        metadata.pop(BILL_TIMING_KEY, None)
    else:
        metadata[BILL_TIMING_KEY] = format(total, "f")
    entry.plan_json = metadata or None


def consume_bill_timing(entry) -> Decimal:
    """Remove and return this row's recorded bill-timing delta."""
    metadata = dict(entry.plan_json) if isinstance(entry.plan_json, dict) else {}
    raw = metadata.pop(BILL_TIMING_KEY, "0")
    entry.plan_json = metadata or None
    return Decimal(str(raw))


def bill_timing_of(plan_json) -> Decimal:
    """The bill-timing delta a row carries (0 when none)."""
    if not isinstance(plan_json, dict):
        return ZERO
    return Decimal(str(plan_json.get(BILL_TIMING_KEY, "0")))


def retime_bill_lines(
    rows_by_key: MutableMapping[Tuple[date, str], object],
    spent: Mapping[Tuple[date, str], Decimal],
    bill_categories: AbstractSet[str],
) -> Dict[str, Decimal]:
    """Move each bill line's own money to the dates its payments were
    recorded on (``settle``). Mutates the rows in place; returns, per bill
    category, how much moved between dates (0 when every payment fell on its
    due date).

    ``rows_by_key`` must hold the month's rows with their base allocations
    restored and ``spent`` accrued, and a row for every ``spent`` key
    (``rebuild_month_plan`` guarantees both).
    """
    moved: Dict[str, Decimal] = {}
    for category in sorted(bill_categories):
        dues: List[Tuple[date, Decimal]] = []
        due_rows = []
        for (day, code), row in sorted(
            rows_by_key.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        ):
            if code != category or getattr(row, "goal_id", None) is not None:
                continue
            planned = Decimal(str(row.planned_amount or 0))
            if planned > ZERO:
                dues.append((day, planned))
                due_rows.append(row)
        payments = [
            (day, amount)
            for (day, code), amount in spent.items()
            if code == category and amount > ZERO
        ]
        if not dues or not payments:
            continue
        settlement = settle(dues, payments)
        total = ZERO
        for index, (due_day, _amount) in enumerate(dues):
            for paid_day, amount in settlement.paid[index]:
                if paid_day == due_day:
                    continue
                source = due_rows[index]
                target = rows_by_key[(paid_day, category)]
                source.planned_amount = Decimal(str(source.planned_amount)) - amount
                source.daily_budget = source.planned_amount
                _record(source, -amount)
                target.planned_amount = (
                    Decimal(str(target.planned_amount or 0)) + amount
                )
                target.daily_budget = target.planned_amount
                _record(target, amount)
                total += amount
        moved[category] = total
    return moved

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

Since 2026-11-03 (docs/chatgpt-app/behavioral-budget.md) an obligation is
settled only by the expenses the user linked to it
(``obligation_lines``): on an obligation's line only linked payments move
its money, each first to the due date it paid (``settle``'s ``target``),
and a purchase in the same category is ordinary spending. The same rule —
a line's own money follows its spending, other lines pay only beyond the
line's whole month — is what a flexible budget and planned purchases use
(``rebuild_month_plan``). Matching is never by amount.
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
    Optional,
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
    payments: Iterable[Tuple],
) -> Settlement:
    """Match one line's recorded spending to its dues in date order.

    ``dues``: ``(due date, amount)``, several may share a date (two bills of
    one category on one day stay two). ``payments``: ``(recorded date,
    amount)`` or ``(recorded date, amount, target due date)``. A payment with
    a target — an expense the user linked to that due date — uses the dues
    on its target date first (the caller passes at most what that due date
    asks for: paying more is spending beyond the bill, never another due
    date's payment). What it still needs, and every untargeted payment,
    follows the date order: the money due on the payment's own date, then
    money due earlier and unpaid (late, oldest first), then money due later
    (early, nearest first) — which finds a bill's money where a plan saved
    before due dates put it. Deterministic: recorded dates ascending,
    targeted before untargeted on one date, and dues on one date in the
    order given.
    """
    remaining = [max(ZERO, Decimal(amount)) for _, amount in dues]
    covered = [ZERO for _ in dues]
    paid: List[List[Tuple[date, Decimal]]] = [[] for _ in dues]
    by_key: Dict[Tuple[date, int, date], Decimal] = defaultdict(lambda: ZERO)
    for payment in payments:
        day, amount = payment[0], Decimal(payment[1])
        target = payment[2] if len(payment) > 2 else None
        if amount > ZERO:
            # untargeted payments sort after targeted ones on the same day
            key = (day, 1, day) if target is None else (day, 0, target)
            by_key[key] += amount
    order = sorted(range(len(dues)), key=lambda i: (dues[i][0], i))
    beyond: Dict[date, Decimal] = defaultdict(lambda: ZERO)

    def take(i: int, day: date, need: Decimal) -> Decimal:
        amount = min(need, remaining[i])
        if amount <= ZERO:
            return need
        remaining[i] -= amount
        covered[i] += amount
        if paid[i] and paid[i][-1][0] == day:
            paid[i][-1] = (day, paid[i][-1][1] + amount)
        else:
            paid[i].append((day, amount))
        return need - amount

    for day, kind, target in sorted(by_key):
        need = by_key[(day, kind, target)]
        if kind == 0:
            for i in order:
                if need <= ZERO:
                    break
                if dues[i][0] == target:
                    need = take(i, day, need)
        same = [i for i in order if dues[i][0] == day]
        earlier = [i for i in order if dues[i][0] < day]
        later = [i for i in order if dues[i][0] > day]
        for i in same + earlier + later:
            if need <= ZERO:
                break
            need = take(i, day, need)
        if need > ZERO:
            beyond[day] += need
    return Settlement(covered=covered, paid=paid, beyond=dict(beyond))


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
    linked: Optional[Mapping[str, Sequence[Tuple[date, Decimal, date]]]] = None,
    linked_only: AbstractSet[str] = frozenset(),
) -> Dict[str, Decimal]:
    """Move each self-settling line's own money to the dates its payments
    were recorded on (``settle``). Mutates the rows in place; returns, per
    line, how much moved between dates (0 when every payment fell on its due
    date).

    ``linked``: per line, ``(recorded date, amount, due date paid)`` of the
    expenses the user linked to an obligation. On a line in ``linked_only``
    (an identified obligation) ONLY those move its money; any other spending
    there is ordinary spending, judged date by date like everyday money.

    ``rows_by_key`` must hold the month's rows with their base allocations
    restored and ``spent`` accrued, and a row for every ``spent`` key
    (``rebuild_month_plan`` guarantees both).
    """
    linked = linked or {}
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
        if category in linked_only:
            payments = list(linked.get(category, ()))
        else:
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

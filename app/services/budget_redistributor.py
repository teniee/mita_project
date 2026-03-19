from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DailyPlan
from app.core.category_priority import is_sacred, donor_sort_key
from app.services.redistribution_audit_log import record_redistribution_event


def redistribute_budget_for_user(db: Session, user_id: UUID, year: int, month: int):
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1)

    # 1. Fetch all calendar entries for the user for the month
    entries = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user_id)
        .filter(DailyPlan.date >= start)
        .filter(DailyPlan.date < end)
        .all()
    )

    surplus_by_cat = defaultdict(float)
    deficit_by_cat = defaultdict(float)
    plan_map = defaultdict(list)

    for entry in entries:
        delta = float(entry.planned_amount - entry.spent_amount)
        plan_map[entry.category].append(entry)

        if delta > 0.01:
            surplus_by_cat[entry.category] += delta
        elif delta < -0.01:
            deficit_by_cat[entry.category] += abs(delta)

    # 2. Move surplus amounts into deficit categories
    redistribution_log = []
    for cat, deficit in deficit_by_cat.items():
        transferred_total = 0.0
        remaining_deficit = deficit

        # Sort donors: DISCRETIONARY (3) first, skip SACRED (0)
        sorted_donors = sorted(
            [
                (d_cat, d_avail)
                for d_cat, d_avail in surplus_by_cat.items()
                if d_cat != cat
                and d_avail > 0
                and not is_sacred(d_cat)
            ],
            key=lambda x: donor_sort_key(x[0]),
            reverse=True,
        )

        for donor_cat, _ in sorted_donors:
            available = surplus_by_cat[donor_cat]
            if available <= 0 or remaining_deficit <= 0:
                continue

            transfer = min(available, remaining_deficit)
            if transfer <= 0:
                continue

            # Deduct from donor_cat
            for donor_entry in sorted(plan_map[donor_cat], key=lambda e: e.date):
                d_surplus = float(donor_entry.planned_amount - donor_entry.spent_amount)
                to_take = min(d_surplus, transfer)
                if to_take > 0:
                    donor_entry.planned_amount -= to_take
                    transfer -= to_take
                    transferred_total += to_take
                    remaining_deficit -= to_take
                    surplus_by_cat[donor_cat] -= to_take
                    redistribution_log.append(
                        {
                            "from": donor_cat,
                            "to": cat,
                            "amount": round(to_take, 2),
                            "from_day": donor_entry.date.isoformat(),
                        }
                    )
                    record_redistribution_event(
                        db=db,
                        user_id=user_id,
                        from_category=donor_cat,
                        to_category=cat,
                        amount=Decimal(str(round(to_take, 2))),
                        reason="budget_redistribution",
                        from_day=donor_entry.date,
                    )
                if transfer <= 0:
                    break

        # Add to receiving category - distribute across deficit entries in date order
        remaining = transferred_total
        receiver_entries = sorted(plan_map[cat], key=lambda e: e.date)
        for receiver_entry in receiver_entries:
            entry_deficit = float(receiver_entry.spent_amount - receiver_entry.planned_amount)
            if entry_deficit > 0.01:
                to_add = min(entry_deficit, remaining)
                receiver_entry.planned_amount += to_add
                remaining -= to_add
            if remaining <= 0.01:
                break
        # Fallback: any remainder (e.g. category has no deficit entries yet) goes to earliest day
        if remaining > 0.01:
            receiver_entries[0].planned_amount += remaining

    db.commit()
    return {"status": "redistributed", "log": redistribution_log}

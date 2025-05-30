
from sqlalchemy.orm import Session
from app.db.models import DailyPlan
from collections import defaultdict
from datetime import date

def redistribute_budget_for_user(db: Session, user_id: int, year: int, month: int):
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1)

    # 1. Получаем все записи календаря пользователя за месяц
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

    # 2. Перераспределение из лишних в дефицитные
    redistribution_log = []
    for cat, deficit in deficit_by_cat.items():
        for donor_cat, available in surplus_by_cat.items():
            if donor_cat == cat or available <= 0:
                continue

            transfer = min(available, deficit)
            if transfer <= 0:
                continue

            # списываем из donor_cat
            for donor_entry in sorted(plan_map[donor_cat], key=lambda e: e.date):
                d_surplus = float(donor_entry.planned_amount - donor_entry.spent_amount)
                to_take = min(d_surplus, transfer)
                if to_take > 0:
                    donor_entry.planned_amount -= to_take
                    transfer -= to_take
                    surplus_by_cat[donor_cat] -= to_take
                    redistribution_log.append({
                        "from": donor_cat,
                        "to": cat,
                        "amount": round(to_take, 2),
                        "from_day": donor_entry.date.isoformat()
                    })
                if transfer <= 0:
                    break

            # добавляем к cat
            for receiver_entry in sorted(plan_map[cat], key=lambda e: e.date):
                receiver_entry.planned_amount += to_take
                break  # только один день

    db.commit()
    return {"status": "redistributed", "log": redistribution_log}

#!/usr/bin/env python3
"""
REAL TEST: Verify calendar distribution fix actually works
"""
import sys
sys.path.insert(0, '/Users/mikhail/StudioProjects/mita_project')

from app.services.core.engine.monthly_budget_engine import build_monthly_budget

# Sarah Martinez test case from the analysis docs
test_user = {
    "monthly_income": 5100,
    "region": "US-CA",
    "fixed_expenses": {
        "rent": 1200,
        "utilities": 150,
        "insurance": 100
    },
    "spending_habits": {
        "coffee_per_week": 5,  # 20 days per month
        "transport_per_month": 25,  # Daily commute
        "dining_out_per_month": 15,
        "entertainment_per_month": 4,
        "clothing_per_month": 4,
        "travel_per_year": 0
    },
    "goals": {
        "savings_goal_amount_per_month": 500
    },
    "discretionary_breakdown": {
        "coffee": 677.27,
        "transport": 677.27,
        "dining out": 508.18,
        "entertainment events": 135.45,
        "clothing": 135.45,
        "travel": 0
    }
}

print("=" * 80)
print("TESTING CALENDAR GENERATION FIX")
print("=" * 80)
print()

try:
    calendar = build_monthly_budget(test_user, 2025, 12)

    print(f"✅ Calendar generated: {len(calendar)} days")
    print()

    # Count zero-budget days
    zero_days = [day for day in calendar if day['total'] == 0]
    print(f"Zero-budget days: {len(zero_days)}/31 ({len(zero_days)/31*100:.1f}%)")

    if len(zero_days) > 0:
        print("❌ STILL HAS ZERO-BUDGET DAYS!")
        for day in zero_days:
            print(f"  - {day['date']}: ${day['total']}")
    else:
        print("✅ No zero-budget days!")

    print()

    # Check coffee distribution
    coffee_days = [day for day in calendar if 'coffee' in day['planned_budget']]
    print(f"Coffee allocated to: {len(coffee_days)} days")
    print("Expected: 20 days (5 days/week * 4 weeks)")

    if len(coffee_days) < 20:
        print(f"❌ COFFEE STILL UNDER-ALLOCATED! Missing {20 - len(coffee_days)} days")
    else:
        print("✅ Coffee properly allocated!")

    print()

    # Check transport distribution
    transport_days = [day for day in calendar if 'transport' in day['planned_budget']]
    print(f"Transport allocated to: {len(transport_days)} days")
    print("Expected: 25 days (daily commute)")

    if len(transport_days) < 22:  # Weekdays only
        print(f"❌ TRANSPORT STILL UNDER-ALLOCATED! Missing {22 - len(transport_days)} days")
    else:
        print("✅ Transport properly allocated!")

    print()

    # Show sample of calendar
    print("First 5 days:")
    for day in calendar[:5]:
        print(f"\n{day['date']} ({day['day_type']}): ${day['total']:.2f}")
        for category, amount in day['planned_budget'].items():
            if amount > 0:
                print(f"  - {category}: ${amount:.2f}")

    print()
    print("=" * 80)
    if len(zero_days) == 0 and len(coffee_days) >= 20:
        print("✅✅✅ FIX VERIFIED - CALENDAR WORKS CORRECTLY!")
    else:
        print("❌❌❌ FIX INCOMPLETE - ISSUES REMAIN!")
    print("=" * 80)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

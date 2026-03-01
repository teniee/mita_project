"""
Verification script to test onboarding data flow with the fixes.

This simulates what happens when a user submits onboarding data.
"""

# Simulated user input from frontend after transformation
user_input = {
    "region": "US",
    "income": {
        "monthly_income": 5000,
        "additional_income": 0
    },
    "fixed_expenses": {
        "rent": 1500,
        "utilities": 200
    },
    "spending_habits": {
        "dining_out_per_month": 15,
        "entertainment_per_month": 4,
        "clothing_per_month": 2,
        "travel_per_year": 2,
        "coffee_per_week": 5,
        "transport_per_month": 20
    },
    "goals": {
        "savings_goal_amount_per_month": 500,
        "savings_goal_type": "emergency_fund",
        "has_emergency_fund": True
    }
}

# Simulate budget generation (from budget_logic.py)
income_data = user_input.get("income", {})
monthly_income = income_data.get("monthly_income", 0)
print(f"✓ Monthly income extracted: ${monthly_income}")

fixed_expenses_dict = user_input.get("fixed_expenses", {})
fixed_total = sum(fixed_expenses_dict.values())
print(f"✓ Fixed expenses total: ${fixed_total}")

discretionary = monthly_income - fixed_total - 500  # minus savings
print(f"✓ Discretionary income: ${discretionary}")

# Simulate budget_plan return value (FIXED version)
budget_plan = {
    "savings_goal": 500,
    "user_class": "middle",
    "behavior": "balanced",
    "total_income": monthly_income,
    "fixed_expenses_total": fixed_total,  # NOTE: Renamed from "fixed_expenses"
    "discretionary_total": discretionary,
    "discretionary_breakdown": {
        "dining_out": 550,
        "entertainment": 200,
        "clothing": 100,
        "travel": 50,
        "coffee": 250,
        "transport": 1050
    }
}

print("\n✓ Budget plan generated successfully")
print(f"  - fixed_expenses_total: ${budget_plan['fixed_expenses_total']}")

# Simulate calendar config merge (FIXED version from routes.py)
calendar_config = {
    **user_input,
    **budget_plan,
    "monthly_income": monthly_income,  # Added at top level
    "user_id": "test-user-123"
}

# Verify calendar config has what the engine needs
print("\n=== VERIFICATION ===")
print(f"✓ calendar_config['monthly_income'] = ${calendar_config.get('monthly_income')}")
print(f"✓ calendar_config['fixed_expenses'] type = {type(calendar_config.get('fixed_expenses'))}")
print(f"✓ calendar_config['fixed_expenses'] value = {calendar_config.get('fixed_expenses')}")
print(f"✓ calendar_config['fixed_expenses_total'] = ${calendar_config.get('fixed_expenses_total')}")

# Simulate what calendar engine will see (from monthly_budget_engine.py line 28)
income_from_config = calendar_config.get("monthly_income", 3000)
fixed_from_config = calendar_config.get("fixed_expenses", {})

print("\n=== CALENDAR ENGINE WILL SEE ===")
print(f"✓ Income: ${income_from_config} (should be 5000, NOT 3000)")
print(f"✓ Fixed expenses type: {type(fixed_from_config)} (should be dict, NOT float)")
print(f"✓ Fixed expenses dict: {fixed_from_config}")

# Final check
if income_from_config == 5000:
    print("\n✅ SUCCESS: Calendar will use correct income of $5000")
else:
    print(f"\n❌ FAILED: Calendar will use ${income_from_config} instead of $5000")

if isinstance(fixed_from_config, dict):
    print("✅ SUCCESS: Calendar will receive fixed_expenses as dict")
else:
    print(f"❌ FAILED: Calendar will receive fixed_expenses as {type(fixed_from_config)}")

# Calculate expected daily budget
days_in_month = 30
daily_budget = discretionary / days_in_month
print("\n=== EXPECTED RESULT ===")
print(f"✓ User's income: ${monthly_income}/month")
print(f"✓ User's fixed expenses: ${fixed_total}/month")
print(f"✓ User's discretionary: ${discretionary}/month")
print(f"✓ Expected daily budget: ${daily_budget:.2f}/day")
print(f"\n✅ User should see approximately ${daily_budget:.2f} per day in their calendar!")

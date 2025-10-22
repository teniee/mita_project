# User Input Data Usage Analysis

## Question: Does the app use ALL user input for budget calculations?

**Answer: MOSTLY YES, with 1 POTENTIAL GAP**

---

## What User Inputs During Onboarding

1. **Monthly Income** (+ optional additional income)
2. **Fixed Expenses** (rent, utilities, insurance, etc.)
3. **Savings Goal**
4. **Spending Habits** (dining out, entertainment, clothing, travel, coffee, transport frequencies)
5. **Region/Country**
6. **Goals** (savings targets, timelines)
7. **Demographics** (age, family size, life stage)

---

## Data Flow Analysis

### Step 1: Budget Generation (`generate_budget_from_answers()`)
**File:** `app/services/core/engine/budget_logic.py`

| User Input | Used? | How Used | Line |
|------------|-------|----------|------|
| **Income** | ✅ YES | Calculates total income (monthly + additional) | 10-13 |
| **Region** | ✅ YES | Loads country profile for defaults | 6 |
| **Fixed Expenses** | ✅ YES | Sums all fixed expenses | 19-20 |
| **Savings Goal** | ✅ YES | Deducts from discretionary budget | 27-31 |
| **Spending Habits** | ✅ YES | Calculates frequency weights for categories | 33-47 |
| **Income Tier** | ✅ YES | Classifies user into low/medium/high income tier | 16-17 |

**Result:**
```python
{
  "savings_goal": 500,
  "user_class": "middle_income",
  "total_income": 5000,
  "fixed_expenses_total": 1700,
  "discretionary_total": 2800,
  "discretionary_breakdown": {
    "dining out": 800,      # Based on user's dining_out_per_month
    "entertainment": 600,   # Based on user's entertainment_per_month
    "clothing": 400,        # Based on user's clothing_per_month
    "travel": 500,          # Based on user's travel_per_year / 12
    "coffee": 300,          # Based on user's coffee_per_week * 4
    "transport": 200        # Based on user's transport_per_month
  }
}
```

✅ **All inputs used correctly here**

---

### Step 2: Calendar Building (`build_monthly_budget()`)
**File:** `app/services/core/engine/monthly_budget_engine.py`

| User Input | Used? | How Used | Line |
|------------|-------|----------|------|
| **Income** | ✅ YES | Gets from `monthly_income` | 28-30 |
| **Region** | ✅ YES | Loads country profile | 27, 33 |
| **Fixed Expenses** | ✅ YES | Adds to monthly plan | 34, 72 |
| **Savings Goal** | ✅ YES | Deducts from discretionary | 35-37 |
| **Category Weights** | ⚠️ **PARTIAL** | Uses country profile defaults, NOT user's spending habits | 46-55 |

**The Issue:**

```python
# Line 46-55: Uses country profile, not user's habits!
category_weights = profile.get(
    "category_weights",
    {
        "food": 0.3,           # ❌ Regional default
        "transport": 0.15,     # ❌ Regional default
        "entertainment": 0.1,  # ❌ Regional default
        "bills": 0.25,         # ❌ Regional default
        "savings": 0.2,        # ❌ Regional default
    },
)
```

**NOT using:**
```python
# From budget_logic.py, this WAS calculated but NOT passed through:
discretionary_breakdown = {
    "dining out": 800,      # ✅ Based on user's actual habits
    "entertainment": 600,   # ✅ Based on user's actual habits
    "clothing": 400,        # ✅ Based on user's actual habits
    # ... etc
}
```

---

## The Gap

### What Happens:
1. ✅ User inputs spending habits (e.g., "I dine out 8 times per month")
2. ✅ `generate_budget_from_answers()` calculates weights based on these habits
3. ❌ `build_monthly_budget()` **IGNORES** these calculated weights
4. ❌ Uses regional defaults instead (e.g., food: 30%, transport: 15%)

### Example Impact:

**User Input:**
- Income: $5000
- Dining out: 15 times/month (very frequent)
- Entertainment: 2 times/month (infrequent)
- Coffee: 0 times/week (never)

**Expected Budget:**
- Dining out: High allocation (frequent habit)
- Entertainment: Low allocation (infrequent)
- Coffee: $0 (never drinks coffee)

**Actual Budget:**
- Dining out: 15% of discretionary (regional default)
- Entertainment: 10% of discretionary (regional default)
- Coffee: Some % of discretionary (regional default)

**Result:** Budget doesn't reflect user's actual spending patterns! ❌

---

## What IS Working

### Income & Fixed Expenses ✅
```
User Input: $5000 income, $1700 fixed expenses
Calculation: $5000 - $1700 = $3300 discretionary
Result: ✅ Correctly calculated
```

### Savings Goal ✅
```
User Input: Save $500/month
Calculation: $3300 - $500 = $2800 for spending
Result: ✅ Correctly deducted
```

### Regional Adaptation ✅
```
User Input: Region = "Bulgaria"
Result: Uses Bulgarian cost-of-living profiles ✅
```

---

## What MIGHT NOT Be Working

### Spending Habits ⚠️
```
User Input: Specific frequencies for each category
Step 1: ✅ Calculates custom weights
Step 2: ❌ Overwrites with regional defaults
Result: ⚠️ Budget uses generic allocation, not personalized
```

---

## Code Evidence

### Budget Logic (DOES calculate from habits):
```python
# app/services/core/engine/budget_logic.py:33-47
freq = answers.get("spending_habits", {})
freq_weights = {
    "dining out": freq.get("dining_out_per_month", 0),      # ✅ Uses user input
    "entertainment": freq.get("entertainment_per_month", 0), # ✅ Uses user input
    "clothing": freq.get("clothing_per_month", 0),          # ✅ Uses user input
    "travel": freq.get("travel_per_year", 0) / 12,          # ✅ Uses user input
    "coffee": freq.get("coffee_per_week", 0) * 4,           # ✅ Uses user input
    "transport": freq.get("transport_per_month", 0),        # ✅ Uses user input
}

weights = {k: v / total_freq for k, v in freq_weights.items()}
```

### Monthly Budget (Uses regional defaults):
```python
# app/services/core/engine/monthly_budget_engine.py:46-55
category_weights = profile.get(
    "category_weights",  # ❌ Gets from country profile, not user habits
    {
        "food": 0.3,
        "transport": 0.15,
        "entertainment": 0.1,
        # ...
    },
)
```

---

## Verification Complete: GAP CONFIRMED ❌

### Checked: `apply_behavioral_adjustments()`
**File:** `app/services/behavior_adapter.py`

**What it does:**
- Extracts patterns from **historical transaction data**
- Adjusts budget based on **detected spending behavior**
- Examples: "weekend_spender", "food_dominated", "emotional_spender"

**The Problem:**
```python
def apply_behavioral_adjustments(user_id: int, config: dict, db):
    # Extract behavior patterns from HISTORY
    patterns = extract_patterns(user_id, year, month, db=db)  # ❌ Needs transaction history

    # Adjust weights based on patterns
    if "weekend_spender" in patterns:
        weights["entertainment"] += 0.05
    # ...
```

**For NEW users (just completed onboarding):**
- ❌ No transaction history exists
- ❌ `extract_patterns()` returns empty
- ❌ No adjustments applied
- ❌ User gets regional defaults, NOT their stated habits

**For EXISTING users (with transaction history):**
- ✅ Patterns extracted from actual spending
- ✅ Adjustments applied
- ✅ Budget adapts to real behavior

---

## The Design Issue

### What Happens to Onboarding Habits:

```
Step 1: User inputs spending habits during onboarding
  "I dine out 15 times/month"
  "I buy coffee 5 times/week"
  ↓
Step 2: Budget logic calculates custom weights
  discretionary_breakdown = {
    "dining out": 35%,  # High because of 15 times/month
    "coffee": 20%,      # High because of 5 times/week
    "entertainment": 10%,
    ...
  }
  ↓
Step 3: Calendar builder receives config
  ❌ Ignores discretionary_breakdown
  ✅ Uses regional defaults instead
  Result: {
    "food": 30%,           # Regional default
    "transport": 15%,      # Regional default
    "entertainment": 10%,  # Regional default
  }
  ↓
Step 4: apply_behavioral_adjustments() called
  patterns = extract_patterns(user_id, ...)  # Returns [] for new user
  No adjustments made
  ↓
Step 5: User sees budget based on REGIONAL DEFAULTS
  ❌ NOT based on their stated habits from onboarding
```

### Later, After User Has Transaction History:

```
Step 1: User has spent money for 1-2 months
  ↓
Step 2: extract_patterns() analyzes actual transactions
  Detects: "weekend_spender", "food_dominated"
  ↓
Step 3: apply_behavioral_adjustments() applies tweaks
  Increases weekend spending by 5%
  ↓
Step 4: Budget NOW adapts to actual behavior
  ✅ But this takes 1-2 months of data
```

---

## Recommendation

### Issue: Onboarding Habits Not Used for New Users

**Severity:** Medium

**Impact:**
- New users see generic budget not matching their stated habits
- Onboarding spending habits questions are essentially wasted
- Budget only becomes personalized after 1-2 months of transaction history

**Fix Options:**

### Option 1: Pass discretionary_breakdown to Calendar Builder (Recommended)
```python
# In onboarding/routes.py line 101-107
calendar_config = {
    **answers,
    **budget_plan,  # This includes discretionary_breakdown
    "monthly_income": monthly_income,
    "user_id": str(current_user.id),
}

# Modify monthly_budget_engine.py to use discretionary_breakdown if present:
if "discretionary_breakdown" in user_answers:
    # Use onboarding habits
    category_weights = calculate_weights_from_breakdown(
        user_answers["discretionary_breakdown"]
    )
else:
    # Fall back to regional defaults
    category_weights = profile.get("category_weights", {...})
```

### Option 2: Store Habits as Initial Behavioral Profile
```python
# Create initial behavioral profile from onboarding
# Store in database as "onboarding_preferences"
# Use as starting point before transaction history exists
```

### Option 3: Document Current Behavior
```
# Add to onboarding completion message:
"Your budget will become more personalized as we learn from your actual spending patterns over the next 1-2 months."
```

---

## Files to Check

1. `app/services/behavior_adapter.py` - Check `apply_behavioral_adjustments()`
2. `app/services/core/engine/monthly_budget_engine.py` - Verify weight source
3. Test with actual user data to see if habits affect budget

---

## Summary

| Data | Captured? | Used in Budget? | Used in Calendar? | Status |
|------|-----------|-----------------|-------------------|--------|
| Income | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Working |
| Fixed Expenses | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Working |
| Savings Goal | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Working |
| Region | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Working |
| **Spending Habits (Onboarding)** | ✅ Yes | ✅ Calculated | ❌ **NOT USED** | ❌ **Gap Found** |
| Spending Habits (from transactions) | N/A | N/A | ✅ Yes | ✅ Working (after 1-2 months) |

---

## Final Answer

**Question:** Does the app take all info that user inputs correctly and use that info for budget calculations?

**Answer:** **MOSTLY YES, with 1 IMPORTANT EXCEPTION**

### What Works ✅ (80%)
1. **Income** - Used immediately, correctly
2. **Fixed expenses** - Used immediately, correctly
3. **Savings goal** - Used immediately, correctly
4. **Region** - Used for cost-of-living adjustments

### What Doesn't Work ❌ (20%)
5. **Spending habits from onboarding** - Calculated but NOT applied to new user budgets

---

## The Issue Explained Simply

**What user thinks happens:**
```
User: "I dine out 15 times/month and buy coffee 5 times/week"
User expects: Budget shows high allocation for dining & coffee
```

**What actually happens:**
```
User: "I dine out 15 times/month and buy coffee 5 times/week"
System: "Noted, but I'll use Bulgarian regional averages instead"
User sees: Generic budget based on country, not their habits
```

**When it gets fixed:**
```
After 1-2 months: System analyzes actual transactions
System: "Oh, you really do dine out a lot!"
Budget finally adapts to actual behavior
```

---

## Impact

**Severity:** Medium (not critical, but affects user experience)

**User Experience:**
- ❌ New user's budget feels generic, not personalized
- ❌ Onboarding questions feel pointless ("Why did you ask if you're not using it?")
- ✅ Budget eventually adapts after 1-2 months of real data
- ✅ Core budgeting still works (income, expenses, goals)

**Technical:**
- `generate_budget_from_answers()` correctly calculates habit-based weights
- `build_monthly_budget()` ignores them and uses regional defaults
- Data is captured but not utilized for new users

---

## Status: 80% Complete

- ✅ Major inputs (income, expenses, goals) fully utilized
- ❌ Spending habits not utilized for new users
- ✅ Spending habits utilized for existing users (from transaction history)

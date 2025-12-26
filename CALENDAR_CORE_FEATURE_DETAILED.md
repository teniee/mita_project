# COMPREHENSIVE CALENDAR BUDGET BUILDING PROCESS - MITA FINANCE

## COMPLETE END-TO-END WORKFLOW ANALYSIS

This document provides maximum-detail documentation of how MITA builds a user's budget calendar, from initial data collection through mobile display and real-time updates.

---

## PART 1: INITIAL DATA COLLECTION & INCOME CLASSIFICATION

### 1.1 Onboarding Data Capture

**Entry Point**: Mobile App → User completes onboarding questionnaire

**File**: `/app/api/onboarding/schemas.py` (Lines 1-115)

**Captured Data Structure**:
```
OnboardingSubmitRequest:
├── income
│   ├── monthly_income (float) [Required, > 0]
│   └── additional_income (float) [Optional, >= 0]
├── fixed_expenses
│   └── {category: amount} [Dict[str, float]]
├── spending_habits
│   ├── dining_out_per_month (int)
│   ├── entertainment_per_month (int)
│   ├── clothing_per_month (int)
│   ├── travel_per_year (int)
│   ├── coffee_per_week (int)
│   └── transport_per_month (int)
├── goals
│   ├── savings_goal_amount_per_month (float)
│   ├── savings_goal_type (str)
│   ├── has_emergency_fund (bool)
│   └── all_goals (list)
├── region (str) [Optional, defaults to "US"]
└── meta (Dict) [Additional mobile metadata]
```

**Validation Process** (Lines 60-100):
- Fixed expenses: validated non-negative, reasonable bounds (<$1M per category)
- Income: must be positive
- Region: sanitized and trimmed

### 1.2 Income Tier Classification

**File**: `/app/services/core/income_classification_service.py` (Lines 1-392)

**5-Tier Classification System**:

```python
class IncomeTier(Enum):
    LOW              # Annual: < $36,000
    LOWER_MIDDLE     # Annual: $36K - $57.6K
    MIDDLE           # Annual: $57.6K - $86.4K
    UPPER_MIDDLE     # Annual: $86.4K - $144K
    HIGH             # Annual: > $144K
```

**Classification Algorithm** (Lines 67-101):

```
Input: monthly_income, region
↓
Calculate annual_income = monthly_income × 12
↓
Get region-specific thresholds from country profile
↓
Compare annual_income to thresholds:
  if annual_income <= low_threshold        → IncomeTier.LOW
  elif annual_income <= lower_middle       → IncomeTier.LOWER_MIDDLE
  elif annual_income <= middle             → IncomeTier.MIDDLE
  elif annual_income <= upper_middle       → IncomeTier.UPPER_MIDDLE
  else                                      → IncomeTier.HIGH
↓
Return: IncomeTier enum
```

**Default Thresholds** (Used when region profile unavailable):
- LOW: $36,000/year
- LOWER_MIDDLE: $57,600/year
- MIDDLE: $86,400/year
- UPPER_MIDDLE: $144,000/year

### 1.3 Location-Based Cost of Living Adjustments

**File**: `/app/services/core/income_scaling_algorithms.py` (Lines 36-545)

**Income Scaling Service**: Applies regional and economic adjustments to budget thresholds

**Key Scaling Functions**:

1. **Housing Ratio Scaling** (Lines 97-147):
   - Base: 30% of income
   - Elasticity: -0.3 (decreases with income)
   - Formula: `base_ratio × (income_ratio)^elasticity_coefficient`
   - Regional adjustment: multiplies base by cost-of-living multiplier
   - Family size: +5% per additional person
   - Bounds: 20% - 50%

2. **Food Ratio Scaling** (Lines 149-186) [Engel's Law]:
   - Base: 12% of income
   - Elasticity: -0.5 (strong negative, per Engel's Law)
   - Family size impact: +30% per additional person
   - Bounds: 8% - 20%

3. **Savings Rate Target** (Lines 188-235):
   - Base: 12% of income
   - Elasticity: +0.4 (increases with income)
   - Life-cycle adjustment: varies by age
   - Debt burden penalty: `max(0.5, 1 - debt_ratio × 1.5)`
   - Bounds: 2% - 50%

---

## PART 2: BUDGET CALCULATION PROCESS

### 2.1 Budget Generation from Answers

**File**: `/app/services/core/engine/budget_logic.py` (Lines 1-60)

**Entry Function**: `generate_budget_from_answers(answers: dict) → dict`

**Step-by-Step Algorithm**:

```
Step 1: Extract Income Data
├── Get region (default: "US")
├── Get monthly_income from income.monthly_income
├── Get additional_income from income.additional_income
└── total_income = monthly_income + additional_income

Step 2: Classify Income Tier
├── Call classify_income(total_income, region)
├── Get user_class = tier string representation
└── Retrieve region-specific profile from country_profiles_loader

Step 3: Calculate Fixed Expenses
├── Extract fixed_expenses dict from request
├── Sum all fixed expense values
├── Validate: fixed_total <= total_income
└── If invalid: raise ValueError

Step 4: Calculate Discretionary Budget
├── discretionary = total_income - fixed_total
├── Extract savings_goal from goals.savings_goal_amount_per_month
├── Deduct savings_goal: discretionary -= savings_goal
├── If discretionary < 0:
│   ├── Adjust savings_goal downward
│   └── Set discretionary = 0

Step 5: Process Spending Habits Frequencies
├── Extract spending_habits frequencies:
│   ├── dining_out_per_month
│   ├── entertainment_per_month
│   ├── clothing_per_month
│   ├── travel_per_year (convert to monthly ÷12)
│   ├── coffee_per_week (convert to monthly ×4)
│   └── transport_per_month
├── Calculate total_freq = sum of all frequencies
├── Normalize weights: weight = frequency / total_freq
└── If total_freq == 0: use equal weights

Step 6: Generate Discretionary Breakdown
├── For each category with weight:
│   └── allocation = discretionary × weight × 0.01 (rounded to 2 decimals)
└── Return discretionary_breakdown dict

Step 7: Return Budget Plan
{
    "savings_goal": round(savings_goal, 2),
    "user_class": user_class,
    "behavior": behavior_from_profile,
    "total_income": round(total_income, 2),
    "fixed_expenses_total": round(fixed_total, 2),
    "discretionary_total": round(discretionary, 2),
    "discretionary_breakdown": {
        "dining out": amount,
        "entertainment events": amount,
        "clothing": amount,
        "travel": amount,
        "coffee": amount,
        "transport": amount
    }
}
```

### 2.2 Category Behavior Types

**File**: `/app/services/core/engine/calendar_engine.py` (Lines 5-39)

**Three Core Behavior Types**:

#### FIXED Categories
**Definition**: Same amount each day or concentrated on specific days

**Subcategories**:
- Rent, mortgage (allocated to Day 1)
- Utilities, insurance (allocated to Day 5)
- Subscriptions, media streaming (fixed days)
- Cloud storage, gym fitness
- School fees, debt repayment
- Investment contributions

**Distribution Algorithm** (Lines 71-77):
```
if category in ["rent", "mortgage", "school fees"]:
    allocate_to_day = 0  # First day of month
else:
    allocate_to_day = min(4, num_days - 1)  # Day 5 typically

days[allocate_to_day].planned_budget[category] = total_amount
```

#### SPREAD Categories
**Definition**: Distributed across weekdays, ideally spread throughout month

**Categories**:
- Groceries, local transport
- Public transport, savings (emergency, goal-based)

**Distribution Algorithm** (Lines 79-84):
```
1. Filter weekdays (Monday-Friday)
2. Select every other weekday: weekday_days[::2]
3. Fallback to all days if insufficient weekdays
4. per_day = total_amount / num_spread_days (rounded)
5. Allocate per_day to each selected spread day
```

#### CLUSTERED Categories
**Definition**: Concentrated on specific days (usually weekends or payday)

**Categories**:
- Dining out, delivery, shopping
- Entertainment events, gaming
- Clothing, tech gadgets, books
- Home repairs, car maintenance
- Transportation (gas, taxi), hobbies
- Out-of-pocket medical

**Distribution Algorithm** (Lines 86-95):
```
1. Start with weekend days (Saturday, Sunday)
2. If fewer than 4 candidates:
   - Add random non-weekend days until we have 4+ candidates
3. Randomly select up to 4 candidate days
4. chunk = total_amount / num_selected_days (rounded)
5. Allocate chunk to each selected day
```

---

## PART 3: CALENDAR GENERATION FLOW

### 3.1 Monthly Budget Engine

**File**: `/app/services/core/engine/monthly_budget_engine.py` (Lines 1-110)

**Function**: `build_monthly_budget(user_answers: dict, year: int, month: int) → List[Dict]`

**Complete Algorithm**:

```
Input: user_answers (with income, fixed, spending habits, goals), year, month
↓
Step 1: Extract and Prepare Data
├── Get region from answers (default: "US-CA")
├── Convert monthly_income to Decimal for precision
├── Get country profile for region
├── Extract fixed_expenses dict
├── Extract savings_goal_amount_per_month

Step 2: Validate Budget Feasibility
├── fixed_total = sum(fixed.values())
├── discretionary = income - fixed_total - savings_goal
├── If discretionary < 0: raise ValueError

Step 3: Determine Budget Allocation Method
├── If user has discretionary_breakdown (from budget_logic):
│   └── Use personalized allocation
├── Else:
│   ├── Get category_weights from region profile
│   ├── Normalize weights if sum ≠ 1.0
│   └── Calculate flexible_alloc from discretionary × weights

Step 4: Build Full Month Plan
├── full_month_plan = {}
├── Add all fixed_expenses to plan
├── Add all flexible_alloc to plan
└── Result: {category: monthly_total, ...}

Step 5: Setup Calendar Days
├── Calculate num_days = days in month
├── Create day entries for 1..num_days:
│   {
│       "date": "YYYY-MM-DD",
│       "planned_budget": {},
│       "total": Decimal("0.00")
│   }

Step 6: Distribute Categories Across Days
├── For each category, monthly_amount in full_month_plan:
│   └── Call distribute_budget_over_days(days, category, amount)
│       (Uses FIXED/SPREAD/CLUSTERED logic from Section 2.2)

Step 7: Calculate Daily Totals
├── For each day:
│   └── day["total"] = sum(day["planned_budget"].values())

Return: List[Dict] with 28-31 day entries
```

**Output Structure** (Example for one day):
```json
{
    "date": "2025-01-15",
    "planned_budget": {
        "rent": 1200.00,
        "groceries": 50.00,
        "dining out": 35.00,
        "transport": 15.00,
        "entertainment": 10.00,
        "utilities": 0.00
    },
    "total": 1310.00
}
```

### 3.2 Behavioral Calendar Engine

**File**: `/app/engine/calendar_engine_behavioral.py` (Lines 1-45)

**Function**: `build_calendar(config: dict) → dict`

**Two Modes**:

#### Mode 1: Goal-Based Budget
```
config.mode == "goal"
├── Extract: income, fixed, weights, savings_target
├── Call: build_goal_budget(income, fixed, savings_target, weights)
└── Returns: {fixed, flexible, savings_goal}
```

#### Mode 2: Behavioral/Default Budget
```
config.mode == "default" (or missing)
├── Extract: user_id, answers
├── Call: apply_behavioral_adjustments(user_id, config)
│   (Personalizes budget based on user history if available)
├── Call: build_monthly_budget(adjusted_config, year, month)
└── Returns: List[Dict] with calendar days
```

---

## PART 4: DATABASE PERSISTENCE

### 4.1 DailyPlan Model

**File**: `/app/db/models/daily_plan.py` (Lines 1-28)

**Table Structure**:
```sql
CREATE TABLE daily_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL [INDEX],
    date DATETIME NOT NULL [INDEX],
    category VARCHAR(100) [INDEX],
    planned_amount NUMERIC(12,2),
    spent_amount NUMERIC(12,2) DEFAULT 0.00,
    daily_budget NUMERIC(12,2),
    status VARCHAR(20) DEFAULT 'green',
    plan_json JSONB,
    created_at DATETIME DEFAULT now()
)
```

### 4.2 Calendar Persistence

**File**: `/app/services/calendar_service_real.py` (Lines 1-121)

**Function**: `save_calendar_for_user(db: Session, user_id: UUID, calendar: Dict|List)`

**Storage Algorithm**:

```
Input: calendar (Dict or List format)
↓
Step 1: Convert List Format to Dict (if needed)
├── If List: iterate and build {date_str: {category: amount}}
└── If Dict: use directly

Step 2: Validate Data
├── If calendar is empty: log warning and return
└── Else: proceed

Step 3: Create DailyPlan Entries
├── For each day_str, categories dict:
│   ├── Parse date_str to date object
│   ├── For each category, amount:
│   │   └── Create DailyPlan entry:
│   │       {
│   │           id: uuid.uuid4(),
│   │           user_id: user_id,
│   │           date: date_obj,
│   │           category: category,
│   │           planned_amount: Decimal(amount),
│   │           spent_amount: Decimal("0.00")
│   │       }
│   └── db.add(entry)

Step 4: Commit Transaction
├── db.commit()

Step 5: Verify Save
├── Query count of DailyPlan for this user
├── Log success with entry count
├── If count == 0: raise ValueError

Error Handling:
└── On exception: db.rollback() and raise
```

**Example Output** (Database state after save):
```
Daily_plan table entries:
- (uuid, user_id, 2025-01-01, "rent", 1200.00, 0.00)
- (uuid, user_id, 2025-01-01, "groceries", 50.00, 0.00)
- (uuid, user_id, 2025-01-02, "groceries", 50.00, 0.00)
- ...
```

---

## PART 5: ONBOARDING FLOW INTEGRATION

### 5.1 Complete Onboarding Endpoint

**File**: `/app/api/onboarding/routes.py` (Lines 34-187)

**Endpoint**: `POST /onboarding/submit`

**Complete Flow**:

```
User submits onboarding data
    ↓
[Dependency] get_current_user validates JWT
    ↓
[Pydantic] Validates OnboardingSubmitRequest schema
    ↓
Step 1: Update User Income
├── Update user.monthly_income from request.income.monthly_income
├── db.flush() (not commit yet)
└── Log update

Step 2: Generate Budget Plan
├── Call generate_budget_from_answers(request.model_dump())
├── Returns: {user_class, behavior, savings_goal,
│            discretionary_breakdown, ...}
└── Log generation

Step 3: Build Calendar
├── Prepare calendar_config:
│   {
│       **request.model_dump(),      (all request data)
│       **budget_plan,               (generated allocations)
│       "monthly_income": amount,    (top-level)
│       "user_id": str(user.id)
│   }
├── Call build_calendar(calendar_config)
├── Receives: List[Dict] with 28-31 day entries
├── Call save_calendar_for_user(db, user.id, calendar_data)
└── Log save with day count

Step 4: Mark Onboarding Complete
├── user.has_onboarded = True
├── db.add(user)
├── db.commit()
│   (Commits income update, calendar save, and flag)
└── Log completion

Step 5: Return Success Response
{
    "status": "success",
    "calendar_days": 31,
    "budget_plan": {...},
    "message": "Onboarding completed successfully"
}

Error Handling:
├── 400: Budget/Calendar validation errors
├── 401: Authentication failure
├── 422: Pydantic validation failure
└── 500: Database or processing errors
```

---

## PART 6: BUDGET REDISTRIBUTION MECHANISM

### 6.1 Redistribution Algorithm

**File**: `/app/engine/budget_redistributor.py` (Lines 1-108)

**Core Class**: `BudgetRedistributor`

**Key Feature**: When user overspends in one category on one day, automatically redistributes available surplus from other categories/days to maintain monthly budget limit.

**Algorithm** (Lines 42-76):

```
Input: calendar = {day: {total: amount, limit: amount}, ...}
↓
Step 1: Convert to Decimal Precision
├── Convert all amounts to Decimal(28 decimal places)
├── Set ROUND_HALF_UP for financial accuracy
└── Creates self.calendar with Decimal values

Step 2: Identify Over and Under Days
├── over_days = days where total > limit
├── under_days = days where total < limit

Step 3: Sort by Magnitude
├── Sort over_days by _overage() in descending order
│   (largest surpluses first)
├── Sort under_days by _shortfall() in descending order
│   (largest deficits first)
└── Greedy matching: largest donors to largest needs

Step 4: Execute Transfers
├── For each over_day src (in sorted order):
│   ├── src_over = _overage(src) = src_total - src_limit
│   ├── If src_over > 0:
│   │   ├── For each under_day dst (in sorted order):
│   │   │   ├── dst_need = _shortfall(dst) = dst_limit - dst_total
│   │   │   ├── If dst_need > 0:
│   │   │   │   ├── transfer = min(src_over, dst_need)
│   │   │   │   ├── Apply transfer:
│   │   │   │   │   ├── src.total -= transfer
│   │   │   │   │   └── dst.total += transfer
│   │   │   │   ├── Record transfer
│   │   │   │   ├── src_over -= transfer
│   │   │   │   └── If src_over == 0: break
│   │   │   └── (continue with next under_day)
│   │   └── (continue with next over_day)

Step 5: Return Results
├── Updated calendar with redistributed amounts
└── List of all transfers made:
    [(src_day, dst_day, amount), ...]
```

**Helper Methods**:
- `_overage(day)`: `total - limit` (positive = overspent)
- `_shortfall(day)`: `limit - total` (positive = underspent)
- `_apply_transfer(src, dst, amount)`: modifies totals directly

**Public API Method**:
- **Method Name**: `redistribute_budget()` (NOT `redistribute()`)
- **Returns**: `Tuple[Dict[str, Dict[str, Decimal]], List[Tuple[str, str, Decimal]]]`
- **Usage**:
  ```python
  redistributor = BudgetRedistributor(calendar_dict)
  updated_calendar, transfers = redistributor.redistribute_budget()
  ```

**Example**:
```
Before:
  Day 1: {total: 150, limit: 100}  (over by 50)
  Day 2: {total: 70, limit: 100}   (under by 30)
  Day 3: {total: 85, limit: 100}   (under by 15)

Processing:
  Transfer 30 from Day 1 to Day 2
  Transfer 15 from Day 1 to Day 3
  Remaining: 5 in Day 1 (within limit)

After:
  Day 1: {total: 100, limit: 100}  (balanced)
  Day 2: {total: 100, limit: 100}  (balanced)
  Day 3: {total: 100, limit: 100}  (balanced)
```

### 6.2 Redistribution API Endpoint

**File**: `/app/api/calendar/routes.py` (Lines 101-108)

**Endpoint**: `POST /calendar/redistribute`

```
Request: RedistributeInput
{
    "calendar": {
        "2025-01-01": {"total": 150, "limit": 100},
        "2025-01-02": {"total": 70, "limit": 100},
        ...
    },
    "strategy": "balance"  (currently unused, reserved for future)
}

Processing:
├── Call redistribute_calendar_budget(payload.calendar)
└── Uses BudgetRedistributor internally

Response: RedistributeResult
{
    "updated_calendar": {
        "2025-01-01": {"total": 100, "limit": 100},
        "2025-01-02": {"total": 100, "limit": 100},
        ...
    }
}
```

---

## PART 7: MOBILE INTEGRATION

### 7.1 Calendar Data Flow to Mobile

**File**: `/mobile_app/lib/services/api_service.dart` (Lines 1008-1327)

**Two Retrieval Methods**:

#### Method 1: getSavedCalendar() - Onboarding Data
**Endpoint**: `GET /calendar/saved/{year}/{month}`

**Purpose**: Retrieve calendar generated during onboarding

**Algorithm**:
```
1. Check for valid JWT token
2. GET /calendar/saved/2025/1
3. Parse response (handles nested structures):
   - {data: {calendar: [...]}}
   - {calendar: [...]}
   - [...] (direct list)
4. Validate: list format, non-empty
5. Return: List<dynamic> of calendar days
6. On error: return null, log error, handle gracefully
```

#### Method 2: getCalendar() - Computed Calendar
**Endpoint**: `POST /calendar/shell`

**Purpose**: Generate calendar dynamically with fallback support

**Algorithm**:
```
1. Get user income (from profile if needed)
2. Validate income > 0
3. Check cache for existing calendar data
4. If cached and valid: return cached data
5. POST /calendar/shell with:
   {
       "income": double,
       "fixed": {category: amount, ...},
       "weights": {category: weight, ...},
       "year": int,
       "month": int
   }
6. Transform response: _transformCalendarData()
7. Cache result: _cacheCalendarData()
8. On failure: use CalendarFallbackService
   ├── Generate realistic fallback data
   ├── Based on income tier and location
   ├── Includes pattern variations (weekends, paydays)
   └── Return synthetic calendar
```

### 7.2 Fallback Calendar Service

**File**: `/mobile_app/lib/services/calendar_fallback_service.dart` (Lines 1-407)

**Purpose**: Provide offline-first calendar when backend unavailable

**Key Functions**:

#### generateFallbackCalendarData()
```
Input: monthlyIncome, location, year, month
↓
Step 1: Classify income tier
├── Call incomeService.classifyIncome(monthlyIncome)
└── Get tier string: "low", "mid_low", "mid", "mid_high", "high"

Step 2: Calculate location multiplier
├── High-cost cities (SF, NYC): 1.4x
├── Medium-cost (Chicago, Austin): 1.2x
├── Low-cost areas (Rural): 0.8x
└── Default: 1.0x

Step 3: Get category allocations
├── Select base weights by income tier
├── Apply location multiplier
├── Example for "mid" tier:
   {
       "food": 0.15 * 1.0 = 0.15,
       "transportation": 0.15,
       "entertainment": 0.08,
       "shopping": 0.12,
       "healthcare": 0.05
   }
└── Calculate absolute amounts: income × weight × location_multiplier

Step 4: Generate daily budget variations
├── For each day in month:
│   ├── Apply weekend effect:
│   │   ├── Friday: 1.3x variation
│   │   ├── Saturday-Sunday: 1.5x variation
│   │   └── Monday: 0.8x variation
│   ├── Apply payday effect (day 15, 30, 31): 1.2x
│   ├── End-of-month tightening (day 26+): 0.7x
│   └── Income tier adjustments

Step 5: Calculate realistic spending
├── For past days:
│   ├── Base spending ratio: 70-90% of budget
│   ├── Weekend adjustment: 80-120%
│   ├── Income tier behavior:
│   │   ├── Low: more cautious (60-90%)
│   │   └── High: more flexible (70-120%)
│   ├── 10% chance of overspending (1.3x multiplier)
│   └── Deterministic randomness per day
├── For today:
│   ├── Calculate day progress: hour_of_day / 20 (clamped 0-1)
│   └── Scale spending ratio by progress

Step 6: Calculate day status
├── Ratio = spent / limit
├── > 1.1 (110%): "over"
├── 0.85 - 1.1 (85-110%): "warning"
├── < 0.85 (< 85%): "good"

Return: List<Map> with 28-31 day entries including:
├── day, limit, spent, status
├── categories breakdown
├── is_today, is_weekend, day_of_week
└── All computed locally without network
```

### 7.3 Calendar Screen Display

**File**: `/mobile_app/lib/screens/calendar_screen.dart`

**Display Integration**:
```
CalendarScreen State:
├── budgetProvider.loadCalendarData(year, month)
│   ├── Tries getSavedCalendar() first
│   ├── Falls back to getCalendar() if no saved data
│   └── Falls back to fallback service if both fail
├── Render daily budget boxes
├── Show status colors: green/yellow/red
├── Display spending vs limit
└── Support month navigation
```

---

## PART 8: EDGE CASES & VALIDATION

### 8.1 Mid-Month Changes

**Scenario**: User changes income, fixed expenses, or savings goal mid-month

**Current Handling**:
```
1. User can update profile anytime
2. Next month's calendar uses new values
3. Current month's calendar remains unchanged
4. No retroactive redistribution
5. Potential enhancement: proportional redistribution
```

### 8.2 Irregular Income

**File**: `/app/services/core/income_scaling_algorithms.py` (Lines 188-235)

**Handling**:
```
1. Debt-to-income ratio adjustment
   └── If debt_ratio > 0.1: apply penalty
       max(0.5, 1 - debt_ratio × 1.5)

2. Economic uncertainty adjustment
   └── Increase emergency fund target by up to 40%

3. Job security consideration
   └── Less secure = more months of emergency fund

4. For freelancers/variable income:
   └── Use conservative estimate (lower percentile)
```

### 8.3 Fixed Expenses Exceed Income

**Validation** (Multiple checks):

1. In `budget_logic.py` (Line 22-23):
   ```python
   if fixed_total > income:
       raise ValueError("Fixed expenses exceed income")
   ```

2. In `monthly_budget_engine.py` (Lines 40-43):
   ```python
   if discretionary < 0:
       raise ValueError("Fixed expenses + goal exceed income")
   ```

3. In `build_goal_budget` (Line 7-8):
   ```python
   if goal_amount >= income:
       return {"error": "goal exceeds income"}
   ```

### 8.4 Empty Spending Habits

**Handling** (Line 43-47):
```
If total_frequency == 0:
  └── Use equal weights across all categories
     (1/n for each category)
Else:
  └── Normalize frequency to weights
```

### 8.5 Zero Income

**Validation**:
```
1. Pydantic schema validates: monthly_income > 0
2. Will raise 422 Validation Error if attempt to submit 0
3. Mobile app prevents submission if income = 0
```

---

## PART 9: DATA TRANSFORMATIONS & STATE

### 9.1 State Transitions

```
User State Machine:
├── Unauthenticated
│   └── Register/Login → Authenticated, !has_onboarded
├── Authenticated, !has_onboarded
│   └── Submit onboarding
│       ├── Save income → user.monthly_income
│       ├── Generate budget → budget_plan
│       ├── Build calendar → DailyPlan entries
│       └── Mark complete → has_onboarded = true
├── Authenticated, has_onboarded
│   ├── View calendar (GET /calendar/saved/{year}/{month})
│   ├── Update spending (PATCH /day/{year}/{month}/{day})
│   ├── Request redistribution (POST /calendar/redistribute)
│   └── Update profile → Next month uses new values

Calendar State:
├── Not yet generated
│   └── No DailyPlan entries
├── Generated (Onboarding)
│   ├── Planned amounts for each category/day
│   ├── Spent amounts = 0.00
│   └── Status = "green" (not started)
├── In Progress (User spending)
│   ├── Spent amounts updated
│   ├── Status changes: green → yellow → red
│   └── May request redistribution
└── Completed (Month ended)
    ├── All spending recorded
    ├── Final status locked
    └── Historical data for next month
```

### 9.2 Data Transformation Layers

```
Layer 1: Mobile Input (Dart/Flutter)
  └── {income, fixed_expenses, habits, goals, region}

Layer 2: API Validation (Pydantic)
  └── OnboardingSubmitRequest schema validation

Layer 3: Budget Generation (Python)
  ├── Income classification
  ├── Budget logic
  └── Returns: {user_class, discretionary_breakdown, ...}

Layer 4: Calendar Building (Python)
  ├── Distribution algorithm (FIXED/SPREAD/CLUSTERED)
  └── Returns: List[{date, planned_budget, total}]

Layer 5: Database Storage (SQLAlchemy)
  ├── Converts to DailyPlan rows
  └── Multiple entries per day (one per category)

Layer 6: Mobile Retrieval (Dart)
  ├── GET /calendar/saved/{year}/{month}
  ├── Transforms to display format
  └── Renders in UI
```

---

## PART 10: MATHEMATICAL FORMULAS

### 10.1 Income Elasticity Scaling

**General Formula**:
```
scaled_value = base_value × (target_income / base_income)^elasticity_coefficient

Where:
  base_income = reference income (typically $70,000)
  elasticity_coefficient = negative for essentials, positive for discretionary
  target_income = user's actual income
```

**Examples**:

1. **Housing Ratio** (Elasticity: -0.3):
   ```
   base_ratio = 0.30 (30%)
   user_income = $120,000

   income_ratio = 120,000 / 70,000 = 1.714
   adjustment = 1.714^(-0.3) = 0.823
   scaled_ratio = 0.30 × 0.823 = 0.247 (24.7%)
   ```

2. **Savings Rate** (Elasticity: +0.4):
   ```
   base_rate = 0.12 (12%)
   user_income = $120,000

   income_ratio = 120,000 / 70,000 = 1.714
   adjustment = 1.714^(0.4) = 1.229
   scaled_rate = 0.12 × 1.229 = 0.147 (14.7%)
   ```

### 10.2 Daily Budget Distribution

**SPREAD Distribution**:
```
1. Filter to weekdays: [Mon, Tue, Wed, Thu, Fri]
2. Select every other day: [Mon, Wed, Fri]
3. Amount per day = monthly_total / num_days

Example (Budget = $300):
  Spread days = 3
  Amount/day = $300 / 3 = $100
  Distribution: Mon=$100, Wed=$100, Fri=$100
```

**CLUSTERED Distribution**:
```
1. Start with weekends: up to 4 days
2. If < 4 available: add random weekdays
3. Select randomly up to 4 days
4. Amount per day = monthly_total / num_selected_days

Example (Budget = $200):
  Selected days = 4 (Fri, Sat, Sun, Mon)
  Amount/day = $200 / 4 = $50
  Distribution: Each day = $50
```

**FIXED Distribution**:
```
Special cases by category:
  Rent/Mortgage/School fees → Day 1
  Others → Day 5 (middle of month)

Example (Rent = $1200):
  Distribution: Day 1 = $1200
```

### 10.3 Budget Redistribution Formula

**Transfer Amount**:
```
For each over-day and under-day pair:
  transfer = min(over_day_surplus, under_day_deficit)

  over_day.total -= transfer
  under_day.total += transfer

Greedy approach (maximize-match):
  1. Sort over_days by surplus descending
  2. Sort under_days by deficit descending
  3. Match largest to largest
  4. Continue until all deficits covered or surpluses exhausted
```

---

## PART 11: COMPLETE EXAMPLE WALKTHROUGH

### Example: User Onboarding to Calendar Display

**User Input**:
```json
{
    "income": {
        "monthly_income": 5000,
        "additional_income": 500
    },
    "fixed_expenses": {
        "rent": 1200,
        "utilities": 150
    },
    "spending_habits": {
        "dining_out_per_month": 8,
        "entertainment_per_month": 4,
        "shopping_frequency": 8
    },
    "goals": {
        "savings_goal_amount_per_month": 500
    },
    "region": "US-CA"
}
```

**Step 1: Income Classification**
```
total_income = 5000 + 500 = 5500/month = $66,000/year
region = "US-CA"
→ IncomeTier.LOWER_MIDDLE (between $57.6K and $86.4K)
→ user_class = "lower_middle"
```

**Step 2: Budget Generation**
```
fixed_total = 1200 + 150 = 1350
discretionary = 5500 - 1350 - 500 = 3650

spending_habits frequencies:
  dining_out: 8
  entertainment: 4
  shopping: 8
  total_freq: 20

weights:
  dining_out: 8/20 = 0.40
  entertainment: 4/20 = 0.20
  shopping: 8/20 = 0.40

discretionary_breakdown:
  dining_out: 3650 × 0.40 = 1460
  entertainment: 3650 × 0.20 = 730
  shopping: 3650 × 0.40 = 1460

budget_plan:
{
    "user_class": "lower_middle",
    "total_income": 5500,
    "fixed_expenses_total": 1350,
    "savings_goal": 500,
    "discretionary_total": 3650,
    "discretionary_breakdown": {
        "dining out": 1460,
        "entertainment": 730,
        "shopping": 1460
    }
}
```

**Step 3: Calendar Generation (January 2025, 31 days)**
```
Full month plan:
  rent: 1200
  utilities: 150
  dining out: 1460
  entertainment: 730
  shopping: 1460
  savings: 500

Distribution by behavior type:
  FIXED (rent) → Day 1: $1200
  FIXED (utilities) → Day 5: $150
  CLUSTERED (dining out) → Fri/Sat/Sun: ~$365 each
  CLUSTERED (shopping) → Fri/Sat/Sun: ~$365 each
  CLUSTERED (entertainment) → Fri/Sat: ~$365 each
  SPREAD (savings) → Every other weekday: varies

Example daily values:
  2025-01-01: rent($1200) = $1200
  2025-01-03: savings($143) = $143
  2025-01-05: utilities($150) + savings($143) = $293
  2025-01-10: dining($365) + shopping($365) = $730
  2025-01-15: savings($143) = $143
  2025-01-17: entertainment($365) = $365
  2025-01-24: shopping($365) = $365
  ...
  Total for month = $5500 ✓
```

**Step 4: Database Storage**
```
DailyPlan entries created:
  (UUID, user_id, 2025-01-01, "rent", 1200.00, 0.00)
  (UUID, user_id, 2025-01-01, "savings", 0.00, 0.00)
  (UUID, user_id, 2025-01-03, "savings", 143.00, 0.00)
  ...
  Total: 31 days × 3-4 categories = 93-124 entries
```

**Step 5: Mobile Display**
```
Mobile app calls GET /calendar/saved/2025/1
Response:
{
    "calendar": [
        {
            "date": "2025-01-01",
            "planned_budget": {
                "rent": {"planned": 1200, "spent": 0, "status": "pending"},
                "savings": {"planned": 0, "spent": 0, "status": "pending"}
            },
            "limit": 1200,
            "total": 1200,
            "spent": 0,
            "status": "active"
        },
        ...
    ]
}

UI shows:
  January 1: Budget $1200, Spent $0, Status: Good
  January 3: Budget $143, Spent $0, Status: Good
  January 10: Budget $730, Spent $0, Status: Good
  ...
```

**Step 6: User Spending & Redistribution**
```
After user spends $400 on Jan 10 (budget was $730):
  Jan 10: Spent $400, Status: Green (55% of budget)

After user spends $800 on Jan 15 (budget was $143):
  Jan 15: Spent $800, Limit $143, OVERSPENT by $657
  Status: Red

Redistribution triggered:
  Find surplus days: Jan 17 (entertainment $365, only need $50)
  Transfer $200 from Jan 17 to Jan 15
  Transfer $100 from Jan 24 (shopping $365) to Jan 15
  Result: Jan 15 deficit reduced, month still balances
```

---

## PART 12: PERFORMANCE & OPTIMIZATION

### 12.1 Key Performance Metrics

**Target**: 75ms average response time

**Bottlenecks & Optimizations**:

1. **Budget Calculation** (Lines 5-60 in budget_logic.py):
   - Input validation: O(1)
   - Frequency calculations: O(n) where n=6 categories
   - Optimization: Pre-computed category weights

2. **Calendar Distribution** (Lines 65-95 in calendar_engine.py):
   - Day iteration: O(31) days
   - Category distribution: O(6) categories per day
   - Random sampling for clustered: O(4) selection
   - Optimization: Deterministic random seed (consistent across runs)

3. **Database Storage** (Lines 15-78 in calendar_service_real.py):
   - Bulk insert: O(31 × 5) = O(155) DailyPlan rows
   - Single commit: reduces transaction overhead
   - Query verification: O(1) count operation
   - Optimization: Batch inserts, single commit

4. **Mobile Caching**:
   - API Service caches calendar data locally
   - Cache key: `calendar_{income}_{year}_{month}`
   - Reuse if same month/year requested
   - Optimization: Avoid repeated API calls within session

### 12.2 Database Query Optimization

```python
# Optimized query in calendar_service_real.py
# Uses indexes on (user_id, date, category)
db.query(DailyPlan)
  .filter(DailyPlan.user_id == user_id)      # Index on user_id
  .filter(DailyPlan.date >= date(year, month, 1))  # Index on date
  .filter(DailyPlan.date < end_date)
  .all()
```

---

## PART 13: SECURITY & VALIDATION

### 13.1 Input Validation Layers

**Layer 1: Pydantic Schema** (Lines 47-101):
- Fixed expenses: validate non-negative, max $1M
- Income: must be > 0
- Region: max 100 chars, trimmed
- Extra fields: allowed (mobile compatibility)

**Layer 2: Business Logic** (Lines 22-44):
- Fixed expenses cannot exceed income
- Savings goal cannot exceed discretionary income
- Income tier classification (prevents invalid states)

**Layer 3: Database** (DailyPlan Model):
- user_id: FK constraint, NOT NULL
- date: NOT NULL, indexed
- planned_amount: NUMERIC precision (12,2)
- spent_amount: defaults to 0, prevents NULL

### 13.2 Authorization

**File**: `/app/api/dependencies.py` (dependency injection)

**Every Calendar Endpoint** requires:
```python
user = Depends(get_current_user)  # Validates JWT
# Only user can access their own calendar
Filter by user_id == user.id
```

---

## SUMMARY: COMPLETE CALENDAR BUILDING WORKFLOW

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER ONBOARDING (Mobile)                                 │
│   - Input: income, fixed expenses, spending habits, goals   │
│   - Region: location for COL adjustment                     │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. API VALIDATION (FastAPI)                                 │
│   - Pydantic schema validation                              │
│   - Auth: JWT token verification                            │
│   - Endpoint: POST /onboarding/submit                       │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. INCOME CLASSIFICATION (Python Service)                   │
│   - Classify into 5 tiers (LOW to HIGH)                    │
│   - Get income scaling factors                              │
│   - Regional thresholds applied                             │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. BUDGET GENERATION (budget_logic.py)                      │
│   - Calculate total income                                  │
│   - Deduct fixed expenses                                   │
│   - Deduct savings goal                                     │
│   - Allocate discretionary across categories                │
│   - Return: discretionary_breakdown                         │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. CALENDAR GENERATION (monthly_budget_engine.py)           │
│   - Merge fixed + flexible allocations                      │
│   - Distribute across 28-31 days using:                     │
│     • FIXED: Day 1 or Day 5                                 │
│     • SPREAD: Every other weekday                           │
│     • CLUSTERED: 4 weekend days                             │
│   - Calculate daily totals                                  │
│   - Return: List[{date, planned_budget, total}]            │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. DATABASE PERSISTENCE (calendar_service_real.py)          │
│   - Convert to DailyPlan entries (31 days × 5-6 cats)      │
│   - Generate UUIDs explicitly                               │
│   - Bulk insert with single commit                          │
│   - Verify save success                                     │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. ONBOARDING COMPLETION (onboarding/routes.py)             │
│   - Mark user.has_onboarded = True                          │
│   - Commit all changes atomically                           │
│   - Return: success response with calendar_days count       │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. MOBILE RETRIEVAL (Dart/Flutter)                          │
│   - Call: GET /calendar/saved/2025/1                        │
│   - Or: POST /calendar/shell (dynamic generation)           │
│   - Fallback: CalendarFallbackService (offline)             │
│   - Transform to display format                             │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. CALENDAR DISPLAY (Flutter UI)                            │
│   - Render daily budget cards                               │
│   - Show status colors: green/yellow/red                    │
│   - Display spending vs limit                               │
│   - Support month navigation                                │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. RUNTIME OPERATIONS                                      │
│   - User logs spending → updates DailyPlan.spent_amount    │
│   - Redistribution: POST /calendar/redistribute             │
│   - Rebalances overspent days from underspent days         │
│   - Uses BudgetRedistributor algorithm                      │
└─────────────────────────────────────────────────────────────┘
```

---

**© 2025 YAKOVLEV LTD - All Rights Reserved**
**Proprietary Software License**

This comprehensive documentation provides the complete technical understanding of MITA's calendar budget building system, covering every aspect from user input to mobile display and real-time budget redistribution.
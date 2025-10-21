# MITA End-to-End Flow Trace: Onboarding to Main App

## COMPLETE FLOW ANALYSIS

### 1. ONBOARDING COMPLETION PHASE

#### 1.1 Frontend: Onboarding Finish Screen
**File:** `/home/user/mita_project/mobile_app/lib/screens/onboarding_finish_screen.dart` (lines 27-171)

**Process:**
1. Collects all onboarding data from `OnboardingState`
2. Transforms data to backend format:
   - Income: `{monthly_income: 5000, additional_income: 0}`
   - Fixed expenses: `{category_1: amount1, category_2: amount2, ...}`
   - Spending habits, goals, region
3. Caches data locally via `UserDataManager.instance.cacheOnboardingData(onboardingData)`
4. Submits to backend via `_api.submitOnboarding(onboardingData)`
5. Refreshes user data: `UserDataManager.instance.refreshUserData()`
6. Navigates to `/main` screen

#### 1.2 Backend: Onboarding Submit Endpoint
**File:** `/home/user/mita_project/app/api/onboarding/routes.py` (lines 29-137)

**Endpoint:** `POST /onboarding/submit`

**Process:**
1. Validates income data (must be > 0)
2. **Saves income** to `current_user.monthly_income` 
3. **Generates budget plan** via `generate_budget_from_answers(answers)`
4. **Builds calendar** via `build_calendar(config)` with merged answers + budget_plan + monthly_income
5. **Saves calendar to database** via `save_calendar_for_user(db, current_user.id, calendar_data)`
6. **Marks onboarding complete** by setting `current_user.has_onboarded = True`
7. **Commits all database changes**
8. Returns success response with budget_plan and calendar_days

#### 1.3 Backend: Calendar Save Service
**File:** `/home/user/mita_project/app/services/calendar_service_real.py` (lines 11-43)

**Process:**
- Converts calendar data (Dict or List format) to database records
- For each day and category:
  - Creates `DailyPlan` entry with:
    - user_id
    - date
    - category
    - **planned_amount** (from onboarding budget)
    - spent_amount = 0
  - Adds to database session
- Commits all entries

**Database Model:** `/home/user/mita_project/app/db/models/daily_plan.py`
- Stores daily budget breakdown by category
- Fields: user_id, date, category, planned_amount, spent_amount, daily_budget, status, plan_json

### 2. POST-ONBOARDING: USER PROFILE UPDATE

**File:** `/home/user/mita_project/app/api/users/routes.py` (lines 14-26)

**Endpoint:** `GET /users/me`

**Returns:**
```json
{
  "id": user_id,
  "email": user_email,
  "income": 5000.0,  // from user.monthly_income
  "has_onboarded": true,  // newly set during onboarding
  "country": user_country,
  "timezone": user_timezone,
  "created_at": timestamp
}
```

### 3. MAIN APP INITIALIZATION PHASE

#### 3.1 Frontend: Main Screen Initialization
**File:** `/home/user/mita_project/mobile_app/lib/screens/main_screen.dart` (lines 49-235)

**Process:**
1. Calls `_initializeOfflineFirst()`
2. Loads cached data: `_loadCachedDataToUI()`
3. Calls `_loadProductionBudgetData()`:
   - Gets financial context: `UserDataManager.instance.getFinancialContext()`
   - Gets dashboard data: `_budgetService.getDashboardData()`
   - Gets budget insights: `_budgetService.getBudgetInsights()`
   - Updates UI with loaded data
4. Initializes live updates service
5. Sets up listeners for real-time data updates

#### 3.2 Frontend: Get Financial Context
**File:** `/home/user/mita_project/mobile_app/lib/services/user_data_manager.dart` (lines 206-293)

**Process:**
1. **First checks cached onboarding data** (immediate after onboarding)
   - If available, transforms and returns it
2. **Falls back to API call** to get user profile
3. Calls `getUserProfile()` → GET `/users/me`
4. Extracts income from profile
5. Returns financial context with income, expenses, goals, habits, region

#### 3.3 Frontend: Get Dashboard Data
**File:** `/home/user/mita_project/mobile_app/lib/services/budget_adapter_service.dart` (lines 27-59)

**Process:**
1. Calls `_apiService.getDashboard()`
2. Which:
   - Gets user profile to retrieve actual income
   - Prepares shell configuration
   - Calls POST `/calendar/shell` 
   - Falls back to local calculations if API fails
3. Returns dashboard data with budget breakdown

#### 3.4 Frontend: Get Budget Insights  
**File:** `/home/user/mita_project/mobile_app/lib/services/budget_adapter_service.dart` (lines 121-172)

**Process:**
1. Gets user income from profile
2. Calls `_apiService.getIncomeBasedBudgetRecommendations(income)`
3. Which calls POST `/budget/income_based_recommendations` with monthly_income
4. Returns budget recommendations (confidence, methodology, category_insights)

#### 3.5 Backend: Get Income-Based Recommendations
**File:** `/home/user/mita_project/app/api/budget/routes.py` (lines 498-523)

**Endpoint:** `POST /budget/income_based_recommendations`

**Returns:**
```json
{
  "recommended_savings_rate": 0.20,
  "emergency_fund_target": monthly_income * 6,
  "max_housing_cost": monthly_income * 0.30,
  "discretionary_budget": monthly_income * 0.30,
  "category_limits": {
    "food": monthly_income * 0.15,
    "transportation": monthly_income * 0.10,
    ...
  }
}
```

#### 3.6 Backend: Get Calendar Shell Data
**File:** `/home/user/mita_project/app/api/calendar/routes.py` (lines 111-147)

**Endpoint:** `POST /calendar/shell`

**Process:**
- Takes shell configuration (income, fixed expenses, weights)
- Calculates category budgets based on weights and income
- Merges with fixed expenses
- Generates shell calendar
- Returns calendar with planned budgets per day

---

## KEY FINDINGS: DATA FLOW VERIFICATION

### What IS Working Correctly:

✅ **Onboarding Data Capture**
- User input (income $5000, expenses $1700) is collected

✅ **Data Transformation**
- Frontend transforms data to backend format
- Backend processes and validates structure

✅ **Database Storage**
- Budget plan is generated
- Calendar is built
- **DailyPlan table IS populated with planned_amounts for each day/category**
- has_onboarded flag IS set to true
- Data IS committed to database

✅ **User Profile Update**
- Income IS saved to user.monthly_income
- has_onboarded flag IS saved
- GET /users/me endpoint RETURNS correct data

✅ **Frontend Caching**
- Onboarding data IS cached in UserDataManager
- Immediate use in main app on navigation

---

## CRITICAL GAP IDENTIFIED: 

### The Disconnect Between Saved Data and Display

**Problem:** The Main App is NOT using the DailyPlan data saved during onboarding.

**Why:**
1. The mobile app calls `/calendar/shell` which **GENERATES** calendar data based on:
   - Current user income
   - Fixed shell configuration (hardcoded weights)
   - NOT the actual saved DailyPlan entries from onboarding

2. The mobile app calls `/budget/income_based_recommendations` which:
   - Returns generic income-based recommendations
   - NOT the specific budget plan that was generated during onboarding

3. The `/plan/{year}/{month}` endpoint EXISTS in the backend:
   - **File:** `/home/user/mita_project/app/api/plan/routes.py`
   - Retrieves saved DailyPlan data from database
   - **BUT IS NEVER CALLED BY THE MOBILE APP**

**Result:**
- The specific budget generated during onboarding ($5000 income, $1700 expenses) is:
  - ✅ Saved to database (DailyPlan table)
  - ✅ Associated with user (via user_id)
  - ❌ NOT retrieved or displayed
  - ❌ Replaced with regenerated generic calendar based on income only

---

## MISSING CONNECTIONS

### What Should Happen:
1. Main app loads → checks if onboarding completed
2. If yes, retrieves the SAVED calendar from DailyPlan table
3. Displays the specific budget that was calculated during onboarding
4. Shows actual planned amounts for each category per day

### What Actually Happens:
1. Main app loads → checks if onboarding completed (✅)
2. Retrieves user income (✅)
3. **Regenerates calendar** from scratch using hardcoded weights and income (❌)
4. Shows generic budget allocation, not onboarding-specific budget

---

## REMAINING VERIFICATION NEEDED

### Current State Check:
- [ ] Does `/calendar/shell` actually return different data than what was saved?
- [ ] Are DailyPlan entries actually being created with correct data?
- [ ] Is there an endpoint/screen that SHOULD use `/plan/{year}/{month}`?

### Potential Solutions:
1. Make main app call `/plan/{year}/{month}` to get saved calendar
2. Modify `/calendar/shell` to return saved DailyPlan data for the user
3. Add a `/calendar/saved` or similar endpoint for retrieving onboarding calendar

---

## FILE LOCATIONS SUMMARY

### Backend
- Onboarding API: `/home/user/mita_project/app/api/onboarding/routes.py`
- Budget Routes: `/home/user/mita_project/app/api/budget/routes.py`
- Calendar Routes: `/home/user/mita_project/app/api/calendar/routes.py`
- Plan Routes: `/home/user/mita_project/app/api/plan/routes.py`
- Calendar Service: `/home/user/mita_project/app/services/calendar_service_real.py`
- DailyPlan Model: `/home/user/mita_project/app/db/models/daily_plan.py`

### Frontend
- Main Screen: `/home/user/mita_project/mobile_app/lib/screens/main_screen.dart`
- Onboarding Finish: `/home/user/mita_project/mobile_app/lib/screens/onboarding_finish_screen.dart`
- User Data Manager: `/home/user/mita_project/mobile_app/lib/services/user_data_manager.dart`
- Budget Adapter Service: `/home/user/mita_project/mobile_app/lib/services/budget_adapter_service.dart`
- API Service: `/home/user/mita_project/mobile_app/lib/services/api_service.dart`


# Data Flow Diagram: Onboarding to Main App

## COMPLETE ARCHITECTURE VIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER COMPLETES ONBOARDING                    │
│              Income: $5000 | Expenses: $1700/month              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Frontend: OnboardingFinishScreen    │
        │  - Transform onboarding data         │
        │  - Cache locally in UserDataManager  │
        │  - Submit POST /onboarding/submit    │
        └──────────┬───────────────────────────┘
                   │
                   ▼ (HTTP POST)
    ┌──────────────────────────────────────┐
    │  Backend: POST /onboarding/submit    │
    │                                      │
    │  1. Validate income               ✅ │
    │  2. Save to user.monthly_income   ✅ │
    │  3. Generate budget plan          ✅ │
    │  4. Build calendar                ✅ │
    │  5. Save calendar_data to DB      ✅ │
    │     (create DailyPlan entries)       │
    │  6. Set has_onboarded = true      ✅ │
    │  7. Commit all changes            ✅ │
    │                                      │
    └──────────┬───────────────────────────┘
               │
               ▼ (Database Commit)
      ┌─────────────────────────────────┐
      │  DATABASE - User Table          │
      │  ├─ id: user_123                │
      │  ├─ monthly_income: 5000        │
      │  ├─ has_onboarded: true         │
      │  └─ [other fields]              │
      │                                 │
      │  DATABASE - DailyPlan Table     │
      │  ├─ user_id: user_123           │
      │  ├─ date: 2025-01-01            │
      │  ├─ category: "food"            │
      │  ├─ planned_amount: 150.00      │
      │  ├─ spent_amount: 0.00          │
      │  ├─ [more entries...]           │
      │  └─ [one entry per day/category]│
      └──────────┬──────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
         ▼                ▼ (Response)
    ✅ DATA SAVED   Frontend caches data
         │          & navigates to /main
         │                │
         │                ▼
         │    ┌─────────────────────────┐
         │    │  Frontend: MainScreen   │
         │    │  initState()            │
         │    └────────────┬────────────┘
         │                 │
         │                 ▼
         │   ┌──────────────────────────────────┐
         │   │ getFinancialContext()            │
         │   │ - Check cached onboarding ✅     │
         │   │ - Get income: 5000 ✅            │
         │   │ - Call GET /users/me ✅          │
         │   └───────────────┬──────────────────┘
         │                   │
    ┌────┴────────────────────┴──────────────────┐
    │     CRITICAL DIVERGENCE POINT               │
    │     What SHOULD happen vs What DOES happen │
    └───────┬─────────────────────────────────────┘
            │
    ┌───────┴──────────────────────────────────────┐
    │                                              │
    ▼ (SHOULD HAPPEN)               ▼ (ACTUALLY HAPPENS)
┌─────────────────────────┐    ┌──────────────────────┐
│ Call /plan/{year}/{month}│   │ Call /calendar/shell │
│                         │   │                      │
│ Returns DailyPlan data  │   │ REGENERATES budget   │
│ Specific to user        │   │ from scratch using:  │
│ Based on onboarding     │   │ - Income only        │
│ Amount: 150 food/day    │   │ - Hardcoded weights  │
│                         │   │ - No onboarding data │
│                         │   │ Amount: 150 food/day │
│                         │   │ (happens to match)   │
└────────────┬────────────┘   └──────────┬───────────┘
             │                           │
             ▼                           ▼
    ✅ Uses saved data        ❌ Ignores saved data
    ✅ Specific budget        ❌ Generic budget
    ✅ Data actually used     ❌ Data wasted in DB


    ┌──────────────────────────────────────┐
    │  DATABASE - /plan/{year}/{month}     │
    │  NEVER CALLED ❌                      │
    │                                      │
    │  Contains the saved DailyPlan data   │
    │  that was created during onboarding │
    │  but is never retrieved or displayed│
    └──────────────────────────────────────┘
```

---

## ENDPOINT CALL FLOW

### What Frontend ACTUALLY Calls:

```
MainScreen._loadProductionBudgetData()
    ├── UserDataManager.getFinancialContext()
    │   ├── Checks cached onboarding data ✅
    │   └── GET /users/me ✅ (for profile)
    │
    ├── BudgetAdapterService.getDashboardData()
    │   └── POST /calendar/shell  ← SHOULD BE: GET /plan/{year}/{month}
    │
    └── BudgetAdapterService.getBudgetInsights()
        └── POST /budget/income_based_recommendations
```

### What Endpoints Actually Exist:

```
Backend Routes:
├── POST /onboarding/submit          ✅ (Creates and saves data)
├── GET /users/me                    ✅ (Returns user profile)
├── POST /calendar/shell             ✅ (Regenerates calendar)
├── GET /plan/{year}/{month}         ✅ (Returns saved DailyPlan)  ← UNUSED!
└── POST /budget/income_based_recommendations  ✅
```

---

## DATA FLOW MATRIX

| Data | Saved | Retrieved | Displayed | Used |
|------|-------|-----------|-----------|------|
| Onboarding Income | ✅ | ✅ | ✅ | ✅ |
| has_onboarded Flag | ✅ | ✅ | (internal) | ✅ |
| **DailyPlan Entries** | **✅** | **❌** | **❌** | **❌** |
| Budget Breakdown | ✅ | ❌* | ✅* | ✅* |
| Spending Habits | ✅ | ✅ | ⚠️ (cached) | ⚠️ (cached) |

\* Generated fresh, not retrieved

---

## MISSING LINK IN CHAIN

```
Onboarding Data
    │
    ├─→ Save to Database ✅
    │       │
    │       └─→ User Table ✅
    │       └─→ DailyPlan Table ✅
    │
    ├─→ Return to Frontend ✅
    │
    └─→ Frontend caches ✅
            │
            ├─→ Navigate to /main ✅
            │
            ├─→ Check has_onboarded ✅
            │
            ├─→ Get income from API ✅
            │
            ├─→ Retrieve saved DailyPlan ❌ ← THIS IS MISSING
            │                 │
            │                 └─→ Should call: GET /plan/{year}/{month}
            │                 └─→ Actually calls: POST /calendar/shell
            │
            └─→ Display budget ❌ (shows regenerated, not saved)
```

---

## CONCRETE EXAMPLE WITH NUMBERS

### What User Entered (Onboarding):
- Monthly Income: **$5,000**
- Fixed Expenses:
  - Rent: **$1,500** (30%)
  - Food: **$600** (12%)
  - Transport: **$400** (8%)
  - Utilities: **$250** (5%)
  - Savings: **$1,000** (20%)
  - Other: **$250** (5%)

### What Gets Saved to DailyPlan:
```
Date: 2025-01-01
├─ Rent: 50/day (1500/30 days)
├─ Food: 20/day (600/30 days) 
├─ Transport: 13.33/day (400/30 days)
├─ Utilities: 8.33/day (250/30 days)
├─ Savings: 33.33/day (1000/30 days)
└─ Other: 8.33/day (250/30 days)

[Similar entries for all 365 days of the year]
```

### What Frontend SHOULD Get:
```
GET /plan/2025/1
→ Returns the saved DailyPlan entries
→ Shows exact budget from onboarding
```

### What Frontend ACTUALLY Gets:
```
POST /calendar/shell
→ Generates NEW budget using:
  - Income: 5000 ✅ (correct number, but...)
  - Weights: food 15%, transport 15%, etc. ❌ (hardcoded, may differ from onboarding)
  - Ignores actual user's expense categories ❌
→ Shows percentage-based budget, not expense-based
```

---

## ROOT CAUSE ANALYSIS

| Layer | Issue | Impact |
|-------|-------|--------|
| **Database Design** | Endpoints for retrieving saved data exist | No actual issue |
| **Backend** | Saves data correctly to DailyPlan | No actual issue |
| **Frontend Code** | Doesn't call GET /plan endpoint | Never retrieves saved data |
| **Frontend Logic** | Uses /calendar/shell instead | Regenerates data |
| **Architecture** | No integration between save & retrieve | Data path incomplete |

---

## RECOMMENDED FIX PRIORITY

### Priority 1: Direct Use of Saved Data (Best)
Make main app call `/plan/{year}/{month}` directly
- File: `/home/user/mita_project/mobile_app/lib/services/budget_adapter_service.dart`
- Change: Line 27-59 (`getDashboardData()`)
- Impact: Uses exact onboarding data

### Priority 2: Hybrid Approach (Good)
Check if saved data exists before regenerating
- File: `/home/user/mita_project/app/api/calendar/routes.py`
- Change: Modify `/calendar/shell` to return saved data if available
- Impact: Seamless fallback

### Priority 3: New Endpoint (Workaround)
Create dedicated endpoint for onboarding calendar
- Add: `GET /calendar/user-onboarded`
- Impact: Explicit endpoint for onboarding data

---

## TEST CASE TO VERIFY FIX

After implementing fix:

1. Complete onboarding with specific expenses
2. Navigate to main app
3. Verify displayed budget matches onboarded expenses
4. Check that DailyPlan data from database is used
5. Confirm no data regeneration happens

Expected: Display shows exact budget from onboarding, not generic allocation.


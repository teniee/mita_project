# END-TO-END FLOW VERIFICATION - EXECUTIVE SUMMARY

## Status: PARTIAL SUCCESS - Critical Gap Identified

### The Flow That WORKS:

**Onboarding → Database → User Profile** ✅

```
1. User completes onboarding with income=$5000, expenses=$1700
   ↓
2. Frontend caches data locally
   ↓
3. Backend receives POST /onboarding/submit
   ↓
4. Backend saves income to user.monthly_income (5000) ✅
   ↓
5. Backend generates budget plan ✅
   ↓
6. Backend builds calendar ✅
   ↓
7. Backend saves calendar entries to DailyPlan table ✅
   ↓
8. Backend sets has_onboarded = true ✅
   ↓
9. Backend commits all database changes ✅
   ↓
10. Frontend navigates to /main ✅
    ↓
11. Backend returns user income via GET /users/me ✅
```

### The Flow That BREAKS:

**Database → Main App Display** ❌

```
11. Main App loads MainScreen
    ↓
12. Calls getFinancialContext() 
    - Checks cached onboarding data (has it) ✅
    - Extracts income (5000) ✅
    ↓
13. Calls getDashboardData()
    ↓
14. Calls POST /calendar/shell
    - Takes income (5000) ✅
    - Uses hardcoded weights and shell config ❌
    - REGENERATES budget from scratch ❌
    - IGNORES saved DailyPlan entries ❌
    ↓
15. Main app shows generic calendar budget
    - NOT the specific budget from onboarding ❌
    - NOT the DailyPlan data from database ❌
```

---

## THE CRITICAL GAP

### What Was Saved:
- DailyPlan table has entries with planned budgets for each day/category
- These were calculated based on the specific income ($5000) and expenses ($1700)
- Database has complete budget breakdown from onboarding

### What Gets Displayed:
- Generic calendar based on income percentage allocations
- Hardcoded weight distribution (food 15%, transport 15%, etc.)
- NO connection to the actual saved DailyPlan data

### Why This Happens:
1. Mobile app calls `/calendar/shell` endpoint instead of `/plan/{year}/{month}`
2. `/calendar/shell` is designed to generate shell calendars on-the-fly
3. `/plan` endpoint exists but is never called by the mobile app
4. The saved onboarding data is completely bypassed

---

## PROOF

### Backend Endpoint That SAVES Data:
**File:** `/home/user/mita_project/app/api/onboarding/routes.py` (lines 108)
```python
save_calendar_for_user(db, current_user.id, calendar_data)
```

### Backend Endpoint That EXISTS to RETRIEVE Data:
**File:** `/home/user/mita_project/app/api/plan/routes.py` (line 14)
```python
@router.get("/{year}/{month}", response_model=dict)
async def plan_month(...)
```
Returns: `{row.date.day: row.plan_json for row in rows}`

### Frontend Endpoint Actually Called:
**File:** `/home/user/mita_project/mobile_app/lib/services/api_service.dart` (line 682)
```dart
final response = await _dio.post('/calendar/shell', ...)
```

### Frontend Endpoint NEVER Called:
```
/plan/{year}/{month}  <-- Never called by mobile app
```

---

## SPECIFIC ISSUES

### 1. Data Saving WORKS
- `DailyPlan` entries ARE created with correct user_id, date, category, planned_amount
- Data IS persisted to database
- `has_onboarded` flag IS set

### 2. Data Retrieval BROKEN
- Main app does NOT call `/plan/{year}/{month}`
- Main app calls `/calendar/shell` instead which generates NEW data
- Saved `DailyPlan` data is orphaned in database

### 3. Display INCORRECT
- Shows generic budget allocation percentages
- Does NOT show user-specific budget from onboarding
- User sees calculated budget, not planned budget

---

## WHAT THIS MEANS

When a user completes onboarding with:
- **Income: $5000**
- **Expenses: Food $200, Rent $1500, etc.**

The app:
1. ✅ Saves this specific data to the database
2. ✅ Marks user as onboarded
3. ❌ Never displays this specific data
4. ❌ Shows generic income-based percentages instead

**Result:** Onboarding data is saved but never used!

---

## REQUIRED FIXES

### Option A: Use Saved Data (Recommended)
Make main app retrieve saved DailyPlan:
```dart
// In BudgetAdapterService.getDashboardData()
// Instead of: _apiService.getDashboard()
// Call: _apiService.getPlanForMonth(year, month)
```

### Option B: Store Onboarding Data Reference
Modify `/calendar/shell` to check if user has saved DailyPlan and return that instead of regenerating.

### Option C: Create New Endpoint
Add `/calendar/user-onboarding` endpoint that returns saved DailyPlan entries.

---

## VERIFICATION CHECKLIST

- [x] Onboarding data is captured correctly
- [x] Backend receives and validates data
- [x] Income is saved to user profile
- [x] Calendar is generated correctly
- [x] DailyPlan entries are created
- [x] has_onboarded flag is set
- [x] Database commits successfully
- [x] User can navigate to /main
- [x] User profile returns has_onboarded=true
- [x] User profile returns income=5000
- [x] Frontend caches onboarding data
- [x] Main app detects has_onboarded flag
- [x] Main app retrieves user income
- ❌ Main app retrieves saved DailyPlan entries
- ❌ Main app displays saved budget breakdown
- ❌ Calendar shows onboarding-specific budget

---

## FILE REFERENCES

### Complete Flow Trace:
`/home/user/mita_project/END_TO_END_FLOW_TRACE.md`

### Key Files:
- Backend Onboarding: `/home/user/mita_project/app/api/onboarding/routes.py`
- Backend Plan Retrieval: `/home/user/mita_project/app/api/plan/routes.py` 
- Frontend Main Screen: `/home/user/mita_project/mobile_app/lib/screens/main_screen.dart`
- Frontend Calendar Data: `/home/user/mita_project/mobile_app/lib/services/budget_adapter_service.dart`


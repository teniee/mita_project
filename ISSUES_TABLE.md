# 📊 MITA Finance Mobile App - Issues Table

**Date:** January 20, 2026
**Test Duration:** 9 minutes
**Total Issues Found:** 8 Critical

---

## CRITICAL ISSUES TABLE

| # | Issue | Severity | Screen | File Location | Line | Status | User Impact |
|---|-------|----------|--------|---------------|------|--------|-------------|
| 1 | Onboarding data not saved | 🔴 P0 | All | **UNKNOWN - NEEDS INVESTIGATION** | - | 🔴 BROKEN | User loses all setup data |
| 2 | Fake calendar data shown | 🔴 P0 | Calendar | `/mobile_app/lib/services/calendar_fallback_service.dart` | 13-107 | 🔴 ACTIVE | Shows $1784 budget, $851 spent (fake) |
| 3 | Fake goals data shown | 🔴 P0 | Goals | `/mobile_app/lib/providers/goals_provider.dart` | 460-476 | 🔴 ACTIVE | Shows $1250/$5000 fake goal |
| 4 | Fake insights data shown | 🔴 P0 | Insights | **NEEDS INVESTIGATION** | - | 🔴 ACTIVE | Shows fake AI analysis |
| 5 | Add Expense button broken | 🔴 P0 | Home | **NEEDS INVESTIGATION** | - | 🔴 BROKEN | Cannot add transactions |
| 6 | Session expired during onboarding | 🟠 P1 | Onboarding | **NEEDS INVESTIGATION** | - | 🔴 ACTIVE | Shows before session exists |
| 7 | Generic "Server error" banner | 🟠 P1 | All | **NEEDS INVESTIGATION** | - | 🔴 ACTIVE | No context, misleading |
| 8 | Habits screen fails to load | 🟠 P1 | Habits | Backend API | - | 🔴 BROKEN | Returns error |

---

## FILES THAT NEED FIXING

### 🔴 Confirmed Issues (Fix These First)

```
/Users/mikhail/mita_project/mobile_app/
├── lib/
│   ├── services/
│   │   ├── calendar_fallback_service.dart    [FIX LINE 13-107]
│   │   │   └── generateFallbackCalendarData() - Remove or disable
│   │   └── api_service.dart                   [CHECK LINE 1274-1276]
│   │       └── Calls fallback service too early
│   └── providers/
│       └── goals_provider.dart                [FIX LINE 460-476]
│           └── _getSampleGoals() - Remove sample data
```

### 🟡 Need Investigation

```
/Users/mikhail/mita_project/mobile_app/
├── lib/
│   ├── screens/
│   │   ├── *onboarding*.dart                  [FIND & FIX]
│   │   │   └── Missing API call to save onboarding data
│   │   ├── home_screen.dart                   [FIND & FIX]
│   │   │   └── Add Expense button handler broken
│   │   └── insights_screen.dart               [FIND & FIX]
│   │       └── Showing fake AI analysis
│   └── services/
│       └── session_service.dart or auth_*.dart [FIND & FIX]
│           └── Session validation running too early
```

---

## BACKEND API STATUS

| Endpoint | Method | URL | Status | Response |
|----------|--------|-----|--------|----------|
| Health | GET | `/health` | ✅ 200 OK | `{"status":"healthy"}` |
| Register | POST | `/api/auth/register` | ✅ 201 Created | Returns access_token |
| Login | POST | `/api/auth/login` | ✅ Assumed Working | Not tested |
| Onboarding | POST | `/api/v1/users/onboarding` | ❓ Unknown | Not tested |
| Calendar | GET | `/api/v1/calendar` | ❓ Unknown | Mobile app using fallback |
| Goals | GET | `/api/v1/goals` | ❓ Unknown | Mobile app using fallback |
| Habits | GET | `/api/v1/habits` | 🔴 Error | Returns error |
| Transactions | POST | `/api/v1/transactions` | ❓ Unknown | Add Expense broken |

---

## TEST RESULTS BY SCREEN

| Screen | Data Source | Expected | Actual | Pass/Fail |
|--------|-------------|----------|--------|-----------|
| **Onboarding** |
| Step 1 (Location) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 2 (Income) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 3 (Expenses) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 4 (Goals) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 5 (Habits) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 6 (Bad Habits) | User Input | Save to backend | UI works, save unknown | ⚠️ PARTIAL |
| Step 7 | - | Complete & save | Shows "Session expired" | 🔴 FAIL |
| **Home** |
| Balance | Backend API | $0.00 or real | $0.00 (data lost) | ⚠️ PARTIAL |
| Budget Targets | Backend API | Empty or real | "No budget targets" | ⚠️ PARTIAL |
| This Week | Backend API | Empty or real | All green (questionable) | ⚠️ PARTIAL |
| Add Expense | Button Handler | Opens form | Does nothing | 🔴 FAIL |
| **Calendar** |
| Overview | Backend API | Empty or real | $1784/$851 FAKE DATA | 🔴 FAIL |
| Daily Status | Backend API | Empty or real | 28 green, 3 orange FAKE | 🔴 FAIL |
| **Goals** |
| Goals List | Backend API | Empty or real | $1250/$5000 FAKE GOAL | 🔴 FAIL |
| **Insights** |
| Health Score | Backend API | Empty or real | 50/100 Grade C FAKE | 🔴 FAIL |
| AI Analysis | Backend API | Empty or real | Fake analysis text | 🔴 FAIL |
| **Habits** |
| Habits List | Backend API | Empty or real | ERROR: Failed to load | 🔴 FAIL |
| **Mood** |
| Mood Check-in | User Input | Empty state | Proper empty state | ✅ PASS |

---

## FAKE DATA EXAMPLES

### Calendar Screen
```
Total Budget: $1784 (FAKE)
Spent: $851 (FAKE)
Remaining: $933 (FAKE)
"31 days tracked" (FAKE - account 30 seconds old)
```

**Source:** `calendar_fallback_service.dart` line 13-107

---

### Goals Screen
```
Emergency Fund
Build a 3-month emergency fund
$1250 of $5000 (25%)
$3750 remaining
```
**All FAKE** - Source: `goals_provider.dart` line 463-468

---

### Insights Screen
```
Financial Health Score: 50/100 Grade: C (FAKE)

AI Financial Analysis (FAKE):
"Your spending patterns show good discipline with
occasional room for improvement. You're doing well
with food budgeting but could optimize transportation costs."
```
**Source:** Unknown insights provider

---

## ERROR MESSAGES ENCOUNTERED

| Error | When | Screen | User Sees |
|-------|------|--------|-----------|
| "Your session has expired. Please log in again to continue." | After Step 6 of onboarding | Onboarding | Red text, Retry/Create Account buttons |
| "Server error. Please try again later" | After registration | All screens | Red banner at bottom |
| "Failed to load habits. Please try again." | Opening Habits tab | Habits | Red icon, Try Again button |
| (Silent failure) | Tapping Add Expense | Home | Nothing happens |

---

## FIX VERIFICATION MATRIX

After implementing fixes, verify each cell is ✅:

| Issue | Fix Applied | Test Passed | User Impact Resolved |
|-------|-------------|-------------|---------------------|
| Onboarding data not saved | [ ] | [ ] | [ ] |
| Fake calendar data | [ ] | [ ] | [ ] |
| Fake goals data | [ ] | [ ] | [ ] |
| Fake insights data | [ ] | [ ] | [ ] |
| Add Expense broken | [ ] | [ ] | [ ] |
| Session expired | [ ] | [ ] | [ ] |
| Generic error banner | [ ] | [ ] | [ ] |
| Habits screen error | [ ] | [ ] | [ ] |

---

## SEARCH COMMANDS TO FIND ISSUES

```bash
cd /Users/mikhail/mita_project/mobile_app

# Find onboarding files
find lib -name "*onboarding*.dart" -type f

# Find where "session expired" is triggered
grep -r "session has expired\|session.*expired" lib --include="*.dart"

# Find Add Expense button handler
grep -r "Add Expense" lib --include="*.dart"
grep -B10 -A10 "Add Expense" lib/screens/home_screen.dart

# Find insights fake data
grep -r "Financial Health Score\|50.*100" lib --include="*.dart"
grep -r "food budgeting\|transportation costs" lib --include="*.dart"

# Find onboarding save/complete functions
grep -r "completeOnboarding\|saveOnboarding\|submitOnboarding" lib --include="*.dart"

# Find session validation
grep -r "validateSession\|checkSession\|isSessionValid" lib --include="*.dart"
```

---

## PRIORITY MATRIX

```
HIGH IMPACT, HIGH URGENCY (P0 - Fix Today):
┌────────────────────────────────────────┐
│ 1. Onboarding data not saved           │
│ 2. Fake calendar data                  │
│ 3. Fake goals data                     │
│ 4. Add Expense button broken           │
└────────────────────────────────────────┘

HIGH IMPACT, MEDIUM URGENCY (P1 - Fix This Week):
┌────────────────────────────────────────┐
│ 5. Fake insights data                  │
│ 6. Session expired during onboarding   │
│ 7. Generic error banner                │
└────────────────────────────────────────┘

MEDIUM IMPACT (P2 - Fix Soon):
┌────────────────────────────────────────┐
│ 8. Habits screen error                 │
└────────────────────────────────────────┘
```

---

## TEST ARTIFACTS LOCATION

All screenshots saved to: `/Users/mikhail/Downloads/`

```
phase1_initial_launch_onboarding.png
phase2_step1_california_selected.png
phase2_step2_income.png
phase2_step2_welcome_dialog.png
phase2_step3_fixed_expenses.png
phase2_step4_financial_goals.png
phase2_step5_spending_habits.png
phase2_step6_bad_habits.png
BUG1_session_expired_during_onboarding.png
phase2_registration_screen.png
BUG2_main_screen_server_error.png
BUG3_calendar_fake_data.png
BUG4_goals_fake_data.png
BUG5_insights_fake_data.png
BUG6_habits_failed_to_load.png
BUG7_mood_tab_working.png
TEST_onboarding_restart.png
```

---

## RELATED DOCUMENTATION

- Full Report: `/Users/mikhail/mita_project/COMPREHENSIVE_E2E_DEBUG_REPORT_2026-01-20.md`
- Critical Summary: `/Users/mikhail/mita_project/CRITICAL_ISSUES_SUMMARY.md`
- Quick Fix Guide: `/Users/mikhail/mita_project/QUICK_FIX_GUIDE.md`
- This Table: `/Users/mikhail/mita_project/ISSUES_TABLE.md`

---

**Status:** 🔴 8 Critical Issues Found
**Impact:** 🔴 App Unusable for Real Users
**Action:** 🔴 P0 Fixes Required Before Production Launch


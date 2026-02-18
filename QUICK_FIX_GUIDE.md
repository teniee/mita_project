# 🔧 QUICK FIX GUIDE - MITA Finance Mobile App

**Last Updated:** January 20, 2026
**Priority:** P0 - Production Critical

---

## 🎯 THE 3 FILES YOU NEED TO FIX

### 1️⃣ `/Users/mikhail/mita_project/mobile_app/lib/services/calendar_fallback_service.dart`

**Problem:** Generates fake calendar data ($1784 budget, $851 spent, 31 days tracked)

**Line 13-107:** `generateFallbackCalendarData()` function

**Fix Option A (Quick):** Disable in production
```dart
Future<List<Map<String, dynamic>>> generateFallbackCalendarData({...}) async {
  // PRODUCTION FIX: Never show fake data
  if (environment == 'production') {
    return []; // Return empty instead of fake data
  }
  // ... rest of existing code for development
}
```

**Fix Option B (Better):** Remove entirely and show proper empty states in UI

---

### 2️⃣ `/Users/mikhail/mita_project/mobile_app/lib/providers/goals_provider.dart`

**Problem:** Shows fake emergency fund goal ($1250 saved toward $5000)

**Line 460-476:** `_getSampleGoals()` function

**Fix:** Remove sample goals in production
```dart
List<Goal> _getSampleGoals() {
  // PRODUCTION FIX: Never show fake goals
  if (environment == 'production') {
    return []; // Return empty instead of fake data
  }

  // Development only:
  return [
    Goal(
      id: '1',
      title: 'Emergency Fund',
      targetAmount: 5000,
      savedAmount: 1250,
      // ... rest of fake data
    ),
  ];
}
```

---

### 3️⃣ **FIND THIS FILE:** Onboarding Data Persistence

**Problem:** Onboarding data (income $5000, rent $1500, goals) not saved

**Need to find:** Where onboarding completion should call API

**Search for:**
```bash
grep -r "onboarding" mobile_app/lib --include="*.dart"
grep -r "completeOnboarding\|saveOnboarding\|submitOnboarding" mobile_app/lib --include="*.dart"
```

**Expected API call:**
```dart
// Should exist somewhere but missing or broken:
Future<void> saveOnboardingData() async {
  final response = await apiService.post(
    '/api/v1/users/onboarding',
    data: {
      'location': selectedState,
      'monthly_income': monthlyIncome,
      'fixed_expenses': fixedExpenses,
      'financial_goals': selectedGoals,
      'spending_habits': spendingHabits,
      'bad_habits': badHabits,
    },
  );
}
```

---

## 🔍 HOW TO FIND THE ISSUES

### Find Onboarding Persistence Code
```bash
cd /Users/mikhail/mita_project/mobile_app

# Find onboarding files
find lib -name "*onboarding*.dart"

# Find where onboarding completes
grep -r "Step 7 of 7" lib
grep -r "onboarding.*complete" lib --include="*.dart"

# Find API calls in onboarding
grep -r "apiService\|api_service" lib/screens/*onboarding*.dart
```

### Find Add Expense Button Handler
```bash
# Find Add Expense button
grep -r "Add Expense" lib --include="*.dart"

# Find button onTap handler
grep -B5 -A5 "Add Expense" lib/screens/home_screen.dart
```

### Find Session Expiry Logic
```bash
# Find session expired message
grep -r "session has expired\|session.*expired" lib --include="*.dart"

# Find where it's triggered
grep -r "checkSession\|validateSession" lib --include="*.dart"
```

---

## 🧪 HOW TO TEST THE FIXES

### Test Onboarding Data Persistence
```bash
# 1. Uninstall app from simulator
xcrun simctl uninstall AD534ABE-9A47-46E8-8001-F88586F07655 finance.mita.app

# 2. Rebuild and install
cd /Users/mikhail/mita_project/mobile_app
flutter run

# 3. Complete onboarding with test data:
# - Location: California
# - Income: $5000
# - Rent: $1500
# - Goal: Emergency fund

# 4. After registration, verify:
# - Balance shows calculated amount (not $0.00)
# - Budget targets appear
# - Goals show the selected goal
# - NO fake data ($1784, $851, $1250)
```

### Test Backend API Directly
```bash
# Verify backend is healthy
curl https://mita-production-production.up.railway.app/health

# Test registration
curl -X POST https://mita-production-production.up.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test_'$(date +%s)'@mita.finance",
    "password": "Test@Pass123",
    "country": "US"
  }'

# Should return 201 with access_token and user data
```

---

## 📋 VERIFICATION CHECKLIST

After fixes, test this exact flow:

- [ ] Fresh app install
- [ ] Complete onboarding Step 1: Select California
- [ ] Complete onboarding Step 2: Enter $5000 income
- [ ] Complete onboarding Step 3: Enter $1500 rent
- [ ] Complete onboarding Step 4: Select "Emergency fund" goal
- [ ] Complete onboarding Step 5: Set spending habits
- [ ] Complete onboarding Step 6: Select bad habit
- [ ] Complete onboarding Step 7: Should save data here
- [ ] Create account with unique email
- [ ] Verify Home screen shows:
  - [ ] Balance > $0.00 (based on income/expenses)
  - [ ] Budget targets appear
  - [ ] NO $1784 fake budget
- [ ] Verify Calendar screen shows:
  - [ ] Real budget based on $5000 income
  - [ ] NO $1784/$851 fake data
- [ ] Verify Goals screen shows:
  - [ ] Emergency fund goal (user created)
  - [ ] NO $1250/$5000 fake goal
- [ ] Tap "+ Add Expense" button
  - [ ] Form should open
  - [ ] Should NOT do nothing
- [ ] No "Server error" banner
- [ ] No "Session expired" during onboarding

---

## 🚨 COMMON PITFALLS

### ❌ Don't Do This
```dart
// BAD: Silently falling back to fake data
try {
  data = await apiService.getCalendar();
} catch (e) {
  data = fallbackService.getFakeData(); // User thinks it's real!
}
```

### ✅ Do This Instead
```dart
// GOOD: Show error or empty state
try {
  data = await apiService.getCalendar();
} catch (e) {
  logError('Calendar API failed', error: e);
  data = []; // Empty state
  showError('Unable to load calendar. Please try again.');
}
```

---

## 🔗 RELATED FILES

### Configuration
- `/Users/mikhail/mita_project/mobile_app/lib/config_clean.dart` - Backend URL config ✅ (correct)

### Services
- `/Users/mikhail/mita_project/mobile_app/lib/services/api_service.dart` - API calls (line 1274-1276 calls fallback)
- `/Users/mikhail/mita_project/mobile_app/lib/services/calendar_fallback_service.dart` - Fake calendar data 🔴
- `/Users/mikhail/mita_project/mobile_app/lib/services/income_service.dart` - Income classification

### Providers
- `/Users/mikhail/mita_project/mobile_app/lib/providers/goals_provider.dart` - Fake goals 🔴

### Screens (need to find)
- `lib/screens/*onboarding*.dart` - Onboarding flow
- `lib/screens/home_screen.dart` - Home screen with Add Expense button

---

## 📞 NEED HELP?

### Debug Logs
```bash
# View Flutter logs
flutter logs

# View simulator logs
xcrun simctl spawn AD534ABE-9A47-46E8-8001-F88586F07655 log stream --predicate 'process == "Runner"'
```

### Backend Logs
Check Railway dashboard for backend logs:
https://railway.app (login required)

### Test Account
If you need to test with the account created during debugging:
- Email: debug_1768943856@mita.finance
- Password: Test@Pass123
- User ID: 05270418-d0a5-4bf3-a6f1-8d8950e90172

---

## 📊 SUCCESS METRICS

### Before Fixes
- ❌ 8 major bugs
- ❌ Fake data on 3 screens
- ❌ Onboarding data lost
- ❌ Core features broken
- 🔴 User trust: LOW

### After Fixes
- ✅ Real data only
- ✅ Onboarding data persists
- ✅ Add Expense works
- ✅ No fake data
- ✅ Clear error messages
- 🟢 User trust: HIGH

---

**Fix these 3 things and the app will actually work!**


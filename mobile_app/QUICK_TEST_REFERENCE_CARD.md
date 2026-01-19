# MITA E2E Test - Quick Reference Card
**Date:** 2026-01-19 | **Test Duration:** ~1 hour | **Test ID:** e2e_final_jan19

---

## ⚠️ BEFORE YOU START: REBUILD REQUIRED ⚠️

```bash
cd /Users/mikhail/mita_project/mobile_app
flutter clean && flutter pub get && flutter build ios --release
```

**Why?** Commits ccf7acf and 3b81998 modified Flutter code. Current deployed app has old code.

---

## 📋 PHASE 1: REGISTRATION (~10 min)

**Credentials:** test+final@mita.finance / MitaTest@Pass123

**Steps:**
1. Launch app → Grant permissions
2. Tap "Sign Up" → Enter credentials
3. Tap "Register" → **Should complete in <10 seconds** (no hang!)
4. Complete 7 onboarding steps:
   - Name: Final Test User
   - Currency: USD
   - Income: $5000
   - Categories: Use defaults
   - Goals: Skip or add
   - Notifications: Enable
5. Verify dashboard loads

**✅ Success Criteria:**
- No indefinite loading spinner (Fix #2 test)
- Password accepted (Fix #1 already verified)
- Reach dashboard

**📸 Screenshots:** 11 total

---

## 📋 PHASE 2: ALL 10 CATEGORIES (~20 min)

**For EACH category below:**
1. Tap "+" → Enter amount → Select category → Add description → Tap "Save"
2. Verify: No error, success message, appears in dashboard

| # | Category | Amount | Description |
|---|----------|--------|-------------|
| 1 | Food & Dining | $12.50 | Coffee test |
| 2 | Transportation | $45.00 | Gas test |
| 3 | Health & Fitness | $30.00 | Gym test |
| 4 | Entertainment | $25.00 | Movie test |
| 5 | Shopping | $80.00 | Clothes test |
| 6 | Bills & Utilities | $150.00 | Electric bill |
| 7 | Education | $60.00 | Course test |
| 8 | Travel | $200.00 | Flight test |
| 9 | Personal Care | $35.00 | Haircut test |
| 10 | Other | $15.00 | Misc test |

**Total:** $652.50

**✅ Success Criteria:**
- All 10 save successfully (no errors = Fix #3 working!)
- All appear in dashboard
- Total matches $652.50

**📸 Screenshots:** 10 total (one per category)

---

## 📋 PHASE 3: VERIFICATION (~10 min)

**Quick Checks:**
- [ ] Dashboard shows 10 transactions
- [ ] Total: $652.50
- [ ] Remaining: $4,347.50 (from $5000)
- [ ] Calendar shows today's expenses
- [ ] Category breakdown correct
- [ ] Habits screen loads (may fail - known issue)
- [ ] Profile shows "Final Test User"

**📸 Screenshots:** 8 total

---

## ✅ SUCCESS CRITERIA

**Fix #1 (Password):** ✅ ALREADY VERIFIED
- Backend accepts "MitaTest@Pass123" (contains "123")

**Fix #2 (Health Endpoint):** 🎯 TEST TODAY
- Registration completes without hanging
- No SYSTEM_8001 error
- Time: <10 seconds

**Fix #3 (Category Mapping):** 🎯 TEST TODAY
- All 10 categories save successfully
- No validation errors
- Dashboard shows all transactions

**Overall:** 12/12 tests pass = ✅ **APP STORE READY**

---

## 📸 SCREENSHOT CHECKLIST (29 total)

**Phase 1 (11):**
- [ ] initial_launch.png
- [ ] permissions_granted.png
- [ ] registration_form.png
- [ ] registration_success.png
- [ ] onboarding_step2.png (name)
- [ ] onboarding_step3_currency.png
- [ ] onboarding_step4_income.png
- [ ] onboarding_step5_categories.png
- [ ] onboarding_step6_goals.png
- [ ] onboarding_step7_notifications.png
- [ ] dashboard_initial.png

**Phase 2 (10):**
- [ ] test1_food_dining.png through test10_other.png

**Phase 3 (8):**
- [ ] dashboard_final_verification.png
- [ ] calendar_final_verification.png
- [ ] category_breakdown.png
- [ ] transaction_history.png
- [ ] budget_status.png
- [ ] habits_screen_final.png
- [ ] insights_screen_final.png
- [ ] profile_settings.png

---

## 🐛 IF ISSUES FOUND

**Registration hangs again:**
```bash
# Check health endpoint
curl https://mita-production-production.up.railway.app/health
# Should return: {"status":"healthy"...}

# Verify mobile app config shows '/health' not '/api/health'
# Check: lib/config.dart line 18
```

**Category save fails:**
```bash
# Check which category failed
# Verify error message from backend
# Check Railway logs: railway logs --tail 50
# Look for validation errors
```

**Unexpected behavior:**
- Screenshot the error
- Note exact steps to reproduce
- Check backend logs
- Document in final report

---

## 📊 QUICK MATH CHECK

**Budget Verification:**
- Income: $5,000.00
- Spent: $652.50
- Remaining: $4,347.50
- Percentage: 13.05% spent

**Category Breakdown:**
- Travel: $200 (30.7%) - Largest
- Bills: $150 (23.0%)
- Shopping: $80 (12.3%)
- Education: $60 (9.2%)
- Transportation: $45 (6.9%)
- Personal Care: $35 (5.4%)
- Health: $30 (4.6%)
- Entertainment: $25 (3.8%)
- Other: $15 (2.3%)
- Food: $12.50 (1.9%) - Smallest

---

## 🔧 BACKEND QUICK CHECKS

**Health Check:**
```bash
curl -s https://mita-production-production.up.railway.app/health | jq .
```
Expected: `"status":"healthy"`

**Registration Test (bypass UI):**
```bash
curl -X POST https://mita-production-production.up.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test+verify@mita.finance","password":"MitaTest@Pass123"}'
```
Expected: `"success":true`

---

## 📝 FINAL REPORT TEMPLATE

**Success Rate:** ____ / 12 tests passed (____%)

**Fix Results:**
- Fix #1 (Password): ✅ PASS
- Fix #2 (Health): ✅ PASS / ❌ FAIL
- Fix #3 (Categories): ✅ PASS / ❌ FAIL (__ /10 categories)

**App Store Ready?** ✅ YES / ❌ NO / ⚠️ CONDITIONAL

**Issues Found:** ______________________________

**Time Taken:** ______ minutes

**Tester:** ______________________________

---

## 🚀 TESTING TIPS

1. **Take screenshots at EVERY step** - easier to capture too many than miss one
2. **Test categories in order** - helps track progress
3. **Verify each expense before moving on** - don't batch test
4. **Note exact error messages** - helps debugging
5. **Check backend logs if stuck** - Railway dashboard
6. **Use today's date for all expenses** - easier to verify in calendar
7. **Keep running total** - verify math as you go
8. **Be thorough** - this is the final test before App Store

---

## 📞 SUPPORT INFO

**Backend:** https://mita-production-production.up.railway.app
**Database:** Supabase (atdcxppfflmiwjwjuqyl)
**Monitoring:** Railway dashboard + Sentry

**Key Files:**
- `lib/config.dart` - Health endpoint config
- `lib/screens/add_expense_screen.dart` - Category mapping
- `lib/services/password_validation_service.dart` - Password validation

**Git Commits:**
- 5369673 - Password fix (VERIFIED)
- ccf7acf - Health endpoint fix (PENDING)
- 3b81998 - Category mapping fix (PENDING)

---

**GOOD LUCK! 🍀**

**Expected Result:** 100% success rate, all fixes working perfectly! 🎉

---

**Document:** Quick Reference Card
**Version:** 1.0
**Date:** 2026-01-19
**Status:** Ready for use

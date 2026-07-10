# MITA Finance — End-to-End Test Matrix

> ## Re-run status (Fable 5, 2026-07-10)
> `scripts/production_e2e_test.py` now automates the full journey (register →
> onboard → dashboard/calendar baseline → create 42 → list/get → exact recalc
> 5958/42 → edit 100 → 5900/100 → category move → delete → 6000/0 + 404 →
> refresh rotation → old refresh rejected → logout → access AND refresh
> rejected → re-login → state recovered).
> - **A23/A24/A25 (txn list/update/delete): now PASS in production** (were the
>   DEF-001/002 500s).
> - **B5/B6 (edit/delete exact recalc): now PASS in production** — required
>   fixing two additional defects: the edit path double-counted the daily-plan
>   accrual and delete never reversed it (INV-13/14).
> - **B8/B9/B10/B12/B13-class engine cases**: covered by
>   `app/tests/test_budget_logic_invariants.py` (+ 300-case reconciliation
>   property).
> - **New A-step: refresh token after logout** — was ACCEPTED (defect), now
>   rejected (fix `5beb440`).
> - Local integration suites run against real PostgreSQL 15 through the real
>   async DI (`test_transactions_crud_integration.py`,
>   `test_async_sweep_integration.py`, `test_onboarding_idempotency.py`,
>   `test_authz_regressions.py`).

> Audit date: **2026-07-08/09** · Target: production `https://mita-production-production.up.railway.app` (commit `d682f3f969a6`)
> "VERIFIED" = executed first-hand this session with the shown result. "NOT EXECUTED" = expected value derived from source; needs a test.
> Evidence scripts live in the auditor scratchpad: `remote_smoke_deployed.py` (30 checks), `audit_opus_e2e.py` (gap-filling), `capture500b.py` (500 bodies).

## Route contract (as mounted) — reference

All feature routers mount under `/api`. Response bodies are wrapped `{"success":true,"data":{...}}` unless noted.

| Area | Method + path | Auth |
|------|---------------|------|
| Register | `POST /api/auth/register` | none |
| Login | `POST /api/auth/login` | none |
| Refresh | `POST /api/auth/refresh-token` | refresh token in body |
| Logout | `POST /api/auth/logout` | access token |
| Onboarding | `POST /api/onboarding/submit` | access token |
| Dashboard | `GET /api/dashboard` | access token |
| Calendar (month) | `GET /api/calendar/saved/{year}/{month}` | access token |
| Calendar (day) | `GET /api/calendar/day/{year}/{month}/{day}` | access token |
| Plan | `GET /api/plan/{year}/{month}` | access token |
| Txn create | `POST /api/transactions/` | access token |
| Txn list | `GET /api/transactions/` | access token |
| Txn get | `GET /api/transactions/{id}` | access token |
| Txn update | `PUT /api/transactions/{id}` | access token |
| Txn delete | `DELETE /api/transactions/{id}` | access token |

---

## A. API-level / production smoke cases (VERIFIED this session)

Test account(s) created: `smoke.<ts>@mita-smoketest.dev` (existing smoke script) and `audit_opus_<ts>@mita-audit.dev`.

| # | Case | Input | Expected | Actual | Result |
|---|------|-------|----------|--------|--------|
| A1 | `GET /` liveness | — | 200 healthy | 200 `{"status":"healthy"}` | ✅ PASS |
| A2 | `GET /health` | — | 200, deps connected | 200; `degraded`; db/redis/firebase connected; alembic `0034`; commit `d682f3f969a6` | ✅ PASS (degraded = DEF-006) |
| A3 | Docs not public | `GET /docs`,`/openapi.json`,`/metrics` | 404 in prod | all 404 | ✅ PASS |
| A4 | Security headers | `GET /` | HSTS, X-CTO, X-Frame, CSP | all present | ✅ PASS |
| A5 | HTTP→HTTPS | `GET http://…/health` | redirect/refuse | 301 → https | ✅ PASS |
| A6 | Register | email/pw/country/income/tz | 201 + token pair | 201, access+refresh | ✅ PASS |
| A7 | Login | same creds | 200 + token pair | 200 | ✅ PASS |
| A8 | Refresh rotation | refresh token | 200 + new pair | 200 | ✅ PASS |
| A9 | Old refresh reuse rejected | rotated-out refresh | 4xx | 401 | ✅ PASS (revocation live) |
| A10 | Rotated access works | new access | 200 | 200 | ✅ PASS |
| A11 | Logout | access token | 200 | 200 | ✅ PASS |
| A12 | Access token dead after logout | old access | 401/403 | 401 | ✅ PASS (blacklist live) |
| A13 | Unknown route | `GET /api/nope` | 404 (not 500) | 404 | ✅ PASS |
| A14 | Bad credentials | wrong pw | 4xx (not 500) | 401 | ✅ PASS |
| A15 | Invalid register body | `{email:"x"}` | 4xx | 422 | ✅ PASS |
| A16 | Protected route no token | `GET /api/calendar/...` | 401/403 | 401 | ✅ PASS |
| A17 | Malformed JSON | `{not-json` | 4xx (not 500) | 422 | ✅ PASS |
| A18 | Onboarding submit | see B1 inputs | 200 + budget_plan | 200 | ✅ PASS |
| A19 | Txn create (today) | amount 42.00 food | 201 | 201 | ✅ PASS |
| A20 | Calendar month | `saved/2026/7` | 31 days, `YYYY-MM-DD`, all limit>0 | 31/31, no bad keys, no zero limits | ✅ PASS |
| A21 | Calendar reflects txn | today.spent | ≥ 42 | 42.0 | ✅ PASS |
| A22 | Calendar day detail | `day/2026/7/8` | 200 (no Decimal 500) | 200 | ✅ PASS |
| **A23** | **Txn list** | `GET /api/transactions/` | **200 list** | **500 SYSTEM_8001** | ❌ **FAIL (DEF-001)** |
| **A24** | **Txn update** | `PUT .../{id}` amount 100 | **200** | **500 (ConversionSyntax)** | ❌ **FAIL (DEF-002)** |
| **A25** | **Txn delete** | `DELETE .../{id}` | **200** | **500 (AsyncSession.query)** | ❌ **FAIL (DEF-001)** |

---

## B. Financial-logic deterministic cases (exact expected numbers)

Budget formula (`app/services/core/engine/budget_logic.py`): `income = monthly + additional`; `fixed_total = Σ fixed`; **`discretionary = income − fixed_total − savings_goal`** (savings clamped so discretionary ≥ 0); if `fixed_total > income` → `ValueError` → HTTP 400.
Dashboard (`app/api/dashboard/routes.py`): `balance = monthly_income − Σ(this-month txns)`; `spent = Σ(today txns)`.

| # | Scenario | Inputs | Expected (exact) | Actual | Result |
|---|----------|--------|------------------|--------|--------|
| B1 | Normal income + fixed + savings | income 6000, fixed {rent 1500, util 200}=1700, savings 400 | total_income **6000**, fixed **1700**, discretionary **3900**, savings **400**, 31 calendar days | exactly those; breakdown real tier-weighted (Σ≈2730, remainder unallocated) | ✅ VERIFIED |
| B2 | Dashboard baseline (post-onboarding, no spend) | above | balance **6000**, spent **0** | 6000 / 0 | ✅ VERIFIED |
| B3 | daily_targets are real (not fallback) | above | targets from `DailyPlan` rows, not income/30 weights | Groceries 13.57, Transport Public 25.57 (real) | ✅ VERIFIED |
| B4 | Create txn recalc | +42.00 today | balance **5958**, today spent **42**, calendar today.spent **42** | 5958 / 42 / 42 | ✅ VERIFIED |
| B5 | Edit txn recalc | 42→100 | balance **5900**, spent **100**, calendar **100** | 500 error | ❌ BLOCKED by DEF-002/001 |
| B6 | Delete txn recalc | delete the txn | balance **6000**, spent **0**, calendar **0** | 500 error | ❌ BLOCKED by DEF-001 |
| B7 | Persistence + recovery | logout → login → dashboard | prior state recovered exactly | balance 5958 recovered (txn still present because delete failed) — recovery itself works | ✅ VERIFIED (persistence) |
| B8 | Income fully consumed by fixed | income 2000, fixed {rent 2000}, savings 400 | discretionary **0**, savings clamped to **0** | — | ⬜ NOT EXECUTED (add unit test on `generate_budget_from_answers`) |
| B9 | Fixed exceed income | income 2000, fixed {rent 2500} | HTTP **400** `BUDGET_GENERATION_FAILED` ("Fixed expenses exceed income") | — | ⬜ NOT EXECUTED |
| B10 | Negative free after savings | income 3000, fixed 2800, savings 500 | discretionary **0**, savings clamped to **200** | — | ⬜ NOT EXECUTED |
| B11 | 30-day month | onboard in a 30-day month | 30 calendar days, all limit>0 | — | ⬜ NOT EXECUTED (server uses current month; test `build_calendar` directly) |
| B12 | February (28) | build_calendar year=2026 month=2 | 28 days | — | ⬜ NOT EXECUTED |
| B13 | Leap February (29) | build_calendar year=2028 month=2 | 29 days | — | ⬜ NOT EXECUTED |
| B14 | Mid-month onboarding | onboard on day 15 | calendar full month; remaining budget spread over remaining days (verify engine behavior) | — | ⬜ NOT EXECUTED |
| B15 | Txn on past day | spent_at = yesterday | counts in month balance, not today's spent | — | ⬜ NOT EXECUTED |
| B16 | Txn on future day | spent_at = tomorrow (≤ +1d allowed) | excluded from balance (`spent_at < now`) and today's spent | — | ⬜ NOT EXECUTED |
| B17 | Category overspend | spend > category daily limit | calendar day status flips to over/warning | — | ⬜ NOT EXECUTED |
| B18 | Decimal rounding | amount 23.755 | stored/So quantized to 2dp (ROUND_HALF_UP) | — | ⬜ NOT EXECUTED |
| B19 | Duplicate create | same txn twice | two rows (no dedupe on single create) — confirm intended | — | ⬜ NOT EXECUTED |
| B20 | Timezone boundary | spent_at near local midnight | assigned to correct day per user tz | — | ⬜ NOT EXECUTED |

> B8–B20 are best implemented as **unit tests** against `generate_budget_from_answers` and `build_calendar` (deterministic, no DB), plus a few API integration tests once DEF-001/002 are fixed.

---

## C-bis. Android on-device verification (Fable 5, 2026-07-10)

Android SDK is now available on the build machine (the prior owner blocker is
cleared here). Executed:
- `flutter pub get` ✅; `flutter analyze` ✅ **0 errors** (47 infos, unchanged class); `flutter build apk --debug` ✅ → `app-debug.apk` (221 MB).
- `flutter test` → **388 passed, 1 pre-existing golden-pixel failure** (`onboarding_location_initial.png`, 1.48% diff — font rendering; also fails on the unmodified tree, not caused by these changes).
- APK installed and launched on emulator `Medium_Phone_API_36.0` (Android 15 / API 36) against **production** Railway. Login screen renders and **email/password auth succeeds** (navigates away from login).

**NEW mobile finding (P1, Flutter-state — not backend):** after a successful
login for an **already-onboarded** account, the app routes to onboarding
Step 1 instead of the dashboard. The backend contract is correct —
`GET /api/users/me` returns `has_onboarded: true` and `income: 6000.0` for
the same token — so `hasCompletedOnboarding()` / `getFinancialContext()` in
`user_data_manager.dart` + `user_provider.dart` are misreading or
cold-cache-defaulting the onboarding flag on session restore. This is a
client state/caching defect (welcome_screen → UserProvider.initialize path),
not one of the P0/P1 backend defects, and did not exist as a backend
regression. Recommended: assert `hasCompletedOnboarding()` returns true when
`/users/me.has_onboarded == true`, and stop defaulting to `needs_onboarding`
on a transient profile-fetch miss. **Owner/next: fix before closed beta.**

## C. Flutter manual test cases (device/emulator — original audit plan)

| # | Flow | Expected | Depends on |
|---|------|----------|-----------|
| C1 | App launch → register | account created, tokens stored in secure storage | — |
| C2 | Login | dashboard loads with real numbers | — |
| C3 | Onboarding | budget + calendar generated, `has_onboarded` persists | — |
| C4 | Dashboard | balance/spent/targets match backend | — |
| C5 | Calendar | per-day planned/spent/remaining shown; days clickable | — |
| C6 | Create transaction | dashboard + calendar recalc | works (create OK) |
| C7 | **View all transactions** | list shows txns | ❌ will fail (DEF-001) |
| C8 | **Edit transaction** | value recalcs | ❌ will fail (DEF-002/001) |
| C9 | **Delete transaction** | value returns to baseline | ❌ will fail (DEF-001) |
| C10 | Restart app | session + data persist | — |
| C11 | Logout | tokens cleared; revoked | backend verified |
| C12 | Re-login | same data recovered | backend verified (B7) |

## D. Flutter automation candidates
- Widget/unit: `TransactionModel` JSON (de)serialization against real API payloads; token refresh/interceptor in `api_service.dart`.
- Integration (`integration_test/`): full journey C1–C12 against a staging base URL via `--dart-define=API_BASE_URL=...`; gate C7–C9 on the DEF-001/002 fix.
- Contract test: assert Dart request/response models match FastAPI schemas for auth, onboarding, dashboard, calendar, transactions.

## E. Backend automated tests (Phase 7, this session)
- **Collection:** 617 tests, **0 import/collection errors** (venv, py3.12, pytest 8.3.3).
- **Focused pass:** `test_transactions_services.py` + `test_transactions_routes.py` → **4 passed** — *these pass while the same operations 500 in production* because the tests use a **sync** session and never exercise the async route wiring (see DEF-001). Treat as a coverage gap, not proof.
- **Full suite:** not completable in a bare environment — many tests require a live Postgres/Redis and some concurrency tests hang; bounded 5-min run reached ~5% then timed out. Some `security/test_api_endpoint_security.py` and `performance/test_database_performance.py` cases fail without infra.
- **Recommendation:** run the full suite in CI (`main-ci.yml`) with service containers; add async-wired integration tests for transactions list/get/update/delete.

## F. Flutter analyze (Phase 7)
- `flutter analyze` → **49 issues, 0 errors** (info/warnings only): `avoid_dynamic_calls`, deprecated `value`→`initialValue`, Sentry SDK deprecations, and unused `_getSampleGoals` (dead sample-data, not wired). Compiles clean.

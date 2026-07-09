# MITA Finance — API ↔ Flutter Contract Map

> Auditor: Claude (Opus 4.8), 2026-07-09, base `d54667a`. Read-only.
> Backend routes extracted from `app/api/**/routes.py` (`@router.<method>` + `APIRouter(prefix=…)`, all mounted under `/api`, see `app/main.py`). Flutter callers extracted from `mobile_app/lib/services/*.dart` path literals (`_dio.<method>('…')`).
> **Wrapper:** backend success bodies are `{"success": true, "data": {…}}` (`app/utils/response_wrapper.py`); Flutter must read `data`.
> "Mismatch" = a difference that changes behavior on the wire (path, method, slash, missing endpoint, field/enum/type).

## How to read severity
A mismatch is **P1** only if it blocks a **core screen** (auth, onboarding, dashboard, calendar, transactions). Mismatches on deferred features are **P2/P3**.

---

## A. Core mobile-facing endpoints (the MVP journey)

| Screen / flow | Flutter call | Backend route | Auth | Status |
|---|---|---|---|---|
| Register | `POST /auth/register` (`api_service.dart:583`) | `POST /api/auth/register` | public | ✅ match |
| Login | `POST /auth/login` (`:661`) | `POST /api/auth/login` | public | ✅ match |
| Google | `POST /auth/google` (`:575`) | `POST /api/auth/google` | public | ✅ match (Google Sign-In optional) |
| Refresh | token refresh via interceptor | `POST /api/auth/refresh-token` | refresh in body | ✅ (prior audit verified rotation) |
| Onboarding submit | `POST /onboarding/submit` | `POST /api/onboarding/submit` | access | ✅ match (verified working in prior audit) |
| Onboarding steps | `POST /onboarding_location`, `/onboarding_income`, `/onboarding_habits`, `/onboarding_expenses`, `/onboarding_goal`, `/onboarding_spending_frequency`, `/onboarding_finish` | **NONE** (backend only exposes `/onboarding/questions`, `/onboarding/submit`) | — | ❌ **STALE — nonexistent backend endpoints** (see P-CONTRACT-1) |
| Dashboard | `GET /dashboard` | `GET /api/dashboard` | access | ✅ match |
| Dashboard stats | `GET /dashboard/quick-stats` | `GET /api/dashboard/quick-stats` | access | ✅ match — but see `adversarial-audit.md` N-P1-DASH-SOFTDELETE (counts deleted txns) |
| Calendar month | `GET /calendar/saved/{y}/{m}` | `GET /api/calendar/saved/{year}/{month}` | access | ✅ match |
| Calendar day | `GET /calendar/day/{y}/{m}/{d}` | `GET /api/calendar/day/{year}/{month}/{day}` | access | ✅ match |
| Calendar shell | `GET /calendar/shell` | `GET /api/calendar/shell` (verify) | access | ✅ likely |
| Txn create | `POST /transactions/` and `POST /transactions` | `POST /api/transactions/` | access | ⚠️ **DEF-008** — both slash/slashless used → 307 redirect |
| Txn list | `GET /transactions` | `GET /api/transactions/` | access | ❌ **DEF-001** (500) + DEF-008 (slash) |
| Txn get | `GET /transactions/{id}` | `GET /api/transactions/{transaction_id}` | access | ❌ **DEF-001** (500) |
| Txn update | `PUT /transactions/{id}` (`transaction_service.dart:181`) | `PUT /api/transactions/{transaction_id}` | access | ✅ method matches — ❌ blocked by **DEF-002** (validator 500) |
| Txn delete | `DELETE /transactions/{id}` | `DELETE /api/transactions/{transaction_id}` | access | ❌ **DEF-001** (500) |
| Txn by-date | `GET /transactions/by-date` | `GET /api/transactions/by-date` (verify) | access | ⚠️ verify |
| Notifications list | `GET /notifications/list` / `GET /notifications` | `GET /api/notifications` / `/notifications/list` | access | ✅ likely (both exist) |
| Notifications ops | `POST /notifications/{id}/mark-read`, `/notifications/mark-all-read`, `GET /notifications/unread-count`, `GET/PUT /notifications/preferences`, `DELETE /notifications/{id}` | matching backend routes exist | access | ✅ match |

## B. Secondary/feature endpoints

| Flutter call | Backend | Status / note |
|---|---|---|
| `GET /goals/`, `POST /goals/`, `GET/PATCH/DELETE /goals/{id}`, `GET /goals/statistics` | present | ✅ match (goals CRUD is async-correct) |
| `GET /goals/adjustments/suggestions`, `/smart_recommendations`, `/opportunities/detect`, `/income_based_suggestions` | present, async-correct | ✅ |
| `GET /goals/budget/allocate|progress|adjustment_suggestions` | present but **500** (async/sync, `adversarial-audit.md` §2-D) | ❌ — **not currently called by Flutter** |
| `GET /analytics/behavioral-insights`, `/seasonal-patterns`; `POST /analytics/feature-usage`, `/feature-access-attempt`, `/paywall-impression` | present, async-correct (`await db.execute`) | ✅ match |
| `GET /analytics/monthly`, `/trend` | present but **500** (async/sync + `Transaction.timestamp` nonexistent) | ❌ — **not called by Flutter** (no core impact) |
| `GET /ai/*` (spending-patterns, etc.) | present but **silently return empty 200** (async/sync swallowed) | ⚠️ mobile shows empty AI cards, not an error |
| `POST /challenge/eligibility|check|streak` | present but **500** (signature mismatch) | ❌ — **not called by Flutter** |
| `GET /challenge/{id}/progress`, `/challenges` | present | ✅ |
| `GET /users/{userId}/premium-status|premium-features|subscription-history` | present, ownership-checked (403 on mismatch) | ✅ (authenticated, id-scoped) |
| `GET /subscriptions/{id}/status` | **verify** — no `subscriptions` router seen in mount list | ⚠️ possible stale/missing |
| `POST /iap/validate` | `POST /api/iap/validate` | ✅ |
| `POST /ocr/process|enhance|categorize`, `GET /ocr/status/{id}` | present | ✅ path; OCR record path broken server-side (`record_expense` `date=`, `adversarial-audit.md` N-P2) |
| `/transactions/receipt*` (advanced/batch/validate/status) | present | deferred OCR |
| `GET /referral` vs `GET /referrals/code` | **singular/plural inconsistency** in Flutter usage | ⚠️ verify which the backend `referral_router` exposes |
| `/habits/`, `/habits/{id}/`, `/habits/{id}/complete`, `/habits/{id}/progress` | present | ✅ (trailing-slash style) |
| `/mood` and `/mood/` | both used | ⚠️ trailing-slash inconsistency |
| `/behavior/*`, `/budget/*`, `/insights/*`, `/installments`, `/cohort/*` | present | mostly ✅ (deferred features) |

---

## Verified contract defects

### P-CONTRACT-1 (P2/P3) — Stale Flutter onboarding-step endpoints target nonexistent backend routes
- Flutter references `POST /onboarding_location`, `/onboarding_income`, `/onboarding_habits`, `/onboarding_expenses`, `/onboarding_goal`, `/onboarding_spending_frequency`, `/onboarding_finish` (multiple `mobile_app/lib` sites). The backend onboarding router (`app/api/onboarding/routes.py`, prefix `/onboarding`) exposes only `GET /onboarding/questions` and `POST /onboarding/submit`.
- **Impact:** if any active onboarding screen calls these, it gets 404/405. The prior audit verified onboarding works **via `/onboarding/submit`**, so these are almost certainly **legacy/dead** Flutter code paths — but they are a latent break and a maintenance hazard. **Action:** confirm they are unreferenced by the live onboarding flow; delete or repoint to `/onboarding/submit`.

### P-CONTRACT-2 — (withdrawn; verified NOT a defect)
- Initial suspicion of a `PATCH` vs `PUT` transaction-update mismatch was **refuted**: `transaction_service.dart:181` uses `.put('/transactions/{id}')`, which matches the backend `PUT /api/transactions/{transaction_id}`. The `PATCH` at `api_service.dart:1510` is `updateGoal` (`PATCH /goals/{id}`), which correctly matches backend `PATCH /api/goals/{goal_id}` (`goals/routes.py:666`). Item-route paths (`/transactions/{id}`, `/goals/{id}`) carry no trailing slash on either side. Transaction edit is blocked only by **DEF-002**, not by method/slash.

### P-CONTRACT-3 (P2) — DEF-008 reaffirmed (trailing slash on `/transactions`)
- Flutter uses both `'/transactions'` (4×) and `'/transactions/'` (3×); backend collection route is `'/transactions/'`. The slashless calls incur a 307 redirect; some Dio configurations drop the `Authorization` header/body across redirects. Fix client to always use the trailing slash (matches DEF-008).

### P-CONTRACT-4 (P3) — Broken backend endpoints escaped production smoke because no mobile caller
- `/analytics/monthly`, `/analytics/trend`, `/goals/budget/*`, `/challenge/eligibility|check|streak`, `/ai/*` are all broken server-side (`adversarial-audit.md` §2) but are **not on the mobile app's call graph**, which is why the prior production smoke (which drives the app's real paths) did not surface them. They will surface the moment a screen is wired to them. Add backend-contract tests independent of the current mobile call graph.

## Notes on formats (verify during implementation)
- **Dates:** calendar keys are `YYYY-MM-DD`; transaction `spent_at` is ISO-8601 datetime. Confirm Flutter parses `spent_at` (not `date`/`timestamp` — the Transaction model has neither `date` nor `timestamp`; a server-side `Transaction(date=…)` bug exists in the OCR path, `adversarial-audit.md` N-P2).
- **Money:** backend serializes `Decimal` → number; several services coerce to `float` before JSON (`analytics_service.py:29`, `dashboard/routes.py:69`). Confirm the Flutter models read numbers, not strings.
- **204/empty:** delete/logout return wrapped JSON (not bare 204) — confirm Flutter does not try to JSON-parse an empty body.

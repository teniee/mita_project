# MITA Finance — Fable 5 Implementation Backlog (second-pass audit)

> ## Implementation status (Fable 5, 2026-07-10)
> Historical audit content below is unchanged; this block records what shipped.
>
> | Item | Status | Commit | Evidence |
> |---|---|---|---|
> | DEF-002 (TxnUpdate validator) | ✅ FIXED | `e36b7ef` | every TxnUpdate field was broken, not only amount; 26 unit regressions; prod PUT verified |
> | DEF-001 (txn CRUD async/sync) | ✅ FIXED | `e36b7ef` | run_sync bridge on list/get/update/delete + affordability/budget-status (both mobile-called); async-DI integration suite; prod E2E 29/30 → 30/30 |
> | TASK-1 (dashboard soft-delete) | ✅ FIXED | `e36b7ef` | 7 aggregations filtered (audit's 6 + recent-transactions list) + /transactions/by-date; exact-number regressions |
> | INV-13/14 (edit double-count, delete not reversed) | ✅ FIXED | `e36b7ef` | NEW defects found during implementation: update re-applied additively (42→100 gave 142), delete never reversed accrual; recalculate_plan_spent() recomputes from ledger |
> | Latent 500s in error paths | ✅ FIXED | `e36b7ef` | ResourceNotFoundError(details=) crashed all 404s; 7 missing ErrorCode members; FinancialResponseHelper.transaction_updated didn't exist; validators.ValidationError now ValueError → 422 not 500 |
> | TASK-2 (async sweep A–D) | ✅ FIXED | `51647d6` | ai/snapshot, 14 ai/* analyzer endpoints, analytics monthly/trend, goals/budget/*; analyzer also read the legacy expenses table (varchar user_id + missing columns) — now reads transactions; UUID-in-JSON snapshot insert fixed; content-asserting regressions |
> | TASK-10 / V4 (goal expense sign) | ✅ FIXED | `51647d6` | amount>0 + deleted_at filter; exact-number regression (6000 income − 100 spent = 5900 available) |
> | N-P2-IDOR-1 (/goal/* body user_id) | ✅ FIXED | `521ce39` | session-bound identity, 403 on mismatch; two-user tests |
> | N-P2-SECMON (auth security monitoring) | ✅ FIXED | `521ce39` | require_admin_access on both endpoints; anon 401 + non-admin 403 tests |
> | NEW: logout didn't revoke refresh token | ✅ FIXED | `5beb440` | found by prod E2E step 22; logout now blacklists the provided refresh token; Flutter sends it (`1510071`) |
> | TASK-3 / V3 (daily_plan unique + onboarding idempotency) | ✅ FIXED | `74b6011` | migration 0035 (normalize→merge→constraint, tested with seeded dupes: 12+30→42 spent), upsert save, already_onboarded guard; prod-verified (re-submit idempotent, spend accrues once) |
> | TASK-13 / V2 (budget float) | ✅ FIXED | `92ac95e` | Decimal + ROUND_HALF_UP; B1/B8/B9/B10 + 300-case reconciliation property; 100.005→100.01 |
> | TASK-14 / V5 (record_expense) | ✅ FIXED | `e36b7ef` | spent_at + Decimal(str()) in both copies |
> | DEF-003 (.mcp.json secrets) | ⚠️ PARTIAL | `95193a3` | untracked + gitignored + example committed; **rotation & history purge remain owner-blocked** (owner-actions §1) |
> | TASK-5 / DEF-008 (Flutter slashes) | ✅ FIXED | `1510071` | all collection calls use /transactions/; P-CONTRACT-1 was a false positive (Navigator routes, not API calls) |
> | DEF-007 (Flutter env default) | ✅ FIXED | `1510071` | ENV defaults to production; pinning auto-disabled until fingerprints configured |
> | TASK-4 (async test harness) | ✅ DONE | `e36b7ef`+ | TestClient with real get_async_db against local PostgreSQL 15; pattern used by all new integration suites |
> | Empty-DB migration on real PostgreSQL | ✅ VERIFIED | — | alembic upgrade head from empty PG15 → head 0035, 33 tables; downgrade/upgrade cycle idempotent |
> | TASK-6/7/8/9/11-остальное, 15–19 | ⏳ OPEN | — | P2/P3; not core-journey blocking |

> Auditor: Claude (Opus 4.8), 2026-07-09, base of truth **`teniee/mita_project@main` `d54667a`** (clone fresh; do not edit a stale copy — DEF-004).
> Ordering (per mandate): **1** confirmed P0 security/data-loss → **2** confirmed P1 core-journey → **3** regression tests with each fix → **4** mobile/backend contract → **5** data-integrity/concurrency → **6** P2 cleanup.
> **Baseline (already in `verified-defects.md`): DEF-001 (P0), DEF-002 (P1), DEF-003 (P0 secrets, owner), DEF-005/006/007/008.** They remain the top of the queue; the tasks below are the **new** work from this pass, sequenced against them. Nothing here is vague — each task is a concrete code change with evidence.
> Prod base URL for verification: `https://mita-production-production.up.railway.app`. After every backend deploy, confirm `/health.commit == pushed SHA` and re-run `scripts/remote_smoke_test.py`.

Legend scope: **tiny** (<1h), **small** (~½ day), **medium** (~1–2 days), **large** (>2 days).

---

## TIER 0 — Baseline P0/P1 (do first; details in prior audit)
- **DEF-003 (P0, owner):** rotate leaked `.mcp.json` secrets + purge history. Non-code, parallel. See `owner-actions.md §1`.
- **DEF-002 (P1):** fix `TxnUpdate.amount` validator (schema-local, lowest risk). Do before DEF-001.
- **DEF-001 (P0):** transactions list/get/update/delete async/sync bridge. **Extend to TASK-2 (systemic sweep).**

---

## TIER 1 — New P1 (core-journey correctness)

### TASK-1 — Dashboard/quick-stats exclude soft-deleted transactions
- **Severity:** P1 · **Subsystem:** backend/dashboard · **Scope:** small
- **Exact problem:** all six dashboard aggregations omit a `deleted_at IS NULL` filter, so balance/today-spent/weekly/monthly/savings-rate/top-category include soft-deleted txns; after a delete, balance permanently diverges from the ledger.
- **Evidence:** `grep -c deleted_at app/api/dashboard/routes.py` = 0; queries at `dashboard/routes.py:60-67,75-82,94-103,179-186,487-513`; delete sets `deleted_at` (`transactions/services.py:301`); ledger filters `deleted_at.is_(None)` (`services.py:167,194,214,292`).
- **Affected files:** `app/api/dashboard/routes.py` (6 queries).
- **Expected:** `balance = income − Σ(non-deleted spend)`; delete reverts balance/spent to pre-txn values.
- **Fix direction:** add `Transaction.deleted_at.is_(None)` to each aggregation `where(...)`. Nothing else.
- **Do NOT rewrite:** the dashboard response shape or the daily-target logic.
- **Tests:** integration create→balance reflects; soft-delete→balance reverts (exact numbers). See `test-gap-analysis.md` V1.
- **Local verify:** async integration test on `/api/dashboard` with real async session.
- **Prod verify:** with a throwaway `audit_*` account, create→delete a txn (after DEF-001), assert `/api/dashboard` balance returns to baseline.
- **Rollback risk:** very low (adds a filter). **Owner dep:** none. **Sequencing:** ship with DEF-001 (delete must stop 500-ing to observe).

### TASK-2 — Sweep the systemic AsyncSession/sync-query bug beyond transactions
- **Severity:** P1 (systemic; per-endpoint P2) · **Subsystem:** backend/ai,analytics,goals · **Scope:** medium
- **Exact problem:** DEF-001's root cause recurs: routes inject `AsyncSession` then call sync `db.query()` / `await` a sync `def`. Four more router groups affected.
- **Evidence (verified):**
  - `POST /api/ai/snapshot` — `ai/routes.py:61` `await save_ai_snapshot(...)` (sync def; `db.query(User)` in `ai_personal_finance_profiler.py:18`).
  - `GET /api/analytics/monthly|trend` — `analytics/routes.py:43,52` await sync `get_monthly_category_totals/get_monthly_trend` (`analytics_service.py:12,31` `db.query`); **also uses nonexistent `Transaction.timestamp`** (fix to `spent_at`).
  - `GET /api/ai/*` (14 endpoints) — `AIFinancialAnalyzer.__init__`→`self.db.query(User)` (`ai_financial_analyzer.py:40`), AttributeError **swallowed** by `except Exception` → 200 empty fallback.
  - `GET /api/goals/budget/allocate|progress|adjustment_suggestions` — `goals/routes.py:600,622,642` build `GoalBudgetIntegration(db)` which uses `self.db.query` (`goal_budget_integration.py:33,40,155,258-287`).
- **Affected files:** `app/services/core/engine/ai_snapshot_service.py`, `ai_personal_finance_profiler.py`, `app/services/analytics_service.py`, `app/api/analytics/routes.py`, `app/services/ai_financial_analyzer.py`, `app/services/goal_budget_integration.py` (+ their routes).
- **Expected:** each endpoint returns real data (200), or is explicitly deprecated.
- **Fix direction:** per service, convert to async (`await db.execute(select(...))`, `await db.commit()`) mirroring `app/api/dashboard/routes.py`, **or** inject `app.core.session.get_db` (sync `Session`) and call off-loop. Also fix `Transaction.timestamp`→`spent_at`. Remove the broad `except Exception` in the AI routes so failures surface.
- **Do NOT rewrite:** the analysis/aggregation math; only the session plumbing.
- **Tests:** `test-gap-analysis.md §2` §2-A..D (assert **content**, not just 200).
- **Local verify:** async integration hitting each endpoint with seeded data.
- **Prod verify:** call each with an `audit_*` token; expect 200 + non-empty; check Railway logs for no new `AsyncSession`/`await` tracebacks.
- **Rollback risk:** medium (touches several services). Ship behind the same release as DEF-001; these are non-core so a partial rollback is safe. **Owner dep:** none.

### TASK-3 — Enforce one daily_plan per (user, day, category) + onboarding idempotency
- **Severity:** P1 · **Subsystem:** backend/db+onboarding · **Scope:** medium
- **Exact problem:** no `UNIQUE(user_id, date, category)` on `daily_plan`; `save_calendar_for_user` appends without delete-first; `submit_onboarding` has no `has_onboarded`/idempotency guard → re-submit or mobile retry duplicates plan rows; spend accrues via `.first()` so only one duplicate updates → per-category budget/remaining wrong.
- **Evidence:** `daily_plan.py` no `__table_args__`; no migration adds unique (`0001`,`0016`,…); `calendar_service_real.py` append loop; `onboarding/routes.py:63` only logs `has_onboarded`; `user_data_service.py:51` shows the correct delete-first pattern the onboarding path lacks.
- **Affected files:** `app/db/models/daily_plan.py`, new Alembic migration, `app/services/calendar_service_real.py` (`save_calendar_for_user`), `app/api/onboarding/routes.py`.
- **Expected:** at most one plan row per (user, day, category); re-submit is idempotent.
- **Fix direction:** normalize `date` to day; add composite `UniqueConstraint`; make `save_calendar_for_user` delete-first or upsert (`ON CONFLICT`); add a `has_onboarded`/idempotency-key guard on `POST /onboarding/submit`. **Migration must de-dupe existing rows before adding the constraint.**
- **Do NOT rewrite:** the calendar generation engine (`budget_logic`/build_calendar).
- **Tests:** `test-gap-analysis.md` V3 (submit twice → count==1; spent==amount).
- **Local verify:** run migration against a seeded DB with intentional dupes; assert de-dupe + constraint holds.
- **Prod verify:** **CAUTION** — de-dupe migration touches real data; dry-run count of duplicate `(user,day,category)` first; run in a maintenance window; verify `alembic current == new head` and calendar renders unchanged for an existing user.
- **Rollback risk:** medium-high (data migration). Keep the de-dupe reversible (log removed rows). **Owner dep:** none, but coordinate the migration window.

---

## TIER 2 — Regression-test enablers (land with the fixes above)
### TASK-4 — Async integration test harness (PostgreSQL, real DI)
- **Severity:** P1 (enabler) · **Scope:** medium
- **Problem:** tests use `Mock(spec=Session)` / nulled `AsyncSessionLocal` (`test_dashboard_api.py:34`, `app/tests/conftest.py:74`) so the entire async/sync bug class is invisible.
- **Fix direction:** add a TestClient/httpx harness with `get_async_db` overridden to a real async session on a Postgres test container; assert content + DB state. Wire the regressions from `test-gap-analysis.md §2` for DEF-001, DEF-002, TASK-1/2/3.
- **Tests/verify:** the new tests must **fail on current code** and pass after each fix. Run in CI with Postgres+Redis service containers.
- **Rollback risk:** none (test-only). **Owner dep:** CI infra (service containers).

---

## TIER 3 — Mobile/backend contract
### TASK-5 — Transaction trailing slash (DEF-008) + remove stale Flutter onboarding endpoints
- **Severity:** P2 · **Subsystem:** Flutter · **Scope:** small
- **Evidence:** Flutter uses `'/transactions'` and `'/transactions/'` (`transaction_service.dart:43,137` vs backend `'/transactions/'`) → 307; Flutter references `/onboarding_location|income|habits|expenses|goal|finish|spending_frequency` which don't exist in the backend (`api-contract-map.md` P-CONTRACT-1/3).
- **Fix direction:** always use `'/transactions/'` for the collection; confirm the live onboarding flow uses `/onboarding/submit` and delete/repoint the stale `/onboarding_*` calls.
- **Do NOT rewrite:** the auth/interceptor layer.
- **Tests:** Flutter unit assert the built URLs; contract test that no client path 404s.
- **Local verify:** run the app against staging; confirm no 307/404 on onboarding/transactions.
- **Prod verify:** N/A (client). **Rollback risk:** low. **Owner dep:** none.

### TASK-6 — Backend full-route contract test (catch no-mobile-caller breakage)
- **Severity:** P2 · **Scope:** small–medium
- **Problem:** broken endpoints (`/analytics/monthly|trend`, `/goals/budget/*`, `/challenge/*`, `/ai/*`) escaped the app-driven smoke because no mobile caller (`api-contract-map.md` P-CONTRACT-4).
- **Fix direction:** enumerate every mounted route; assert a valid authenticated request returns non-5xx with seeded data. **Owner dep:** none.

---

## TIER 4 — Data-integrity & concurrency
### TASK-7 — Add FK+CASCADE to five user-scoped tables
- **Severity:** P2 · **Subsystem:** db · **Scope:** small–medium
- **Evidence:** `moods`, `budget_advice`, `notification_logs`, `push_tokens`, `ignored_alerts` have `user_id` with no FK (`mood.py:13`, `budget_advice.py:14`, `notification_log.py:14`, `push_token.py:14`, `ignored_alert.py:27`; migrations `0002/0005/0016/0028`). Orphans survive user deletion; `push_tokens` orphans could push to deleted users.
- **Fix direction:** migration + model FK `ondelete='CASCADE'`, mirroring `0022` (clean orphans first, then add constraint).
- **Prod verify:** dry-run orphan count first; run in a window; verify cascade. **Rollback risk:** medium (data). **Owner dep:** migration window.

### TASK-8 — Money precision: bind income columns + Expense.amount to Numeric(12,2)
- **Severity:** P2 · **Subsystem:** db/models · **Scope:** small
- **Evidence:** `users.monthly_income/savings_goal` unbounded `Numeric` in DB (`0008:37,77`); model declares bare `Numeric` for all three income cols and `Float` for `Expense.amount` (`expense.py:12`) though DB is `Numeric(12,2)` (`0006`).
- **Fix direction:** model → `Numeric(12,2)`; migration to bound `monthly_income/savings_goal`; assign quantized `Decimal` in `onboarding/routes.py:93`.
- **Tests:** schema assertions (`test-gap-analysis.md §2`). **Rollback risk:** low-medium. **Owner dep:** migration window.

### TASK-9 — Subscription idempotency: unique (platform, original_transaction_id)
- **Severity:** P2 · **Subsystem:** db/iap · **Scope:** small
- **Evidence:** `subscriptions.original_transaction_id` non-unique index only (`subscription.py:21`, `0034:43-47`); app-level find-or-create not race-safe (`iap/routes.py:129-158`).
- **Fix direction:** partial unique index on `(platform, original_transaction_id) WHERE original_transaction_id IS NOT NULL`. **Owner dep:** migration window.

### TASK-10 — Fix goal-budget expense sign + guard (V4)
- **Severity:** P2 · **Subsystem:** backend/goals · **Scope:** tiny
- **Evidence:** `goal_budget_integration.py:313-318` filters `amount < 0` while expenses are positive → `available_for_goals` = full income. (Also fixed alongside TASK-2 since these endpoints 500 today.)
- **Fix:** use `amount > 0`. **Tests:** unit asserting `_get_monthly_expenses` sums positive expenses.

---

## TIER 5 — P2/P3 cleanup & hardening
### TASK-11 — Lock down auth security-monitoring endpoints
- **Severity:** P2 · **Scope:** tiny · Add `Depends(require_admin_access)` to `get_security_status` / `get_password_security_config` (`auth/security_monitoring.py:110-113,147-148`). Tests: 401/403 for anon/non-admin. **Owner dep:** none.

### TASK-12 — Bind `/goal/*` identity to the session (authenticated IDOR)
- **Severity:** P2 · **Scope:** tiny · Add `user=Depends(get_current_user)` to `full_progress`/`goal_from_state`; use `user.id`; drop/validate body `user_id` (`goal/routes.py:19,31`). Tests: `test-gap-analysis.md` N-P2-IDOR-1.

### TASK-13 — Budget engine to Decimal + ROUND_HALF_UP (V2)
- **Severity:** P2 · **Scope:** small · `budget_logic.py` — Decimal end-to-end; `quantize(Decimal('0.01'), ROUND_HALF_UP)`. Tests: reconciliation property test. **Do NOT rewrite** the tier-weight allocation logic; only the numeric type/rounding.

### TASK-14 — OCR record_expense uses spent_at + Decimal(str) (V5)
- **Severity:** P2 (deferred OCR) · **Scope:** tiny · Replace `date=day`→`spent_at=<datetime>` and `Decimal(amount)`→`Decimal(str(amount))` in **both** `app/services/expense_tracker.py:24` and `app/services/core/engine/expense_tracker.py:109`.

### TASK-15 — Fix broken challenge endpoints (or mark deprecated)
- **Severity:** P2 (deferred) · **Scope:** small · `challenge/routes.py:26-54` — import the real `evaluate_challenge` from `app/api/challenge/services.py`, pass a `db` session and correct args to `check_eligibility`/`run_streak_challenge`. If challenges are deferred, mark the router deprecated/unmounted rather than shipping broken.

### TASK-16 — Android release hardening
- **Severity:** P2 · **Scope:** small · Add `POST_NOTIFICATIONS` permission (Android 13+ FCM); make release signing **fail** (not fall back to debug) when no keystore (`app/build.gradle.kts:71-76`); set `android:allowBackup="false"`; justify/remove `ACCESS_FINE_LOCATION` for Play policy. **Owner dep:** keystore (owner-actions §3).

### TASK-17 — Error-handling hygiene
- **Severity:** P2 · **Scope:** medium · Remove `str(e)` from client-facing `HTTPException(detail=…)` (75 sites); tighten broad `except Exception` that returns success fallbacks so real failures surface (233 sites — prioritize financial paths). Do NOT swallow-then-200 on money paths.

### TASK-18 — P3 schema/migration cleanup
- **Severity:** P3 · **Scope:** small · `push_tokens.platform` add `server_default='fcm'`; align `daily_plan.date` timestamptz (or model to `Date`); constrain notification enum columns + `retry_count`→Integer; fix `0008/0009` `Revises:` docstrings + delete orphan `app/migrations/`; remove legacy `render.yaml`; guard inspection migrations for offline `--sql` or document unsupported. Each is independent and low-risk.

### TASK-19 — PATCH /users/me email hygiene
- **Severity:** P3 · **Scope:** tiny · In `app/services/users_service.py update_user_profile`, on email change set `email_verified=False` and pre-check uniqueness (the unused `app/api/users/services.py` variant shows the pattern).

---

## Dependency ordering (critical path)
```
DEF-003(owner) ─ parallel
DEF-002 → DEF-001 → TASK-1 (soft-delete) ─┐
                     └→ TASK-2 (async sweep) ┤→ TASK-4 (async test harness gates all)
TASK-3 (daily_plan unique + onboarding idempotency)  [independent migration window]
TASK-5/6 (contract) ─ parallel after TASK-1/2
TASK-7/8/9 (db migrations) ─ batch into one window
TASK-10..19 ─ opportunistic P2/P3
```
Do TASK-4 early enough that TASK-1/2/3 land **with** failing→passing regressions, not after.

# MITA Finance — Second-Pass Adversarial Production Audit

> Auditor: Claude (Opus 4.8), read-only. **2026-07-09.**
> Base of truth: fresh **git worktree at GitHub `teniee/mita_project@main` = `d54667a308a351bcfe1a9569457c21fb8ec28fa1`** (verified: local HEAD == `git ls-remote origin main`; 0 dirty files).
> Method: 8 completed inspector domains from a fan-out workflow + **first-hand verification of every P0/P1 against source** (the workflow's automated verification stage did not run — session limit — so I verified each candidate myself, including running the budget engine and migration chain locally). Every finding below cites `file:line` and was re-opened and checked. Secrets are never printed.
> Companion (this session): `api-contract-map.md`, `financial-invariants.md`, `test-gap-analysis.md`, `fable-5-task-backlog.md`.
> **Does not overwrite** the prior audit docs (`fable-5-handoff.md`, `verified-defects.md`, `end-to-end-test-matrix.md`, `owner-actions.md`).

## Severity legend
- **P0** — cross-user data access, persisted financial corruption, live security exposure, **or** a 500 on a **core-journey** step. Fix before beta.
- **P1** — breaks an important feature, an independent second cause, or a core financial-correctness error.
- **P2** — quality/observability/hardening/latency; does not block the core journey.
- **P3** — informational / latent.

The **core MVP journey** (per `fable-5-handoff.md §15`): register → onboard → plan → dashboard → calendar → create/edit/delete transaction → persist → logout → recover. AI insights, analytics deep-dives, OCR, IAP, goals-budget, challenges, behavior/cohort are **explicitly deferred non-core**.

---

## 0. What was preserved / confirmed from the prior audit (baseline — still valid)

| Prior finding | Status this pass |
|---|---|
| DEF-001 — txn list/get/delete 500 (`AsyncSession` has no `.query`) | **Confirmed still present**, and shown to be the tip of a **systemic pattern** (§2, N-P1-3). |
| DEF-002 — `TxnUpdate.amount` validator `ConversionSyntax` | Confirmed present (`app/api/transactions/schemas.py`). |
| DEF-003 — secrets in `.mcp.json` | Out of scope to re-verify (owner action); unchanged. |
| DEF-005 — `SMTP_PASSWORD` missing | Owner/config; unchanged. |
| DEF-006 — `/health` degraded (Sentry) | Unchanged. |
| DEF-007 — Flutter defaults to `development` | Confirmed (`mobile_app/lib/config.dart`). |
| DEF-008 — Flutter txn calls omit trailing slash | **Confirmed** — Flutter uses both `'/transactions'` and `'/transactions/'` (see `api-contract-map.md`). |
| Alembic single base→single head through `0034` | **Confirmed** by two methods (`alembic heads` and a custom chain parser): one base `0001_initial`, one head `0034`, 0 branches, 0 broken links. |
| Model table count == migration table count | **Confirmed**: 33 model `__tablename__` == 33 migration `create_table` (no orphan tables, no missing tables). |
| Budget uses binary float in important paths | **Confirmed by live repro** (§3, N-P2-BUDGETFLOAT). |
| Cross-user isolation generally enforced | **Confirmed** for profile/onboarding/income/preferences/premium/transactions/goals/installments/scheduled-expenses/dashboard/calendar/notifications/habits/mood/ocr — every stateful query filters by the authenticated `user.id`. **Two authenticated-IDOR exceptions found** (§1). |

---

## 1. Cross-user authorization & isolation (Phase 1)

**Overall result: no unauthenticated cross-user data dump; isolation is enforced in-query across the resource surface.** Two authenticated broken-access-control issues and two info-disclosure issues were found and verified.

### N-P2-IDOR-1 — `/api/goal/user-progress` trusts a body-supplied `user_id` (authenticated IDOR, latent)
- **Severity:** P2 (authenticated IDOR; **latent P1** — see impact caveat).
- **Route:** `POST /api/goal/user-progress` → `app/api/goal/routes.py:31-39`.
- **Verified path:** handler `full_progress(payload: ProgressRequest)` has **no** `user=Depends(get_current_user)` param and calls `get_user_progress(payload.user_id, payload.year, payload.month, …)`. `ProgressRequest.user_id: str` is taken straight from the request body (`app/api/goal/schemas.py:22-26`). Downstream `app/engine/progress_logic.py:10` → `get_calendar_for_user(user_id, …)` → `app/services/calendar_service_real.py:150` `fetch_calendar(db, user_id, …)` opens a **real DB session** (`SessionLocal()`) and reads DailyPlan rows for the supplied `user_id`.
- **Auth nuance (verified — corrects a naïve reading):** the endpoint **is authenticated** — `goal_router` is in `private_routers_list` and the mount loop applies `dependencies=[Depends(get_current_user), Depends(check_api_rate_limit)]` (`app/main.py:1000-1006`). So it is **not** an unauthenticated exposure. It **is** a broken-access-control flaw: authenticated user A can pass user B's UUID in the body and the backend issues B-scoped DB reads, never checking `payload.user_id == current_user.id`.
- **Actual data disclosure today: ~nil.** The response (`get_progress_data`) returns `spent`/`saved` from an **in-memory** `ProgressTracker` that is never populated in the request path (`app/engine/progress_tracker.py:6` `self.history = {}`) → both `None`; and challenge fields from `ChallengeTracker([])` (empty) → `[]`/`0`. The fetched B calendar is used only to compute challenge sums (all zero) and is **not echoed** in the response. So the IDOR currently leaks no B values — but it is wrong-by-design and becomes a real P1 leak the moment progress/challenges are wired.
- **Fix direction:** add `user=Depends(get_current_user)`, use `user.id`, drop/validate `payload.user_id` (403 on mismatch). Same for `/goal/state-progress` (`app/api/goal/routes.py:19-23`, body `GoalState.user_id`) — impact there is nil (in-memory analytics, self-echoed values) but the design is the same.
- **Do NOT rewrite:** the goal_service/progress engines; only bind identity to the session.

### N-P2-SECMON — Auth security-monitoring endpoints are publicly reachable (no auth)
- **Severity:** P2 (security-config disclosure; no PII).
- **Routes:** `GET /api/auth/security/status`, `GET /api/auth/security/password-config` (`app/api/auth/security_monitoring.py:110-113, 147-148`).
- **Verified:** both handlers declare **no** `Depends`. Their sub-router is included at `app/api/auth/routes.py:46`, and `auth_router` is mounted at `app/main.py:941` **without** the global `Depends(get_current_user)` (that dependency is only on `private_routers_list`, `main.py:1005`). Anonymous callers receive bcrypt round count, average hash time (ms), security-health status, and compliance booleans.
- **Contrast (correctly guarded — verified):** all `app/api/endpoints/{database_performance,cache_management,audit}.py` and `endpoints/security_monitoring.py` routes require `Depends(require_admin_access)`.
- **Fix:** add `Depends(require_admin_access)` to both handlers.

### N-P3-FLAGREAD — `/api/feature-flags` reads are not admin-gated; `/check` accepts arbitrary `user_id`
- **Severity:** P3. `app/api/endpoints/feature_flags.py:25,73,167` require only `get_current_user`; `/check` uses caller-supplied `user_id` (typed `Optional[int]`, while real ids are UUIDs, so it won't match). The **mutation** endpoint `/{flag_key}/set` IS guarded by an inline `is_admin` check (`feature_flags.py:133`).

### Verified NOT vulnerable (adversarial refutations)
- **Calendar `/generate` & `/redistribute` "unauthenticated"** — **FALSE POSITIVE.** `calendar_router` is in `private_routers_list`; the mount-level `Depends(get_current_user)` (`main.py:1005`) applies to every calendar route regardless of whether the handler declares a `user=` param. They are authenticated. (The handlers are stateless/in-memory, so even the missing per-user attribution has no data impact.)
- **Feature-flag SET privilege escalation** — **FALSE POSITIVE** (inline `is_admin` check at `feature_flags.py:133`).
- **`endpoints/security_monitoring.py` and `admin/rollback_webhook.py`** — not mounted / self-protected (HMAC); no exposure.
- Every id-taking financial route (`transactions`, `goals`, `installments`, `scheduled-expenses`) filters by **both** `id` and `user_id` in the WHERE clause (`app/api/base_crud.py` `CRUDHelper`/`AsyncCRUDHelper`; `transactions/services.py`; `scheduled_expense_service.py`; `smart_goal_advisor.py`). No numeric-id IDOR — ids are UUIDs.
- Premium/subscription reads (`users/routes.py`) hard-check `current_user.id != user_id → 403` **before** the query. IAP `/validate` blocks receipt reuse across users (`iap/routes.py:129`, 409 on mismatch).

---

## 2. AsyncSession / sync-query production risks (Phase — the headline of this pass)

**DEF-001 is not isolated to transactions. The same root cause — a route injecting `AsyncSession` (`Depends(get_async_db)`) then calling code that uses the synchronous SQLAlchemy API (`db.query(...)`, sync `def` returning a dict/list that is then `await`-ed) — recurs across at least four more router groups.** `AsyncSession` has no `.query`, so every such path raises `AttributeError` (or `TypeError: object dict can't be used in 'await' expression`) at runtime.

### N-P1-3 — Systemic async/sync mismatch (verified sites)

| # | Endpoint(s) | Injected | Sync callee | Failure | Reachable? | Sev |
|---|---|---|---|---|---|---|
| baseline | `GET/GET{id}/PUT/DELETE /api/transactions` | AsyncSession | `transactions/services.py` `db.query` | 500 | **core** | **P0 (DEF-001)** |
| A | `POST /api/ai/snapshot` (`ai/routes.py:61`) | AsyncSession | `save_ai_snapshot()` sync + `db.query(User)` in `ai_personal_finance_profiler.py:18`; also `await <dict>` | 500 every call | non-core (AI) | P2 |
| B | `GET /api/analytics/monthly`, `GET /api/analytics/trend` (`analytics/routes.py:43,52`) | AsyncSession | `get_monthly_category_totals/get_monthly_trend` sync `db.query(...)` (`app/services/analytics_service.py:12,31`) — **also references `Transaction.timestamp`, a column that does not exist** (model has `spent_at`) | 500 every call | **not called by mobile** (Flutter uses `/analytics/behavioral-insights` + `/seasonal-patterns`, which are correctly async) | P2 |
| C | `GET /api/ai/*` — 14 analyzer endpoints (`spending-patterns`, `personalized-feedback`, `weekly-insights`, `financial-health-score`, `spending-anomalies`, `savings-optimization`, `day-status-explanation`, `category-suggestions`, `assistant`, `spending-prediction`, `profile`, `goal-analysis`, `monthly-report`, `advice`) | AsyncSession | `AIFinancialAnalyzer.__init__`→`_get_user()`→`self.db.query(User)` (`ai_financial_analyzer.py:40`) | AttributeError **swallowed by `except Exception` → HTTP 200 empty fallback** | non-core (AI) | P2 |
| D | `GET /api/goals/budget/allocate`, `/budget/progress`, `/budget/adjustment_suggestions` (`goals/routes.py:600,622,642`) | AsyncSession (`from app.core.async_session import get_async_db as get_db`, line 18) | `GoalBudgetIntegration.*` sync `db.query` (`goal_budget_integration.py:33,40,155,258-287`; the auto-transfer path also `db.add`/`db.commit`) | 500 | **not called by mobile** (Flutter uses `/goals/adjustments/suggestions` etc., which are correctly async) | P2 |

- **Confirmed correct (not broken):** `dashboard`, `calendar`, `goals` CRUD/statistics/health/adjustments, `habits`, `installments`, `account_management`, `analytics` (behavioral-insights/seasonal-patterns/feature-usage/access/paywall) all use `await db.execute(...)` properly. The pure sync-injecting routers (`behavior`, `insights`, `cohort`, `plan`, `mood`, `notifications`, `onboarding`, `users`, `ocr`, `calendar` saved, `expense`, `financial`) consistently use `get_db` (real sync `Session`) — no inverse bug found.
- **Why P1-systemic even though each broken endpoint is non-core:** when Fable fixes DEF-001 in `transactions`, it **must sweep A–D or they stay broken/masked.** Case C is the worst pattern — a broad `except Exception` turns a hard bug into a silent 200 fallback, so the premium AI feature looks healthy while never running.
- **Fix direction:** for each, either convert the service to async (`await db.execute(select(...))`, `await db.commit()`) **or** inject a real sync `Session` (`app.core.session.get_db`) and call the sync function off the event loop; mirror the working `app/api/dashboard/routes.py`. **Do not just `await` a sync `def`.**

### N-P2-CHALLENGE — Challenge stateless endpoints always 500 (signature/import mismatch)
- **Routes:** `POST /api/challenge/eligibility|check|streak` (`app/api/challenge/routes.py:34-54`).
- **Verified:** routes import `check_eligibility` and `check_eligibility as evaluate_challenge` from `app/services/challenge_service.py`. Real signatures require a `db: Session`: `check_eligibility(user_id, current_month, db)` (`:44`) and `run_streak_challenge(user_id, challenge_id, required_days, db)` (`:149`). The routes call them **without `db`** and with wrong positional args (`/streak` passes `(calendar, user_id, log_data)` for `(user_id, challenge_id, required_days, db)`). `/check`'s alias makes `evaluate_challenge` actually call `check_eligibility` with a calendar as `user_id`. → `TypeError`/`AttributeError` → 500 on every call. The real evaluator `app/api/challenge/services.py:8 evaluate_challenge(calendar, today_date, challenge_log)` is never wired up.
- **Reachability:** not called by the mobile app (Flutter uses `/challenge/{id}/progress`, `/challenges`). **P2** (deferred feature fully broken; strong evidence it was never integration-tested).

---

## 3. Financial correctness (Phase 3)

Invariants and deterministic examples are in `financial-invariants.md`. Confirmed violations:

### N-P1-DASH-SOFTDELETE — Dashboard/quick-stats include soft-deleted transactions
- **Severity:** P1 (core financial correctness; **latent behind DEF-001** which currently 500s delete).
- **Verified:** `delete_transaction` soft-deletes (`app/api/transactions/services.py:301` `txn.deleted_at = now`); the ledger endpoints filter `Transaction.deleted_at.is_(None)` (`services.py:167,194,214,292`). **Every** dashboard aggregation omits that filter — `grep -c deleted_at app/api/dashboard/routes.py` = **0**. Six sum/group queries (`dashboard/routes.py:60-67, 75-82, 94-103, 179-186, 487-513`) filter only `user_id` + date range. There is **no** global SQLAlchemy soft-delete loader criterion.
- **Impact:** after a user deletes a transaction (core step B6), the ledger hides it but `balance = income − Σ(spend)`, today-spent, weekly overview, monthly spending, savings rate, and top-category **still include it**. Balance permanently diverges from the visible ledger.
- **Fix:** add `Transaction.deleted_at.is_(None)` to all six queries. **Sequencing:** ship with the DEF-001 delete fix (the divergence is only reachable once delete stops 500-ing).

### N-P1-DUP-DAILYPLAN — Duplicate `daily_plan` rows corrupt per-category budgets
- **Severity:** P1 (data integrity, persisted).
- **Verified:** `daily_plan` model has **no** `UniqueConstraint`/`__table_args__` (columns `user_id`,`date`,`category` are individually indexed only); **no** migration adds a composite unique (checked `0001`,`0016`, all 34). `save_calendar_for_user` **appends** `DailyPlan(id=uuid4(), …)` with no delete-first (`app/services/calendar_service_real.py`). `submit_onboarding` only **logs** `has_onboarded` (`app/api/onboarding/routes.py:63`) — there is **no early-return guard**, so a re-submit / mobile retry inserts a **second full set** of rows. Spend is then accrued via `.first()` (`app/services/core/engine/expense_tracker.py`), so only one of the duplicate rows is updated and the displayed per-category budget/remaining silently diverges.
- **Note the inconsistency:** a different save path *does* delete-first (`app/services/user_data_service.py:51` `db.query(DailyPlan).filter_by(user_id=user_id).delete()`); the onboarding path does not.
- **Fix:** add `UNIQUE(user_id, day-normalized date, category)` **and** make `save_calendar_for_user` delete-first/upsert, **and** add an idempotency/`has_onboarded` guard on `POST /onboarding/submit`. Invariant: **at most one `daily_plan` row per (user, day, category).**

### N-P2-BUDGETFLOAT — Budget engine does all money math in binary float + banker's rounding
- **Severity:** P2 (sub-cent drift; onboarding inputs are ~whole numbers so real-world impact is small, but it violates the money invariant).
- **Verified by live repro** (`python3` on the actual module): `generate_budget_from_answers` (`app/services/core/engine/budget_logic.py`) computes `income = monthly_income + additional_income` (float), `fixed_total = sum(...)` (float), `discretionary = income − fixed − savings`, and returns every field via Python `round(x, 2)` (round-half-to-**even**). Repro results:
  - `B1` income 6000 / fixed 1700 / savings 400 / discretionary **3900** ✅
  - `B8` income==fixed (2000/2000) → discretionary **0**, savings clamped **0** ✅
  - `B9` fixed>income → `ValueError` → HTTP 400 ✅
  - `B10` (3000, fixed 2800, savings 500) → savings clamped **200**, discretionary **0** ✅
  - negative income → `ValueError: Income cannot be negative` ✅ (rejected via `classify_income`)
  - `0.1 + 0.2` income → stored `0.3` (masked by `round`), but internal value is `0.30000000000000004`
  - `100.005` income → `100.0` (float repr + banker's rounding; a user's half-cent is lost)
- **Money invariant risk:** for inputs carrying sub-cent precision, `total_income ≠ fixed_expenses_total + savings_goal + discretionary_total` to the cent, and `.xx5` boundaries round the wrong way vs financial ROUND_HALF_UP.
- **Fix:** convert inputs to `Decimal` at function entry; do arithmetic in `Decimal`; replace `round(v,2)` with `v.quantize(Decimal('0.01'), ROUND_HALF_UP)`.

### N-P2-GOALEXP — `GoalBudgetIntegration._get_monthly_expenses` filters `amount < 0` but expenses are stored positive
- **Severity:** P2 (latent — endpoint also 500s per §2-D).
- **Verified:** `goal_budget_integration.py:313-318` sums `Transaction.amount` where `amount < 0` ("Expenses are negative"), but the app stores expenses **positive** (`schemas.py` `validate_amount` min `0.01`; `services.py:118-120` rejects `amount <= 0`; dashboard uses `income − Σamount`). → `_get_monthly_expenses` always returns 0 → `available_for_goals = monthly_income − 0` (full income), `allocation_ratio = 1.0`, never warns about over-allocation.
- **Fix:** change the predicate to match the positive-expense convention.

---

## 4. Database & migrations (Phase 2)

**Chain is well-maintained** (single head `0034`, no branches, no table-level drift — see §0). Column-level and constraint findings:

- **N-P2-USERNUM** — `users.monthly_income` and `users.savings_goal` are **unbounded `NUMERIC`** in the live DB (created bare in `0008` via raw `ALTER … ADD COLUMN monthly_income NUMERIC` at `:77` and `sa.Numeric()` at `:37`; no later migration adds precision). `users.annual_income` **is** `Numeric(12,2)` in the DB (`0006:110`) but the **model** still declares bare `Numeric` (`app/db/models/user.py:17,47,54`) → ORM/DB precision drift. These are the source-of-truth income figures the daily-budget engine divides by. Invariant: all stored money = `Numeric(12,2)`.
- **N-P2-EXPFLOAT** — `Expense.amount` is `Column(Float)` in the model (`app/db/models/expense.py:12`) though migration `0006:60-67` converted the DB column to `Numeric(12,2)`; `Expense.user_id` is `String` in the model but UUID+FK in the DB (`0006`). Reads through the ORM re-introduce float for money.
- **N-P2-NOFK** — five user-scoped tables have **no FK on `user_id`** in model or migration → orphan rows survive user deletion: `moods`, `budget_advice`, `notification_logs`, `push_tokens`, `ignored_alerts` (`0002`,`0005`,`0016:33-84`,`0028` create them FK-less). Contrast `notifications`/`goals`/`installments`/`subscriptions`/`redistribution_events` which have FK+CASCADE (`0014`,`0022`,`0025`). `push_tokens` orphans could push to a deleted user's device.
- **N-P3-PLATFORM** — `0016:129` adds `push_tokens.platform` as `NOT NULL` **without `server_default`**; safe on a fresh (empty) table but fails on any non-empty DB, and the model's `default="fcm"` is ORM-only (non-ORM inserts violate NOT NULL).
- **N-P3-TZ** — `daily_plan.date` is `DateTime(timezone=True)` in the model but `TIMESTAMP WITHOUT TIME ZONE` in the DB (`0001:57`; not included in the `0031` timestamptz alignment). Works today only because `daily_plan` is written via a sync `Session`; would break under an async (asyncpg) session (the exact class `0031` fixed elsewhere).
- **N-P3-ENUM** — `notifications.type/priority/status/channel` are free `String` with a PyEnum only supplying the default `.value` (`notification.py:57-71`) — no DB-side validation, enum drift possible; `retry_count = Column(String, default='0')` stores an int counter as text (`:84`). Contrast `installments` which use `Enum(..., native_enum=False)`.
- **N-P3-SUBUNIQ** — `subscriptions.original_transaction_id` (store purchase identity / webhook match key) has only a **non-unique** index (`subscription.py:21`, `0034:43-47`); idempotency relies on an app-level find-or-create (`iap/routes.py:129-158`) that is not race-safe → two concurrent store notifications can both insert.
- **N-P3-OFFLINE** — inspection-based migrations (`sa.inspect(op.get_bind())` in `0006:30`, `0033:29`, `0022`) break `alembic upgrade --sql` (offline) with `NoInspectionAvailable`; online `alembic upgrade head` (the deploy path, `scripts/deployment/start.sh:180`) is unaffected, but `--sql` dry-runs referenced in `scripts/rollback/README.md` are unusable.
- **N-P3-DOCSTRING** — `0008`/`0009` docstrings claim `Revises: f8e0108e3527` (a revision absent from the active tree); an **orphaned second migration folder `app/migrations/`** with conflicting hand-written revision ids exists (not wired to `alembic.ini`; dead but misleading).
- **Empty-DB upgrade: NOT verified against PostgreSQL.** Migrations use `postgresql.UUID`/`JSONB` (PG-only), so a SQLite dry-run is not representative; the inspection-guarded migrations make legacy-only ops safe no-ops on a fresh DB by construction, but this must be confirmed by running `alembic upgrade head` against an empty Postgres in CI.

---

## 5. API ↔ Flutter contract (Phase 5)
Full table in `api-contract-map.md`. Key mismatches: DEF-008 (trailing slash on `/transactions`), stale Flutter `/onboarding_*` step calls to nonexistent backend routes, and several broken backend endpoints that are **not** mobile-called (which is why they escaped the prior production smoke).

## 6. Flutter state & navigation (Phase 6)
Partial (inspector did not complete; spot-checked). The codebase uses `if (mounted)` guards in **38** files (context-after-await awareness is present). `DEF-007` (defaults to `development`) stands. `mobile_app/lib/services` contains a large duplicate-engine surface (many `*_budget_engine.dart`, `*_financial_engine.dart`) — see Phase 11. Full Flutter provider/dispose sweep is a **remaining gap** (marked in `test-gap-analysis.md`).

## 7. Token & session security (Phase 7)
**Primary JWT path is sound.** `app/services/auth_jwt_service.py` validates `audience=JWT_AUDIENCE` (`:176,:370`) and enforces token **type** (`:593` `if payload.get("token_type") != token_type: raise …`), so **refresh-cannot-be-used-as-access** (and vice-versa) — the suspected weakness is **refuted**. Notes: a secondary decode `app/core/security.py:1454` omits the `audience=` arg, and `security.py:1511` decodes with `options={"verify_signature": False, "verify_exp": False}` (extract-only; confirm it never gates an auth decision) — **P3, verify**.

## 8. Input validation & abuse (Phase 8) — partial
Not fully swept (inspector did not complete). Confirmed related pattern: DEF-002 is a validator raising an **unhandled** exception → 500 instead of 422 (`transactions/schemas.py`). Systemically, **75 `HTTPException(detail=f"...{str(e)}")` sites** in `app/api` leak internal exception text to clients (§10). Transaction amount is bounded (`> 1_000_000` rejected, `min 0.01`). A full malformed-input matrix remains a gap.

## 9. Performance & query (Phase 9) — partial
- Transactions list **is paginated** (`list_user_transactions` default `limit=100`, `offset=skip`, `services.py:159,179`) — not unbounded. Dashboard aggregates via SQL `func.sum`/`GROUP BY` (not in-memory). No obvious N+1 in the hot core paths.
- Concerns (est., not load-tested): per-request full-month calendar recompute (`calendar_service_real.get_calendar_for_user` opens its own `SessionLocal()` per call); OCR runs in request/worker paths. First likely to strain at scale: calendar generation and the AI/analytics endpoints (once un-broken). Marked **estimate**.

## 10. Error handling & observability (Phase 10)
- **N-P2-ERRLEAK** — **75** `HTTPException(detail=…str(e)…)` sites in `app/api` return raw internal exception messages to clients (e.g. `feature_flags.py:161-163`).
- **N-P2-SWALLOW** — **233** `except Exception` handlers in `app/api`; the AI-analyzer pattern (§2-C) and the calendar fallback (commit `f45bb47` "return empty list instead of throwing") show broad catches that convert real failures into HTTP 200 with empty/fallback data — masking outages from clients and uptime checks. Same class flagged in `verified-defects.md` DEF-006 for `/health`.

## 11. Dead code / deps / config (Phase 11) — partial
- **`goal` vs `goals` routers:** both mounted (`main.py:964,965`) — **not dead**. `goal_router` is the small legacy 3-endpoint progress router carrying the §1 IDOR; `goals_crud_router` is the real 961-line CRUD. Keep both, fix `goal`.
- **Deploy-config sprawl:** `Dockerfile`, `nixpacks.toml`, `render.yaml`, `start.sh` all present. `render.yaml` is legacy (Render is not the deploy target; Railway runs `start.sh`) → **P3, could mislead Fable**.
- Orphaned `app/migrations/` folder (§4 N-P3-DOCSTRING).
- Full unused-dependency sweep (Python + Flutter) is a **remaining gap**.

## 12. Android readiness (Phase 12)
`namespace`=`applicationId`=`mita.finance` (consistent), `compileSdk`/`targetSdk`=35, `minSdk`=24, Kotlin build via `build.gradle.kts`. Cleartext **disabled** + `networkSecurityConfig` present (good). Findings:
- **N-P2-ANDROID-POSTNOTIF** — manifest lacks `POST_NOTIFICATIONS` (`AndroidManifest.xml`); with `targetSdk=35` (Android 15) FCM notifications **will not display** on Android 13+ without it.
- **N-P2-ANDROID-SIGN** — release build **silently falls back to debug signing** if no keystore (`app/build.gradle.kts:71-76`) → Play rejects debug-signed AABs / ships a debuggable-key build.
- **N-P3-ANDROID-LOCATION** — `ACCESS_FINE_LOCATION` + `ACCESS_COARSE_LOCATION` requested; a finance app requesting precise location is a **Play policy / prominent-disclosure risk** unless justified.
- **N-P3-ANDROID-BACKUP** — no explicit `android:allowBackup="false"` → defaults to `true`; combined with any secure-storage fallback to shared-prefs, tokens could be included in device/cloud backups.
- Owner tooling (Android SDK install, `google-services.json`, keystore) is **not a code defect** — already in `owner-actions.md`; not repeated as a finding.

## 13. Test false confidence (Phase 13)
Summarized here; full list + required regression tests in `test-gap-analysis.md`. Headline: the `tests/` suite (16 files, **0 skips**) is almost entirely **engine-level unit tests** using **sync `Session`** (4 files sync vs 2 async), so the transaction/AI/analytics/goals-budget async-route bugs (§2) **cannot be caught** by them — this is exactly why DEF-001 and its siblings shipped green.

---

## Refuted / disproven / stale (do not act on)
1. **Calendar `/generate` & `/redistribute` unauthenticated** — refuted (mount-level auth). *(would-be P2/P0)*
2. **Feature-flag SET privilege escalation** — refuted (inline `is_admin`).
3. **Multiple alembic heads** — refuted (single head `0034`).
4. **Model↔migration table drift** — refuted (33==33).
5. **`/goal/user-progress` unauthenticated cross-user dump** — partially refuted: it **is** authenticated and currently returns ~no data; the real (latent) issue is an authenticated IDOR by body `user_id` (N-P2-IDOR-1).
6. **Refresh-token accepted as access token (missing token-type validation)** — refuted (`auth_jwt_service.py:593`).
7. **Analytics `/monthly`,`/trend` block a core screen** — stale: those endpoints are broken but **not mobile-called**; the mobile analytics endpoints are healthy.

## Coverage gaps this pass (be skeptical — not fully audited)
- Full Flutter provider/dispose/navigation sweep (Phase 6).
- Full malformed-input → 4xx/500 matrix (Phase 8).
- Concurrency reproduced under real load (Phase 4 is code-reasoning only).
- Empty-DB `alembic upgrade head` against real PostgreSQL (Phase 2).
- Unused-dependency sweep (Phase 11).
These correspond to the workflow inspectors that hit the session limit before finishing.

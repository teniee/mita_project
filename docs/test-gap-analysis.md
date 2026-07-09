# MITA Finance — Test Gap Analysis (false confidence + required regressions)

> Auditor: Claude (Opus 4.8), 2026-07-09, base `d54667a`. Read-only.
> Goal: explain why the suite is green while production 500s / miscomputes, and specify the exact regression tests Fable 5 must add **before or with** each fix.

---

## 1. Why the suite gives false confidence (verified)

### FC-1 — Tests use SYNC / mocked sessions; production routes use `AsyncSession`
- `tests/test_dashboard_api.py:34` — `mock_db = Mock(spec=Session)`. The DB is a **mock**; no query runs. The real `GET /api/dashboard` uses `AsyncSession` + `await db.execute`.
- `app/tests/conftest.py:74` — `async_session.AsyncSessionLocal = None` (the async session factory is **nulled** for tests).
- `app/tests/test_transactions_services.py` / `test_transactions_routes.py` — pass while `GET/DELETE /api/transactions` **500 in production** (DEF-001), because they drive the sync service directly / with a sync fixture and never exercise the async route wiring (`Depends(get_async_db)`).
- **Consequence:** the entire **async/sync class** of bug (DEF-001 and the new sites: `ai/snapshot`, `ai/*`, `analytics/monthly|trend`, `goals/budget/*` — `adversarial-audit.md §2`) is **invisible** to these tests. They will stay green after Fable "fixes" things unless the tests are rewired through the real async DI.

### FC-2 — Structural-only assertions (no execution, no values)
`tests/test_dashboard_api.py` asserts only: `router is not None`, `router.prefix == "/dashboard"`, `callable(get_dashboard)`, `get_dashboard.__name__ == "get_dashboard"`, `hasattr(Transaction, "amount")`, `hasattr(DailyPlan, "spent_amount")`, etc. It **never calls the endpoint** and **never asserts a balance/spent number**. Such a test cannot catch the soft-delete balance bug (V1), an aggregation error, or a wrong query filter. It passes by construction as long as the symbols exist.

### FC-3 — Engine-only coverage; no API-contract tests through real DI
`tests/` (16 files, **0 skips/xfail**) is almost entirely engine unit tests (`test_calendar_*`, `test_rebalancer_*`, `test_budget_forecast_engine`, `test_scheduled_expense_*`, `test_velocity_alert_*`, `test_redistribution_audit_log`). There are **no** integration tests that (a) spin up the FastAPI app, (b) authenticate, (c) hit `/api/transactions`, `/api/dashboard`, `/api/calendar` through the **async** DB, and (d) assert exact numbers + DB state. This is why broken-but-unmocked endpoints ship.

### FC-4 — Broken endpoints escaped the production smoke because they have no mobile caller
`/analytics/monthly|trend`, `/goals/budget/*`, `/challenge/eligibility|check|streak`, `/ai/*` are all broken server-side but **not on the mobile call graph** (`api-contract-map.md`), so the app-driven smoke never touched them. A backend-contract test suite must exercise **every mounted route**, independent of what the app currently calls.

### FC-5 — Error-swallowing hides failures from tests too
The `except Exception → success_response(fallback)` pattern (AI analyzer, `adversarial-audit.md §2-C; §10`) means even an integration test that only asserts HTTP 200 would pass against a completely broken endpoint. **Assert on content, not status.**

### FC-6 — No SQLite/PostgreSQL parity
Migrations are Postgres-only (`postgresql.UUID`/`JSONB`); tests that use a mock or SQLite cannot validate the real schema, the `Numeric(12,2)` precision, timezone columns, FK/CASCADE, or the empty-DB `alembic upgrade head`. None of these is currently asserted.

---

## 2. Required regression tests per defect (write these first)

### Baseline P0/P1 (prior audit)
| Defect | Test (must exercise the REAL async route + DB) |
|---|---|
| DEF-001 | Integration through `get_async_db`: after create, `GET /api/transactions/` returns the txn (200, not 500); `GET /{id}` 200; `DELETE /{id}` 200 then absent from list. Must FAIL on today's code. |
| DEF-002 | Unit: `TxnUpdate(amount=100.00)`, `"100.00"`, `100`, `Decimal("100")`, `None` all valid; API `PUT /api/transactions/{id}` → 200 and dashboard/calendar recompute. |

### New P1
| ID | Test |
|---|---|
| N-P1-DASH-SOFTDELETE (V1) | Integration: create txn → dashboard balance/spent reflect it; **soft-delete** → dashboard balance/spent revert to pre-txn values (asserts exact numbers, not status). Must FAIL today. |
| N-P1-DUP-DAILYPLAN (V3) | Integration: `POST /onboarding/submit` **twice** → assert `count(daily_plan WHERE user,day,category) == 1`; after a transaction, assert `spent_amount == txn.amount` (not split/duplicated). |
| N-P2-IDOR-1 | Integration: user A auth, `POST /api/goal/user-progress` with body `user_id=<B>` → must NOT return B data (expect 403 or A-scoped). Regression: A's own id works. |

### New async/sync sites (P2, but sweep with the DEF-001 fix)
| ID | Test |
|---|---|
| §2-A ai/snapshot | `POST /api/ai/snapshot` (seeded user+txns) → 200 + persisted `AIAnalysisSnapshot` row (not 500). |
| §2-B analytics | `GET /api/analytics/monthly` & `/trend` → 200 with expected aggregation; also assert `Transaction.timestamp` is not referenced (use `spent_at`). |
| §2-C ai analyzer | `GET /api/ai/spending-patterns` (seeded expenses) → **non-empty** patterns (assert content, catching the swallowed fallback). |
| §2-D goals budget | `GET /api/goals/budget/allocate|progress|adjustment_suggestions` → 200 not 500; and V4: seed positive expenses, assert `_get_monthly_expenses` returns their sum. |
| N-P2-CHALLENGE | `POST /api/challenge/eligibility|check|streak` → 200 with valid schema; unit asserts the service is called with a `Session` and correct args. |

### Financial (property tests)
| ID | Test |
|---|---|
| V2 budget float | Property: random 2-dp `monthly_income, additional_income, fixed, savings` → assert `total_income == fixed + savings + discretionary` **exactly**; assert `.xx5` boundaries round half-**up** (`1.005 → 1.01`). |
| V5 OCR | Unit: `record_expense(day, …)` creates a `Transaction` with `spent_at` set (no `date=` kwarg); e2e OCR receipt → transaction persisted. |

### Security / auth
| ID | Test |
|---|---|
| N-P2-SECMON | `GET /api/auth/security/status` and `/security/password-config` → 401/403 for anonymous & non-admin, 200 for admin. |
| Token type (regression, currently passing) | Assert a refresh token is rejected as an access token and vice-versa (`auth_jwt_service.verify_token` type check) — lock in the correct behavior so a refactor can't remove it. |

### Database / migration (CI, real Postgres)
| ID | Test |
|---|---|
| Empty-DB upgrade | In CI with a service Postgres: `alembic upgrade head` from empty → succeeds; head == `0034`; `alembic heads` reports exactly one. |
| Schema assertions | `users.monthly_income/savings_goal/annual_income`, `expenses.amount` are `Numeric(12,2)`; `daily_plan` has `UNIQUE(user_id, day, category)`; the 5 FK-less tables reference `users.id ON DELETE CASCADE`. |
| Cascade | Delete a user → rows in `moods`, `budget_advice`, `notification_logs`, `push_tokens`, `ignored_alerts` are removed (after FK added). |

---

## 3. Test-infrastructure changes Fable should make (enablers)
1. **An async integration harness**: TestClient/httpx against the app with `get_async_db` overridden to a **real** async session on a **PostgreSQL** test container (not SQLite, not a Mock). Without this, none of the async-route regressions above are meaningful.
2. **Content assertions over status assertions** everywhere (defeats FC-5).
3. **A full-route contract test** that enumerates every mounted route and asserts each returns a non-5xx for a valid authenticated request with seeded data (defeats FC-4).
4. **Run the full suite in CI with Postgres + Redis service containers** (the prior audit noted the suite needs live infra and partially hangs without it).
5. Remove/replace the structural-only `test_dashboard_api.py` with a real behavioral test.

## 4. Coverage gaps (not audited this pass — Fable should still add)
- Flutter widget/integration tests for token refresh interceptor and JSON (de)serialization against real payloads.
- Concurrency tests (two simultaneous txn creates; two refreshes; duplicate onboarding) — `adversarial-audit.md` Phase 4 is code-reasoning only.
- Malformed-input matrix (long strings, NaN/Infinity, bad UUID/date) asserting 4xx not 5xx.

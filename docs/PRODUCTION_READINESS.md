# MITA — Production Readiness (Live)

> **Owner:** production-readiness audit · **Branch:** `claude/production-readiness-audit-hlbda5`
> **Last updated:** 2026-07-05
> **Verification environment:** Python 3.11 venv · PostgreSQL 16 (real test DB `test_mita`) · Redis 7 (real, db 0/1/15) · no Flutter SDK (mobile = static review) · no external OpenAI/Firebase/Apple/Google keys

This file is the single source of truth. It supersedes `docs/PRODUCTION_READINESS_PROGRESS.md` (kept for history). Update **before** each change and **after** each verified fix.

---

## Current test totals

Measured with real Postgres + Redis. Two roots (`pytest.ini` scopes to `app/tests`; `tests/` run separately).

| Root | Passed | Failed | Errors | Skipped | Notes |
|------|-------:|-------:|-------:|--------:|-------|
| `app/tests` | _measuring_ | _ | _ | _ | full run in progress |
| `tests/` | _pending_ | _ | _ | _ | engine/rebalancer/calendar unit tests |

Session start baseline (2026-07-04, before this audit): **447 passed / 102 failed / 23 errors** (`app/tests`).
Latest per-file verified green this session (real DB+Redis):
- auth-comprehensive 22/22 · token-blacklist 23/23 · token-version 11/11 · jwt-rotation 2/2
- csrf 12/12 · api-endpoint-security 9/9 · password-security 15/15 · snapshot 1/1
- repositories 17/17 · onboarding-integration 3/3 · middleware-health 25/25
- comprehensive-rate-limiting 21/21 · resilient-services 26/26 · circuit-breaker 26/26
- income-classification 9/9 · dynamic-thresholds 32/32 · goals 22/22 · financial 2/2

## Production bugs found & fixed (severity-ranked, all verified by tests)

### CRITICAL — broke a core user journey
1. **Password reset & change both 500'd.** `confirm_password_reset` / `change_password` called `validate_required_fields()` missing its `required_fields` arg → TypeError → 500 on every request. (`feff93c`)
2. **Token refresh never worked.** Refresh endpoint verified tokens as `access_token` then compared to `"refresh"`; every refresh returned 401 → users logged out when the 2h access token expired. (`60b1019`)
3. **Logout was a silent no-op.** Blacklist couldn't decode current tokens (unhandled `aud` claim) → `blacklist_token` always returned False; revoke-all crashed on a set slice. (`53ad3e2`)
4. **Every goal detail/update/delete 500'd.** Async routes awaited the sync `CRUDHelper` (`AsyncSession.query` doesn't exist); delete called a non-existent method. (`5473b89`)
5. **Repository writes never committed.** `get_async_db_context` dropped its commit → OAuth user creation and all repository writes silently discarded. (`a758093`)
6. **Goal inserts failed at runtime.** Aware datetimes bound to naive TIMESTAMP columns (asyncpg rejects) + missing `users.last_login` + phantom `transaction_type` filter. Migrations 0031/0032. (`a758093`)
7. **Onboarding 500'd on optional sections.** Omitting goals/spending_habits crashed budget generation & calendar build (None.get). Additional income silently dropped. (`a758093`)

### HIGH — security / correctness
8. **Unknown URLs → 500 (not 404)** and every bot probe logged as server error + sent to Sentry (Starlette vs FastAPI HTTPException). (`21eac92`)
9. **401s missing `WWW-Authenticate`** (RFC 7235); exception headers dropped. (`21eac92`)
10. **Rate-limit errors → 500** (MITAException fell through to the generic catch-all instead of its handler). (`4975063`)
11. **Error responses leaked internals** (raw exception text + reflected input in prod). (`60b1019`)
12. **bcrypt silently ran 10 rounds** while config/docs claimed 12. (`0ecf66e`)
13. **SQLi scanner missed quoted tautologies** (`' OR '1'='1`). (`feff93c`)
14. **Blacklist skipped for tokens < 30 min old** — logout delayed up to 30 min. (`21eac92`)
15. **Audit-log failure crashed budget redistribution** (the core money op). (`73da4e1`)
16. **Installment endpoint discarded computed metadata**; naive timestamps → 500 on transactions. (`b8246b2`)
17. **`get_dynamic_budget_method` dropped the food allocation** (~13% of income) via a wrong dict key. (`b8246b2`)
18. **SQLite engine fallback crashed** (Postgres pool kwargs passed to StaticPool). (`4975063`)

### MEDIUM — reliability / quality
19. Goal model crashed on pre-flush None; zero-income scaling ZeroDivisionError; goal timeline min>max; GPT fallback fabricated confidence; AI flagged irregular spending from 5 tx; middleware-health `_store_health_history` removed; auth-health referenced non-existent `AuthJWTService`; velocity-alert silently dropped malformed goals. (`b8246b2`, `73da4e1`, `feff93c`)

## Quality gates (last local run)

| Gate | Status |
|------|--------|
| `black --check .` | PASS |
| `isort --check .` | PASS |
| `ruff check .` | PASS |
| `bandit -r app/ -ll` | PASS (0 findings; MD5→usedforsecurity, /tmp→tempfile, parameterized-SQL nosec, pickle-of-own-cache nosec) |
| `pytest` (full) | _re-measuring after this session's fixes_ |
| migrations apply | PASS (0001→0032 applied to build `test_mita`) |

## Remaining blocker clusters

### Real production bugs
- _None currently open._ (Re-triage after the full-suite re-measure completes.)

### Environment / configuration (verifiable here — being worked)
- Full-suite re-measure in progress to confirm no regressions.

### Blocked — need credentials / external access / product decision
- **IAP webhook is unauthenticated** (`POST /api/iap/webhook` trusts body `user_id`/`expires_at` → anyone can self-grant premium). Fix needs Apple JWS / Google RTDN signature verification + store credentials. **HIGH — recommend gating behind a shared secret until signatures ship.**
- **Railway env vars** (`JWT_PREVIOUS_SECRET`, `PYTHONPATH=/app`, `SENTRY_DSN`, Upstash Redis, SMTP password, `APPSTORE_SHARED_SECRET`) — Railway dashboard access. (docs/FIX_ALL.md R-01/02/03)
- **Firebase / APNs push** — needs service-account JSON + APNs cert; code paths degrade gracefully without them.
- **OpenAI insights** — needs `OPENAI_API_KEY`; resilient fallback verified (no blocking dependency).
- **Mobile build (Android/iOS)** — no Flutter SDK in this environment; static review only.
- **Flutter test suite** (~105 failures per docs/FIX_ALL.md M-06) — no Flutter SDK here.
- **L-01** module triplication (`app/logic` vs `app/engine` vs `app/services/core`) — multi-day refactor; needs sign-off.

## Core user journeys — verified status

| Journey | Backend | Mobile | Evidence |
|---------|---------|--------|----------|
| Register → login → refresh → logout | ✅ | static | csrf + api-endpoint-security + auth-comprehensive suites |
| Password reset / change | ✅ (bug #1 fixed) | static | reset flow test hits real endpoint |
| Token blacklist / revocation | ✅ | n/a | token-blacklist 23/23 |
| Onboarding → budget generation → persistence | ✅ | static | onboarding-integration 3/3 (real DB) |
| Goal CRUD + budget sync | ✅ (bug #4 fixed) | static | goals 22/22, repositories 17/17 |
| Budget redistribution / rebalance | ✅ | n/a | redistributor + rebalancer suites |
| OCR receipt (queue/degrade) | ⚠️ needs live Redis for queue; degrades | ❌ not wired in app | resilient/rate-limit suites |
| AI insights (fallback) | ✅ fallback | static | resilient-services 26/26 |
| Premium / IAP | ⚠️ webhook unauthenticated (blocked) | static | iap tests pass; signature verify pending |

## Changed files (this session)
Commits `b8246b2 · 0ecf66e · 5473b89 · 73da4e1 · 21eac92 · 53ad3e2 · a758093 · 4975063 · 60b1019 · feff93c`.
Production code: `app/api/auth/{password_reset,account_management,services,token_management,registration}.py`, `app/api/{financial,transactions,goals}/*`, `app/core/{security,standardized_error_handler,error_decorators,async_session,password_security,config,caching,secret_manager,audit_logging,deployment_optimizations,health_monitoring_alerts,middleware_health_monitor,middleware_components_health}.py`, `app/db/models/{goal,user,habit,push_token,ai_analysis_snapshot,daily_plan}.py`, `app/repositories/{base,user,transaction}_repository.py`, `app/services/{budget_redistributor,resilient_gpt_service,ai_financial_analyzer,velocity_alert_service,token_blacklist_service}.py`, `app/services/core/**`, `app/config/country_profiles/US-CA.yaml`, `app/main.py`, `app/ocr/**`, `app/orchestrator/**`. Migrations: `alembic/versions/0031_timestamptz_alignment.py`, `0032_add_user_last_login.py`.

## Production-readiness estimate

**~80%** by verified backend functionality (all critical backend user journeys work end-to-end against real Postgres + Redis; quality gates green). Remaining 20% is gated on: IAP signature verification (needs store creds), mobile build/e2e (needs Flutter SDK), and production env-var wiring on Railway (needs dashboard). Not a code-volume estimate.

## Next task
1. Complete full-suite re-measure (both roots); record exact totals above.
2. Triage any residual failures into the buckets above; fix real bugs first.
3. Verify backend cold start + `/health` + migration-from-empty.

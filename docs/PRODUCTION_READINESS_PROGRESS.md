# MITA — Production Readiness Progress (Live Tracker)

> **Started:** 2026-07-04 · **Last updated:** 2026-07-05
> **Branch:** `claude/production-readiness-audit-hlbda5`
> **Predecessor trackers:** `docs/FIX_ALL.md` (C/H/M/L/R issues, mostly FIXED), `docs/problems audit.md` (April 2026 audit)
> **Environment:** Python 3.11 venv (prod = 3.12 Docker), local Redis available, **no Postgres** (Postgres-bound tests unverifiable here), no Flutter SDK (mobile = static review only)

Statuses: `[x]` fixed+verified · `[~]` in progress · `[ ]` open · `[B]` blocked (credentials/product decision/environment)

---

## CRITICAL production bugs found & fixed this session (all verified by tests)

- [x] **Logout was a silent no-op.** `token_blacklist_service._extract_token_info` decoded JWTs without handling the `aud` claim every issued token carries → `InvalidAudienceError` swallowed → `blacklist_token()` always returned `False`. Logout/revocation never blacklisted anything. (`53ad3e2`)
- [x] **Revoke-all-user-tokens always crashed.** `blacklist_user_tokens` sliced the *set* returned by `smembers` → TypeError swallowed → returned failure. (`53ad3e2`)
- [x] **Blacklist skipped for tokens < 30 min old** — even where blacklisting worked, fresh tokens bypassed the check; logout took up to 30 min to take effect. Now checked unconditionally (fail-open on Redis outage retained). (`21eac92`)
- [x] **Every goal detail/update/delete endpoint returned HTTP 500.** Async goals routes awaited the sync `CRUDHelper` (`AsyncSession` has no `.query()`); the delete endpoint called a method that didn't exist. New `AsyncCRUDHelper` + regression tests. (`5473b89`)
- [x] **Unknown URLs returned HTTP 500 (SYSTEM_8001) instead of 404** and every bot probe was logged as a server error + shipped to Sentry. isinstance checks used `fastapi.HTTPException` while Starlette's router raises the parent class. (`21eac92`)
- [x] **Refreshed/OAuth tokens omitted `token_version_id`** → session-revocation consistency broken after refresh or Google login. (`53ad3e2`)
- [x] **bcrypt silently ran 10 rounds** (config default) while validation/docs claimed 12. Now 12 everywhere. (`0ecf66e`)
- [x] **401 responses missing `WWW-Authenticate`** (RFC 7235 violation) — exception-attached headers were dropped by the response builder. (`21eac92`)
- [x] **Failed audit-log insert crashed budget redistribution** (the core money operation). (`73da4e1`)
- [x] **Installment endpoint discarded computed metadata** (monthly payment, total cost never reached the client; wrong `affordable` key). (`b8246b2`)
- [x] **Naive client timestamps → 500** on transaction validation (aware/naive comparison TypeError). (`b8246b2`)
- [x] **`get_dynamic_budget_method` lost the food allocation** (~13% of income) summing a non-existent `groceries` key — user-facing percentages didn't add up. (`b8246b2`)
- [x] Goal model crashes on pre-flush instances (`progress`/`saved_amount` None). (`b8246b2`)
- [x] Zero-income crash in income scaling (`0 ** negative` ZeroDivisionError); goal timeline constraints could return min > max; `small_purchase` dispatcher missing required arg. (`b8246b2`)
- [x] GPT-service health check reported healthy ~2/3 of the time while the API was down; connection-failure fallbacks parsed as real model output (fabricated confidence). (`73da4e1`)
- [x] AI analyzer flagged `irregular_spending` from 5 transactions straddling a month boundary. (`73da4e1`)

## CI / quality gates

- [x] **black** — repo-wide reformat (271 files were failing the blocking gate ⇒ CI was permanently red since M-05 made gates blocking). Now `black --check .` passes.
- [x] **isort** — passes.
- [x] **ruff check .** — 65 errors fixed (unused/shadowed imports incl. a latent bug: pydantic `ValidationError` shadowing meant pydantic validation errors mapped to 500 not 422; SQLAlchemy `== True` → `.is_(True)`; etc.). Passes.
- [x] **bandit -r app/ -ll** — 23 findings resolved: MD5 → `usedforsecurity=False` (5), hardcoded `/tmp` → `tempfile.gettempdir()` (6), missing request timeout checked (already present — false positive annotated), parameterized-SQL false positives annotated, pickle-of-own-cache-data annotated. Exit 0.
- [~] **pytest in CI** — CI runs bare `pytest` (= `app/tests` incl. dirs needing live Postgres). Needs service containers or scoping (see next task).
- [ ] CI not yet exercised on GitHub for this branch (push pending).

## Test-suite triage (in progress this session; counts being re-measured)

Fixed this session (all previously failing/stale): income classification (9), dynamic thresholds (7), goals model/routes (18+4), transactions routes (2), financial installment (2+script), password security (15), token blacklist (23), token version (11), JWT rotation (2), snapshot route (1), resilient GPT (26), circuit breaker (26), AI analyzer (25), budget redistributor (1), rate limit (2), tasks/worker/sentry/iap (6), testsprite/AI-API/insights (47 after removing suite-wide `sys.modules['openai']` pollution).

Remaining known-failing clusters (per last full run, being re-measured):
- `app/tests/test_repositories.py` — needs live Postgres (fixtures create real tables). **[B: environment]**
- `app/tests/test_onboarding_calendar_integration.py` — same. **[B: environment]**
- `app/tests/performance/*` — live DB + load; CI/nightly with services only. **[B: environment]**
- `app/tests/security/test_api_endpoint_security.py` — asserts legacy route paths (404 drift) + patched internals; stale, needs rewrite against current router map.
- `app/tests/security/test_mita_authentication_comprehensive.py` — mix of Redis-dependent + stale internals.
- `app/tests/test_comprehensive_middleware_health.py` — health-status enum drift + removed private methods; stale.
- `app/tests/test_comprehensive_rate_limiting.py` — partially fixed by live Redis; remainder asserts drifted internals (penalty multipliers, payload shapes).

## Remaining blockers — need credentials / product decisions / external access

- [B] **IAP webhook is unauthenticated** (`POST /api/iap/webhook` trusts `user_id`/`expires_at` from the body — anyone can grant themselves premium). Proper fix = verify Apple signed JWS / Google RTDN signatures; needs product decision + store credentials. **HIGH severity — recommend disabling the route or gating behind a shared secret until signature verification ships.**
- [B] **R-01/R-02/R-03** Railway env fixes (`JWT_PREVIOUS_SECRET`, `PYTHONPATH`, Sentry/Redis/SMTP vars) — needs Railway dashboard access.
- [B] **L-02** stale remote branches — blocked by GitHub rulesets.
- [B] Mobile ↔ backend integration gaps (calendar/budget sync, OCR wiring) — feature work + Flutter toolchain.
- [B] Flutter test suite (105 failures noted in M-06) — no Flutter SDK here.
- [B] **L-01** module triplication (`app/logic` vs `app/engine` vs `app/services/core`) — multi-day refactor; consolidation plan needed.
- [B] OCR "99.8% accuracy" claim vs Tesseract reality — marketing/product decision.

## Changed files: see commits `b8246b2`, `0ecf66e`, `5473b89`, `73da4e1`, `21eac92`, `53ad3e2`, plus pending commit (formatting + bandit + ruff + progress file).

## Next task

1. Finish full-suite re-measure; classify/fix remaining clusters.
2. Scope CI pytest (or add service containers) so the backend job can pass.
3. Commit + push branch; verify GitHub CI.

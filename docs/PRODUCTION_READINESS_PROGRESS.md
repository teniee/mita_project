# MITA — Production Readiness Progress (Live Tracker)

> **Started:** 2026-07-04
> **Branch:** `claude/production-readiness-audit-hlbda5`
> **Predecessor trackers:** `docs/FIX_ALL.md` (C/H/M/L/R issues, mostly FIXED), `docs/problems audit.md` (April 2026 honest audit)
> **Environment:** Python 3.11.15 (prod = 3.12 via Dockerfile), no Flutter SDK available (mobile = static review only), no DB/Redis (unit tests only)

This file is the single source of truth for the current production-readiness pass.
Update it after every verified fix: status, root cause, changed files, next task.

---

## Verification of prior audit claims (2026-07-04)

| # | Claim (from `problems audit.md`) | Verified? | Notes |
|---|----------------------------------|-----------|-------|
| 1 | `goals/routes.py` imports non-existent `app.services.notification_integration` | **FALSE** | File exists; `get_notification_integration` defined at `app/services/notification_integration.py:641`. Full import check pending. |
| 2 | `financial/routes.py` dead statements — installment metadata computed and discarded | **CONFIRMED** | `app/api/financial/routes.py` ~84–93: `monthly_payment * payload.months` no-op + discarded dict literal. |
| 3 | `app/main.py:84` uses `str \| None` (breaks Python 3.9 local dev) | **CONFIRMED** | Only PEP 604 usage in `app/` (1 file). Prod runs 3.12 — dev-experience issue, not prod blocker. |
| 4 | 8 failing tests (category mapping, discretionary calc, scheduled impact) | **STALE** | The cited test files (`test_category_mapping_fix.py`, `test_income_location_budget_allocation.py`) do not exist in the current tree. Running current suite to get ground truth. |
| 5 | `except Exception: pass` in production files | **CONFIRMED (partial)** | ~10 production files; several look like legitimate best-effort cache/limiter ops. Case-by-case review needed. |
| 6 | Tracked junk files | **CONFIRMED** | `.DS_Store`, `app/api/goals/routes.py.backup`, `routes.py.before_fix`, 2× `project.pbxproj.backup` tracked in git. |
| 7 | docker-compose.yml hardcoded postgres creds | **CONFIRMED (dev-only)** | Only in dev compose files; `docker-compose.prod.yml` correctly uses env vars. Low severity. |

## Prioritized checklist

Statuses: `[ ]` open · `[~]` in progress · `[x]` fixed+verified · `[B]` blocked (needs credentials/product decision)

### P0 — Broken code paths / test truth
- [~] **PR-2** Run full backend test suite; triage every failure and collection error into real-bug vs test-infra buckets.
- [ ] **PR-1** `app/api/financial/routes.py`: installment metadata (monthly payment, total cost) computed but never returned to client. Fix: include in response.

### P1 — Reliability / correctness
- [ ] **PR-3** `app/main.py:84` `str | None` → `Optional[str]` (restores Py3.9 local dev; zero prod risk).
- [ ] **PR-4** Verify goals routes import & router registration end-to-end.
- [ ] **PR-5** Review production `except Exception: pass` sites; add logging where silent failure hides real errors.

### P2 — Hygiene / deployment
- [ ] **PR-6** Remove tracked junk files (`.DS_Store`, `*.backup`, `*.before_fix`); ensure `.gitignore` covers them.
- [ ] **PR-7** CI review: workflows reference correct paths/versions after repo restructure; pytest invocation matches what can actually pass.

### Deferred — needs credentials / product decision / external access
- [B] **R-01/R-02/R-03** Railway env-var fixes (JWT_PREVIOUS_SECRET, PYTHONPATH, SENTRY_DSN/Redis/SMTP) — needs Railway dashboard access.
- [B] **L-02** Delete 81+ stale remote branches — blocked by GitHub repo rulesets.
- [B] Mobile ↔ Backend integration gaps (calendar/budget sync, OCR wiring in app) — feature work requiring product decisions + Flutter toolchain.
- [B] Flutter test suite (105 failures reported in M-06 note) — no Flutter SDK in this environment.
- [B] **L-01** Module consolidation (app/logic vs app/engine vs app/services/core) — multi-day refactor; needs sign-off.

## Changed files (this session)

| File | Change | Issue |
|------|--------|-------|
| `docs/PRODUCTION_READINESS_PROGRESS.md` | created (this file) | — |

## Next task

PR-2: run `pytest` on `app/tests` and `tests/`, triage results.

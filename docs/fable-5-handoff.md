# Fable 5 Execution Package — MITA Finance

> Prepared by: Claude (Opus 4.8), read-only production auditor · **2026-07-08 / 2026-07-09**
> Purpose: remove uncertainty so Fable 5 can implement fixes with zero re-discovery. Everything here is **evidence-backed** (production HTTP, Railway tracebacks, local reproduction, blob-hash diffs). Companion docs: `verified-defects.md`, `end-to-end-test-matrix.md`, `owner-actions.md`.
> **Do the security items in `owner-actions.md §1` regardless of code work — the repo is public with live secrets.**

---

## 1. Current verified system state

MITA is a FastAPI backend (`app/`) + Flutter app (`mobile_app/`) deployed on Railway (Postgres + Upstash Redis + Firebase). The **backend core is genuinely functional in production** — auth, onboarding/budget generation, dashboard, calendar, and transaction **create** all work with correct numbers, and Redis-backed token revocation is live. The **transaction read/update/delete** endpoints are **broken (HTTP 500)**, which breaks the app's Transactions screen and the edit/delete core-journey steps. There is a **P0 public secret leak**. The **local copy on disk is stale** vs what is deployed.

Production `/health`: `degraded` (only because Sentry is unconfigured); `database`, `redis`, `firebase` all connected; alembic `0034`.

## 2. Exact Git and Railway SHAs

| Item | Value |
|------|-------|
| GitHub repo | `teniee/mita_project` (**public**), default branch `main` |
| GitHub `main` HEAD | **`d682f3f969a6`** — "Enhance smoke test coverage and security hardening (#275)", 2026-07-08T20:29:32Z |
| Railway deployed commit (`/health.commit`) | **`d682f3f969a6`** — **matches GitHub HEAD** |
| Alembic head (repo & deployed DB) | `0034` |
| Local working dir | `E:\mita finance\mita_project-main\mita_project-main` — **NOT a git checkout** (extracted ZIP), **stale** (see DEF-004) |
| Railway project / service | `Mita Finance` (`d44d0580-…`) / `mita-production` (`b6cebfcc-…`) |

**Base of truth for Fable 5 = GitHub `teniee/mita_project@main` (`d682f3f969a6` or later). Clone fresh; do not edit the audited local copy** — its `app/main.py`, `app/core/async_session.py`, `app/services/token_blacklist_service.py`, `scripts/remote_smoke_test.py` are one PR behind deployed.

## 3. What is PROVEN working (first-hand, production)

- **Auth:** register (201), login (200), refresh rotation (200), **old refresh rejected (401)**, logout (200), **access token dead after logout (401)** → Redis revocation & blacklist are live.
- **Onboarding / budget:** `POST /api/onboarding/submit` → 200 with exact math: income 6000, fixed 1700, **discretionary 3900**, savings 400; 31-day calendar generated; real tier-weighted category breakdown.
- **Dashboard:** `GET /api/dashboard` → balance = income − month spend; today spend exact; `daily_targets` come from real `DailyPlan` rows (not the naive fallback).
- **Calendar:** `GET /api/calendar/saved/{y}/{m}` → full month, `YYYY-MM-DD` keys, every day non-zero limit; `GET /api/calendar/day/...` → 200.
- **Transaction CREATE:** `POST /api/transactions/` → 201; dashboard + calendar recalculate correctly (balance 6000→5958, today spent→42).
- **Persistence & recovery:** logout → re-login restores exact state.
- **Error contracts:** 404/401/422 with no 500s on bad input; security headers present; HTTP→HTTPS 301; `/docs`,`/openapi.json`,`/metrics` are 404 in prod.
- **Tooling:** backend suite collects 617 tests cleanly; `flutter analyze` → 0 errors; Flutter base URL defaults to prod, tokens stored via `SecureTokenStorage`/`flutter_secure_storage`.

## 4. What is NOT verified (be skeptical)

- Transaction **update/delete recalculation values** (blocked by the 500s — expected values are in `end-to-end-test-matrix.md` B5/B6).
- Email send (password reset/verification) — `SMTP_PASSWORD` absent; failure inferred, **not** exercised (avoided sending mail).
- Calendar behavior for **other months / leap-year / mid-month onboarding** (only current month, July 2026, verified) — B11–B14.
- **Flutter on a device** — no Android SDK this session; APK build failed. UI flows C1–C12 not executed.
- Full backend suite **pass rate** — needs live Postgres/Redis; not completable in a bare env.
- Redis MCP / leaked-instance liveness — MCP timed out.
- OCR, IAP, analytics, notifications endpoints — not exercised.

## 5. P0 defects (fix before closed beta)

- **DEF-001 — Transaction list/get/delete 500 (`AsyncSession` has no `.query`).** Routes inject an AsyncSession but call sync `db.query(...)` services without `db.run_sync`. Breaks Transactions screen + delete step. *(Prod 500 + Railway traceback.)*
- **DEF-003 — Live secrets in the public repo (`.mcp.json`).** Supabase secret key + Upstash Redis URL, public. **Owner action** (`owner-actions.md §1`).

## 6. P1 defects

- **DEF-002 — Transaction update (PUT) 500:** `TxnUpdate.amount` validator raises `ConversionSyntax` for *every* value (reproduced locally). Blocks *edit* independent of DEF-001.
- **DEF-004 — Local copy is stale** vs deployed (4 files behind PR #275, incl. token-blacklist security fix) → clone fresh.
- **DEF-005 — `SMTP_PASSWORD` missing** → email (password reset) cannot send. Owner config.

## 7. P2 defects

- **DEF-006** — `/health` = `degraded` solely due to missing `SENTRY_DSN`.
- **DEF-007** — Flutter defaults to `development` env (SSL pinning / crash reporting off) unless `--dart-define=ENV=production`.
- **DEF-008** — Flutter txn calls omit trailing slash → 307 redirect per request.

## 8. Exact files involved

| Defect | Files (fresh clone paths) |
|--------|---------------------------|
| DEF-001 | `app/api/transactions/routes.py` (list ~L285, get ~L798, update ~L850, delete ~L881) · `app/api/transactions/services.py` (`list_user_transactions` L165, `get_transaction_by_id` L189, `update_transaction` L209, `delete_transaction` L288). Correct pattern to copy: same file, `POST` route L130 `await db.run_sync(...)`. Async reference: `app/api/dashboard/routes.py`. |
| DEF-002 | `app/api/transactions/schemas.py` (`TxnUpdate` L258–277; reused validators L271–277; `TxnIn.validate_amount` L48–57) · `app/core/validators.py` (`sanitize_amount` L251+, `Decimal(str(amount))`). |
| DEF-003 | `.mcp.json` (root). |
| DEF-006 | `app/main.py` health aggregation (deployed version — clone fresh). |
| DEF-007 | `mobile_app/lib/config.dart` (L22). |
| DEF-008 | `mobile_app/lib/services/transaction_service.dart` (URLs L43, L98, L137, L182, L225). |

## 9. Exact reproduction steps

**DEF-001/002 (backend, against prod or local):**
1. `POST /api/auth/register {email,password,country:"US",annual_income:72000,timezone:"UTC"}` → 201, capture access token.
2. `POST /api/onboarding/submit` with the B1 body → 200.
3. `POST /api/transactions/ {amount:42.00,category:"food",spent_at:<now ISO>}` → 201 (works), capture `id`.
4. `GET /api/transactions/` → **500** (DEF-001). Railway log: `'AsyncSession' object has no attribute 'query'` at `services.py:165`.
5. `PUT /api/transactions/{id} {amount:100.00,category:"food"}` → **500** (DEF-002). Log: `ConversionSyntax` at `schemas.py:52`.
6. `DELETE /api/transactions/{id}` → **500** (DEF-001) at `services.py:288`.

**DEF-002 unit repro (no server):** `python -c "from app.api.transactions.schemas import TxnUpdate; TxnUpdate(amount=100.00)"` → raises `ValidationError: Invalid transaction amount format: [decimal.ConversionSyntax]` (also for `"100.00"`, `100`, `Decimal("100")`). `TxnIn(amount=100.00, category="food")` succeeds.

## 10. Exact expected behavior after fix

- `GET /api/transactions/` → 200 list (excludes soft-deleted).
- `PUT /api/transactions/{id} {amount:100.00}` → 200; dashboard balance 6000→**5900**, today spent→**100**, calendar today.spent→**100**.
- `DELETE /api/transactions/{id}` → 200 `{deleted:true}`; dashboard balance→**6000**, spent→**0**, calendar today.spent→**0**.
- `GET /api/transactions/{id}` → 200 single txn.

## 11. Recommended implementation order

1. **Owner security (parallel, non-code):** rotate + purge `.mcp.json` secrets (DEF-003) — see `owner-actions.md §1`.
2. **DEF-002** (schema-local, lowest risk): fix `TxnUpdate.amount` validator; add unit test.
3. **DEF-001** (transactions router async bridge): wrap the four sync service calls in `await db.run_sync(...)` (mirror the create route) **or** convert the four service functions to async `select(...)`. Add async-wired integration tests.
4. Redeploy; run the extended production smoke (§13).
5. **DEF-006** (health: don't let missing Sentry force `degraded`) and/or owner sets `SENTRY_DSN`.
6. **DEF-008** (Flutter trailing slash) alongside any transactions-screen work; **DEF-007** in the release build command.
7. Backend deferred-scenario **unit tests** (matrix B8–B20) for budget/calendar engines.

Keep every change targeted — the architecture is sound; no rewrite is warranted. The create route already proves the correct async/sync bridge pattern.

## 12. Tests required per fix

- **DEF-002:** unit — `TxnUpdate(amount=…)` accepts `100.00`/`"100.00"`/`100`/`Decimal`/`None`; API — PUT changes amount → 200 + recalced dashboard/calendar.
- **DEF-001:** integration with the **async** session wiring (a `TestClient`/httpx call through the real route + `get_async_db`, not a sync fixture) — list returns created txn; get returns one; delete soft-deletes and disappears from list. *(Current `test_transactions_*` pass with a sync session and miss this — see matrix E.)*
- **DEF-006:** unit on health aggregation — missing Sentry → not `degraded` when core deps up.
- **Regression gate:** `scripts/remote_smoke_test.py` extended to assert list/edit/delete round-trip end-to-end.

## 13. Deployment verification after each backend phase

After every backend deploy, confirm the deployed commit and behavior (don't trust CI alone):
1. `GET /health` → `commit` == the SHA you just pushed; `database`/`redis` connected; `alembic_revision` == `0034` (or new head).
2. Run `python scripts/remote_smoke_test.py --base-url https://mita-production-production.up.railway.app` → expect **all checks pass** (baseline: 30/30 today).
3. Run the transaction round-trip (create → list → edit → delete) against prod with a throwaway `audit_*` account; assert the §10 numbers.
4. Check Railway deploy logs for new ERROR/traceback lines after the smoke run.

## 14. Owner-only blockers (cannot be solved in code)

- 🔴 Rotate/purge `.mcp.json` secrets (Supabase + Upstash) — `owner-actions.md §1`.
- 🟠 Install Android SDK on the build machine (APK build currently fails: "No Android SDK found").
- 🟠 Provide `google-services.json` (+ `FIREBASE_*` dart-defines) for the Android app.
- 🟠 `SMTP_PASSWORD` in Railway for email/reset.
- 🟢 Sentry DSN; Play/Apple accounts, keystore, store assets (see `owner-actions.md §3–4`).
- Core MVP journey (register→…→create txn→persist→recover) is **not** owner-blocked once DEF-001/002 are fixed.

## 15. Features that must remain DEFERRED (not core MVP)

Do not let these expand scope: OCR/receipt scanning (Google Vision), In-App Purchase/premium, AWS S3 storage/backups, advanced analytics/insights/AI narratives, notifications/push polish, cohort/cluster/drift/behavior modules, Google/Apple social sign-in (email-password works). The core journey needs none of them. Ship the transaction-CRUD fix + security remediation first.

---

### Appendix — verification assets (auditor scratchpad, not committed)
- `remote_smoke_deployed.py` — 30-check production smoke (from deployed `scripts/remote_smoke_test.py`).
- `audit_opus_e2e.py` — dashboard/edit/delete/re-login gap-filling E2E with exact-number assertions.
- `capture500b.py` — captures the raw 500 bodies for txn list/update/delete.
- Test accounts created in prod this session: `smoke.<ts>@mita-smoketest.dev`, `audit_opus_<ts>@mita-audit.dev` (throwaway; safe to purge).

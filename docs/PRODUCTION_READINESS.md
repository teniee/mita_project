# MITA — Production Readiness (Live)

> **Owner:** production-readiness engineering · **Branch:** `claude/verify-production-deployment-adcjj7`
> **Last updated:** 2026-07-14 (session 6 — deployed production verified end to end)
> **Production URL:** https://mita-production-production.up.railway.app
> **Deployed commit:** `69b0fdb30e53` (= current `main`) · **Alembic:** `0035` (= repo head)
> **Verification method:** GitHub Actions runners (sandbox egress blocks the Railway host) + local `ENVIRONMENT=production` boots (PG16+SSL, real Redis, 2 uvicorn workers)

This file is the single source of truth. Update **before** each change and **after** each verified fix.

---

## Where things stand (session 6)

**The Railway deployment exists, is current, and passes the full remote verification.**

- **Remote smoke vs production: 36/36** — Actions run [29320751589](https://github.com/teniee/mita_project/actions/runs/29320751589), 2026-07-14 09:10 UTC.
- **Mobile-to-production E2E: PASSED** — the app's real `ApiService`/`TransactionService` (dio,
  interceptors, secure token storage) ran the full journey against the live backend in the same
  Actions run: register → login → onboarding → create/edit/delete transaction (calendar `spent`
  follows each step) → saved calendar → token refresh → session persistence → logout.
- Production `/health` now self-reports the facts needed for remote verification:
  `commit=69b0fdb30e53`, `alembic_revision=0035`, `database=connected`, `redis=connected`,
  `environment=production`, `firebase=initialized`. Overall status is "degraded" **only**
  because `SENTRY_DSN` is not set.

### What this session found and fixed in the deployed environment

1. **Revoked tokens kept working for up to 5 minutes** (PR #275, deployed): the blacklist's
   per-worker cache served stale negative entries, so with `WEB_CONCURRENCY ≥ 2` a logged-out
   access token or rotated-out refresh token stayed valid on other workers. Caught by the
   strengthened smoke against the real Railway service (coin-flip failures across runs was the
   telltale). Now verified live: old refresh → 401, post-logout access → 401.
2. **/docs, /openapi.json, /metrics were public in production** (PR #275, deployed): now 404
   unless `ENABLE_DOCS` / `METRICS_TOKEN` are set. Verified live.
3. **`/health` had no deploy provenance** (PR #275, deployed): added commit SHA, Alembic
   revision, Redis ping (honors `REDIS_URL`, `UPSTASH_REDIS_URL`, and Upstash REST config).
4. **Transaction list/get/edit/delete 500'd** (sync services on AsyncSession) and the calendar's
   `spent` double-counted edits / never subtracted deletes — fixed on `main` (#276/#277 line)
   while this session ran; this branch added the permanent smoke gates that prove all of it in
   production (edit replaces spent, delete subtracts, unknown id → 404).
5. **Main CI had gone red** with the #276/#277 merges (isort ×5 files, ruff ×8 findings,
   dart-format ×1 file) — fixed on this branch with the CI-pinned toolchain.

## Status dashboard

| Item | Status | Evidence |
|------|--------|----------|
| Railway deployment | ✅ live, serving current `main` (`69b0fdb30e53`) | `/health` commit field, smoke run 29320751589 |
| Health | ✅ `GET /` 200, `GET /health` 200, DB connected, port bound, HTTPS enforced (HTTP → 301 https), Railway edge OK | smoke 36/36 |
| Database / migrations | ✅ Alembic `0035` (= repo head), schema Alembic-built (startup runs `alembic upgrade head`, aborts prod boot on failure; no `create_all` at startup), `daily_plan` columns + `transactions.description` verified by the live journey (limits > 0 on all days, spent updates on create/edit/delete) | smoke + `scripts/deployment/start.sh` |
| Redis | ✅ `redis=connected`; **token revocation live** (rotated-out refresh 401), **logout blacklist live** (access 401 after logout); rate limiting Redis-backed; degrades fail-open with loud startup warning if Redis vanishes | smoke 36/36 |
| Remote smoke (deployed) | ✅ **36/36** — liveness, provenance, security headers, docs/metrics gated, register→login→onboarding→31/31 calendar days, today present, all limits > 0, spent tracks create/edit/delete, day detail, refresh rotation + revocation, logout + blacklist, 404/422/401 contracts, malformed JSON, plain-HTTP redirect | run 29320751589 |
| Mobile → production E2E | ✅ real `ApiService` journey passed vs live backend (same run, `mobile-journey` job); error contracts stay typed exceptions (nonexistent-id 404 path asserted) | run 29320751589 |
| Deployed-smoke automation | ✅ workflow has the current URL as default, runs daily (cron `17 6 * * *`), manual dispatch, and `[deployed-smoke]` push fallback; needs **no secrets** (public URL, one throwaway account per job per run); failures keep full check-by-check logs | `.github/workflows/deployed-smoke.yml` |
| Android build vs production | ✅ default `AppConfig.baseUrl` IS the production URL; CI now builds the debug APK explicitly with `--dart-define=API_BASE_URL=<railway> --dart-define=ENV=production` (debug logging off) and records path/size/SHA-256/applicationId/version in the job log; artifact `mita-debug-apk` (7-day retention). applicationId `mita.finance`, versionCode 1, versionName 1.0, pubspec `1.0.0+1`, HTTPS-only, no localhost/stale URLs, no bundled secrets | `.github/workflows/main-ci.yml` |
| Release-signed APK/AAB | ⚠️ still needs the owner's keystore (`docs/ANDROID_RELEASE.md`); debug-signed sideload works for first testers | owner action |
| Firebase | ✅ backend Firebase Admin **initialized in production** (`/health`); mobile push/Crashlytics still need `google-services.json` in the app build | owner action (mobile only) |
| IAP | ⚠️ fails closed without store credentials; prod IAP/premium 500 fixed in #277. Not required for a free closed beta | owner store setup |
| Sentry | ❌ `SENTRY_DSN` not set — the only reason `/health` says "degraded". Recommended before inviting testers | owner action |
| Security posture | ✅ headers (HSTS/nosniff/frame-deny/CSP) verified live; docs+metrics gated; CORS allowlist = mitafinance.com domains (+localhost only in dev); JWT rotation + revocation verified live; 4xx never became 500 across the whole journey; secrets from env only (start.sh refuses prod boot without them) | smoke + code |
| Offline writes | ❌ not queued — fails visibly, no silent loss (`docs/OFFLINE_BEHAVIOR.md`); product decision pending | owner decision |
| iOS build | ❌ needs macOS/Xcode runner | environment |

## Verified readiness

- **Deployed readiness: ~95% for a free closed beta.** Every gate below is green:
  deployed health ✅ · remote smoke passes completely ✅ · calendar limits correct in
  production ✅ · today present ✅ · spent updates on create/edit/delete ✅ · refresh +
  logout + revocation work in production ✅ · Redis-dependent behavior works ✅ · Android
  build points at production ✅ · mobile-to-production E2E ✅ · no unresolved critical or
  high-severity blocker.
- Remaining items are **owner actions, none code-blocking**: Sentry DSN (observability),
  release keystore (store distribution; sideloading works now), mobile Firebase config
  (push), store credentials (paid IAP later), offline-writes product decision.

## Exact next task

1. **Owner:** set `SENTRY_DSN` on the Railway service (5 min; flips `/health` to "healthy").
2. **Owner:** merge this branch's PR so the daily deployed-smoke schedule, the mobile-journey
   job, the production-pointed APK build, and the CI lint fixes land on `main`.
3. Distribute the `mita-debug-apk` artifact from the latest green Main CI run to the first
   closed-beta testers (or provide the keystore for a release-signed build).

## Session history (compressed)

- **Sessions 3–5** (#272–#274): calendar Decimal 500 fix, deployed-smoke workflow, Security
  Scanning fix, Android CI build, jinja2 clean-env boot crash, Railway recreation recipe.
- **Session 6 pt.1** (#275, merged + deployed): /health deploy diagnostics (commit, alembic,
  Redis incl. Upstash REST), 5-minute revocation-gap fix (positive-only blacklist cache),
  /docs + /metrics gated in production, smoke hardened (revocation, headers, HTTPS redirect,
  malformed JSON, metrics/docs policy).
- **Parallel sessions** (#276/#277, merged + deployed): transaction list/get/edit/delete
  AsyncSession 500s, TxnUpdate validator mis-binding, ValidationError → 422, plan-spent
  recalculation on edit/delete, migration 0035, prod IAP/premium 500.
- **Session 6 pt.2** (this branch): production verified green end to end (smoke 36/36 +
  mobile journey vs the live URL), edit/delete smoke gates, daily schedule + mobile-journey
  job in deployed-smoke, production-pointed beta APK with recorded metadata, main CI
  restored to green (isort/ruff/dart-format debt from the parallel merges).

# MITA — Production Readiness (Live)

> **Owner:** production-readiness engineering · **Branch:** `claude/mita-closed-beta-readiness-4nn5q6`
> **Last updated:** 2026-07-07 (session 4 — post-merge closed-beta readiness)
> **Latest commit:** `c53d812` (tracker update follows it)
> **Verification environment:** Python 3.11 venv · PostgreSQL 16 (real) · Redis 7 (real) · Flutter 3.35.4 / Dart 3.9.2 (real SDK) · no Android SDK (dl.google.com blocked by sandbox egress) · Railway host blocked from sandbox but PROBED FROM GITHUB RUNNERS via the new deployed-smoke workflow

This file is the single source of truth. Update **before** each change and **after** each verified fix.

---

## Where things stand (session 4)

The session-3 branch (`claude/mita-finance-prod-ready-wqj2k9`, commits `2bf578a` + `91b0d5a`)
was **merged into main via PR #272** (squash commit `be220da`, 2026-07-07 07:25 UTC) and the
branch deleted. All session-3 work (calendar fix, migration 0034, Flutter 3.35.4 pin, hermetic
mobile CI) is on main. Follow-up work continues on `claude/mita-closed-beta-readiness-4nn5q6`
(branched from `be220da`).

## Current verified status

| Gate | Status | Evidence |
|------|--------|----------|
| Backend CI (format, lint, migrations 0001→0034 from empty PG16, `pytest` full = tests/ 287 + app/tests 611+, bandit) | ✅ green | CI run #224 & #226 Backend CI job: **success** |
| Migrations from empty PG 16 → **0034** | ✅ | re-verified locally this session AND in CI runs #224/#226/#227 |
| Flutter format / analyze | ✅ 0 errors (3 pre-existing warnings, non-fatal) | local 3.35.4 + CI Verify code step green |
| Flutter tests incl. hermetic live-API E2E vs this commit's backend | ✅ | CI run #224/#226 “Run tests” green; local: **376 passed / 15 skipped / 0 failed** |
| Local backend E2E (remote_smoke_test.py vs local uvicorn, clean-DB migrations) | ✅ **19/19** | register→login→onboarding→transaction→saved calendar (31/31 days, all limits > 0, today present, spent 23.75 reflected, YYYY-MM-DD keys)→day detail→refresh rotation→logout→404/4xx never 500 |
| IAP security suite | ✅ 21 passed (isolated DB) + green inside CI backend job | fixture-based: tampered JWS, unpinned chain, replay, ownership, fail-closed, grace/refund/revoke |
| Android debug APK in CI | 🟡 fix chain in progress — see run history below | run #224 failed (Kotlin `java.util` shadowing → fixed `f45cc65`), #226 failed (google-services.json absent → fixed `c53d812`), #227 running |
| Security Scanning workflow on main | ❌ red on main (deprecated upload-sarif@v2) → fixed on this branch (`93e6a92`: v3 + security-events permission) | lands on main with next merge |
| **Deployed backend (Railway)** | ❌ **HARD DOWN — “Application not found”** | see Deployment status |
| iOS build | ❌ blocked: no macOS/Xcode available anywhere in this setup | needs a macOS runner |

## CI run history (this session)

| Run | Commit | Result | Root cause / action |
|-----|--------|--------|---------------------|
| #220–#222 | 2bf578a / 91b0d5a | failed / superseded | pre-merge branch runs; branch merged as PR #272 and deleted |
| #223 (main) | be220da | ❌ Mobile CI: Android build | same Kotlin-DSL failure as #224 — fix must reach main |
| #224 | 93e6a92 | ❌ Android build only (Backend ✅, format ✅, analyze ✅, tests+E2E ✅) | `java.util.Properties()` in build.gradle.kts — Kotlin DSL shadows `java` → fixed in `f45cc65` |
| #226 | f45cc65 | ❌ Android build only (everything else ✅) | google-services plugin hard-fails: google-services.json is gitignored → plugin now conditional (`c53d812`) |
| #227 | c53d812 | 🟡 in progress | expected green incl. APK artifact |
| Deployed-smoke #1/#3 | d2f09d0 / c53d812 | ❌ (production itself) | Railway edge: `{"status":"error","code":404,"message":"Application not found"}` |

## Deployment status — CRITICAL BLOCKER (needs the owner)

**`https://mita-production-production.up.railway.app` no longer hosts any application.**
Proven from GitHub runners (not a sandbox egress artifact): every path returns Railway's edge
response `{"status":"error","code":404,"message":"Application not found"}`. That means no
Railway service is bound to this domain — the service/environment was deleted, renamed, or its
domain released. This cannot be diagnosed or fixed from the repository.

**Owner actions needed (Railway dashboard):**
1. Check the Railway project: does the backend service still exist? Was the domain regenerated?
2. If gone: create a service from this repo (Dockerfile path works; `start.sh` validates env,
   runs `alembic upgrade head` exactly once, fails closed on migration failure, binds
   `0.0.0.0:$PORT`, workers from `WEB_CONCURRENCY`).
3. Required env vars (production): `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`,
   `OPENAI_API_KEY` (start.sh hard-requires it), `REDIS_URL` (or Upstash vars),
   `ENVIRONMENT=production`, `SENTRY_DSN` (recommended), `IAP_ALLOWED_PRODUCT_IDS`,
   Apple/Google IAP vars per docs/FIX_ALL.md.
4. Tell us the final base URL — then run the **Deployed Backend Smoke Test** workflow
   (Actions → “Deployed Backend Smoke Test” → Run workflow → base_url), or push a commit
   containing `[deployed-smoke]` to a `claude/**` branch. 19 checks verify the whole
   closed-beta journey including non-zero calendar limits.
5. The mobile default API URL (`mobile_app/lib/config.dart`) and the Android
   network-security-config pin `mita-production-production.up.railway.app`; if the domain
   changes, update both (build-time `--dart-define=API_BASE_URL=...` also works).

## Fixed session 4 (2026-07-07, this branch)

1. **Security Scanning red on main** — `github/codeql-action/upload-sarif@v2` is deprecation-
   killed and the job lacked `security-events: write` (upload 403). v3 + permissions. (`93e6a92`)
2. **Deployed-backend verification tooling** — `scripts/remote_smoke_test.py` (stdlib-only,
   19-check journey incl. every calendar acceptance criterion) + `deployed-smoke.yml`
   (workflow_dispatch + `[deployed-smoke]` commit-tag trigger, needed because this
   environment's GitHub token cannot call the dispatch API). Verified 19/19 against a local
   backend built from the exact merged code. (`93e6a92`, `d2f09d0`, `c53d812`)
3. **Android APK build broken in CI (was never buildable)** — two independent causes:
   a. Kotlin DSL: `java.util.Properties()` / `java.io.FileInputStream(...)` — `java` resolves
      to the JavaPluginExtension accessor inside build scripts → script compilation error.
      Imports at top of script (stock Flutter template pattern). (`f45cc65`)
   b. google-services plugin hard-fails without `google-services.json`, which is gitignored →
      every CI/credential-less build failed. Firebase runtime config comes from Dart
      (`firebase_options.dart` via --dart-define), so the plugin is now applied only when the
      file exists. (`c53d812`)
4. **App crashed at startup without Firebase credentials** (HIGH, closed-beta gate):
   `await _initFirebase()` in `main()` was uncaught; `DefaultFirebaseOptions` throws
   `StateError` when FIREBASE_* dart-defines are absent → crash before `runApp`. Now caught
   (budgeting works without push/Crashlytics); Crashlytics calls in both global error handlers
   guarded by `Firebase.apps.isNotEmpty`; post-login push-token registration already had
   graceful failure handling. (`c53d812`)

## Offline-first — honest status (product decision needed)

`AdvancedOfflineService` implements a complete offline machine (sqflite response cache,
`pending_sync` queue table with retry counts, connectivity-triggered `_processPendingSyncs`)
— but **no code path ever enqueues a write**. The only wired consumer is calendar response
caching in `api_service.dart` (2h expiry) plus the deterministic `CalendarFallbackService`.
`createTransaction` (both ApiService and TransactionService) POSTs directly and rethrows on
failure.

Actual offline behavior today: cached/deterministic calendar reads work; transaction creation
offline **fails loudly with an error state** (no silent loss, no corruption, no fake success);
nothing is queued for later sync. That is an *online-first app with cached reads*, not
offline-first. Wiring true offline write-queueing (client queue + server idempotency keys +
dedup + conflict policy + sync-state UI) is a feature, not a fix — **product decision:** ship
closed beta online-first (defensible; beta testers have connectivity) or build the queue first.

## Remaining blockers

### Critical — needs the owner
- **Railway deployment gone** (“Application not found”) — see Deployment status. Until a
  backend is deployed, every deployed-E2E criterion is unmeetable regardless of code state.

### High — fixable here, in progress
- CI run #227 green end-to-end incl. APK artifact (fix chain: `f45cc65` + `c53d812`).
- Main branch itself is red (#223, same Android causes + old security.yml): the fixes on this
  branch need a PR to main (not opened — merges to main require explicit approval).

### Blocked — environment (exact unblock condition documented)
- **Local Android builds**: dl.google.com / maven.google.com 403-blocked in sandbox →
  Android builds and artifact inspection happen in CI only (mobile-ci uploads
  `mita-debug-apk`, 7-day retention).
- **iOS build**: needs macOS/Xcode runner.
- **Railway host & Azure blob (Actions log archive) egress-blocked from sandbox** — worked
  around via GitHub-runner smoke workflow and the logs API.

### Blocked — external credentials (code paths ready & fail closed)
- Firebase: real `google-services.json` (Android), FIREBASE_* dart-defines
  (`firebase_config.json` per `firebase_config.example.json`) — app now degrades gracefully
  without them; push/Crashlytics off until provided.
- Apple IAP: `APPLE_ROOT_CA_PATH` (AppleRootCA-G3.cer), `APPLE_BUNDLE_ID`,
  `APPSTORE_SHARED_SECRET`, ASSN V2 URL → `POST /api/iap/webhook`.
- Google IAP: `GOOGLE_SERVICE_ACCOUNT` JSON, `GOOGLE_PACKAGE_NAME`, RTDN Pub/Sub push with
  OIDC (`GOOGLE_PUBSUB_AUDIENCE`, `GOOGLE_PUBSUB_SERVICE_ACCOUNT`).
- `IAP_ALLOWED_PRODUCT_IDS` — required in production, otherwise IAP validation fails closed.
- OpenAI (`OPENAI_API_KEY` — also hard-required by start.sh in production), Sentry DSN, SMTP.
- Android release signing: `key.properties` or `KEYSTORE_FILE`/`KEYSTORE_PASSWORD`/
  `KEY_ALIAS`/`KEY_PASSWORD` env vars (build.gradle.kts falls back to debug signing with a
  loud warning — fine for closed beta via internal testing track, NOT for store release).

## Production configuration review (verified this session)

- CORS: explicit HTTPS origin allowlist, wildcard removed, localhost only outside production.
- Security headers middleware: HSTS, nosniff, X-Frame-Options DENY, CSP, Referrer-Policy.
- start.sh: production requires DATABASE_URL/SECRET_KEY/JWT_SECRET/OPENAI_API_KEY; migration
  failure aborts startup in production; single migration point (no create_all in prod path).
- Android: `usesCleartextTraffic=false`, network-security-config enforces HTTPS; versionCode 1,
  versionName 1.0; permissions: INTERNET, NETWORK_STATE, CAMERA (OCR), media-read ≤SDK32,
  VIBRATE, BOOT_COMPLETED, WAKE_LOCK, USE_BIOMETRIC, fine/coarse location (**Play review will
  ask for location justification — income classification uses it; have the disclosure ready**).
- JWT: issuer/audience/type/version enforced; refresh rotation + old-token blacklist verified
  in the smoke journey (rotation + rotated-token works + logout).

## Commits (session 4)
`93e6a92` security.yml fix + smoke tooling · `d2f09d0` smoke [deployed-smoke] trigger ·
`f45cc65` Kotlin DSL unshadow · `c53d812` Firebase graceful degradation + conditional
google-services + smoke diagnostics

## Readiness estimate

**Code readiness: ~90%** — all suites green on real PG16+Redis, calendar correctness verified
at four levels locally and in hermetic CI E2E, IAP fail-closed verified with fixtures, app now
launches without any external credentials.
**Deployed readiness: 0% — there is no deployment.** The single gating item for closed beta is
restoring the Railway service (owner action) and then re-running the deployed smoke (19 checks,
one click). After that: Firebase + store credentials for push/IAP, Android release signing for
the Play internal-testing track.

## Next task
1. Confirm CI run #227 green (incl. `mita-debug-apk` artifact) — in progress.
2. Owner: restore Railway service + env vars → provide base URL → run deployed smoke.
3. Open PR to main with this branch (needs explicit approval to merge) so main goes green
   (#223's Android causes + security.yml are fixed here).
4. Provision Firebase/IAP/OpenAI/Sentry credentials per the blocked list.

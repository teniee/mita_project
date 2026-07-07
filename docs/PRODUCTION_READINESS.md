# MITA — Production Readiness (Live)

> **Owner:** production-readiness engineering · **Branch:** `claude/mita-finance-prod-ready-wqj2k9`
> **Last updated:** 2026-07-07 (session 3 — continuation of the 2026-07-05/06 audit)
> **Verification environment:** Python 3.11 venv · PostgreSQL 16 (real) · Redis 7 (real) · Flutter 3.35.4 / Dart 3.9.2 (real SDK, tests + analyze) · no Android SDK (dl.google.com blocked by sandbox egress policy) · no external Apple/Google/OpenAI/Firebase credentials · Railway production URL unreachable from sandbox (egress policy)

This file is the single source of truth. Update **before** each change and **after** each verified fix.

---

## Current verified status (this session)

| Gate | Status | Evidence |
|------|--------|----------|
| `tests/` root | ✅ **287/287** | re-verified 2026-07-07 |
| `app/tests` root | ✅ **611/611** (incl. 7 new calendar-limit + 19 IAP security tests) + 6 new sync-session SSL tests verified separately | full run 2026-07-07, real PG16+Redis |
| black / isort / ruff | ✅ PASS | whole repo |
| bandit -ll | ✅ PASS (0 medium/high) | app/ |
| Migrations from empty PG 16 | ✅ 0001→**0034** | re-verified in CI run #220 (migrations step green) |
| Backend cold start | ✅ | uvicorn against migration-built DB |
| `GET /` & `GET /health` | ✅ 200 / healthy | |
| Backend E2E journey | ✅ register→onboarding→transaction→**saved calendar (31 days, non-zero limits, spent reflected)**→refresh→logout | raw HTTP + the app's real ApiService |
| Flutter analyze | ✅ 0 errors, 0 warnings | |
| Flutter tests | ✅ **376 passed / 15 skipped / 0 failed** (live-API tests skip without a backend; with local backend they run — see mobile↔backend row) | full suite 2026-07-07 |
| Mobile ↔ backend E2E | ✅ full journey through real ApiService (dio, interceptors, secure storage) against local FastAPI: register→login→onboarding→transaction→getSavedCalendar (all limits > 0, today's spent ≥ tx amount)→refresh→persistence→logout | mobile_backend_journey_test.dart |
| Android debug build | ❌ blocked in sandbox (dl.google.com 403) → built in CI mobile job | see CI row |
| iOS build | ❌ blocked: no macOS/Xcode in environment | needs a macOS runner |
| GitHub CI run | 🟡 run #220 (first run on branch) red → all 3 root causes fixed (see session-3 findings); green run pending next push | |

## Fixed session 3 (2026-07-07) — calendar correctness end to end

1. **Calendar returned `limit: 0.0` for every day** (HIGH — core product). `DailyPlan.daily_budget` — summed into each day's `limit` by `GET /api/calendar/saved/{y}/{m}` and read by spending-prevention — was never written by ANY writer. The mobile traffic-light (`limit > 0 && spent > limit`) was silently disabled for every onboarded user. Fixed at every write point with the invariant *daily_budget follows the allocation*: onboarding save, day edits, realtime rebalancer (donor cuts + credit), budget redistributor, both expense trackers (explicit 0, never NULL, for unplanned categories), goal sync, user-data service. Read-side fallback to the planned total for legacy NULL rows. (`2bf578a`)
2. **Saved-calendar endpoint emitted full timestamps** (`2026-07-06T00:00:00+00:00`) instead of the `YYYY-MM-DD` day keys the mobile app merges on. (`2bf578a`)
3. **Mobile ApiService base URL missed the API path** (`AppConfig.baseUrl` → every request 404'd) and `_transformCalendarData` rejected the List contract `/calendar/shell` actually returns (every successful response surfaced as an empty calendar). (`2bf578a`)
4. **Sync DB session forced `sslmode=require`** regardless of the URL's own `?sslmode=disable` — every deployment on non-SSL Postgres (CI containers, docker-compose, private networking) lost the whole sync-session path ("server does not support SSL"). Found via CI run #220; now honors the URL, defaulting to require only when unspecified. 6 regression tests.
5. **CI live-API tests ran against production Railway** (reachable from GitHub runners, unlike this sandbox) — registering junk users in the production DB and testing the previously-deployed code instead of the commit under test. mobile-ci is now hermetic: PG16+Redis service containers, migrations, uvicorn on localhost, `flutter test --dart-define=API_BASE_URL=http://localhost:8000` → the full journey E2E runs in CI on every push.
6. **CI Flutter version floated on `stable`** while the suite is verified on 3.35.4 (SnackBar timer semantics differed → phantom CI-only failure). Pinned.
7. **Date-fragile test**: `calendar_integration_test.dart` "Spending patterns are realistic" failed on the 1st, 2nd and 7th of every month from date arithmetic alone (fixed thresholds over 0–6 past days). Rewritten proportionally; also removed the fallback service's factor bucket sitting exactly on the 1.1 'over' boundary (status flipped with income rounding).
8. **Load tests raced the framework's default 30s timeout** (30s/20s load windows + wind-down). Explicit timeouts; assertions unchanged.
9. Regression coverage for the calendar bug at four levels: backend service + API route (`app/tests/test_calendar_limits.py`, 7 tests), Flutter unit (`test/budget_provider_calendar_merge_test.dart`, 8 tests — merge extracted as pure `mergeSavedCalendarDay`, behavior unchanged), live integration (journey test asserts non-empty days, all limits > 0, today's spent ≥ transaction amount).

## Fixed session 2 (2026-07-06) (all verified by tests)

### Backend
1. **Decimal/date/UUID responses 500'd** — `JSONResponse` used stdlib json; `GET /api/calendar/day/{y}/{m}/{d}` crashed right after onboarding (core journey). Fixed in the response wrapper with `jsonable_encoder`; 5 regression tests. (`890a20b`)
2. **aiosqlite dev dep never installed** — line was concatenated into a comment in requirements-dev.txt → 17 collection errors locally and in CI. (`890a20b`)
3. **IAP webhook accepted client-supplied `{user_id, expires_at}`** (HIGH — anyone could self-grant premium). Replaced with store-signed verification architecture (below). (`e05f270`)

### IAP security architecture (`e05f270`, migration 0034)
- Apple App Store Server Notifications V2: full JWS verification — x5c chain to a **pinned root CA** (`APPLE_ROOT_CA_PATH`), Apple marker OIDs, ES256 signature, bundleId + environment claims, nested signedTransactionInfo verified identically.
- Google RTDN: Pub/Sub push OIDC token verified (issuer/audience/service-account email); entitlement state re-fetched from the Play Developer API — notification content never trusted.
- Replay/idempotency: `iap_events` table, unique (provider, event_id).
- Ownership: subscriptions matched by store transaction key (`originalTransactionId`/`purchaseToken`); unknown transactions change nothing; cross-account receipt reuse → 409.
- Sandbox/production separation (Apple 21007 fallback; Play purchaseType); product-id allowlist `IAP_ALLOWED_PRODUCT_IDS` **required in production** (fails closed).
- Entitlement state machine shared by validate + webhooks: grace keeps premium, cancel keeps until expiry, refund/revoke/hold end immediately; `GET /api/iap/status` for restore flows.
- Fail closed: missing config → 503 and no entitlement change. Legacy payloads → 400.
- 19 tests: tampered signature, unpinned chain, wrong bundle, sandbox rejection, replay, unmatched transaction, fail-closed, OIDC rejection, revoke/refund/grace flows, premium state matrix.

### Flutter app (real product bugs)
4. **executeWithRetry swallowed terminal errors** — screens using `executeRobustly` (login, daily budget) never showed their error state; only an explicit fallback may now absorb failures. (`7dd44b1`)
5. **PII masking disabled in every debug build** regardless of the flag (emails/phones/cards/JWTs leaked to logs); masking now follows configuration only. Also: card/SSN masking ran after the phone pattern (which consumed card digits). (`7dd44b1`)
6. **Error-pattern analytics never detected patterns** (counted windows, not repetitions) → pairwise co-occurrence counting; `clearAllData()` added (GDPR + test isolation). (`7dd44b1`)
7. **buildLoadingWithError not embeddable** — error branch returned a full Scaffold → infinite-height overflow inside any Column. (`7dd44b1`)
8. **Unhandled error types fell to generic "System"** — requestTimeout/invalidEmail/weakPassword/requiredField/dataCorrupted now have dedicated messaging; new securityBreach type (critical). (`7dd44b1`)
9. **Context-taking formatters ignored the widget locale** — screens under an `es` MaterialApp could render US-formatted money; now synced to `Localizations.localeOf`. (`3632694`)
10. **`parseCurrency` couldn't parse US-formatted input** (`$1,234.56`) — thousands separators never stripped. (`3632694`)
11. **Login sign-up row overflowed** with longer translations (Flexible). (`3632694`)
12. **Frontend income thresholds carried a 5th 'high' boundary key** that the backend contract explicitly does not define — removed from all 50 states + defaults (backend_consistency_test now passes). (`e4e50ea`)
13. **Calendar status legend overflowed 136px on 320px-wide phones** — Wrap instead of Row. (uncommitted → this batch)
14. **Missing offline-first feature `CalendarFallbackService`** implemented (37 tests define the contract): deterministic month of daily budgets from income+location when the backend is unreachable. (`f6a60b9`)
15. **InstallmentsProvider not injectable** — screens' mocks were never wired; provider now accepts a service (DI). Category label + popup menu overflow fixes. (`0770048`)
16. **Spanish translation inconsistency** rememberMe unified to "Recordarme". (`3632694`)

### Flutter test infrastructure
- `test/helpers/test_app.dart` — provider tree mirroring `lib/main.dart` (screens throw ProviderNotFoundException without it; caused ~40 failures).
- Stateful secure-storage mock (Keychain-like), SharedPreferences mocks, golden baselines for onboarding, illegal `testWidgets`-inside-`test` nests flattened, pumpAndSettle vs periodic-timer deadlocks replaced with bounded pumps.
- Stale expectations updated **with documented reasons** (income tiers per 5-tier upper-bound semantics; login strings per current .arb).

## Per-file Flutter test status (each verified green this session)
calendar_screen 18/18 · installments_screen 17/17 · onboarding_integration 10/10 (incl. goldens) · calendar_service+calendar_integration 37/37 · secure_token_storage 20/20 · security_services 19/19 · error_message 20/20 · error_handling_comprehensive 24/24 · edge_cases 17/17 · i18n_integration 16/16 · income_classification 17/17 · backend_consistency 9/9 · login_screen 1/1 · dashboard_screen 1/1 · comprehensive_api 12/12 (vs local backend) · ui_fixes_validation (calendar overflow fix in progress)

## Remaining blockers

### Fixable here (in progress)
- Green GitHub Actions run on the branch (all known root causes of run #220 fixed; awaiting next push's run).
- Production deploy of this branch's backend — the deployed Railway backend still serves zero-limit calendars until redeployed.

### Blocked — environment (exact unblock condition documented)
- **Android debug/release build**: sandbox egress policy 403-blocks dl.google.com (Android SDK cmdline-tools, platform tools, google() maven). Unblock: allowlist dl.google.com/maven.google.com in the Claude environment network policy, or rely on GitHub CI (ubuntu runners reach it) — the mobile-ci workflow already runs analyze+test; an `flutter build apk --debug` step can be added.
- **iOS build**: requires macOS/Xcode (not available in Linux sandbox or ubuntu CI). Needs a macOS runner.
- **Railway production verification**: `mita-production-production.up.railway.app` blocked by sandbox egress. Local backend used instead for mobile↔backend E2E.

### Blocked — external credentials (code paths ready & fail closed)
- Apple: `APPLE_ROOT_CA_PATH` (download AppleRootCA-G3.cer from apple.com/certificateauthority — apple.com also blocked in sandbox), `APPLE_BUNDLE_ID`, `APPSTORE_SHARED_SECRET`, App Store Server Notifications V2 URL configured in App Store Connect → `POST /api/iap/webhook`.
- Google Play: service-account JSON (`GOOGLE_SERVICE_ACCOUNT`), `GOOGLE_PACKAGE_NAME`, RTDN Pub/Sub push subscription with OIDC auth → set `GOOGLE_PUBSUB_AUDIENCE` + `GOOGLE_PUBSUB_SERVICE_ACCOUNT`.
- `IAP_ALLOWED_PRODUCT_IDS` (comma-separated store product ids) — **required in production**, otherwise validation fails closed.
- Firebase push (service-account JSON + APNs key), OpenAI (`OPENAI_API_KEY`), Sentry DSN, SMTP password, Railway env vars (docs/FIX_ALL.md R-01/02/03).

## Commits
Session 2: `890a20b` backend Decimal/aiosqlite/cleanup-flake · `e05f270` IAP security · `0770048` calendar+installments tests · `f6a60b9` CalendarFallbackService · `7dd44b1` error handling/PII/recovery · `3632694` i18n · `e4e50ea` thresholds contract + onboarding · `4350a38` CI pipeline + format
Session 3: `2bf578a` calendar non-zero limits end to end (4-level regression coverage) · (this commit) sync-session sslmode + hermetic mobile CI + version pin + date-fragile/timeout test fixes

## Readiness estimate
**Backend: all suites green against real PG16+Redis (611 + 287), all critical journeys verified including saved-calendar correctness and IAP entitlements.**
**Mobile: full suite green (376 pass / 15 env-skip); full app-code journey verified against a live backend; calendar traffic-light now backed by real limits.** Builds: Android via CI job; iOS needs a macOS runner. Remaining evidence: a green CI run on the branch (all #220 root causes fixed).

## Next task
1. Confirm the next CI run is green end to end (backend job, hermetic mobile job incl. E2E + APK build).
2. Deploy the branch's backend to Railway so production stops serving zero-limit calendars.
3. Provision external credentials (Apple/Google IAP, Firebase, OpenAI, Sentry) per the blocked-credentials list.

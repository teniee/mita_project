# MITA — Production Readiness (Live)

> **Owner:** production-readiness engineering · **Branch:** `claude/mita-finance-prod-ready-wqj2k9`
> **Last updated:** 2026-07-06 (session 2 — continuation of the 2026-07-05 audit)
> **Verification environment:** Python 3.11 venv · PostgreSQL 16 (real) · Redis 7 (real) · Flutter 3.35.4 / Dart 3.9.2 (real SDK, tests + analyze) · no Android SDK (dl.google.com blocked by sandbox egress policy) · no external Apple/Google/OpenAI/Firebase credentials · Railway production URL unreachable from sandbox (egress policy)

This file is the single source of truth. Update **before** each change and **after** each verified fix.

---

## Current verified status (this session)

| Gate | Status | Evidence |
|------|--------|----------|
| `tests/` root | ✅ **287/287** | after fixing aiosqlite dep (was inside a comment string) |
| `app/tests` root | ✅ 580 pass + order-dependent cleanup flake fixed; IAP suite rewritten (19 new security tests); full-suite re-run pending final sweep | see below |
| black / isort / ruff | ✅ PASS | whole repo |
| bandit -ll | ✅ PASS (0 medium/high) | app/ |
| Migrations from empty PG 16 | ✅ 0001→**0034** | includes new 0034 (iap_events + subscription purchase identity) |
| ORM ↔ schema drift | ✅ no column/table drift | subscriptions.deleted_at added to model; remaining diffs are index/FK-name noise |
| Backend cold start | ✅ | uvicorn against migration-built DB |
| `GET /` & `GET /health` | ✅ 200 / healthy | |
| Backend E2E journey | ✅ register→login→onboarding→calendar-day→refresh→authed→404 | **found+fixed**: Decimal serialization 500 on calendar day |
| Flutter analyze | ✅ 0 errors (infos/warnings only; CI uses --no-fatal-infos --no-fatal-warnings) | |
| Flutter tests | 🟡 in progress — from **104 failures → single digits**; all failure clusters below fixed and green per-file | full-suite re-measure pending |
| Mobile HTTP client ↔ backend | ✅ comprehensive_api_test 12/12 against local FastAPI (`--dart-define=API_BASE_URL=http://localhost:8000`) | Railway URL blocked in sandbox |
| Android debug build | ❌ blocked in sandbox: dl.google.com (Android SDK + google() maven) returns 403 via egress proxy | CI (GitHub) can build; see Next tasks |
| iOS build | ❌ blocked: no macOS/Xcode in environment | |
| GitHub CI run | ⏳ pending push + run evidence | |

## Fixed this session (all verified by tests)

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
- Full Flutter suite final re-measure (after ui_fixes + performance files) and full backend suite re-run.
- CI workflow: point mobile job's live-API tests at a reachable target or skip cleanly when unreachable.
- Push + real GitHub Actions run evidence.

### Blocked — environment (exact unblock condition documented)
- **Android debug/release build**: sandbox egress policy 403-blocks dl.google.com (Android SDK cmdline-tools, platform tools, google() maven). Unblock: allowlist dl.google.com/maven.google.com in the Claude environment network policy, or rely on GitHub CI (ubuntu runners reach it) — the mobile-ci workflow already runs analyze+test; an `flutter build apk --debug` step can be added.
- **iOS build**: requires macOS/Xcode (not available in Linux sandbox or ubuntu CI). Needs a macOS runner.
- **Railway production verification**: `mita-production-production.up.railway.app` blocked by sandbox egress. Local backend used instead for mobile↔backend E2E.

### Blocked — external credentials (code paths ready & fail closed)
- Apple: `APPLE_ROOT_CA_PATH` (download AppleRootCA-G3.cer from apple.com/certificateauthority — apple.com also blocked in sandbox), `APPLE_BUNDLE_ID`, `APPSTORE_SHARED_SECRET`, App Store Server Notifications V2 URL configured in App Store Connect → `POST /api/iap/webhook`.
- Google Play: service-account JSON (`GOOGLE_SERVICE_ACCOUNT`), `GOOGLE_PACKAGE_NAME`, RTDN Pub/Sub push subscription with OIDC auth → set `GOOGLE_PUBSUB_AUDIENCE` + `GOOGLE_PUBSUB_SERVICE_ACCOUNT`.
- `IAP_ALLOWED_PRODUCT_IDS` (comma-separated store product ids) — **required in production**, otherwise validation fails closed.
- Firebase push (service-account JSON + APNs key), OpenAI (`OPENAI_API_KEY`), Sentry DSN, SMTP password, Railway env vars (docs/FIX_ALL.md R-01/02/03).

## Commits this session
`890a20b` backend Decimal/aiosqlite/cleanup-flake · `e05f270` IAP security · `0770048` calendar+installments tests · `f6a60b9` CalendarFallbackService · `7dd44b1` error handling/PII/recovery · `3632694` i18n · `e4e50ea` thresholds contract + onboarding · (pending) ui_fixes/login/dashboard batch

## Readiness estimate
**~90% backend (verified)** — all critical backend journeys verified against migrated PostgreSQL+Redis including the IAP entitlement architecture; remaining backend risk is CI-run evidence.
**Mobile: test suite from 104 failures → near-green; mobile↔backend contract verified against a real backend.** Builds remain environment-blocked (Android SDK egress, no macOS).

## Next task
1. Finish ui_fixes/performance Flutter files; run the FULL Flutter suite and record exact totals.
2. Re-run full backend suites (app/tests + tests/) after all backend changes; record totals.
3. Push branch; obtain a real GitHub Actions run; add `flutter build apk --debug` to mobile-ci.
4. Update this file with final evidence.

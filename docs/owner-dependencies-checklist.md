# MITA Finance — Owner Dependencies & Credentials Checklist

> **Purpose:** A single source of truth for every external credential, account, console
> action, and owner-only decision required to make MITA Finance fully operational, so that
> the next engineering session can finish the app without being blocked.
>
> **Scope of this document:** *audit only.* No application code was changed to produce it.
> **Secrets policy:** No secret values are printed. Passwords, private keys, API keys, and
> tokens are shown as `‹redacted›`. Non-secret identifiers (OAuth **client IDs**, project
> names, host names, bundle IDs) are shown in full because the owner needs them to locate
> resources.

**Audit date:** 2026-07-08
**Auditor:** Production-readiness inspection session (read-only)
**Repo state:** working tree is a plain directory (not a git checkout); Railway deploys from
GitHub repo `teniee/mita_project`.

---

## 0. How this was verified (evidence base)

| Source | What it gave |
|--------|--------------|
| `app/core/config.py` (`Settings`) | Canonical backend env-var names & defaults |
| `grep os.getenv/os.environ` across `app/` | Every env var actually read by code |
| Railway MCP (`whoami`, `list_*`, `get_service_config`, `list_variables`) | Live project/service/deploy/variable **names** (values redacted) |
| `curl https://mita-production-production.up.railway.app/health` + `/docs` `/metrics` | Live runtime state of the deployed backend |
| `mobile_app/lib/config.dart`, `firebase_options.dart`, `pubspec.yaml` | Mobile API URL + Firebase/integration surface |
| `mobile_app/android/app/build.gradle.kts`, `AndroidManifest.xml`, `network_security_config.xml` | Android IDs, signing, permissions |
| `mobile_app/ios/Runner/Info.plist`, `Runner.xcodeproj/project.pbxproj` | iOS bundle ID, permissions, URL schemes |
| `app/services/google_auth_service.py`, `app/api/iap/*` | Google Sign-In & IAP server requirements |
| `config/secrets_config.json`, `docs/FIREBASE_SETUP.md`, `docs/ANDROID_RELEASE.md`, `docs/RAILWAY_DEPLOYMENT.md` | Owner-facing procedures & severity tiers |

### Verified live production snapshot

- **Railway account:** `mita owner (cutmeout1@gmail.com)`
- **Project:** `Mita Finance` (`d44d0580-3476-4e46-bc4c-b2d95dac64cd`)
- **Environment:** `production` (`d4970d5d-3c58-4be7-b64e-5c05d359de3b`)
- **Services:** `mita-production` (backend, `b6cebfcc-…`) + `mita-production-db` (PostgreSQL, `2a891a03-…`). **No Railway Redis service** — Redis is external (Upstash).
- **Builder:** `RAILPACK` (⚠️ the repo `Dockerfile` and `nixpacks.toml` are **not** what Railway uses). Start command `bash start.sh`, which runs `alembic upgrade head` then launches the app.
- **Deployed commit:** `8880b44873b45505c37f93ad913d4dfe0ca7515d` (deployed 2026-07-07 20:21 UTC, status SUCCESS)
- **Public domain:** `https://mita-production-production.up.railway.app` (sync_status ACTIVE) — **matches** the Flutter default `API_BASE_URL`.
- **`/health`** → `status: degraded` with: `database: connected`, `firebase: initialized`, `openai_configured: true`, `upstash_configured: true`, `sentry: unavailable/false`. "Degraded" is caused **only** by Sentry being unconfigured; DB + Firebase + Redis + OpenAI are healthy.
- **63 variables** defined on the backend service.

> **Note on `docs/ANDROID_RELEASE.md`:** it describes the Railway domain as "dead." That is
> **stale** — as of this audit the domain returns HTTP 200 with the database connected.

---

## 1. 🔴 IMMEDIATE SECURITY ACTIONS (committed secrets — rotate now)

These are **secrets committed into the repository** and therefore must be treated as
compromised and rotated. This is independent of MVP features.

### 1.1 `.mcp.json` contains live-looking secrets (committed)
- **File:** `.mcp.json` (repo root)
- **What is exposed:**
  1. A **Supabase service token** (`sb_secret_‹redacted›`) as a Bearer `Authorization` header, for Supabase project ref `atdcxppfflmiwjwjuqyl`.
  2. An **Upstash Redis connection URL** with embedded password (`rediss://default:‹redacted›@integral-jaybird-23463.upstash.io:6379`).
- **Why it matters:** anyone with repo access gets a Supabase service credential (full DB/API access on that project) and a Redis endpoint. Note this Upstash instance (`integral-jaybird-23463`) is **different** from both production Redis instances (see §2.4), so it is likely a stale dev instance — but it is still a live-format credential in version control.
- **Owner action:**
  1. Rotate the Supabase service key in the Supabase dashboard (Project `atdcxppfflmiwjwjuqyl` → Settings → API) — or delete the project if unused.
  2. Rotate/disable the `integral-jaybird-23463` Upstash database (Upstash console → Redis → that DB → reset password / delete).
  3. Move both out of `.mcp.json` into local-only MCP config; keep `.mcp.json` free of secrets (or gitignore it). *(Requires a code/file change — out of scope for this audit; flagged for the next session.)*
- **MVP:** Not a feature blocker, but a **P0 security hygiene** item. Do first.
- **Verify:** old token returns 401 from Supabase; old Redis URL refuses AUTH.

> **Good news:** the *production* secrets (JWT, DB, OpenAI, Firebase, Redis) live in **Railway
> variables**, not in the repo — that part is done correctly. The exposure is limited to
> `.mcp.json`. Verified: no `.env`, `google-services.json`, `GoogleService-Info.plist`,
> `key.properties`, or `*-credentials.json` files are committed (all are gitignored).

---

## 2. BACKEND — Railway environment variables

Legend for **Status**: ✅ present & verified working · 🟡 present but unverified/partial ·
🔴 missing/required · ⚪ optional/not needed for MVP.

### 2.1 Database — `DATABASE_URL`  ✅
1. **Name:** `DATABASE_URL`
2. **Why:** primary PostgreSQL connection (all persisted data). Async driver derived at runtime (`postgresql+asyncpg://`).
3. **Referenced:** `app/core/config.py:19`, `app/core/enhanced_db_config.py:26`, `alembic` migrations, everywhere via `app.core.session`.
4. **Status:** ✅ SET in Railway (points to `mita-production-db.railway.internal:5432/railway`; credentials redacted). `/health` → `database: connected`. Migrations run at boot (`start.sh` → `alembic upgrade head`).
5. **Obtain:** auto-provisioned by the Railway `mita-production-db` service (Railway → service → Variables, or reference `${{mita-production-db.DATABASE_URL}}`).
6. **Place:** Railway → `mita-production` service → Variables → `DATABASE_URL`.
7. **Verify:** `/health` shows `database: connected`; `alembic upgrade head` succeeds in deploy logs.
8. **Blocks:** Backend (P0 if missing).
9. **MVP:** Required now — **already satisfied.**

### 2.2 Fallback Postgres parts — `PGUSER`/`PGPASSWORD`/`PGHOST`/`PGPORT`/`PGDATABASE`  ⚪
- Read only as a fallback in `app/core/enhanced_db_config.py:41-45` when `DATABASE_URL` is absent. Not needed while `DATABASE_URL` is set. No action.

### 2.3 JWT / crypto secrets  ✅
| Var | Status | Notes |
|-----|--------|-------|
| `JWT_SECRET` | ✅ SET (redacted) | Access/refresh token signing. Prod boot **crashes** if empty (`config.py:75-93`). `/health` → `jwt_secret_configured: true`. |
| `SECRET_KEY` | ✅ SET (redacted) | App-level encryption/signing. Same prod guard. |
| `JWT_PREVIOUS_SECRET` | ⚪ not set | Only needed **during** a JWT-secret rotation (`FEATURE_FLAGS_JWT_ROTATION=true` is on, but no rotation in progress). Set it only when you rotate `JWT_SECRET`. |
| `ALGORITHM` | ✅ `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ `120` | |

- **Obtain/rotate:** `openssl rand -base64 32`. **Place:** Railway variables. **Verify:** login returns a token; token validates on a protected endpoint. **Blocks:** Authentication (P0). **MVP:** required — **satisfied.**

### 2.4 Redis (Upstash, external)  ✅ / 🟡
- **There is no Railway Redis service.** Redis is Upstash over TLS (`rediss://`). Two *different* Upstash databases are configured in production:
  - `REDIS_URL` → host `wise-bonefish-101993.upstash.io` (used by token-revocation/security & task queue: `app/core/security.py:64`, `app/core/task_queue.py:104`).
  - `UPSTASH_REDIS_URL` + `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` → host `daring-moray-87435.upstash.io` (used by the rate limiter / REST API: `app/core/limiter_setup.py`, `app/core/upstash.py`).
1. **Names:** `REDIS_URL`, `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` (+ tuning: `REDIS_MAX_CONNECTIONS`, `REDIS_TIMEOUT`, `REDIS_RETRY_ON_TIMEOUT`).
2. **Why:** token revocation/blacklist (logout must survive across workers), rate limiting, task queue, caching.
3. **Referenced:** see hosts above; `app/core/external_services.py:262-271`.
4. **Status:** ✅ all four SET (redacted). `/health` → `upstash_configured: true`, `upstash_rest_api: true`. 🟡 **Unverified nuance:** the two-instance split (revocation on one DB, rate-limit on another) is intentional but worth a functional check that logout-revocation actually persists (see §7). TLS (`rediss://`) is **required** by Upstash.
5. **Obtain:** Upstash console → Redis → Details (copy the `rediss://` URL and REST URL/token).
6. **Place:** Railway variables.
7. **Verify:** `/health` `upstash_configured: true`; log in → log out → confirm the old token is rejected (revocation uses `REDIS_URL`).
8. **Blocks:** Auth/logout correctness, rate limiting (P1 if broken).
9. **MVP:** required — **satisfied** (pending the revocation functional check).

### 2.5 OpenAI  ✅
1. **Names:** `OPENAI_API_KEY` (+ `OPENAI_MODEL=gpt-4o-mini`; optional `OPENAI_TIMEOUT`, `OPENAI_MAX_RETRIES`, `OPENAI_RATE_LIMIT_REQUESTS`, `OPENAI_RATE_LIMIT_TOKENS`).
2. **Why:** AI budget analysis / categorization features. `validate_required_settings()` lists it as required.
3. **Referenced:** `app/core/config.py:121`, `app/core/external_services.py:49-57`.
4. **Status:** ✅ SET (`sk-proj-‹redacted›`). `/health` → `openai_configured: true`.
5. **Obtain:** platform.openai.com → API keys. **Place:** Railway. **Verify:** an AI endpoint returns a real completion (not a fallback).
6. **Blocks:** AI features only (app core works without it).
7. **MVP:** required for AI features — **satisfied.**

### 2.6 CORS & environment flags  ✅ (verify origin list)
- `ALLOWED_ORIGINS` = `https://app.mita.finance,https://admin.mita.finance,https://mita.finance` (Railway). Code also always appends `https://mitafinance.com` + `https://www.mitafinance.com` (`config.py:182-201`); localhost added only when `ENVIRONMENT != production`.
- `ENVIRONMENT=production`, `DEBUG=false`, `LOG_LEVEL=INFO` ✅ (production guard active).
- **Decision for owner:** the **mobile app** is a native client and does not need a CORS origin, so this list is for web surfaces only. Confirm the web app truly runs at `app.mita.finance`. **Blocks:** web clients only. **MVP:** satisfied for mobile.

### 2.7 Operational / non-secret vars (present, no action)
`ACCESS_TOKEN_EXPIRE_MINUTES, HOST=[::], PORT (Railway-injected), WEB_CONCURRENCY, WORKER_TIMEOUT, MAX_REQUESTS(_JITTER), KEEPALIVE_TIMEOUT, RATE_LIMIT_ENABLED, *_RATE_LIMIT, AUDIT_LOGGING_ENABLED, HEALTH_CHECK_*, FEATURE_FLAGS_*, ENCRYPTION_*, PCI_DSS_COMPLIANT, SECURE_COOKIES, SESSION_SECURE, PYTHON*`.
- ⚠️ **`PYTHONPATH=/opt/render/project/src`** is a leftover **Render** path (wrong for Railway, where code is at `/app`). Harmless today because Railpack sets its own path and imports resolve, but it should be corrected to `/app` or removed. Non-blocking. *(Code/config change — next session.)*

---

## 3. FIREBASE (Auth infra, Cloud Messaging, Crashlytics)

Firebase project in use: **`mita-finance`** (from the service-account `project_id`; service-account email `firebase-adminsdk-fbsvc@mita-finance.iam.gserviceaccount.com`).

### 3.1 Backend — Firebase Admin service account  ✅
1. **Name:** `FIREBASE_JSON` (inline JSON). Fallbacks in code: `GOOGLE_SERVICE_ACCOUNT` or `GOOGLE_APPLICATION_CREDENTIALS` (file path), else Application Default.
2. **Why:** server-side FCM push sending; Firebase Admin init.
3. **Referenced:** `app/main.py:98-118`, `app/core/external_services.py:337-338`, `app/services/drift_service.py:9-19`.
4. **Status:** ✅ SET — full service-account JSON present (private key `‹redacted›`), project `mita-finance`. `/health` → `firebase: initialized`. Firebase init is **non-fatal** if it fails (push just disabled).
5. **Obtain:** Firebase Console → Project settings → Service accounts → Generate new private key.
6. **Place:** Railway variable `FIREBASE_JSON` (paste minified JSON).
7. **Verify:** `/health` `firebase: initialized`; send a test push (`POST /api/notifications/test`).
8. **Blocks:** Push notifications (server side). Non-blocking for core journey.
9. **MVP:** push is deferrable; **currently satisfied** anyway.

### 3.2 Mobile — Firebase client config (`--dart-define-from-file`)  🔴
- The Flutter app reads Firebase config from **dart-defines** (`mobile_app/lib/firebase_options.dart`), not from a committed file. Required keys (all injected at build time):
  `FIREBASE_PROJECT_ID`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_STORAGE_BUCKET`,
  `FIREBASE_ANDROID_API_KEY`, `FIREBASE_ANDROID_APP_ID`,
  `FIREBASE_IOS_API_KEY`, `FIREBASE_IOS_APP_ID`, `FIREBASE_IOS_BUNDLE_ID`,
  (`FIREBASE_MACOS_*` optional).
1. **Files:** `mobile_app/firebase_config.json` (gitignored; template = `firebase_config.example.json`).
2. **Why:** initialize `Firebase.initializeApp` on device; FCM token registration; Crashlytics.
3. **Referenced:** `mobile_app/lib/firebase_options.dart:28-92`.
4. **Status:** 🔴 not present (expected). App is coded to **fail fast** (`StateError`) if `FIREBASE_PROJECT_ID` is empty — **but** `docs/ANDROID_RELEASE.md` confirms graceful degradation exists so the app still boots without Firebase (push/Crashlytics simply stay off). Confirm at integration time.
5. **Obtain:** Firebase Console → Project settings → your Android app / iOS app → SDK config values (or run `flutterfire configure`).
6. **Place:** create `mobile_app/firebase_config.json` from the example, **or** pass each `--dart-define=FIREBASE_...` on the build command.
7. **Verify:** app logs "Firebase initialized"; device receives a test FCM message.
8. **Blocks:** Android + iOS push & Crashlytics.
9. **MVP:** **deferrable** for closed beta (core journey works without push).

### 3.3 Android `google-services.json`  🔴
1. **File:** `mobile_app/android/app/google-services.json` (gitignored).
2. **Why:** the Google Services Gradle plugin auto-applies **only if this file exists** (`build.gradle.kts:14`). Needed for FCM on Android and for Google Sign-In to resolve the OAuth client by SHA-1.
3. **Status:** 🔴 not present. Build works without it (plugin skipped).
4. **Obtain:** Firebase Console → Android app (package **`mita.finance`**) → download `google-services.json`.
5. **Place:** `mobile_app/android/app/`.
6. **Verify:** release build applies the plugin; FCM + Google Sign-In work on a device.
7. **Blocks:** Android push + Android Google Sign-In.
8. **MVP:** deferrable (email/password auth works without it); required before Google Sign-In / push on Android.

### 3.4 iOS `GoogleService-Info.plist`  🔴
1. **File:** `mobile_app/ios/Runner/GoogleService-Info.plist` (gitignored).
2. **Why:** Firebase + Google Sign-In on iOS.
3. **Status:** 🔴 not present.
4. **Obtain:** Firebase Console → iOS app (bundle **`mita.finance`**) → download plist.
5. **Place:** `mobile_app/ios/Runner/` (add to Xcode target).
6. **Verify:** iOS build initializes Firebase; push token registers.
7. **Blocks:** iOS push + iOS Google Sign-In.
8. **MVP:** deferrable; required for iOS store build.

### 3.5 FCM / APNs bridge for iOS push  🔴 (deferred)
- For iOS push, Firebase needs an **APNs Authentication Key (.p8)** uploaded to Firebase Console (Project settings → Cloud Messaging → APNs Authentication Key). Requires an Apple Developer account (§8). Separately, the backend has **native APNs** vars (`APNS_KEY`, `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_TOPIC`, `APNS_USE_SANDBOX`) if you send via APNs directly — none are set. Choose one path (FCM-managed APNs is simpler). **MVP:** deferrable.

---

## 4. GOOGLE SIGN-IN / OAuth

The backend validates Google ID tokens against a **hardcoded allow-list** of OAuth client IDs
(`app/services/google_auth_service.py:10-16`) — all under Google project number `796406677497`
(Android/iOS) and `147595998708` (web/dev). These are **public client IDs** (not secrets):

| Platform | Client ID | Also in |
|----------|-----------|---------|
| Android | `796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com` | Railway `GOOGLE_CLIENT_ID` |
| iOS | `796406677497-0a9jg6vkuv2jtibddll5dp2b0394h21h.apps.googleusercontent.com` | code only |
| Web/dev | `147595998708-0pkq7emouan1rs2lrgjau0ee2lge35pl.apps.googleusercontent.com` | code only |

1. **Backend var:** `GOOGLE_CLIENT_ID` ✅ SET (Android client). Verification also uses the hardcoded list, so it works even without the env var.
2. **Mobile:** `GoogleSignIn().signIn()` is called with **no `serverClientId`** (`login_screen.dart:253`). On Android the returned ID token's `aud` will be the Android client (resolved via `google-services.json` + registered SHA), which the backend allows.
3. **Owner actions to make Google Sign-In actually work:**
   - **Android SHA fingerprints (🔴 required):** register the **SHA-1 and SHA-256** of *both* the debug keystore and the **release** keystore (§7) on the Android OAuth client / Firebase Android app. Get them with `keytool -list -v -keystore <keystore> -alias <alias>` or `./gradlew signingReport`. Without this, Android Google Sign-In returns no ID token.
   - **iOS URL scheme (🔴 required, currently missing):** add `CFBundleURLTypes` with the **reversed** iOS client ID to `mobile_app/ios/Runner/Info.plist`. It is **absent** today, so the Google Sign-In OAuth redirect cannot complete on iOS. *(File change — next session.)*
   - Provide `google-services.json` / `GoogleService-Info.plist` (§3.3–3.4).
4. **Verify:** on a real device, "Sign in with Google" completes and the backend creates/returns a session for the Google email.
5. **Blocks:** Google Sign-In (Android + iOS). Email/password auth is unaffected.
6. **MVP:** **deferrable** if launching with email/password only; required before advertising Google Sign-In.

---

## 5. GOOGLE VISION OCR (receipt scanning)

1. **Vars:** `GOOGLE_APPLICATION_CREDENTIALS=/app/config/google-vision-credentials.json` (Railway) and `GOOGLE_CREDENTIALS_PATH` (alt).
2. **Why (intended):** Google Cloud Vision text detection for receipts. Docs reference a **separate** GCP project `mita-finance-photo-recognition` (`setup_google_credentials.sh`) / `mita-finance-prod` (`config/secrets_config.json`).
3. **Referenced:** `app/ocr/google_vision_ocr_service.py:13`, `app/engine/ocr/google_vision_ocr_service.py:14`.
4. **Status / important finding:** 🟡 The **active OCR path is Tesseract**, not Vision. `POST /api/ocr/process` uses `OCRReceiptService` (`app/ocr/ocr_receipt_service.py`) → `pytesseract`. `GoogleVisionOCRService` is **not wired into any route** (dead/alternative code). So:
   - The `GOOGLE_APPLICATION_CREDENTIALS` file (`/app/config/google-vision-credentials.json`) is **not in the repo and not materialized at boot** — but this does **not** break OCR because Vision isn't on the live path.
   - **However**, the live Tesseract path needs the `tesseract` **system binary**, which the `Dockerfile` installs — but **Railway uses Railpack, not the Dockerfile**, and Railpack does not install `tesseract`. So receipt OCR (`/api/ocr/process`) likely **500s in production** for a different reason (missing binary), not a credential.
5. **Obtain (if you want Vision):** GCP Console → Vision-enabled project → service account key JSON.
6. **Place:** either write it to `/app/config/google-vision-credentials.json` at deploy, or (better) wire an inline-JSON env like `FIREBASE_JSON`.
7. **Verify:** upload a receipt to `/api/ocr/process` and get parsed fields.
8. **Blocks:** receipt-scanning feature only.
9. **MVP:** **deferred.** OCR is not part of the core add/edit/delete-transaction journey. Decide later between (a) add `tesseract` to the Railpack build, or (b) wire Google Vision + provide credentials.

---

## 6. EMAIL / SMTP (password reset, transactional mail)

1. **Vars:** `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`, `SMTP_USERNAME=apikey`, `SMTP_FROM=noreply@mita.finance` (all ✅ set) — **but `SMTP_PASSWORD` is 🔴 NOT set.** Alt providers also supported but unset: `SENDGRID_API_KEY`, `MAILGUN_API_KEY`/`MAILGUN_DOMAIN`, `POSTMARK_API_KEY`.
2. **Why:** password-reset emails and any transactional mail. With SendGrid, `SMTP_USERNAME=apikey` + `SMTP_PASSWORD=<SendGrid API key>`.
3. **Referenced:** `app/core/config.py:143-156`, `app/core/external_services.py:172-181`, `app/services/email_service.py`, `app/api/auth/password_reset.py`.
4. **Status:** 🔴 **email is non-functional in production** — `SMTP_USERNAME=apikey` is set but no password/API key.
5. **Obtain:** SendGrid dashboard → Settings → API Keys → create a "Mail Send" key; verify sender/domain `mita.finance`.
6. **Place:** Railway `SMTP_PASSWORD` = the SendGrid API key (redacted).
7. **Verify:** trigger a password-reset; confirm the email is delivered and (if used) `/api/errors/report` etc. work.
8. **Blocks:** password reset / email verification flows.
9. **MVP:** **required if** the launch includes email-based password reset; otherwise a fast follow. Recommend configuring for a real MVP.

---

## 7. IN-APP PURCHASES (premium subscription)

The backend **fails closed** on IAP until configured (`app/api/iap/routes.py:88-94` raises "IAP_ALLOWED_PRODUCT_IDS is not configured" in production; `:305-306` requires `GOOGLE_PACKAGE_NAME`). The Flutter app uses a **placeholder product id `'premium'`** (`mobile_app/lib/providers/user_provider.dart:305`) — real store product IDs must be created and wired.

| Var | Platform | Status | Purpose | Ref |
|-----|----------|--------|---------|-----|
| `IAP_ALLOWED_PRODUCT_IDS` | both | 🔴 missing | comma-sep allow-list of store product IDs; prod rejects purchases without it | `routes.py:68-94` |
| `IAP_ALLOW_SANDBOX` | both | ⚪ default false | keep false in prod | `config.py:137` |
| `APPSTORE_SHARED_SECRET` (a.k.a. `APPLE_SHARED_SECRET`) | iOS | 🔴 missing | App Store receipt validation | `iap/services.py:43` |
| `APPLE_BUNDLE_ID` | iOS | 🔴 missing | expected `mita.finance` (see §9) | `config.py:131` |
| `APPLE_ROOT_CA_PATH` | iOS | 🔴 missing | Apple Root CA G3 PEM for StoreKit2 JWS | `config.py:132` |
| `GOOGLE_PACKAGE_NAME` | Android | 🔴 missing | expected `mita.finance` (see §9) | `routes.py:305` |
| `GOOGLE_SERVICE_ACCOUNT` | Android | 🔴 missing | Google Play Developer API service account (JSON path) for purchase verification | `iap/routes.py:339`, `iap/services.py:90` |
| `GOOGLE_PUBSUB_AUDIENCE` | Android | 🔴 missing | OIDC audience for Play RTDN push endpoint | `config.py:134` |
| `GOOGLE_PUBSUB_SERVICE_ACCOUNT` | Android | 🔴 missing | allowed push SA email for RTDN | `config.py:135` |

1. **Obtain:** create products in **App Store Connect** (iOS) and **Google Play Console** (Android); App Store shared secret from ASC → App → In-App Purchases; Play verification needs a **Google Cloud service account** with Android Publisher access + Play RTDN Pub/Sub topic.
2. **Place:** Railway variables above; the store product IDs also go into the Flutter paywall (replace the `'premium'` placeholder).
3. **Verify:** sandbox purchase → backend verifies receipt → user flips to premium; production purchase flips premium and RTDN webhooks update status.
4. **Blocks:** monetization only.
5. **MVP:** **deferred** (closed beta does not require IAP — confirmed by `docs/ANDROID_RELEASE.md`). Requires paid Apple + Google developer accounts first.

---

## 8. MONITORING / OTHER BACKEND INTEGRATIONS

| Item | Var(s) | Status | MVP | Notes |
|------|--------|--------|-----|-------|
| Sentry (errors) | `SENTRY_DSN` (+ `SENTRY_TRACES_SAMPLE_RATE=0.1`, `SENTRY_PROFILES_SAMPLE_RATE=0.1` already set) | 🔴 DSN missing → causes `/health: degraded` | ⚪ deferrable | Obtain DSN from sentry.io project; place in Railway; `/health` `sentry: initialized`. Also `sentry_flutter` in the app can take a DSN via config. |
| AWS S3 (backups/storage) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (buckets `AWS_S3_BUCKET`, `BACKUP_BUCKET`, `AWS_DEFAULT_REGION=us-east-1` already set) | 🔴 keys missing | ⚪ deferrable | Receipt image storage falls back to local disk; DB backups to S3 won't run without keys. |
| Admin rollback webhook | `ROLLBACK_WEBHOOK_SECRET`, `ROLLBACK_BASE_URL`, `SLACK_WEBHOOK_URL`, `PAGERDUTY_ROUTING_KEY` | ⚪ none set | ⚪ deferrable | Ops automation only (`app/api/admin/rollback_webhook.py`). |
| Waitlist redirect | `FRONTEND_URL` | ⚪ optional | ⚪ | `app/api/waitlist/service.py:29`. |
| Grafana | `GRAFANA_PASSWORD` | ⚪ | ⚪ | Only if self-hosting the monitoring stack in `monitoring/`. |

---

## 9. ⚠️ PACKAGE / BUNDLE NAMING INCONSISTENCY (owner decision)

- **Actual app identifiers:** Android `applicationId = mita.finance`; iOS `PRODUCT_BUNDLE_IDENTIFIER = mita.finance` (test target `finance.mita.app.RunnerTests`).
- **Backend defaults/examples assume `com.mita.finance`:** `APNS_TOPIC` default `com.mita.finance` (`config.py:162`); `APPLE_BUNDLE_ID` / `GOOGLE_PACKAGE_NAME` examples `com.mita.finance`.
- **Impact:** when you configure IAP/APNs, you must set `APPLE_BUNDLE_ID=mita.finance`, `GOOGLE_PACKAGE_NAME=mita.finance`, and `APNS_TOPIC=mita.finance` to **match the real app IDs**, or receipt/push validation will mismatch. Also register the Firebase Android/iOS apps and store listings under **`mita.finance`**.
- **Decision:** confirm `mita.finance` is the intended forever-identifier (it cannot change after the first Play/App Store upload). If `com.mita.finance` was intended, that is a larger change and must be decided **before** first store submission.

---

## 10. MOBILE — Android build & release signing

1. **Keystore (🔴 does not exist in repo):** required for a Play-distributable AAB. Without it the release build **silently uses debug signing** (Play rejects it).
2. **Provide via** `mobile_app/android/key.properties` (gitignored) **or** env vars `KEYSTORE_FILE`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD` (`build.gradle.kts:31-66`).
3. **Generate:** `keytool -genkey -v -keystore mita-release.keystore -alias mita -keyalg RSA -keysize 2048 -validity 10000` (keep it forever — losing it means losing the Play listing).
4. **Then:** register that keystore's **SHA-1/SHA-256** in Firebase/Google OAuth (see §4).
5. **Build:** `flutter build appbundle --release --dart-define=API_BASE_URL=… --dart-define=ENV=production [--dart-define=FIREBASE_…]`.
6. **Blocks:** Play Store distribution + Android Google Sign-In (SHA).
7. **MVP:** required to ship to Play; side-loaded debug APK is fine for internal testing.
- Android permissions requested (for Play Data Safety form): INTERNET, network state, **CAMERA**, media images/storage, VIBRATE, RECEIVE_BOOT_COMPLETED, WAKE_LOCK, **USE_BIOMETRIC**, **ACCESS_FINE/COARSE_LOCATION**. Location will require a data-safety justification (used for income/expense classification).

---

## 11. MOBILE — iOS build, signing & App Store

1. **Apple Developer Program membership (🔴 owner account, paid $99/yr):** required for device builds, APNs, TestFlight, and App Store.
2. **Signing:** Apple Distribution certificate + provisioning profile for bundle `mita.finance`.
3. **App Store Connect app record** for `mita.finance` (name "MITA").
4. **APNs Auth Key (.p8)** → upload to Firebase (see §3.5) for push.
5. **iOS Google Sign-In URL scheme** must be added to `Info.plist` (see §4 — currently missing).
6. **Privacy nutrition labels / ATT:** Info.plist already declares camera, photos, location, FaceID, contacts, calendar, and **App Tracking Transparency** (`NSUserTrackingUsageDescription`) usage strings. `ITSAppUsesNonExemptEncryption=false` is set. ATS requires TLS 1.3 globally with an exception for `mita.finance` (the Railway API host must serve TLS 1.3 — Railway does).
7. **Blocks:** all iOS distribution.
8. **MVP:** deferred unless iOS is in the initial launch; **entirely gated on the Apple Developer account.**

---

## 12. CI / GitHub Actions

- Workflows: `main-ci.yml` (backend tests on a CI-local Postgres/Redis — all values hardcoded in the workflow, **no secrets needed**), `deployed-smoke.yml` (hits the live URL), `security.yml`, `deploy-production.yml`.
- **Only secret referenced:** `secrets.GITHUB_TOKEN` — **auto-provided** by GitHub. **No owner-managed GitHub secrets are currently required** for CI to run.
- ⚠️ `deploy-production.yml` only **builds & pushes a Docker image to GHCR** on `v*.*.*` tags — it does **not** deploy to Railway. Actual deploys happen via **Railway's GitHub integration** (auto-deploy from `teniee/mita_project`). If you later want CI-driven Android release builds, you'll add GitHub secrets: `KEYSTORE_FILE`(base64)/`KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD` + `FIREBASE_*` + `API_BASE_URL`.
- **MVP:** no action required now.

---

## 13. Local tooling (this machine / next engineer)

| Tool | Status | Needed for |
|------|--------|-----------|
| Python 3.12, pip, alembic | ✅ present | backend, migrations |
| Railway CLI | ✅ present (`railway`) | deploy/inspect |
| GitHub CLI (`gh`), git, node, npx | ✅ present | repo/CI ops |
| **Flutter SDK** | 🔴 **missing** | building/running the mobile app (`flutter`, `dart` not on PATH) |
| **Docker** | 🔴 missing | local Dockerfile builds (not needed — Railway uses Railpack) |
| Flutter MCP server (`.mcp.json`) | 🔴 broken here | `.mcp.json` points to a **macOS** path `/Users/mikhail/.pub-cache/bin/mcp_server`; won't run on this Windows box (matches the "Failed to reconnect to flutter" error). |

- **Owner/next-session action:** install the **Flutter SDK** (and Android SDK / Xcode as needed) on the build machine to compile the app; fix the Flutter MCP path if that tooling is wanted.

---

## 14. Privacy Policy & Terms (store requirement)

- `PRIVACY_POLICY.html` / `.md` and `TERMS_OF_SERVICE.html` / `.md` exist in the repo.
- **Owner action:** host them at stable public URLs (e.g. under `mitafinance.com`) and enter those URLs in App Store Connect and Play Console. **MVP:** required for store submission; not for backend.

---

## 15. Production security-policy decisions (owner to confirm)

Verified live, unauthenticated: `/docs`, `/redoc`, `/openapi.json`, `/metrics` all return **HTTP 200** in production.
- **Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) public:** decide whether a production financial API should expose its full schema publicly. Consider gating behind auth or disabling in prod.
- **`/metrics` (Prometheus) public:** typically should be restricted to the monitoring network or protected. Confirm this is intended.
- These are **configuration/policy** items (no credential); flagged for the next session to change if the intended policy is "closed."

---

## SUMMARY

### A. Immediate blockers for a *working MVP* (backend + core journey)
- **None at the backend infrastructure level.** The deployed backend is live: DB connected, Redis/Upstash connected, JWT/secret/OpenAI/Firebase configured, migrations at head, domain active. The core journey (register → login → onboarding → plan → dashboard → calendar → transactions) is **not blocked by any missing credential.**
- The only "P0" is hygiene: **rotate the committed `.mcp.json` secrets** (§1).

### B. Blockers that specifically require *owner action* (by feature)
1. **`.mcp.json` secret rotation** (Supabase token + Upstash URL) — §1. *(security)*
2. **Email/password-reset:** set `SMTP_PASSWORD` (SendGrid API key) — §6.
3. **Android release to Play:** generate keystore + provide `KEYSTORE_*`/`key.properties` — §10.
4. **Google Sign-In (Android/iOS):** SHA fingerprints + `google-services.json`/`GoogleService-Info.plist` + iOS URL scheme — §3–4.
5. **Push notifications (mobile):** Firebase client config + APNs key — §3.
6. **iOS anything:** Apple Developer account — §11.
7. **In-app purchases:** Apple + Google developer accounts, store products, IAP env vars — §7.
8. **Store submission:** host Privacy/Terms URLs — §14; confirm `mita.finance` naming — §9.

### C. Credentials already configured & verified ✅
`DATABASE_URL`, `JWT_SECRET`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REDIS_URL` + `UPSTASH_REDIS_URL` + `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN`,
`OPENAI_API_KEY` + `OPENAI_MODEL`, `FIREBASE_JSON` (Admin), `GOOGLE_CLIENT_ID`,
`ALLOWED_ORIGINS`, `ENVIRONMENT=production`, `DEBUG=false`, plus all operational flags.
Backend `/health` confirms database + firebase + openai + upstash healthy.

### D. Credentials still missing 🔴
`SMTP_PASSWORD`; `SENTRY_DSN`; `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`;
all IAP vars (`IAP_ALLOWED_PRODUCT_IDS`, `APPSTORE_SHARED_SECRET`, `APPLE_BUNDLE_ID`,
`APPLE_ROOT_CA_PATH`, `GOOGLE_PACKAGE_NAME`, `GOOGLE_SERVICE_ACCOUNT`,
`GOOGLE_PUBSUB_AUDIENCE`, `GOOGLE_PUBSUB_SERVICE_ACCOUNT`);
APNs (`APNS_KEY`/`APNS_KEY_ID`/`APNS_TEAM_ID`);
Vision OCR credentials file; mobile Firebase config (`firebase_config.json`,
`google-services.json`, `GoogleService-Info.plist`); Android keystore + SHA fingerprints;
iOS Google Sign-In URL scheme; Apple/Play/App Store Connect accounts; Privacy/Terms hosting URLs.

### E. Configured but *unverified* 🟡
- **Token revocation across workers** (uses `REDIS_URL` on the `wise-bonefish` Upstash DB) — set, but run a login→logout→reuse test to confirm revocation truly persists (§2.4, §7 verification).
- **Two-instance Redis split** (revocation vs rate-limit on different Upstash DBs) — intentional but confirm both DBs are alive and retained.
- **`.mcp.json` Upstash instance** — could not be reached via the Redis MCP tool (timed out); rotate regardless.
- **Firebase push send** — Admin initialized, but no test push was sent from production.

### F. Features to DEFER (external accounts not ready)
- **In-app purchases** (needs paid Apple + Google accounts) — §7.
- **iOS build/TestFlight/App Store** (needs Apple Developer account) — §11.
- **Push notifications & Crashlytics** (needs mobile Firebase config + APNs) — §3.
- **Receipt OCR** (Tesseract binary absent under Railpack; Vision not wired) — §5.
- **Sentry, AWS S3 backups** (optional monitoring/storage) — §8.

### G. Recommended order for the owner
1. **Rotate `.mcp.json` secrets** (Supabase + Upstash) — 15 min, security-critical (§1).
2. **Confirm the `mita.finance` package/bundle identifier** is final (§9) — blocks all store work if it changes.
3. **Set `SMTP_PASSWORD`** (SendGrid) so password reset works (§6); optionally `SENTRY_DSN` to clear "degraded" (§8).
4. **Run the end-to-end backend journey** against production to confirm auth + plan + transactions + revocation (evidence for the next session).
5. **Firebase project `mita-finance`:** register Android (`mita.finance`) & iOS (`mita.finance`) apps; download `google-services.json` + `GoogleService-Info.plist`; enable FCM.
6. **Generate the Android release keystore**, register SHA-1/SHA-256 (§10, §4), build a signed AAB.
7. **Enroll in Apple Developer Program** → iOS signing, APNs key, App Store Connect record (§11).
8. **Host Privacy/Terms URLs** (§14).
9. **Create store products + configure IAP** env vars once developer accounts exist (§7).
10. **Decide production docs/metrics exposure policy** (§15).

---

*End of audit. This document is descriptive only; no application code, configuration, or
deployment was modified in producing it.*

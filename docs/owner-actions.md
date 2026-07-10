# MITA Finance — Owner Actions (verified)

> Only actions that require **owner access** (dashboards, accounts, secrets, hardware) and that are **backed by evidence from this audit** are listed. Each entry says exactly where to act, whether the value is secret, how to verify, and whether it blocks the **core MVP journey** (register → onboard → plan → dashboard → calendar → create/edit/delete txn → persist → logout → recover).
> A broader speculative list exists at `docs/owner-dependencies-checklist.md`; this file is the **verified subset + corrections**.
> Auditor could **not** and did **not** change any Railway variable, secret, or setting.

Legend: 🔴 blocks core MVP · 🟠 blocks closed beta · 🟢 deferrable

---

## 1. IMMEDIATE — security (do first)

### 1.1 Rotate the leaked Supabase secret key 🔴 (security)
- **Why:** `.mcp.json` (committed to the **public** repo `teniee/mita_project`) contains a live `sb_secret_…` key. Public = compromised.
- **Where:** Supabase dashboard → project ref **`atdcxppfflmiwjwjuqyl`** → Project Settings → API → roll/rotate the secret (service) key.
- **Secret?** Yes. Do not paste it anywhere public.
- **After rotating:** update wherever it is actually consumed (this key appears only in `.mcp.json`; confirm nothing in Railway uses it). Then do §1.3.
- **Verify:** old key returns 401 from Supabase; app/services still work with the new key.

### 1.2 Rotate / delete the leaked Upstash Redis credential 🔴 (security)
- **Why:** `.mcp.json` contains a full `rediss://default:…@integral-jaybird-23463.upstash.io` URL (password included), public.
- **Nuance (verified):** this host is **NOT** the current production Redis (prod uses `wise-bonefish-101993` and `daring-moray-87435`). So it is likely an old/dev instance. Still must be rotated or the database deleted.
- **Where:** Upstash console → database `integral-jaybird-23463` → reset password or delete the DB if unused.
- **Secret?** Yes.
- **Verify:** old URL refuses AUTH; nothing in Railway references this host (confirmed none does at audit time).

### 1.3 Remove `.mcp.json` from the repo and purge history 🔴 (security)
- **Action:** delete `.mcp.json` from the working tree, add it to `.gitignore`, commit a `.mcp.json.example` with placeholders; then purge it from git history (`git filter-repo --path .mcp.json --invert-paths`) and force-push. Consider making the repo **private** until history is clean.
- **Secret?** The file is; the example is not.
- **Verify:** `gh api repos/teniee/mita_project/contents/.mcp.json` → 404; GitHub secret-scanning shows no live alerts.
- **Status (Fable 5, 2026-07-10):** ✅ `.mcp.json` untracked from the repo, added to `.gitignore`, `.mcp.json.example` committed with `${ENV_VAR}` placeholders. ⚠️ **NOT resolved:** the credentials remain in git history of the public repo. Rotation (§1.1/§1.2) and the history purge / force-push remain **owner actions** — no rotation confirmation was found, so the exposure must still be treated as live. Fable did not print, copy, or rotate any value.

---

## 2. BEFORE CLOSED ANDROID BETA — to run/test the working app

### 2.1 Install Android SDK on the build machine 🟠 (build)
- **Why:** `flutter build apk --debug` failed this session: `No Android SDK found. Try setting ANDROID_HOME.` (A JDK was found; only the Android SDK is missing.) No APK can be produced without it.
- **Where:** install Android Studio or `cmdline-tools`; set `ANDROID_HOME`/`ANDROID_SDK_ROOT`; run `flutter doctor --android-licenses`.
- **Secret?** No.
- **Verify:** `flutter doctor -v` shows Android toolchain ✓; `flutter build apk --debug` produces `build/app/outputs/flutter-apk/app-debug.apk`.
- **Blocks core MVP?** Yes for producing an installable build (not the backend journey).

### 2.2 Provide Firebase Android config 🟠
- **Why:** `mobile_app/android/app/google-services.json` is **absent**, and `mobile_app/lib/firebase_options.dart` reads all Firebase keys from `--dart-define` (`FIREBASE_ANDROID_API_KEY`, `FIREBASE_ANDROID_APP_ID`, `FIREBASE_PROJECT_ID`, `FIREBASE_MESSAGING_SENDER_ID`, …) and **throws if `projectId` is empty**. Without either, Firebase (push, crashlytics) won't initialize on device.
- **Where:** Firebase console → project **`mita-finance`** → Android app → download `google-services.json` → place at `mobile_app/android/app/google-services.json`; and/or supply the `FIREBASE_*` values as build-time `--dart-define`s.
- **Secret?** `google-services.json` contains client keys (low sensitivity, but keep out of a public repo / git-ignore it).
- **Verify:** app launches without the `firebase_options` assertion; FCM token registers.

### 2.3 Add Android signing SHA-1 / SHA-256 to Firebase 🟠 (only if Google Sign-In / phone auth used)
- **Where:** Firebase console → project settings → your Android app → "Add fingerprint" (debug + release SHA-1/256 from your keystore). Backend has `GOOGLE_CLIENT_ID` configured.
- **Verify:** Google Sign-In completes end-to-end on device.
- **Blocks core MVP?** No — email/password register+login is fully working (verified). Google Sign-In is optional.

### 2.4 Set `SMTP_PASSWORD` in Railway 🟠 (password reset / email)
- **Why:** Railway has `SMTP_HOST=smtp.sendgrid.net`, `SMTP_USERNAME=apikey`, `SMTP_FROM`, `SMTP_PORT` but **no `SMTP_PASSWORD`**. SendGrid needs the API key as the password.
- **Where:** Railway → `mita-production` → Variables → add `SMTP_PASSWORD` = SendGrid API key.
- **Secret?** Yes.
- **Verify:** trigger password reset to a mailbox you own; email arrives; reset link works.
- **Blocks core MVP?** No — registration/login work without email verification (verified). Needed only for password-reset UX.

### 2.5 (Recommended) Set `SENTRY_DSN` 🟢/🟠
- **Why:** `/health` reports `degraded` **only** because Sentry is unconfigured (traces/profiles sample rates are set; DSN is missing). No crash visibility on backend.
- **Where:** Sentry project → DSN → Railway variable `SENTRY_DSN`.
- **Secret?** DSN is semi-secret (treat as secret).
- **Verify:** `/health` → `sentry:"available"` and status flips toward `healthy`; test event appears in Sentry.
- **Blocks core MVP?** No (observability). Alternatively fix DEF-006 so missing Sentry no longer reports `degraded`.

---

## 3. BEFORE GOOGLE PLAY

| Action | Where | Secret | Verify | Blocks core |
|--------|-------|--------|--------|-------------|
| Create Google Play Developer account | play.google.com/console (one-time $25) | No | Console access | 🟢 (needed to publish) |
| Generate release upload keystore + wire signing | local `keytool`; `mobile_app/android` signing config; store securely (NOT in repo) | **Yes** | signed release AAB builds | 🟢 |
| Confirm `applicationId` / package name | `mobile_app/android/app/build.gradle` | No | matches Firebase + Play listing | 🟢 |
| Host Privacy Policy + Terms at public URLs | you have `PRIVACY_POLICY.html` / `TERMS_OF_SERVICE.html` in repo — host them (e.g. mitafinance.com) | No | URLs load; entered in Play listing | 🟢 |
| Complete Play Data Safety form | Play Console | No | form submitted | 🟢 |

## 4. BEFORE iOS

| Action | Where | Secret | Verify | Blocks core |
|--------|-------|--------|--------|-------------|
| Apple Developer Program account | developer.apple.com ($99/yr) | No | account active | 🟢 |
| `GoogleService-Info.plist` | Firebase → iOS app → download → `mobile_app/ios/Runner/` | client keys | app builds; Firebase init | 🟢 |
| APNs auth key (.p8) for push | Apple Developer → Keys → upload to Firebase | **Yes** | push delivered on device | 🟢 |
| Apple bundle ID | Apple Developer → Identifiers; match `ios/Runner` | No | provisioning profile builds | 🟢 |

## 5. DEFERRED — optional integrations (not needed for the core MVP journey)

| Integration | Evidence | Owner action if/when needed |
|-------------|----------|------------------------------|
| AWS S3 storage / backups | Railway has `AWS_S3_BUCKET`, `BACKUP_BUCKET`, region — but **no `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`** | add IAM keys (secret) only if S3 upload/backup features are exercised; otherwise leave off |
| Google Vision OCR (receipts) | `GOOGLE_APPLICATION_CREDENTIALS=/app/config/google-vision-credentials.json` set, file provided at runtime | mount the Vision service-account JSON on Railway; verify `/api/transactions/receipt` |
| OpenAI (AI insights) | `OPENAI_API_KEY` **is** configured (`gpt-4o-mini`); `openai_configured:true` in `/health` | none — already working; monitor spend |
| In-App Purchase / premium | IAP routers present | configure Play/App Store products + server verification keys before monetizing |
| Sentry | see §2.5 | optional |

---

## 6. What is already correctly configured (verified — no action)
- `DATABASE_URL` (Postgres, Railway internal) — DB **connected**, migrations at head `0034`.
- Production Redis (`REDIS_URL` / `UPSTASH_*`) — **connected**; token revocation/blacklist proven live.
- `FIREBASE_JSON` service account (with private key) — Firebase **initialized** (server side).
- `JWT_SECRET`, `SECRET_KEY`, `ALGORITHM=HS256`, token expiry — auth working end-to-end.
- `OPENAI_API_KEY` — configured.
- CORS `ALLOWED_ORIGINS`, security headers, HTTPS redirect — verified in production.
- All production secrets are **externalized to Railway** (not in the repo) except the two in `.mcp.json` (see §1).

# MITA Android — Closed-Beta Release Preparation

> Verified against commit on `main` (`73c1817` lineage), 2026-07-07.
> Build environment note: this repo's development sandbox cannot run Gradle
> (dl.google.com / maven.google.com blocked), so **APK/AAB builds happen in CI or on the
> owner's machine**. Everything below is source-verified; items needing a real build are marked.

## Release-hygiene checklist (source-verified)

| Check | Status | Evidence |
|-------|--------|----------|
| `applicationId` | ✅ `mita.finance` | `mobile_app/android/app/build.gradle.kts` `defaultConfig` |
| Version | ✅ `versionCode 1`, `versionName "1.0"` (pubspec `1.0.0+1` consistent). Bump `versionCode` for every Play upload. | build.gradle.kts / `pubspec.yaml` |
| API URL injected via dart-define | ✅ `AppConfig.baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: <Railway URL>)` | `mobile_app/lib/config.dart` |
| No localhost / hardcoded IPs in app code | ✅ zero matches in `lib/` | grep `localhost|127.0.0.1|10.0.2.2` |
| Hardcoded production URL | ⚠️ only as the *default value* of the dart-define, pointing at the **dead** Railway domain. Harmless once builds always pass `--dart-define=API_BASE_URL=...`; update the default when the new domain exists (also listed in `network_security_config.xml`, where it is harmless). | `config.dart:17` |
| Release logging disabled | ✅ 0 raw `print()` in `lib/`; logging routed through `logging_service.dart` gated on `kDebugMode`/environment; `AppConfig.enableDebugLogs` is development-only | grep + config.dart |
| No secrets bundled | ✅ no API keys/secrets in Dart source; Firebase config entirely via `FIREBASE_*` dart-defines (`firebase_options.dart`); `google-services.json` gitignored | grep + `firebase_options.dart` |
| Cleartext traffic | ✅ disabled globally (`base-config cleartextTrafficPermitted="false"`, system trust anchors) | `network_security_config.xml` |
| Certificate pinning | ✅ safely disabled (empty fingerprint list → auto-off). A new backend domain needs **no** app change. Optionally add fingerprints later per the instructions in `certificate_pinning_service.dart`. | `certificate_pinning_service.dart` |
| Firebase handling without credentials | ✅ app boots and works without any Firebase config (graceful degradation added in `c53d812`); push + Crashlytics stay off until FIREBASE_* dart-defines and `google-services.json` are provided | `main.dart` |
| Release build config | ✅ `minifyEnabled` + `shrinkResources` + proguard; falls back to **debug signing with a loud warning** when no keystore is configured | build.gradle.kts |

## Current artifact

CI (`mobile-ci`) builds and uploads a **debug APK** (`mita-debug-apk`, ~89 MB, 7-day retention)
on every run — proof of buildability, **not** distributable to beta users via Play.

## Building the closed-beta release (owner machine or CI with secrets)

```bash
cd mobile_app
flutter build appbundle --release \
  --dart-define=API_BASE_URL=https://<deployed-backend-domain> \
  --dart-define=ENV=production \
  # optional, enables push + Crashlytics (values from Firebase console):
  --dart-define=FIREBASE_ANDROID_API_KEY=... \
  --dart-define=FIREBASE_ANDROID_APP_ID=... \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... \
  --dart-define=FIREBASE_PROJECT_ID=... \
  --dart-define=FIREBASE_STORAGE_BUCKET=...
```
Use `build apk --release` instead for direct-install distribution; `appbundle` for the Play
internal-testing track (recommended for closed beta).

## Signing — exact requirements (owner action; no keystore exists in the repo)

1. Generate a keystore (once, keep it forever — losing it means losing the Play listing):
   ```bash
   keytool -genkey -v -keystore mita-release.keystore -alias mita \
     -keyalg RSA -keysize 2048 -validity 10000
   ```
2. Provide credentials to the build in **one** of the two supported ways:
   - `mobile_app/android/key.properties` (gitignored):
     ```properties
     storeFile=/absolute/path/to/mita-release.keystore
     storePassword=...
     keyAlias=mita
     keyPassword=...
     ```
   - or environment variables: `KEYSTORE_FILE`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`
     (this is how a CI release job would do it, from GitHub secrets).
3. Without either, the release build **silently ships debug-signed** (with a console warning) —
   acceptable for side-loaded testing only, rejected by Play.
4. If Firebase is enabled: put `google-services.json` in `mobile_app/android/app/`
   (the google-services plugin applies itself only when the file exists) and register the
   **release** SHA-1/SHA-256 of the keystore in the Firebase project.

## Play Console notes for review

- Permissions include fine/coarse **location** (used for income-pattern classification) —
  prepare the data-safety justification before submitting, or Play review will bounce it.
- IAP is not required for closed beta; backend IAP endpoints fail closed until store
  credentials are configured (see `docs/RAILWAY_DEPLOYMENT.md` §2.8).

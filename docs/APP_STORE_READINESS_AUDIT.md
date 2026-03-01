# MITA — App Store & Google Play Readiness Audit

**Date:** 2026-03-01
**Auditor:** Automated codebase analysis
**App Version:** 1.0.0+1
**Status:** NOT READY FOR SUBMISSION

---

## Executive Summary

MITA (Money Intelligence Task Assistant) is a Flutter-based fintech app with a FastAPI backend.
The project has strong privacy documentation (GDPR/CCPA), a well-configured iOS Privacy Manifest,
and solid security foundations. However, **14 issues must be resolved** before the app can be
submitted to Apple App Store or Google Play Store.

---

## CRITICAL BLOCKERS (App will be rejected)

### 1. iOS Bundle Identifier mismatch across configs

| Location | Bundle ID |
|----------|-----------|
| `ios/Runner.xcodeproj/project.pbxproj` (lines 506, 688, 710) | `com.mikhail-mita.mitaFinance` |
| `lib/firebase_options.dart` / `ios/Runner/GoogleService-Info.plist` | `mita.finance` |
| `ios/Runner/Runner.entitlements` (keychain) | `com.yakovlev.mita` |

**Impact:** Firebase services (Crashlytics, Push, Analytics) will silently fail in production.
Apple will reject the build if entitlements reference a different bundle ID.

**Fix:** Unify all references to a single identifier (e.g., `finance.mita.app`).

### 2. APNs environment set to "development"

**File:** `ios/Runner/Runner.entitlements:11`
```xml
<key>aps-environment</key>
<string>development</string>
```

**Impact:** Push notifications will not work for App Store users. Apple requires `production`.

**Fix:** Change value to `production` for release builds.

### 3. No DEVELOPMENT_TEAM in Xcode project

**File:** `ios/Runner.xcodeproj/project.pbxproj`

No `DEVELOPMENT_TEAM` setting found anywhere in the project. Without an Apple Developer
Team ID the app cannot be code-signed for distribution.

**Fix:** Add `DEVELOPMENT_TEAM = <YOUR_TEAM_ID>;` to all Runner build configurations.

### 4. No Android release keystore configured

**File:** `android/key.properties` — **does not exist**

The build falls back to debug signing:
```
WARNING: Release keystore not configured. Using debug signing.
```

**Impact:** Google Play rejects debug-signed APK/AAB.

**Fix:** Generate a release keystore, create `key.properties`, reference it in `build.gradle.kts`.

### 5. Three duplicate MainActivity.kt files

| Path | Package |
|------|---------|
| `android/.../com/example/mobile_app/MainActivity.kt` | `com.example.mobile_app` |
| `android/.../mita/finance/MainActivity.kt` | `mita.finance` |
| `android/.../mita/mobile_app/MainActivity.kt` | `mita.mobile_app` |

**Impact:** The `com.example` package is a Flutter default template marker. Google Play may
reject the app or flag it. Only `mita.finance` matches the `applicationId`.

**Fix:** Delete `com/example/mobile_app/` and `mita/mobile_app/` directories.

### 6. CFBundleName = "mobile_app" instead of "MITA"

**File:** `ios/Runner/Info.plist:16`
```xml
<key>CFBundleName</key>
<string>mobile_app</string>
```

**Impact:** The app name under the icon on the home screen may display as "mobile_app".
Apple may reject for unprofessional naming.

**Fix:** Change to `MITA`.

---

## SERIOUS ISSUES (High rejection risk)

### 7. Certificate pinning list is empty

**File:** `lib/services/certificate_pinning_service.dart:28-37`

All certificate fingerprints are commented out with a `TODO` marker. The pinning service
is a no-op — MITM attacks are possible.

**Fix:** Run `openssl s_client` against `mita.finance:443`, extract SHA-256 fingerprint,
and add it to `_pinnedCertificates`.

### 8. Sentry DSN hardcoded in main.dart

**File:** `lib/main.dart:132-133`

The full Sentry DSN (including organization ID and project ID) is committed to source
control. While Sentry DSNs are semi-public, this is an infrastructure leak.

**Fix:** Use `String.fromEnvironment('SENTRY_DSN')` without a default value, or load
from secure storage at build time via `--dart-define`.

### 9. Deprecated Android storage permissions

**File:** `android/app/src/main/AndroidManifest.xml:6-7`
```xml
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
```

These permissions are deprecated since API 33 (Android 13). With `targetSdk = 35`,
Google Play will flag this.

**Fix:** Add `android:maxSdkVersion="32"` to both, and add `READ_MEDIA_IMAGES` for API 33+.

### 10. Missing Android permissions for biometrics and location

The app uses `local_auth` (biometrics) and `geolocator` (location), but
`AndroidManifest.xml` is missing:
- `android.permission.USE_BIOMETRIC`
- `android.permission.ACCESS_FINE_LOCATION`
- `android.permission.ACCESS_COARSE_LOCATION`

**Fix:** Add the missing `<uses-permission>` entries.

### 11. No Adaptive Icons for Android

Missing:
- `ic_launcher_foreground.xml` (adaptive icon foreground layer)
- `ic_launcher_round.png` (round icons for Pixel/Samsung)
- `mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon definition)

Required since Android 8.0 (API 26) and expected by Google Play.

**Fix:** Generate adaptive icons using Android Studio's Image Asset wizard or
the `flutter_launcher_icons` package.

### 12. Debug screens compiled into production bundle

Files exist in the project and will be compiled:
- `lib/screens/debug_test_screen.dart`
- `lib/screens/auth_test_screen.dart`

Although routes are removed, the code is still in the binary. Apple review may
discover debug UIs via static analysis.

**Fix:** Wrap imports and classes with `if (kDebugMode)` guards, or remove files entirely.

### 13. Kotlin version conflict

| Source | Version |
|--------|---------|
| `build.gradle.kts` | `kotlin-gradle-plugin:2.1.0`, `languageVersion = "2.1"` |
| `gradle.properties` | `kotlin.languageVersion=1.8`, `kotlin.apiVersion=1.8` |

**Impact:** Build may fail or produce unpredictable behavior.

**Fix:** Align all Kotlin version settings — remove overrides from `gradle.properties`
or update them to match `build.gradle.kts`.

---

## MODERATE ISSUES (May affect review or user experience)

### 14. No `network_security_config.xml` for Android

While `usesCleartextTraffic="false"` is set, Google recommends an explicit
`network_security_config.xml` for fine-grained HTTPS enforcement.

### 15. CCPA phone number placeholder

`PRIVACY_POLICY.md` contains `XXX-XXX-XXXX` instead of a real phone number.
Required for California users under CCPA.

### 16. print() calls in production code

18 `print()`/`debugPrint()` calls found across 5 files. These leak information to
the device console log.

### 17. Unfinished TODO comments

5 `TODO` comments in production code, including the critical certificate pinning one.

### 18. Windows/Desktop metadata still shows `com.example`

`mobile_app/windows/runner/Runner.rc:92` contains `CompanyName = "com.example"`.

---

## WHAT IS ALREADY DONE WELL

- [x] Privacy Policy + Terms of Service (GDPR/CCPA compliant, 500+ lines)
- [x] iOS Privacy Manifest (`PrivacyInfo.xcprivacy`) for iOS 17+
- [x] `ITSAppUsesNonExemptEncryption = false` (export compliance)
- [x] `NSAllowsArbitraryLoads = false` (App Transport Security enforced)
- [x] All iOS `NSUsageDescription` strings filled (Camera, Photos, Location, Face ID, etc.)
- [x] App icons present for all iOS sizes (20pt through 1024pt)
- [x] Android mipmap icons present (mdpi through xxxhdpi)
- [x] ProGuard/R8 configuration for Android release builds
- [x] Firebase Crashlytics + Sentry dual error monitoring
- [x] In-App Purchases via official `in_app_purchase` package
- [x] Biometric authentication with `NSFaceIDUsageDescription`
- [x] iOS Security Bridge (jailbreak detection)
- [x] `usesCleartextTraffic="false"` on Android
- [x] Localization support (English, Spanish)
- [x] 26 mobile test files + 88 backend test files

---

## ACTION PLAN (priority order)

| # | Task | Platform | Effort |
|---|------|----------|--------|
| 1 | Unify iOS Bundle ID to single value | iOS | Medium |
| 2 | Set `aps-environment` to `production` | iOS | Easy |
| 3 | Add `DEVELOPMENT_TEAM` to project.pbxproj | iOS | Easy |
| 4 | Create release keystore + `key.properties` | Android | Medium |
| 5 | Delete duplicate `MainActivity.kt` files | Android | Easy |
| 6 | Fix `CFBundleName` to `MITA` | iOS | Easy |
| 7 | Add missing Android permissions (biometrics, location) | Android | Easy |
| 8 | Update storage permissions for API 33+ | Android | Easy |
| 9 | Fix Kotlin version conflict | Android | Medium |
| 10 | Generate Adaptive Icons | Android | Medium |
| 11 | Populate certificate pinning fingerprints | Both | Medium |
| 12 | Remove debug screens from production build | Flutter | Easy |
| 13 | Move Sentry DSN to build-time env variable | Flutter | Easy |
| 14 | Fill CCPA phone number in Privacy Policy | Legal | Easy |

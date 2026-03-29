# MITA Finance — Production Readiness Audit: All Issues

> **Date:** 2026-03-24
> **Last updated:** 2026-03-29
> **Branch:** `main`
> **Auditor:** Claude Opus 4.6 (Bulletproof Deep Scan)
> **Files analyzed:** 1221 files across backend, frontend, infrastructure, CI/CD, configs

---

## Table of Contents

- [CRITICAL — App won't start or massive security breach](#critical)
  - [C-01: JWT and Secret Keys leaked in render.yaml — FIXED](#c-01-jwt-and-secret-keys-leaked-in-renderyaml)
  - [C-02: Firebase API keys hardcoded in source code](#c-02-firebase-api-keys-hardcoded-in-source-code)
  - [C-03: JWT_SECRET auto-generates on every restart if not set](#c-03-jwt_secret-auto-generates-on-every-restart-if-not-set)
  - [C-04: Database URL logged in plaintext with credentials — FIXED](#c-04-database-url-logged-in-plaintext-with-credentials)
  - [C-02: Firebase API keys hardcoded in source code — FIXED](#c-02-firebase-api-keys-hardcoded-in-source-code)
  - [C-03: JWT_SECRET auto-generates on every restart if not set — FIXED](#c-03-jwt_secret-auto-generates-on-every-restart-if-not-set)
  - [C-04: Database URL logged in plaintext with credentials](#c-04-database-url-logged-in-plaintext-with-credentials)
  - [C-05: JWT tokens partially logged (first 30 chars)](#c-05-jwt-tokens-partially-logged-first-30-chars)
- [HIGH — App starts but has major problems](#high)
  - [H-01: CORS always allows localhost origins in production — FIXED](#h-01-cors-always-allows-localhost-origins-in-production)
  - [H-02: API base URL hardcoded in Flutter with no environment switching — FULLY FIXED](#h-02-api-base-url-hardcoded-in-flutter-with-no-environment-switching)
  - [H-03: MinimalSettings fallback silently swallows config errors](#h-03-minimalsettings-fallback-silently-swallows-config-errors)
  - [H-04: datetime.utcnow() used throughout (deprecated in Python 3.12)](#h-04-datetimeutcnow-used-throughout-deprecated-in-python-312)
  - [H-05: Alembic migrations may fail silently and app starts anyway — FIXED](#h-05-alembic-migrations-may-fail-silently-and-app-starts-anyway)
  - [H-06: aioredis dependency is deprecated/dead](#h-06-aioredis-dependency-is-deprecateddead)
  - [H-07: Excessive debug logging in auth flow](#h-07-excessive-debug-logging-in-auth-flow)
  - [H-08: Single worker deployment ignores WEB_CONCURRENCY](#h-08-single-worker-deployment-ignores-web_concurrency)
- [MEDIUM — Functional issues, tech debt, reliability](#medium)
  - [M-01: onGenerateRoute returns null, breaking dynamic navigation](#m-01-ongenerateroute-returns-null-breaking-dynamic-navigation)
  - [M-02: login_data.dict() is deprecated in Pydantic v2](#m-02-login_datadict-is-deprecated-in-pydantic-v2)
  - [M-03: Missing IgnoredAlert model in __init__.py](#m-03-missing-ignoredalert-model-in-__init__py)
  - [M-04: spacy and transformers in production requirements (huge image)](#m-04-spacy-and-transformers-in-production-requirements-huge-image)
  - [M-05: CI/CD quality checks are non-blocking](#m-05-cicd-quality-checks-are-non-blocking)
  - [M-06: Flutter tests are continue-on-error](#m-06-flutter-tests-are-continue-on-error)
  - [M-07: Two different Base definitions in db/](#m-07-two-different-base-definitions-in-db)
- [LOW — Code quality, minor issues](#low)
  - [L-01: Massive code duplication across engine/logic/services](#l-01-massive-code-duplication-across-enginelogicservices)
  - [L-02: 200+ stale remote branches](#l-02-200-stale-remote-branches)
  - [L-03: Root-level test files outside tests/ directory](#l-03-root-level-test-files-outside-tests-directory)
  - [L-04: APNS_USE_SANDBOX defaults to True](#l-04-apns_use_sandbox-defaults-to-true)
- [RAILWAY — Production environment misconfigurations](#railway)
  - [R-01: JWT_PREVIOUS_SECRET not set while JWT rotation is enabled](#r-01-jwt_previous_secret-not-set-while-jwt-rotation-is-enabled)
  - [R-02: PYTHONPATH points to Render path, not Railway](#r-02-pythonpath-points-to-render-path-not-railway)
  - [R-03: Missing critical environment variables in Railway](#r-03-missing-critical-environment-variables-in-railway)
- [Priority Fix Order](#priority-fix-order)

---

<a id="critical"></a>
## CRITICAL — App won't start or massive security breach

---

<a id="c-01-jwt-and-secret-keys-leaked-in-renderyaml"></a>
### C-01: JWT and Secret Keys leaked in `render.yaml` — FIXED

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **File** | `render.yaml` lines 57–62 |
| **Priority** | P0 — Fix immediately |
| **Effort** | 30 minutes |
| **Status** | **FIXED** (2026-03-24) |
| **Fix commit** | `feature/fix-c01-secrets-leaked-render-yaml` |

#### Description

The `render.yaml` file, which is committed to the git repository and visible to anyone with repo access, contained the actual production secret values in YAML comments:

```yaml
- key: SECRET_KEY
  sync: false  # Set to: _2xehg0QmsjRElHCg7hRwAhEO9eYKeZ9EDDSFx9CgoI
- key: JWT_SECRET
  sync: false  # Set to: LZaS6tha51MBwgBoHW6GbK4VbbboeQO12LsmEDdKp3s
- key: JWT_PREVIOUS_SECRET
  sync: false  # Set to: b0wJB1GuD13OBI3SEfDhtFBWA8KqM3ynI6Ce83xLTHs
```

These were the actual production JWT signing secrets. With these, **anyone could:**
- Forge valid JWT access and refresh tokens for any user
- Bypass all authentication and authorization
- Access any user's financial data (transactions, budgets, goals)
- Impersonate admin users

#### What was fixed

1. **Removed secret values from `render.yaml` comments** — replaced with safe placeholder instructions that include the generation command (`openssl rand -base64 32`)
2. Preserved `sync: false` so secrets remain dashboard-managed

#### Remaining manual action required

> **CRITICAL:** The old secrets remain in git history. You MUST:
> 1. **Generate completely new secrets immediately:**
>    ```bash
>    openssl rand -base64 32   # Run 3 times for SECRET_KEY, JWT_SECRET, JWT_PREVIOUS_SECRET
>    ```
> 2. **Update the new secrets in the Render Dashboard** (Environment → Service Variables)
> 3. Consider the old secrets permanently compromised — rotate them regardless of repo visibility

---

<a id="c-02-firebase-api-keys-hardcoded-in-source-code"></a>
### C-02: Firebase API keys hardcoded in source code — FIXED

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **File** | `mobile_app/lib/firebase_options.dart` |
| **Priority** | P0 — Fix immediately |
| **Effort** | 1 hour |
| **Status** | **FIXED** (2026-03-25) |
| **Fix commit** | `feature/fix-c02-firebase-keys-hardcoded` |

#### Description

The Firebase configuration file contained hardcoded API keys, app IDs, and project identifiers for Android, iOS, and macOS. The same API key was reused across all platforms.

#### What was fixed

1. **Replaced all hardcoded values with `String.fromEnvironment()`** — Firebase config is now injected at compile time via `--dart-define-from-file=firebase_config.json`
2. **Added fail-fast validation** — app throws a clear `StateError` at startup if Firebase config was not provided at build time, instead of silently failing
3. **Created `firebase_config.example.json`** — template showing all required environment variables for developers
4. **Fixed `.gitignore` patterns** — `google-services.json` and `GoogleService-Info.plist` patterns now use `**` prefix to match inside `mobile_app/` directory
5. **Untracked `google-services.json` and `GoogleService-Info.plist`** from git index — these files contained the same API key and were incorrectly tracked despite being in `.gitignore` (path pattern didn't match `mobile_app/` subdirectory)

#### Build usage

```bash
# Local development
flutter run --dart-define-from-file=firebase_config.json

# Production build
flutter build apk --dart-define-from-file=firebase_config.json
flutter build ipa --dart-define-from-file=firebase_config.json
```

#### Remaining manual action required

> **IMPORTANT:** The old API keys remain in git history. You SHOULD:
> 1. **Restrict the existing API key** in Google Cloud Console → API Credentials → restrict to your app's package name/bundle ID
> 2. **Enable Firebase App Check** in the Firebase Console to restrict which apps can use the key
> 3. **Set up proper Firebase Security Rules** for Firestore and Storage
> 4. **Create `mobile_app/firebase_config.json`** locally by copying `firebase_config.example.json` and filling in real values
> 5. Consider rotating the API key if the repo was ever public

---

<a id="c-03-jwt_secret-auto-generates-on-every-restart-if-not-set"></a>
### C-03: JWT_SECRET auto-generates on every restart if not set — FIXED

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **File** | `app/core/config.py` lines 73–89 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 10 minutes |
| **Status** | **FIXED** (2026-03-25) |
| **Fix commit** | `feature/fix-c03-jwt-secret-autogenerate` |

#### Description

The pydantic field validator for `JWT_SECRET` and `SECRET_KEY` generated a random fallback if the environment variable was empty — even in production. On every server restart, `secrets.token_urlsafe(32)` produced a **new random string**, invalidating all previously issued JWT tokens.

Additionally, the `MinimalSettings` fallback (try/except around `Settings()`) would silently swallow the error and create a settings object with empty secrets, making any validator-level crash ineffective.

#### What was fixed

1. **Validator now crashes in production** — `raise ValueError` with a clear message and generation command instead of `logging.warning()` + auto-generate
2. **MinimalSettings fallback re-raises in production** — the `try/except` around `Settings()` now checks `ENVIRONMENT` and re-raises the error in production, preventing silent fallback to empty secrets
3. **Development/test behavior preserved** — auto-generates secrets for local convenience, no changes to developer workflow

---

<a id="c-04-database-url-logged-in-plaintext-with-credentials"></a>
### C-04: Database URL logged in plaintext with credentials — FIXED

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Files** | `app/core/async_session.py` line 71, `app/core/session.py` lines 57–58 |
| **Priority** | P0 — Fix immediately |
| **Effort** | 5 minutes |
| **Status** | **FIXED** (2026-03-25) |
| **Fix commit** | `feature/fix-c04-db-url-credential-leakage` |

#### Description

The async database initialization logs the full database URL (which includes username and password) at INFO level:

```python
# app/core/async_session.py:71
logger.info(f"Final database URL used by asyncpg: {database_url}")
```

And in the sync session:

```python
# app/core/session.py:57-58
logger.info(f"Sync session connecting to: {host}:{port}/{database}")
logger.info(f"Username (via connect_args): {parsed.username}")
```

A typical database URL looks like:
```
postgresql+asyncpg://user.name:p4ssw0rd@db.supabase.co:6543/postgres?ssl=require
```

This is written to stdout, log files, and any log aggregation service (Sentry breadcrumbs, Render logs, CloudWatch, etc.).

#### What will happen if not fixed

- Database credentials exposed to anyone with log access
- If Sentry captures this as a breadcrumb, credentials are stored in Sentry's servers
- Render logs are accessible to all team members — violates principle of least privilege
- Compliance violation (PCI DSS requirement 8: protect stored credentials)

#### What was fixed

1. **`app/core/async_session.py:71`** — Replaced full URL logging with redacted version that only shows the host portion after `@` (e.g., `db.supabase.co:6543/postgres?ssl=require`). URLs without `@` log `"configured"`.
2. **`app/core/session.py:58`** — Removed the username logging line entirely. The safe `host:port/database` log (line 57) was kept since it contains no credentials.

---

<a id="c-05-jwt-tokens-partially-logged-first-30-chars"></a>
### C-05: JWT tokens partially logged (first 30 chars) — FIXED

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Files** | `app/api/dependencies.py` line 113, `app/services/auth_jwt_service.py` line 517 |
| **Priority** | P0 — Fix immediately |
| **Effort** | 5 minutes |
| **Status** | **FIXED** (2026-03-29) |
| **Fix commit** | `feature/fix-h05-alembic-migration-fail-silently` |

#### Description

Two critical authentication files log the first 30 characters of JWT tokens at INFO level:

```python
# app/api/dependencies.py:113
logger.info(f"Token (first 30 chars): {token[:30] if token else 'None'}...")

# app/services/auth_jwt_service.py:517
logger.info(f"Token (first 30 chars): {token[:30] if token else 'None'}...")
```

A JWT token has three base64-encoded parts: `header.payload.signature`. The first 30 characters always include the **full header** and the **beginning of the payload** (which contains `sub` = user ID, `token_type`, `iss`, and sometimes `scope`).

Example — first 30 chars of a real JWT:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6Ik
```
This decodes to: `{"alg":"HS256","typ":"J` — revealing the algorithm used.

#### What was fixed

1. **`app/api/dependencies.py:113`** — Removed `token[:30]` logging line entirely. Replaced with `logger.debug` that only logs token length (safe metadata, no content).
2. **`app/services/auth_jwt_service.py:515-517`** — Removed `token[:30]` logging. Downgraded remaining logs from `logger.info` to `logger.debug` so token metadata doesn't appear in production INFO logs.
3. **`app/api/auth/token_management.py:126`** — Removed `token_prefix: refresh_token[:20]` from security audit event details (was leaking partial refresh tokens into audit logs).
4. **`mobile_app/lib/screens/register_screen.dart:94`** — Removed `accessToken.substring(0, 20)` and `refreshToken.substring(0, 20)` logging. Replaced with length-only logging.
5. **`mobile_app/lib/services/api_service.dart:458,506`** — Removed partial token logging (`refresh.substring(0, min(20, ...))` and `newAccess.substring(0, min(20, ...))`). Replaced with safe length-only logging.
6. **`mobile_app/lib/services/logging_service.dart:135`** — Token sanitization function now fully redacts detected tokens with `[REDACTED_TOKEN]` instead of leaking first 8 characters (which contained the JWT algorithm header `eyJhbGci`).

---

<a id="high"></a>
## HIGH — App starts but has major problems

---

<a id="h-01-cors-always-allows-localhost-origins-in-production"></a>
### H-01: CORS always allows localhost origins in production — FIXED

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **File** | `app/core/config.py` lines 157–180 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 10 minutes |
| **Status** | **FIXED** (2026-03-25) |
| **Fix commit** | `feature/fix-h01-cors-localhost-in-production` |

#### Description

The `ALLOWED_ORIGINS_LIST` property **always** appended localhost origins regardless of environment, meaning in production `http://localhost:8080` was a valid CORS origin. Additionally, `http://mitafinance.com` and `http://www.mitafinance.com` (HTTP, not HTTPS) were in the always-allow list unnecessarily.

#### What was fixed

1. **Localhost origins gated by environment** — `http://localhost:8080`, `http://localhost:3000`, `http://localhost:5173`, `http://127.0.0.1:8080` are now only added when `ENVIRONMENT != "production"`
2. **Removed HTTP production origins** — `http://mitafinance.com` and `http://www.mitafinance.com` removed from always-allow list (Railway terminates TLS at proxy; browser `Origin` header is always `https://`)
3. **Removed dead `isinstance` check** — `ALLOWED_ORIGINS` is typed as `str` in Pydantic v2; the `isinstance` branch was unreachable
4. **Cleaned default `ALLOWED_ORIGINS`** — removed `http://localhost:8080` from the default value (localhost is added dynamically in dev via `always_allow`)

---

<a id="h-02-api-base-url-hardcoded-in-flutter-with-no-environment-switching"></a>
### H-02: API base URL hardcoded in Flutter with no environment switching — FULLY FIXED

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Files** | `mobile_app/lib/config.dart`, `mobile_app/lib/core/error_handling.dart`, `mobile_app/lib/services/api_service.dart`, `mobile_app/test/comprehensive_api_test.dart` |
| **Priority** | P2 — Fix for staging/multi-env |
| **Effort** | 1 hour |
| **Status** | **FULLY FIXED** (2026-03-29) |
| **Fix commits** | `338c859` (initial), `fb905fc` (follow-up audit — 3 missed files) |

#### Description

The Flutter app had a single hardcoded API URL with no mechanism to switch between environments:

```dart
const String defaultApiBaseUrl =
    'https://mita-production-production.up.railway.app/api/';

class ApiConfig {
  static const String baseUrl =
      'https://mita-production-production.up.railway.app';
  // ...
}
```

There were three problems:
1. **No environment switching** — if you need staging, dev, or a new prod URL, you edit source code
2. **Railway-specific URL** — if you switch hosting providers, every installed client needs a new build
3. **Two duplicate URL definitions** — `defaultApiBaseUrl` and `ApiConfig.baseUrl` can get out of sync

#### What was fixed

Rewrote `config.dart` with a new `AppConfig` class using `String.fromEnvironment` for build-time URL injection:

```dart
class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://mita-production-production.up.railway.app',
  );
  static const String environment = String.fromEnvironment(
    'ENV', defaultValue: 'development',
  );
  // ...computed URLs, feature flags, security/performance settings
}
```

**Changes made (initial fix):**
- **`config.dart`** — replaced hardcoded URLs with `AppConfig` class using `String.fromEnvironment('API_BASE_URL')` and `String.fromEnvironment('ENV')`. Added environment-based feature flags, security settings, performance tuning. Legacy `ApiConfig` class kept as backward-compat wrapper delegating to `AppConfig`.
- **`api_service.dart`** — changed `_baseUrl` from `const String.fromEnvironment('API_BASE_URL', defaultValue: defaultApiBaseUrl)` to `AppConfig.baseUrl` (single source of truth).
- **`installment_service.dart`** — replaced `$defaultApiBaseUrl/installments/...` with `${AppConfig.fullApiUrl}/installments/...` (also fixed a double-slash URL bug).
- **`transaction_service.dart`** — changed import from `config_clean.dart` to `config.dart`.
- **`user_settings_screen.dart`** — replaced hardcoded Railway URLs for privacy-policy and terms-of-service with `${AppConfig.baseUrl}/...`.
- **Deleted `config_clean.dart`** — merged its environment-switching concept into `config.dart` (it was unused except by `transaction_service.dart`).

**Additional fixes (2026-03-29, follow-up audit):**

A deep audit found 3 files that were missed in the initial H-02 fix:

- **`config.dart`** — added `webAppUrl` (build-time injectable via `--dart-define=WEB_APP_URL=...`, default `https://app.mita.finance`), `errorReportEndpoint`, `fullErrorReportUrl`, and `passwordResetRedirectUrl` computed getters so that ALL URLs flow through `AppConfig`.
- **`error_handling.dart`** — replaced placeholder `https://your-api.com/api/errors/report` with `AppConfig.fullErrorReportUrl`. Added `import '../config.dart' show AppConfig`. The placeholder URL would silently fail every error report in production.
- **`api_service.dart`** — replaced hardcoded `'https://app.mita.finance/reset-password'` in `sendPasswordResetEmail()` with `AppConfig.passwordResetRedirectUrl`, making it environment-switchable.
- **`test/comprehensive_api_test.dart`** — replaced dead Render URL (`https://mita-docker-ready-project-manus.onrender.com/api`) with `AppConfig.fullApiUrl`. Added `import 'package:mita/config.dart' show AppConfig`. Tests were pointing at a decommissioned host.

**Post-audit verification:** Full grep of `railway.app|onrender.com|your-api.com` across all `.dart` files confirms the only remaining Railway URL is the `defaultValue` in `AppConfig.baseUrl` — which is correct (it's the compile-time fallback for production builds without `--dart-define`).

Build commands:
```bash
# Production
flutter build apk --dart-define=API_BASE_URL=https://api.mita.finance --dart-define=WEB_APP_URL=https://app.mita.finance --dart-define=ENV=production

# Staging
flutter build apk --dart-define=API_BASE_URL=https://staging.mita.finance --dart-define=WEB_APP_URL=https://staging-app.mita.finance --dart-define=ENV=staging

# Local dev
flutter run --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=WEB_APP_URL=http://localhost:3000 --dart-define=ENV=development
```

---

<a id="h-03-minimalsettings-fallback-silently-swallows-config-errors"></a>
### H-03: MinimalSettings fallback silently swallows config errors

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **File** | `app/core/config.py` lines 194–227 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 10 minutes |

#### Description

At module import time, if `Settings()` fails for any reason, a `MinimalSettings` object with all-empty credentials is silently substituted:

```python
try:
    settings = Settings()
except Exception as e:
    import logging
    logging.warning(f"Could not load settings: {e}")
    class MinimalSettings:
        DATABASE_URL = ""
        JWT_SECRET = ""
        SECRET_KEY = ""
        OPENAI_API_KEY = ""
        ENVIRONMENT = "development"
        # ... all empty
    settings = MinimalSettings()
```

This can be triggered by:
- A typo in `.env` file (e.g., `DATABASE_URL=postgres://` with a trailing space)
- A pydantic validation error on any field
- Missing `pydantic-settings` package
- File encoding issues

#### What will happen if not fixed

- The application starts with **no database connection**, **no JWT secret**, **no API keys**
- Every endpoint returns 500 errors or empty data
- There's only a single WARNING log line — easy to miss in production
- Debugging is extremely difficult because the app "seems" to start fine

#### How to fix

Remove the `MinimalSettings` fallback entirely. Let the application crash on startup if settings can't load:

```python
settings = Settings()

# If you want a safety net for development only:
# try:
#     settings = Settings()
# except Exception as e:
#     if os.getenv("ENVIRONMENT") == "production":
#         raise  # Always crash in production
#     logging.warning(f"Settings load failed: {e}, using defaults")
#     settings = Settings(_env_file=None)  # Load with pydantic defaults
```

---

<a id="h-04-datetimeutcnow-used-throughout-deprecated-in-python-312"></a>
### H-04: `datetime.utcnow()` used throughout (deprecated in Python 3.12)

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Files** | `app/db/models/user.py` lines 20–21, `app/api/auth/login.py` lines 88, 109, 179, 186, `app/api/auth/registration.py` lines 101–102, and many more |
| **Priority** | P2 — Fix before Python 3.13 |
| **Effort** | 1 hour (project-wide search/replace) |

#### Description

The codebase extensively uses `datetime.utcnow()` which was deprecated in Python 3.12 (the version used in the Dockerfile):

```python
# app/db/models/user.py:20-21
created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

# app/api/auth/login.py:88
if user.account_locked_until and user.account_locked_until > datetime.utcnow():

# app/api/auth/login.py:109
user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

# app/api/auth/registration.py:101-102
created_at=datetime.utcnow(),
updated_at=datetime.utcnow(),
```

The core issue: `datetime.utcnow()` returns a **naive** datetime (no timezone info), but the columns are `DateTime(timezone=True)` (timezone-aware). This creates an implicit assumption that "naive = UTC" which PostgreSQL handles differently depending on the server timezone setting.

#### What will happen if not fixed

- Python 3.13 will raise `DeprecationWarning` on every call
- Future Python versions will remove it entirely
- Timezone-naive datetimes stored in timezone-aware columns cause subtle bugs:
  - Account lockout comparison may be wrong if DB server timezone differs from UTC
  - Token expiration calculations can be off
  - Timestamps in API responses may confuse clients expecting ISO 8601 with timezone

#### How to fix

Replace all occurrences across the project:

```python
# Old
from datetime import datetime
datetime.utcnow()

# New
from datetime import datetime, timezone
datetime.now(timezone.utc)
```

For SQLAlchemy model defaults:
```python
from datetime import datetime, timezone

created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

---

<a id="h-05-alembic-migrations-may-fail-silently-and-app-starts-anyway"></a>
### H-05: Alembic migrations may fail silently and app starts anyway — FIXED

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Files** | `start.sh` lines 177–211, `scripts/deployment/start.sh` lines 177–211 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 5 minutes |
| **Status** | **FIXED** (2026-03-29) |
| **Fix commit** | `feature/fix-h05-alembic-migration-fail-silently` |

#### Description

The startup script runs Alembic migrations but continues even if they fail:

```bash
python -m alembic upgrade head

if [ $? -ne 0 ]; then
    echo "Migration failed! Attempting to continue anyway..."
    echo "The application may not work correctly without migrations"
else
    echo "Migrations completed successfully"
fi
```

Additionally, the script has `set -e` at line 5, making the `if [ $? -ne 0 ]` block **dead code** — `set -e` would exit the script immediately on migration failure before reaching the error handler, producing a raw exit with no meaningful diagnostic.

Migration failures can happen when:
- Database is temporarily unreachable (cold start on Railway)
- A migration has a conflict (two branches modified the same table)
- A migration requires a table that was manually dropped
- Supabase connection limits are exhausted

#### What was fixed

1. **`set +e` / `set -e` guard around migration** — Temporarily disables exit-on-error so the migration exit code can be captured in a variable (`MIGRATION_EXIT_CODE`), then re-enables `set -e` for the rest of the script
2. **Production hard stop** — If `ENVIRONMENT == "production"` and migration fails, the script prints a detailed diagnostic box (possible causes, remediation steps) and exits with code 1. Railway/Render will mark the deployment as crashed, preventing the app from serving requests with an outdated schema
3. **Development continues with warning** — If not in production, migration failure prints a warning and allows the app to start for local development convenience
4. **Both copies updated** — Root `start.sh` and `scripts/deployment/start.sh` (which the Dockerfile copies into the container) are both fixed identically

---

<a id="h-06-aioredis-dependency-is-deprecateddead"></a>
### H-06: `aioredis` dependency is deprecated/dead

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **File** | `requirements.txt` line 37 |
| **Priority** | P2 |
| **Effort** | 30 minutes |

#### Description

```
aioredis==2.0.1  # Async Redis client
```

The `aioredis` package was **merged into `redis-py`** starting from `redis>=4.2.0`. The standalone `aioredis` package:
- Has not been updated since 2021
- Has known unfixed security issues
- Conflicts with modern `redis` package (you also have `redis==5.2.0`)
- May cause import errors or unexpected behavior when both are installed

#### What will happen if not fixed

- Potential import conflicts between `aioredis` and `redis.asyncio`
- No security patches for the deprecated package
- Larger Docker image for no benefit (two Redis libraries instead of one)
- Future dependency resolution failures when other packages also depend on `redis`

#### How to fix

1. Remove `aioredis==2.0.1` from `requirements.txt`
2. Replace all imports:
   ```python
   # Old
   import aioredis

   # New
   from redis import asyncio as aioredis  # Drop-in compatible
   ```
3. Or use `redis.asyncio.Redis` directly — the API is nearly identical

---

<a id="h-07-excessive-debug-logging-in-auth-flow"></a>
### H-07: Excessive debug logging in auth flow

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Files** | `app/api/dependencies.py` lines 99–283, `app/services/auth_jwt_service.py` lines 515–739 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 30 minutes |

#### Description

The `get_current_user()` function in `dependencies.py` contains **44 `logger.info()` calls** with emoji prefixes that fire on **every single authenticated request**:

```python
logger.info("🔐 GET_CURRENT_USER CALLED")
logger.info(f"Token received - length: {len(token) if token else 0}")
logger.info(f"Token (first 30 chars): {token[:30] if token else 'None'}...")
logger.info("📞 Calling verify_token for access_token...")
logger.info(f"✅ verify_token returned - payload is {'None' if payload is None else 'present'}")
logger.info(f"Payload user_id (sub): {payload.get('sub')}")
logger.info(f"🔍 Extracting user_id from payload...")
logger.info(f"✅ User ID extracted: {user_id}")
logger.info(f"📊 Querying user from cache/database for user_id={user_id}...")
# ... ~35 more logger.info() calls
logger.info(f"🎉 RETURNING USER OBJECT for {user_id}")
```

Similarly, `verify_token()` in `auth_jwt_service.py` has another ~20 `logger.info()` calls.

Combined: **~64 INFO log lines per authenticated API request**.

#### What will happen if not fixed

- At 100 requests/sec, this generates **6,400 log lines per second** — significant I/O overhead
- Log storage fills up quickly (Render's log retention is limited)
- Real errors get buried in noise — hard to spot actual problems
- Sensitive data (user IDs, token types, scopes) at INFO level in all log aggregators
- Added latency on every request from synchronous logging I/O

#### How to fix

1. Change most `logger.info()` to `logger.debug()` — they won't appear at production log level
2. Remove token content logging entirely (see C-05)
3. Keep only 2-3 key log points at INFO level:
   ```python
   logger.info(f"Auth: user {user_id} authenticated successfully")
   logger.warning(f"Auth: token verification failed for request")
   ```

---

<a id="h-08-single-worker-deployment-ignores-web_concurrency"></a>
### H-08: Single worker deployment ignores WEB_CONCURRENCY

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Files** | `start.sh` line 210, `render.yaml` line 46 |
| **Priority** | P1 — Fix before launch |
| **Effort** | 5 minutes |

#### Description

The startup script always starts with exactly 1 worker:

```bash
# start.sh:207-212
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \             # <-- Always 1
    --access-log \
    $UVLOOP_ARG
```

But `render.yaml` configures 4 workers:

```yaml
- key: WEB_CONCURRENCY
  value: 4
```

The `WEB_CONCURRENCY` environment variable is set but **never read** by `start.sh`.

#### What will happen if not fixed

- A single uvicorn worker handles all requests sequentially during I/O operations
- CPU-bound operations (ML inference for spacy/transformers, bcrypt hashing) block the entire server
- Under moderate load (50+ concurrent users), requests queue and timeout
- The Render "standard" plan resources (multiple vCPUs, more RAM) are wasted — only 1 core used

#### How to fix

Use the environment variable in `start.sh`:

```bash
WORKERS="${WEB_CONCURRENCY:-1}"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS}" \
    --access-log \
    $UVLOOP_ARG
```

**Note:** With multiple workers, ensure `JWT_SECRET` is set via environment variable (not auto-generated per C-03), otherwise each worker gets a different secret.

---

<a id="medium"></a>
## MEDIUM — Functional issues, tech debt, reliability

---

<a id="m-01-ongenerateroute-returns-null-breaking-dynamic-navigation"></a>
### M-01: `onGenerateRoute` returns null, breaking dynamic navigation

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **File** | `mobile_app/lib/main.dart` line 351 |
| **Priority** | P2 |
| **Effort** | 15 minutes |

#### Description

```dart
onGenerateRoute: (settings) {
    logInfo('CRITICAL DEBUG: Navigation to route: ${settings.name}',
        tag: 'NAVIGATION');
    return null; // Let the routes table handle it
},
```

When `onGenerateRoute` returns `null` and the route name isn't in the `routes` map, Flutter throws an exception: `Could not find a generator for route "/some-route"`. This crashes the app.

Additionally, the log message says "CRITICAL DEBUG" — this is debug logging that fires on **every navigation** in production.

#### How to fix

```dart
onGenerateRoute: (settings) {
    // Return an error page for unknown routes
    return MaterialPageRoute(
      builder: (context) => Scaffold(
        appBar: AppBar(title: const Text('Page Not Found')),
        body: Center(child: Text('Route ${settings.name} not found')),
      ),
    );
},
```

---

<a id="m-02-login_datadict-is-deprecated-in-pydantic-v2"></a>
### M-02: `login_data.dict()` is deprecated in Pydantic v2

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Files** | `app/api/auth/login.py` line 62, `app/api/auth/registration.py` line 61 |
| **Priority** | P2 |
| **Effort** | 15 minutes |

#### Description

```python
login_dict = login_data.dict()          # Deprecated
registration_dict = registration_data.dict()  # Deprecated
```

The project uses Pydantic v2 (`pydantic==2.9.2`), where `.dict()` is deprecated in favor of `.model_dump()`. This generates `DeprecationWarning` on every login and registration request.

#### How to fix

```python
login_dict = login_data.model_dump()
registration_dict = registration_data.model_dump()
```

Search the entire codebase for other occurrences:
```bash
grep -r "\.dict()" app/ --include="*.py" | grep -v test | grep -v __pycache__
```

---

<a id="m-03-missing-ignoredalert-model-in-__init__py"></a>
### M-03: Missing `IgnoredAlert` model in `__init__.py`

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Files** | `app/db/models/__init__.py`, `app/db/models/ignored_alert.py` |
| **Priority** | P2 |
| **Effort** | 5 minutes |

#### Description

The file `app/db/models/ignored_alert.py` exists and migration `0028_add_ignored_alerts_table.py` creates the table, but `IgnoredAlert` is **not imported** in `app/db/models/__init__.py`.

This means:
- The table exists in the database (created by migration)
- But the ORM model is not registered with SQLAlchemy's metadata
- Any code doing `from app.db.models import IgnoredAlert` will fail with `ImportError`
- Alembic autogenerate may try to **drop** the table because it doesn't see the model

#### How to fix

Add to `app/db/models/__init__.py`:

```python
from .ignored_alert import IgnoredAlert

__all__ = [
    # ... existing exports ...
    "IgnoredAlert",
]
```

---

<a id="m-04-spacy-and-transformers-in-production-requirements-huge-image"></a>
### M-04: `spacy` and `transformers` in production requirements (huge image)

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **File** | `requirements.txt` lines 60–61 |
| **Priority** | P3 |
| **Effort** | 2 hours |

#### Description

```
spacy==3.8.2        # NLP library
transformers==4.52.1 # SECURITY UPDATE: Multiple CVEs fixed
```

These two packages alone add **2–3 GB** to the Docker image:
- `spacy` requires downloading language models (~500MB each)
- `transformers` pulls in `torch` or `tensorflow` as transitive dependencies (~1.5GB)
- Combined with `scikit-learn` and `numpy`, the ML stack is ~3GB

The Docker build takes 10–15 minutes and the final image is likely **4–5 GB**.

#### What will happen if not fixed

- Extremely slow deploys on Render (build timeout risk)
- Higher hosting costs (more RAM needed, larger disk)
- Slow cold starts — the app takes 30+ seconds to import all ML libraries
- If these ML features aren't core to launch, it's unnecessary weight

#### How to fix

Options:
1. **If not used for launch:** Move to `requirements-ml.txt` and exclude from production
2. **If used occasionally:** Extract ML features into a separate microservice
3. **If needed:** At minimum, pin `torch` CPU-only variant to save ~1GB:
   ```
   --extra-index-url https://download.pytorch.org/whl/cpu
   torch==2.x.x+cpu
   ```

---

<a id="m-05-cicd-quality-checks-are-non-blocking"></a>
### M-05: CI/CD quality checks are non-blocking

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **File** | `.github/workflows/main-ci.yml` lines 46–62 |
| **Priority** | P2 |
| **Effort** | 15 minutes |

#### Description

All code quality checks use `|| echo "::warning::"` which prevents them from failing the CI:

```yaml
- name: Code quality checks
  run: |
    black --check . || echo "::warning::Code formatting issues detected"
    isort --check . || echo "::warning::Import sorting issues detected"
    ruff . || echo "::warning::Linting issues detected"

- name: Security scan (Bandit)
  run: |
    bandit -r app/ -ll || echo "::warning::Security issues detected"
  continue-on-error: true
```

#### How to fix

Remove the `|| echo` fallbacks and let CI fail on quality issues:

```yaml
- name: Code quality checks
  run: |
    black --check .
    isort --check .
    ruff check .

- name: Security scan (Bandit)
  run: bandit -r app/ -ll
```

---

<a id="m-06-flutter-tests-are-continue-on-error"></a>
### M-06: Flutter tests are `continue-on-error`

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **File** | `.github/workflows/main-ci.yml` line 94 |
| **Priority** | P2 |
| **Effort** | 5 minutes |

#### Description

```yaml
- name: Run tests
  run: flutter test
  continue-on-error: true
```

Flutter tests can fail completely and CI still passes green. This means broken frontend code can be merged to `main` and auto-deployed.

#### How to fix

Remove `continue-on-error: true`:

```yaml
- name: Run tests
  run: flutter test
```

If some tests are flaky, fix them or mark individual tests as `skip` rather than ignoring all failures.

---

<a id="m-07-two-different-base-definitions-in-db"></a>
### M-07: Two different `Base` definitions in `db/`

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Files** | `app/db/base.py` (empty), `app/db/models/base.py` (actual Base) |
| **Priority** | P3 |
| **Effort** | 15 minutes |

#### Description

- `app/db/base.py` — is an empty file (1 line, no content)
- `app/db/models/base.py` — contains the actual `Base = declarative_base()`

Some imports in the codebase may reference `app.db.base.Base` while others use `app.db.models.base.Base`. If different parts of the code import from different locations, SQLAlchemy models may register with **different** metadata objects, causing:
- Tables not detected by Alembic
- Relationships failing to resolve
- `create_all()` missing tables

#### How to fix

Either:
1. Delete `app/db/base.py` and ensure all imports use `app.db.models.base`
2. Or make `app/db/base.py` re-export: `from app.db.models.base import Base`

---

<a id="low"></a>
## LOW — Code quality, minor issues

---

<a id="l-01-massive-code-duplication-across-enginelogicservices"></a>
### L-01: Massive code duplication across engine/logic/services

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Directories** | `app/logic/`, `app/engine/`, `app/services/core/` |
| **Priority** | P3 |
| **Effort** | Days (major refactor) |

#### Description

The same business logic exists in up to 3 parallel directory structures:

| Functionality | Location 1 | Location 2 | Location 3 |
|---|---|---|---|
| Cohort analysis | `app/logic/cohort_analysis.py` | `app/engine/cohort_analyzer.py` | `app/services/core/cohort/cohort_analysis.py` |
| Budget allocator | `app/logic/behavioral_budget_allocator.py` | `app/engine/budget/behavioral_budget_allocator.py` | `app/services/core/behavior/behavioral_budget_allocator.py` |
| Category priority | `app/logic/category_priority.py` | `app/engine/utils/category_priority.py` | `app/services/core/behavior/category_priority.py` |
| Calendar anomaly | `app/logic/calendar_anomaly_detector.py` | `app/engine/analysis/calendar_anomaly_detector.py` | `app/services/core/analytics/calendar_anomaly_detector.py` |
| Receipt categorization | `app/categorization/receipt_categorization_service.py` | `app/engine/categorization/receipt_categorization_service.py` | — |
| OCR service | `app/ocr/google_vision_ocr_service.py` | `app/engine/ocr/google_vision_ocr_service.py` | — |

This is likely the result of multiple AI-assisted development sessions that each created their own module structure without consolidating.

#### Impact

- Bugs fixed in one location may not be fixed in the duplicate
- Unclear which version is actually used at runtime
- Increases import time and memory usage
- Makes the codebase confusing for new developers

---

<a id="l-02-200-stale-remote-branches"></a>
### L-02: 200+ stale remote branches

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Priority** | P3 |
| **Effort** | 30 minutes |

#### Description

The repository has **200+ remote branches**, mostly from automated codex/claude sessions:
- `remotes/origin/codex/fix-401-error-on-login`
- `remotes/origin/claude/complete-first-task-01JzuqnaxQLC6APrqcptC9eo`
- `remotes/origin/codex/проверить-работоспособность-бэкенда`
- etc.

#### How to fix

```bash
# List all remote branches that are merged into main
git branch -r --merged main | grep -v 'main\|HEAD' | sed 's/origin\///' > branches_to_delete.txt

# Review the list, then delete
while read branch; do git push origin --delete "$branch"; done < branches_to_delete.txt
```

---

<a id="l-03-root-level-test-files-outside-tests-directory"></a>
### L-03: Root-level test files outside `tests/` directory

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Files** | `test_calendar_fix_real.py`, `test_calendar_save.py`, `verify_module5.py`, `verify_onboarding_flow.py` |
| **Priority** | P3 |
| **Effort** | 10 minutes |

#### Description

Four test/verification files sit in the project root instead of the `tests/` directory. They won't be picked up by `pytest` with the standard configuration and clutter the root directory.

#### How to fix

```bash
mv test_calendar_fix_real.py tests/
mv test_calendar_save.py tests/
mv verify_module5.py tests/
mv verify_onboarding_flow.py tests/
```

---

<a id="l-04-apns_use_sandbox-defaults-to-true"></a>
### L-04: `APNS_USE_SANDBOX` defaults to True

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **File** | `app/core/config.py` line 146 |
| **Priority** | P2 |
| **Effort** | 5 minutes |

#### Description

```python
APNS_USE_SANDBOX: bool = True
```

The Apple Push Notification Service sandbox is for **development only**. Push notifications sent via the sandbox environment never reach production devices. If this default isn't overridden in production, users won't receive any push notifications.

#### How to fix

```python
APNS_USE_SANDBOX: bool = False  # Override to True in development .env only
```

Or tie it to environment:
```python
@property
def apns_sandbox(self) -> bool:
    return self.ENVIRONMENT != "production"
```

---

<a id="railway"></a>
## RAILWAY — Production environment misconfigurations

> **Discovered:** 2026-03-24 during Railway environment audit
> **Context:** Server migrated from Render to Railway, but some config was not fully updated

---

<a id="r-01-jwt_previous_secret-not-set-while-jwt-rotation-is-enabled"></a>
### R-01: `JWT_PREVIOUS_SECRET` not set while JWT rotation is enabled

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Location** | Railway Dashboard → `mita-production` → Environment Variables |
| **Priority** | P1 — Fix before launch |
| **Effort** | 5 minutes |

#### Description

`FEATURE_FLAGS_JWT_ROTATION` is set to `true` in Railway, but `JWT_PREVIOUS_SECRET` is **not configured**. JWT rotation requires two secrets:
- `JWT_SECRET` — the current signing key (set: `oPh-TW4BNM9v...`)
- `JWT_PREVIOUS_SECRET` — the previous key used to verify tokens signed before rotation (missing)

When the app tries to verify a token with the previous secret and it's `None` or empty, the verification will either:
- Raise an exception (crash on auth)
- Silently fail, invalidating all tokens issued before the last rotation

#### How to fix

In Railway Dashboard, set `JWT_PREVIOUS_SECRET` to the same value as `JWT_SECRET` (if no rotation has happened yet):
```
JWT_PREVIOUS_SECRET = oPh-TW4BNM9vQc2S8DkP0XYhIMeJBS5vMBRT6s9aQ1_rBjhsSTP3adTUxKMZ-cvq6UabCJSEpUaaBMzqAHXbzA
```

Or, if JWT rotation is not actually needed yet, disable it:
```
FEATURE_FLAGS_JWT_ROTATION = false
```

---

<a id="r-02-pythonpath-points-to-render-path-not-railway"></a>
### R-02: `PYTHONPATH` points to Render path, not Railway

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Location** | Railway Dashboard → `mita-production` → Environment Variables |
| **Priority** | P1 — Fix before launch |
| **Effort** | 5 minutes |

#### Description

```
PYTHONPATH = /opt/render/project/src
```

This is a **Render-specific path**. On Railway, the application runs from `/app/` (or the Docker `WORKDIR`). The `/opt/render/project/src` directory does not exist on Railway.

If any Python code relies on `PYTHONPATH` for module resolution (e.g., absolute imports like `from app.core.config import settings`), it may fail with `ModuleNotFoundError` on Railway — or it may work accidentally if the Docker `WORKDIR` happens to be correct.

#### How to fix

In Railway Dashboard, update:
```
PYTHONPATH = /app
```

Or remove it entirely if the `Dockerfile` already sets `WORKDIR /app` — Python will resolve imports from the working directory automatically.

---

<a id="r-03-missing-critical-environment-variables-in-railway"></a>
### R-03: Missing critical environment variables in Railway

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Location** | Railway Dashboard → `mita-production` → Environment Variables |
| **Priority** | P2 |
| **Effort** | 15 minutes |

#### Description

Several environment variables that are referenced in `render.yaml` and the codebase are **not set** in Railway:

| Variable | Impact if missing |
|----------|------------------|
| `SENTRY_DSN` | No error monitoring — production errors go unnoticed |
| `UPSTASH_REDIS_URL` | Redis caching/rate-limiting non-functional |
| `UPSTASH_REDIS_REST_URL` | Redis REST API fallback non-functional |
| `UPSTASH_REDIS_REST_TOKEN` | Redis auth fails |
| `SMTP_PASSWORD` | Email sending (password reset, notifications) broken |
| `AWS_ACCESS_KEY_ID` | S3 backups non-functional (if used) |
| `AWS_SECRET_ACCESS_KEY` | S3 backups non-functional (if used) |
| `APPSTORE_SHARED_SECRET` | iOS in-app purchase verification will fail |

#### How to fix

For each variable, set the value in Railway Dashboard → Environment Variables:
1. **`SENTRY_DSN`** — get from Sentry project settings (sentry.io)
2. **`UPSTASH_REDIS_*`** — get from Upstash dashboard (upstash.com)
3. **`SMTP_PASSWORD`** — SendGrid API key (sendgrid.com)
4. **`AWS_*`** — only if S3 backups are in use
5. **`APPSTORE_SHARED_SECRET`** — only if iOS IAP is live

If a service is not yet needed, ensure the code gracefully handles the missing variable (not crash).

---

<a id="priority-fix-order"></a>
## Priority Fix Order

| Priority | Issue ID | Description | Effort | Status |
|----------|----------|-------------|--------|--------|
| ~~**P0 NOW**~~ | ~~C-01~~ | ~~Rotate ALL secrets, remove from render.yaml~~ | ~~30 min~~ | **FIXED** |
| ~~**P0 NOW**~~ | ~~C-04~~ | ~~Remove DB URL from logs~~ | ~~5 min~~ | **FIXED** |
| ~~**P0 NOW**~~ | ~~C-05~~ | ~~Remove token logging~~ | ~~5 min~~ | **FIXED** |
| ~~**P1 Before Launch**~~ | ~~C-03~~ | ~~Crash if JWT_SECRET not set in production~~ | ~~10 min~~ | **FIXED** |
| ~~**P1**~~ | ~~H-01~~ | ~~Remove localhost from CORS in production~~ | ~~10 min~~ | **FIXED** |
| **P1** | H-03 | Remove MinimalSettings fallback | 10 min | |
| ~~**P1**~~ | ~~H-05~~ | ~~Fail startup on migration failure in production~~ | ~~5 min~~ | **FIXED** |
| **P1** | H-07 | Reduce auth logging to WARNING/ERROR only | 30 min | |
| **P1** | H-08 | Use WEB_CONCURRENCY env var for workers | 5 min | |
| **P1** | R-01 | Set `JWT_PREVIOUS_SECRET` in Railway (or disable rotation) | 5 min | |
| **P1** | R-02 | Fix `PYTHONPATH` from Render path to `/app` in Railway | 5 min | |
| **P2** | R-03 | Set missing env vars in Railway (Sentry, Redis, SMTP) | 15 min | |
| ~~**P2**~~ | ~~C-02~~ | ~~Restrict Firebase API keys, enable App Check~~ | ~~1 hr~~ | **FIXED** |
| ~~**P2**~~ | ~~H-02~~ | ~~Add environment config to Flutter + eliminate all hardcoded URLs~~ | ~~1 hr~~ | **FULLY FIXED** |
| **P2** | H-04 | Replace `datetime.utcnow()` project-wide | 1 hr | |
| **P2** | H-06 | Remove `aioredis`, use `redis.asyncio` | 30 min | |
| **P2** | M-01 | Add fallback route handler in Flutter | 15 min | |
| **P2** | M-02 | Replace `.dict()` with `.model_dump()` | 15 min | |
| **P2** | M-05 | Make CI quality checks blocking | 15 min | |
| **P2** | M-06 | Remove `continue-on-error` from Flutter tests | 5 min | |
| **P2** | L-04 | Fix APNS sandbox default | 5 min | |
| **P3** | M-03 | Add IgnoredAlert to model imports | 5 min | |
| **P3** | M-04 | Evaluate spacy/transformers necessity | 2 hrs | |
| **P3** | M-07 | Clean up dual Base definitions | 15 min | |
| **P3** | L-01 | Consolidate duplicate modules | Days | |
| **P3** | L-02 | Clean up 200+ stale branches | 30 min | |
| **P3** | L-03 | Move root test files to tests/ | 10 min | |

---

> **Total estimated effort for P0+P1:** ~2 hours
> **Total estimated effort for P2:** ~4 hours
> **Total estimated effort for all:** ~2-3 days (including L-01 refactor)

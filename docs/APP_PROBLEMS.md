# App Production Readiness Problems

> Audit date: 2026-03-23
> Last updated: 2026-03-23
> Tool: Bulletproof Deep Research (3 parallel agents)
> Status: **NOT FULLY READY** — critical issues block production readiness

---

## 🔴 CRITICAL — Block Production Readiness

### ~~1. `ocr_jobs` table missing in DB — no migration for OCRJob model~~ ✅ FIXED 2026-03-23
- **Migration created:** `alembic/versions/0029_add_ocr_jobs_table.py`
- All 18 columns, 3 indexes (`job_id`, `user_id+created_at`, `status`), unique constraint on `job_id`, FK with `ondelete=CASCADE`

---

### ~~2. `user_preferences` table missing in DB — no migration for UserPreference model~~ ✅ FIXED 2026-03-23
- **Migration created:** `alembic/versions/0030_add_user_preferences_table.py`
- All 16 columns, unique constraint on `user_id`, index `ix_user_preferences_user_id`
- Server defaults match model defaults (booleans, `notification_threshold`, `budget_mode`)

---

### ~~3. `app/api/health/routes.py` exists but is NOT registered in `main.py`~~ ✅ FIXED 2026-03-23
- **Fix applied:** Added `from app.api.health.routes import router as health_router` at `app/main.py:61`
- **Fix applied:** Added `app.include_router(health_router, tags=["Health"])` as a **public** route (no auth deps) at `app/main.py:785–786`
- `GET /health`, `GET /health/detailed`, `GET /health/circuit-breakers` now publicly accessible
- Railway health checks can reach `/health` → deployment shows "healthy"

---

## 🟡 HIGH — Degrade Production Quality

### ~~4. Python version mismatch between nixpacks.toml and Dockerfile~~ ✅ FIXED 2026-03-23
- **All Python versions aligned to 3.12** across every deployment config:
  - `nixpacks.toml`: `python39` → `python312` (Railway production)
  - `Dockerfile`: `python:3.10-slim` → `python:3.12-slim` (both builder + production stages)
  - `docker/Dockerfile.clean`: `python:3.11-slim` → `python:3.12-slim` (multi-env base)
  - `mobile_app/scripts/Dockerfile.subscription-manager`: `python:3.11-slim` → `python:3.12-slim` (builder + production + site-packages path)
  - `.github/workflows/main-ci.yml`: `python-version: "3.10"` → `"3.12"` (CI pipeline)
- Python 3.12 chosen over 3.10 for long-term support (EOL Oct 2028 vs Oct 2026)

---

### ~~4b. `pkg_resources` crash — regression from Python 3.12 upgrade~~ ✅ FIXED 2026-03-23
- **Root cause:** `python:3.12-slim` does not bundle `setuptools` (unlike 3.10-slim), so `import pkg_resources` in `dependency_validator.py:12` crashes at startup (`ModuleNotFoundError`)
- **Fix applied:** Replaced all `pkg_resources` usage with `importlib.metadata` (Python stdlib since 3.8) — zero external dependencies, faster than `pkg_resources`
- **Files changed:** `app/core/dependency_validator.py` — 3 edits (import + 2 call sites)

---

### ~~5. `uvloop` used in `start.sh` but missing from `requirements.txt`~~ ✅ FIXED 2026-03-23
- **Dependency added:** `uvloop>=0.21.0; sys_platform != "win32"` in `requirements.txt` (line 9)
- **Fallback added:** `start.sh` and `scripts/deployment/start.sh` now detect uvloop at runtime — uses `--loop uvloop` if available, falls back to default asyncio loop with a warning if not
- Platform marker ensures Windows dev machines are unaffected

---

### ~~6. `ACCESS_TOKEN_EXPIRE_MINUTES` config is silently overridden~~ ✅ FIXED 2026-03-23
- **Root cause:** `app/core/config.py` had a `@field_validator` that silently clamped any value < 120 to 120, while `render.yaml` set 30 — config was a lie
- **Fix applied:** Removed the forced minimum from the validator — configured values are now respected as-is. Validator only handles empty/None (defaults to 120) and rejects non-positive values
- **Fix applied:** Updated `render.yaml` from `ACCESS_TOKEN_EXPIRE_MINUTES: 30` → `120` to reflect the actual desired production value (required for onboarding completion)
- **Files changed:** `app/core/config.py` (validator rewrite), `render.yaml` (value 30→120)

---

### ~~7. Firebase initialization fails silently — not reflected in `/health`~~ ✅ FIXED 2026-03-23
- **Root cause:** Firebase init at module level caught all exceptions with `print()` only — no status variable, no health visibility
- **Fix applied:** Added `_firebase_initialized` flag and `_firebase_init_error` at module level (`app/main.py:83-84`)
- **Fix applied:** `/health` endpoint now includes `firebase` status (`"initialized"` / `"unavailable"`), `firebase_error` (when failed), and `config.firebase_configured`
- **Fix applied:** Overall health degrades to `"degraded"` when Firebase is unavailable (not `"unhealthy"` — core features still work)
- **Fix applied:** Replaced `print()` with `logging.info()` / `logging.warning()` for structured log output
- **Files changed:** `app/main.py` — Firebase init block (lines 82–108) + `/health` endpoint (lines 431–493)

---

### ~~8. Database initialization timeout too aggressive (5 seconds)~~ ✅ FIXED 2026-03-23
- **Root cause:** `asyncio.wait_for(init_database(), timeout=5.0)` at startup — on Railway cold starts (DNS resolution + connection pool warming + system catalog queries), 5s is insufficient
- **Fix applied:** Increased timeout from 5.0s → 15.0s at `app/main.py:985`
- Consistent with Docker HEALTHCHECK `--start-period=30s` (init completes well within grace period)
- Consistent with pool_timeout=30s (half the pool timeout — fails fast if real issue, generous for cold starts)
- Warning message now includes timeout value for easier debugging

---

### ~~9. Redis not in critical environment variable checks~~ ✅ FIXED 2026-03-23
- **Root cause:** `REDIS_URL` was listed in `optional_vars` — app started without Redis in production, causing rate limiting to degrade to per-process in-memory (5x higher effective limits), task queue to silently drop jobs, and JWT revocation to stop working
- **Fix applied:** Added dedicated Redis configuration check block in `start.sh` (lines 81–125) with OR-logic across all 3 supported providers: `REDIS_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_URL`
- **Production behavior:** Hard failure (`exit 1`) with descriptive error listing all provider options and degradation consequences
- **Development behavior:** Warning only — in-memory fallbacks still used for local dev
- **Bonus:** Warns if `UPSTASH_REDIS_REST_URL` is set without `UPSTASH_REDIS_REST_TOKEN` (authentication will fail)
- **Files changed:** `start.sh`, `scripts/deployment/start.sh` — Redis check block added, `REDIS_URL` removed from `optional_vars`

---

### ~~10. Multiple `Base = declarative_base()` definitions~~ ✅ FIXED 2026-03-23
- **Root cause:** 4 separate `Base = declarative_base()` — only `app/db/models/base.py` had models registered; `async_session.py` used its own empty Base for `create_all()`
- **Fix applied:** Removed 3 duplicate Base definitions, kept canonical `app/db/models/base.py`
  - `app/core/async_session.py`: Replaced local `Base = declarative_base()` with `from app.db.models.base import Base` — `init_database()` now uses the correct Base with all 25+ models registered
  - `app/db/__init__.py`: Removed duplicate `Base = declarative_base()` (was unused)
  - `app/db/base.py`: Removed duplicate `Base = declarative_base()` (was unused)
- **Impact verified:** Zero circular imports, zero broken consumers, Alembic unaffected (already used correct Base)

---

## 🟠 MEDIUM — Code Quality / Observability

### ~~11. 15+ `print()` statements used instead of `logger`~~ ✅ FIXED 2026-03-23
- **Fix applied:** Replaced all 24 production `print()` calls with proper `logging` across 9 files:
  - `app/legacy_tasks.py`: 4× `print()` → `logger.info()` (task enqueue confirmations)
  - `app/agent/gpt_agent_service.py`: 1× `print()` → `logger.error()` (OpenAI API errors)
  - `app/core/dependency_validator.py`: 6× `print()` → `logger.critical()` (startup validation failures)
  - `app/engine/behavior/adaptive_behavior_agent.py`: 1× `print()` → `logger.debug()` (policy assignment)
  - `app/engine/onboarding_engine_final.py`: 1× `print()` → `logger.error()` (profile finalization errors)
  - `app/logic/adaptive_behavior_agent.py`: 1× `print()` → `logger.debug()` (policy assignment)
  - `app/services/core/engine/cron_task_ai_advice.py`: 1× `print()` → `logger.error()` (batch failures)
  - `app/services/core/engine/cron_task_budget_redistribution.py`: 4× `print()` → `logger.info()` / `logger.error()` (redistribution status + failures)
  - `app/services/core/engine/cron_task_reminders.py`: 1× `print()` → `logger.error()` (email failures)
- **Pattern used:** `logger = logging.getLogger(__name__)` + lazy `%s` formatting (Sentry-compatible grouping, no f-string overhead)
- **Skipped:** `print()` in `if __name__ == "__main__":` blocks (5 files) — standard Python CLI convention, never executes in production

---

### 12. `SENTRY_DSN` not marked as critical — error monitoring silently disabled
- **File:** `start.sh`
- **Effect:** If `SENTRY_DSN` is not set, app starts without error tracking — no alerts when things break
- **Fix:** Either make `SENTRY_DSN` critical in `start.sh` or add a prominent startup warning

---

### 13. Health check internal timeout (1s) mismatches Dockerfile timeout (10s)
- **`/health` endpoint:** `asyncio.wait_for(check_database_health(), timeout=1.0)`
- **Dockerfile HEALTHCHECK:** `--timeout=10s`
- **Effect:** Race conditions during cold start — Docker sees success while app internally marks DB as timed out
- **Fix:** Align timeouts (increase health endpoint DB check to 5s)

---

### 14. `dependency_validator.py` calls `sys.exit(1)` on import failure
- **File:** `app/core/dependency_validator.py:446–461`
- **Called at:** `app/main.py:282–283` (during import, before any endpoint is ready)
- **Effect:** Container exits silently with code 1; Railway sees failed deployment with no visible logs
- **Fix:** Convert to log + raise RuntimeError instead of sys.exit

---

## 🔵 LOW — Best Practices

### 15. No `/ready` readiness endpoint (only `/health`)
- **Standard:** `/health` = is service running; `/ready` = is service ready to serve traffic
- **Effect:** Railway/K8s can't distinguish "started" from "ready"
- **Fix:** Add `GET /ready` endpoint that checks DB, Redis, and Firebase status

---

### 16. TODO: Push notification in streak wins cron task
- **File:** `app/services/core/engine/cron_task_streak_wins.py:41`
- **Effect:** Streak win feature is incomplete — push notification not sent
- **Fix:** Implement push notification via `NotificationService`

---

## Priority Fix Order

| Priority | Issue | Effort |
|----------|-------|--------|
| ~~1~~ | ~~Register `health/routes.py` in `main.py`~~ | ~~5 min~~ ✅ Done |
| ~~2~~ | ~~Create migration for `OCRJob`~~ | ~~15 min~~ ✅ Done |
| ~~2~~ | ~~Create migration for `UserPreference`~~ | ~~15 min~~ ✅ Done |
| ~~4~~ | ~~Fix Python version mismatch (all configs → 3.12)~~ | ~~10 min~~ ✅ Done |
| ~~5~~ | ~~Add `uvloop` to `requirements.txt`~~ | ~~2 min~~ ✅ Done |
| ~~6~~ | ~~Fix duplicate `Base` definitions~~ | ~~30 min~~ ✅ Done |
| ~~7~~ | ~~Add Firebase status to `/health`~~ | ~~10 min~~ ✅ Done |
| ~~8~~ | ~~Increase DB init timeout to 15s~~ | ~~5 min~~ ✅ Done |
| ~~9~~ | ~~Fix `ACCESS_TOKEN_EXPIRE_MINUTES` config~~ | ~~10 min~~ ✅ Done |
| ~~10~~ | ~~Add Redis to critical env var checks~~ | ~~15 min~~ ✅ Done |
| ~~11~~ | ~~Replace `print()` with `logger` everywhere~~ | ~~1 hr~~ ✅ Done |

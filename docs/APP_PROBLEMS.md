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

### 6. `ACCESS_TOKEN_EXPIRE_MINUTES` config is silently overridden
- **render.yaml:** `ACCESS_TOKEN_EXPIRE_MINUTES: 30`
- **`app/core/config.py`:** Forces minimum of 120 minutes regardless of config
- **Effect:** Tokens expire in 120 min, not 30 — security regression, config is ignored
- **Fix:** Either remove the forced minimum or update render.yaml to 120+

---

### 7. Firebase initialization fails silently — not reflected in `/health`
- **File:** `app/main.py` lines 82–101
- **Effect:** Push notifications silently disabled in production; `/health` shows no warning
- **Fix:** Add Firebase status to the `/health` response payload

---

### 8. Database initialization timeout too aggressive (5 seconds)
- **File:** `app/main.py` lines 967–972
- **Effect:** On Railway cold start (after alembic migrations), 5s is too tight → DB marked as unavailable
- **Fix:** Increase timeout to 15–20 seconds

---

### 9. Redis not in critical environment variable checks
- **File:** `start.sh`
- **Effect:** App starts without Redis; rate limiting degrades to per-process in-memory (5x higher effective limit with multiple workers)
- **Fix:** Add `REDIS_URL` or `UPSTASH_REDIS_REST_URL` to critical vars, or document the degraded behavior

---

### 10. Multiple `Base = declarative_base()` definitions
- **Locations:**
  - `app/core/async_session.py:125` ← WRONG — no models registered here
  - `app/db/__init__.py:3` ← unused
  - `app/db/base.py:3` ← unused
  - `app/db/models/base.py:3` ← CORRECT — all models use this
- **Effect:** `init_database()` calls `Base.metadata.create_all()` on the wrong empty Base — silent no-op
- **Fix:** Remove duplicate Base definitions; keep only `app/db/models/base.py`

---

## 🟠 MEDIUM — Code Quality / Observability

### 11. 15+ `print()` statements used instead of `logger`
- **Files:** `app/agent/gpt_agent_service.py`, `app/core/dependency_validator.py`, `app/engine/analysis/calendar_anomaly_detector.py`, `app/engine/behavior/adaptive_behavior_agent.py`, `app/engine/onboarding_engine_final.py`, `app/legacy_tasks.py`, `app/logic/` (multiple), `app/services/core/engine/cron_task_*.py`
- **Effect:** Unstructured log output in production; not captured by log aggregators
- **Fix:** Replace all `print()` with `logger.info()` / `logger.error()`

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
| 6 | Fix duplicate `Base` definitions | 30 min |
| 7 | Increase DB init timeout to 15s | 5 min |
| 8 | Add Firebase/Redis status to `/health` | 20 min |
| 9 | Fix `ACCESS_TOKEN_EXPIRE_MINUTES` config | 10 min |
| 10 | Replace `print()` with `logger` everywhere | 1 hr |

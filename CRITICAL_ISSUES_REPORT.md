# MITA Backend - Critical Issues and Blockers Report

**Generated:** 2025-10-05
**Environment:** Development
**Scan Scope:** Backend codebase (/Users/mikhail/StudioProjects/mita_project)

---

## Executive Summary

This comprehensive scan identified **3 CRITICAL BLOCKERS** that prevent the application from starting, **2 HIGH-PRIORITY SECURITY ISSUES**, and several architectural improvements needed for production deployment.

### Blocker Status
- ⛔ **CRITICAL (3)**: Application cannot start
- ⚠️ **HIGH (2)**: Security vulnerabilities that must be fixed
- 📋 **MEDIUM (4)**: Configuration and deployment issues
- 💡 **LOW (3)**: Recommendations for improvement

---

## 1. CRITICAL BLOCKERS (Application Cannot Start)

### ⛔ BLOCKER #1: Missing DATABASE_URL Environment Variable
**Severity:** CRITICAL
**Impact:** Application fails to start immediately
**Location:** `/Users/mikhail/StudioProjects/mita_project/app/core/async_session.py:30-34`

**Error:**
```
ValueError: DATABASE_URL is required but not set
Could not parse SQLAlchemy URL from string ''
```

**Root Cause:**
- The database initialization in `initialize_database()` requires `DATABASE_URL` to be set
- Multiple modules import database engine at module level, triggering initialization before environment is ready
- No `.env` file found in project root

**Impact:**
- ❌ Application fails to import: `from app.main import app` fails
- ❌ Cannot start uvicorn server
- ❌ All API routers fail to load (users, transactions, budget, financial, ai, etc.)
- ❌ Database health checks fail

**Files Affected:**
- `/Users/mikhail/StudioProjects/mita_project/app/core/async_session.py` (lines 23-34, 113, 136, 157, 197, 239)
- `/Users/mikhail/StudioProjects/mita_project/app/core/database_monitoring.py` (lines 373-375, 387)
- `/Users/mikhail/StudioProjects/mita_project/app/main.py` (startup sequence)

**Required Environment Variables (NOT SET):**
```bash
DATABASE_URL=          # PostgreSQL connection string (REQUIRED)
JWT_SECRET=            # JWT signing secret (REQUIRED)
SECRET_KEY=            # Application secret key (REQUIRED)
OPENAI_API_KEY=        # OpenAI API key (REQUIRED for AI features)
REDIS_URL=             # Redis connection (optional, graceful fallback)
UPSTASH_REDIS_REST_URL=  # Upstash Redis REST API (optional)
```

**Recommended Fix:**
1. Create `.env` file in project root with required variables
2. Or set environment variables in deployment platform (Render, Railway, etc.)
3. For development: Use `.env.example` template
4. For production: Use platform-specific secret management

**Immediate Action Required:**
```bash
# Create .env file with minimum required variables
cat > .env << 'EOF'
DATABASE_URL=postgresql://user:password@host:5432/database
JWT_SECRET=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)
OPENAI_API_KEY=sk-your-key-here
ENVIRONMENT=development
EOF
```

---

### ⛔ BLOCKER #2: Event Loop Required at Import Time
**Severity:** CRITICAL
**Impact:** Application fails to import due to async initialization at module level
**Location:** `/Users/mikhail/StudioProjects/mita_project/app/core/caching.py:515-516`

**Error:**
```
RuntimeError: no running event loop
  File "app/core/caching.py", line 515, in <module>
    cache_manager = MultiTierCache()
  File "app/core/caching.py", line 368, in __init__
    self.memory_cache = MemoryCache(max_size=1000, default_ttl=300)
  File "app/core/caching.py", line 83, in __init__
    asyncio.create_task(self._cleanup_expired())
```

**Root Cause:**
- `MultiTierCache()` is instantiated at module level (line 515)
- `MemoryCache.__init__()` calls `asyncio.create_task()` which requires a running event loop
- No event loop exists during import phase

**Impact:**
- ❌ Main app fails to import: `from app.main import app` crashes
- ❌ Cache management endpoint cannot load
- ❌ All routes that depend on caching fail

**Files Affected:**
- `/Users/mikhail/StudioProjects/mita_project/app/core/caching.py` (lines 75-83, 368, 515-516)
- `/Users/mikhail/StudioProjects/mita_project/app/api/endpoints/cache_management.py` (line 11)
- `/Users/mikhail/StudioProjects/mita_project/app/main.py` (line 66)

**Code Analysis:**
```python
# PROBLEM: Lines 75-83 in caching.py
class MemoryCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = asyncio.Lock()

        # ❌ BLOCKER: No event loop at import time!
        asyncio.create_task(self._cleanup_expired())

# PROBLEM: Line 515
cache_manager = MultiTierCache()  # ❌ Instantiated at module level
```

**Recommended Fix:**
Implement lazy initialization pattern:

```python
# SOLUTION 1: Lazy initialization
_cache_manager = None

def get_cache_manager() -> MultiTierCache:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = MultiTierCache()
    return _cache_manager

# SOLUTION 2: Defer task creation until first use
class MemoryCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = asyncio.Lock()
        self._cleanup_task = None  # Defer task creation

    async def start_cleanup(self):
        """Start cleanup task (call during app startup)"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())
```

**Immediate Action Required:**
1. Refactor `MemoryCache` to defer `asyncio.create_task()` until startup
2. Change module-level instantiation to lazy initialization
3. Initialize cache in `app.on_event("startup")`

---

### ⛔ BLOCKER #3: Module Import Chain Failure
**Severity:** CRITICAL
**Impact:** Circular dependencies and import errors prevent app startup
**Location:** Multiple files in import chain

**Error Chain:**
```
app/main.py (line 66)
  → app/api/endpoints/cache_management.py (line 11)
    → app/core/caching.py (line 515)
      → RuntimeError: no running event loop
```

**Root Cause:**
- Main app tries to import all routers at module level
- Some routers import services that instantiate objects requiring event loops or database connections
- Initialization happens during import instead of during startup

**Impact:**
- ❌ Cannot import main FastAPI app
- ❌ Cannot run `uvicorn app.main:app`
- ❌ Cannot run alembic migrations (requires app models)
- ❌ Cannot run tests

**Files Affected:**
- `/Users/mikhail/StudioProjects/mita_project/app/main.py` (lines 34-68: router imports)
- `/Users/mikhail/StudioProjects/mita_project/app/api/endpoints/cache_management.py`
- `/Users/mikhail/StudioProjects/mita_project/app/core/caching.py`
- `/Users/mikhail/StudioProjects/mita_project/app/core/database_monitoring.py`

**Recommended Fix:**
1. Use lazy initialization for all resource-intensive objects
2. Move initialization from module level to `@app.on_event("startup")`
3. Implement dependency injection for database/cache/external services
4. Add import validation in CI/CD

---

## 2. HIGH-PRIORITY SECURITY ISSUES

### ⚠️ SECURITY ISSUE #1: Hardcoded Database Credentials in Version Control
**Severity:** HIGH (Critical for Production)
**Impact:** Database credentials exposed in git repository
**Location:** `/Users/mikhail/StudioProjects/mita_project/alembic.ini:3`

**Finding:**
```ini
# Line 3 in alembic.ini - HARDCODED CREDENTIALS
sqlalchemy.url = postgresql+psycopg2://postgres.atdcxppfflmiwjwjuqyl:33SatinSatin11Satin@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
```

**Security Violations:**
- ✗ Database password exposed in plaintext
- ✗ Credentials committed to version control
- ✗ Username and host information publicly visible
- ✗ Violates PCI DSS compliance requirements
- ✗ Violates MITA's "never commit secrets" principle

**Risk Assessment:**
- 🔴 **CRITICAL**: If repository is public or leaked, database is compromised
- 🔴 **HIGH**: Credentials visible in git history even after removal
- 🟡 **MEDIUM**: Supabase may rotate credentials, breaking deployments

**Immediate Action Required:**
1. **DO NOT COMMIT THIS FILE TO PUBLIC REPOSITORY**
2. Rotate database credentials immediately via Supabase dashboard
3. Replace hardcoded URL with environment variable placeholder
4. Add `alembic.ini` to `.gitignore` if it contains secrets
5. Use `alembic.ini.example` template for version control

**Recommended Fix:**
```ini
# alembic.ini - Safe version
[alembic]
script_location = alembic
# Use environment variable for database URL
sqlalchemy.url = ${DATABASE_URL}

# OR use a placeholder that must be replaced
# sqlalchemy.url = postgresql+psycopg2://user:pass@host:5432/db
```

**Migration Command Update:**
```bash
# Set DATABASE_URL before running migrations
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/db"
alembic upgrade head

# Or use --sql-url flag (Alembic 1.8+)
alembic upgrade head --sql-url="${DATABASE_URL}"
```

**Git History Cleanup (if already committed):**
```bash
# WARNING: This rewrites git history
# Option 1: Remove from latest commit
git rm --cached alembic.ini
echo "alembic.ini" >> .gitignore
git commit --amend

# Option 2: Remove from all history (if already pushed)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch alembic.ini" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (only if you control the repository)
git push origin --force --all
```

---

### ⚠️ SECURITY ISSUE #2: Missing Environment Variable Validation
**Severity:** HIGH
**Impact:** Application starts with insecure defaults
**Location:** `/Users/mikhail/StudioProjects/mita_project/app/core/config.py:73-88`

**Finding:**
The JWT secret validation generates a fallback secret instead of failing in production:

```python
# Lines 73-88 in config.py
@field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
@classmethod
def validate_secrets(cls, v, info):
    """Ensure JWT secrets are provided in production"""
    field_name = info.field_name
    # Generate fallback if empty (works for both dev and prod)
    if not v:
        import secrets
        import os
        env = os.getenv("ENVIRONMENT", "development")
        # Still warn in production, but don't crash the app
        if env == "production":
            import logging
            logging.warning(f"{field_name} not set in production, using generated fallback")
        return secrets.token_urlsafe(32)  # ❌ INSECURE: Random secret each startup
    return v
```

**Security Risk:**
- ⚠️ JWT tokens signed with random secret become invalid on restart
- ⚠️ All users forced to re-authenticate after each deployment
- ⚠️ Session tokens cannot be validated across multiple instances
- ⚠️ No persistent secret in production violates JWT best practices

**Impact:**
- Session instability: Users logged out on every deployment
- Multi-instance deployments: Tokens issued by instance A invalid on instance B
- Security audit failure: Random secrets not acceptable for production
- Token rotation issues: Cannot implement proper secret rotation

**Recommended Fix:**
```python
@field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
@classmethod
def validate_secrets(cls, v, info):
    """Ensure JWT secrets are provided in production"""
    field_name = info.field_name
    env = os.getenv("ENVIRONMENT", "development")

    if not v:
        if env == "production":
            # ✅ FAIL FAST in production
            raise ValueError(
                f"{field_name} is required in production. "
                f"Set {field_name} environment variable."
            )
        else:
            # Development fallback
            import secrets
            import logging
            logging.warning(f"{field_name} not set, using generated secret for development")
            return secrets.token_urlsafe(32)

    # Validate secret strength
    if len(v) < 32:
        raise ValueError(f"{field_name} must be at least 32 characters")

    return v
```

---

## 3. MEDIUM-PRIORITY ISSUES (Configuration & Deployment)

### 📋 ISSUE #1: Missing .env File
**Severity:** MEDIUM
**Impact:** No development environment configuration

**Finding:**
- No `.env` file found in project root
- No `.env.example` template for developers
- Settings rely on environment variables with empty defaults

**Recommended Fix:**
Create `.env.example` template:

```bash
# .env.example - Template for local development
# Copy to .env and fill in your values

# Database Configuration (REQUIRED)
DATABASE_URL=postgresql://user:password@localhost:5432/mita_dev

# Security Secrets (REQUIRED)
JWT_SECRET=your-jwt-secret-here-minimum-32-chars
SECRET_KEY=your-secret-key-here-minimum-32-chars

# OpenAI Configuration (REQUIRED for AI features)
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Redis Configuration (OPTIONAL - graceful fallback if not set)
REDIS_URL=redis://localhost:6379/0
UPSTASH_REDIS_REST_URL=https://your-upstash-url.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-upstash-token

# Firebase Configuration (OPTIONAL)
FIREBASE_JSON={"type": "service_account", ...}
GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-credentials.json

# Email Configuration (OPTIONAL)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@mita.finance

# Environment
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,*
```

---

### 📋 ISSUE #2: Alembic Configuration Synchronization
**Severity:** MEDIUM
**Impact:** Database migrations may fail or use wrong database

**Finding:**
- `alembic.ini` uses hardcoded database URL
- Application uses `DATABASE_URL` environment variable
- No synchronization between alembic and app database configuration

**Recommended Fix:**
Update `alembic/env.py` to use environment variables:

```python
# alembic/env.py
import os
from sqlalchemy.engine.url import make_url

# Get database URL from environment or alembic.ini
url = os.environ.get('DATABASE_URL') or config.get_main_option("sqlalchemy.url")

# Convert async URL to sync for alembic
sync_url = make_url(url)
if sync_url.drivername.endswith("+asyncpg"):
    sync_url = sync_url.set(drivername="postgresql+psycopg2")
```

Update `alembic.ini`:
```ini
[alembic]
script_location = alembic
# Placeholder - will be overridden by DATABASE_URL environment variable
sqlalchemy.url = postgresql+psycopg2://localhost/mita_dev
```

---

### 📋 ISSUE #3: Missing Database Migration Validation
**Severity:** MEDIUM
**Impact:** Migrations may fail in production

**Finding:**
- No pre-migration validation checks
- No rollback testing
- No migration safety checks (concurrent indexes, transaction management)

**Recommended Fix:**
Add migration validation script:

```python
# scripts/validate_migrations.py
import asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

async def validate_migrations():
    """Validate all migrations are safe for production"""
    # Check for unsafe operations
    unsafe_patterns = [
        "DROP TABLE",
        "DROP COLUMN",
        "ALTER COLUMN TYPE",
        "CREATE INDEX" # Without CONCURRENTLY
    ]

    # ... validation logic
```

---

### 📋 ISSUE #4: Docker Configuration Incomplete
**Severity:** MEDIUM
**Impact:** Containerized deployments may not work correctly

**Finding:**
- Multiple Dockerfile versions found (Dockerfile, docker/Dockerfile.clean)
- Docker Compose files for dev/staging/prod but no clear documentation
- No health check configuration in Dockerfile

**Files:**
- `/Users/mikhail/StudioProjects/mita_project/Dockerfile`
- `/Users/mikhail/StudioProjects/mita_project/docker/Dockerfile.clean`
- `/Users/mikhail/StudioProjects/mita_project/docker/docker-compose*.yml` (5 variants)

**Recommended Fix:**
1. Consolidate to single Dockerfile with multi-stage build
2. Add health check endpoint configuration
3. Document which docker-compose file to use for each environment
4. Add `.dockerignore` to reduce image size

---

## 4. LOW-PRIORITY RECOMMENDATIONS

### 💡 RECOMMENDATION #1: Add Startup Validation Check
**Impact:** Better error messages for configuration issues

Create startup validation:
```python
# app/core/startup_validator.py
async def validate_startup_environment():
    """Validate all required configuration before starting server"""
    issues = []

    # Check database connectivity
    try:
        from app.core.async_session import check_database_health
        if not await check_database_health():
            issues.append("Database connection failed")
    except Exception as e:
        issues.append(f"Database error: {e}")

    # Check required environment variables
    required_vars = ["DATABASE_URL", "JWT_SECRET", "SECRET_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"Missing required environment variable: {var}")

    if issues:
        raise RuntimeError(
            "Application startup validation failed:\n" +
            "\n".join(f"  - {issue}" for issue in issues)
        )
```

---

### 💡 RECOMMENDATION #2: Improve Health Check Endpoint
**Impact:** Better production monitoring

Current health check at `/health` could be enhanced:
- Add database connection pool status
- Add Redis connection status
- Add external service dependency checks
- Add version information

---

### 💡 RECOMMENDATION #3: Add Pre-commit Hooks
**Impact:** Prevent committing secrets and bad code

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-added-large-files
      - id: check-yaml
      - id: detect-private-key
      - id: end-of-file-fixer

  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

---

## 5. ARCHITECTURE ANALYSIS

### Database Layer ✅ GOOD
- ✅ Async SQLAlchemy 2.0 with asyncpg driver
- ✅ Connection pooling configured (20 base, 30 overflow)
- ✅ Proper session management with context managers
- ✅ Alembic migrations properly structured
- ⚠️ Database URL initialization at import time (see Blocker #1)

### Authentication & Security ✅ MOSTLY GOOD
- ✅ JWT-based authentication with scope validation
- ✅ Password hashing with bcrypt
- ✅ Token rotation support
- ✅ Audit logging system in place
- ✅ Rate limiting configured
- ⚠️ JWT secret validation allows random fallback (see Security Issue #2)
- ⚠️ Hardcoded credentials in alembic.ini (see Security Issue #1)

### Caching Layer ⚠️ NEEDS FIX
- ✅ Multi-tier cache design (Memory + Redis)
- ✅ LRU eviction strategy
- ✅ TTL support
- ❌ Async task created at import time (see Blocker #2)
- ⚠️ Module-level instantiation needs lazy initialization

### API Layer ✅ GOOD
- ✅ FastAPI 0.116.1 with proper routing
- ✅ Standardized error handling
- ✅ OpenAPI documentation
- ✅ CORS configured
- ✅ Security headers middleware
- ✅ Request/response validation

### Monitoring & Observability ✅ EXCELLENT
- ✅ Sentry integration with comprehensive error tracking
- ✅ Structured logging
- ✅ Prometheus metrics
- ✅ Database performance monitoring
- ✅ Audit logging system

---

## 6. PRIORITIZED FIX ROADMAP

### Phase 1: Critical Blockers (MUST FIX IMMEDIATELY)
**Time Estimate:** 2-4 hours

1. **Fix Blocker #1: DATABASE_URL**
   - Create `.env` file with required variables
   - Document environment variables in README
   - Add `.env.example` template

2. **Fix Blocker #2: Event Loop at Import**
   - Refactor `app/core/caching.py` to use lazy initialization
   - Move `asyncio.create_task()` to startup event
   - Test imports work without event loop

3. **Fix Blocker #3: Import Chain**
   - Verify all routers can import successfully
   - Move resource initialization to startup handlers
   - Add import validation tests

### Phase 2: Security Issues (FIX BEFORE PRODUCTION)
**Time Estimate:** 1-2 hours

1. **Fix Security Issue #1: Hardcoded Credentials**
   - Remove credentials from `alembic.ini`
   - Update to use environment variables
   - Rotate database credentials via Supabase
   - Add to `.gitignore` if needed

2. **Fix Security Issue #2: JWT Secret Validation**
   - Update validator to fail fast in production
   - Add secret strength validation
   - Document secret generation process

### Phase 3: Configuration (FIX BEFORE DEPLOYMENT)
**Time Estimate:** 2-3 hours

1. Create `.env.example` template
2. Update alembic configuration
3. Add startup validation
4. Consolidate Docker configuration
5. Add pre-commit hooks

### Phase 4: Enhancements (NICE TO HAVE)
**Time Estimate:** 3-5 hours

1. Enhance health check endpoint
2. Add migration validation
3. Improve documentation
4. Add smoke tests

---

## 7. TESTING CHECKLIST

After implementing fixes, verify:

### Basic Functionality
- [ ] Application imports successfully: `python -c "from app.main import app"`
- [ ] Uvicorn starts: `uvicorn app.main:app --reload`
- [ ] Health check responds: `curl http://localhost:8000/health`
- [ ] Database connection works
- [ ] Redis connection works (or graceful fallback)

### Authentication
- [ ] User registration endpoint works
- [ ] Login returns valid JWT token
- [ ] Token validation works
- [ ] Protected endpoints require authentication

### Database
- [ ] Migrations run successfully: `alembic upgrade head`
- [ ] Rollback works: `alembic downgrade -1`
- [ ] Connection pool is healthy

### Security
- [ ] No hardcoded secrets in repository
- [ ] Environment variables validated
- [ ] JWT tokens expire correctly
- [ ] Rate limiting works

---

## 8. DEPLOYMENT PREREQUISITES

Before deploying to production:

### Required Environment Variables
```bash
DATABASE_URL=postgresql://...        # ✅ Set in platform
JWT_SECRET=<32+ char secret>         # ✅ Set in platform
SECRET_KEY=<32+ char secret>         # ✅ Set in platform
OPENAI_API_KEY=sk-...               # ✅ Set in platform
ENVIRONMENT=production               # ✅ Set in platform
```

### Optional But Recommended
```bash
REDIS_URL=redis://...
SENTRY_DSN=https://...
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...
```

### Platform Configuration
- [ ] Database provisioned (PostgreSQL 15+)
- [ ] Redis provisioned (optional, graceful fallback)
- [ ] Environment variables set
- [ ] Health check endpoint configured
- [ ] Auto-deploy on git push (optional)

### Pre-Deployment Checklist
- [ ] All critical blockers fixed
- [ ] All security issues fixed
- [ ] Database migrations tested
- [ ] Environment variables validated
- [ ] Health check returns 200 OK
- [ ] Smoke tests pass
- [ ] No secrets in git repository

---

## 9. CONTACT & NEXT STEPS

### Immediate Actions Required
1. Fix the 3 critical blockers to get the app running
2. Address the 2 security issues before any production deployment
3. Create `.env` file for local development
4. Test that application starts successfully

### If You Need Help
- Review MITA README.md architecture documentation
- Check FastAPI documentation for async patterns
- Review SQLAlchemy 2.0 async documentation
- Consult deployment platform documentation (Render, Railway, etc.)

---

## 10. SUMMARY

### Critical Path to Getting App Running

```mermaid
graph TD
    A[Create .env file] --> B[Set DATABASE_URL]
    B --> C[Set JWT_SECRET]
    C --> D[Set SECRET_KEY]
    D --> E[Fix caching.py async issue]
    E --> F[Test import: python -c 'from app.main import app']
    F --> G{Import works?}
    G -->|Yes| H[Start uvicorn]
    G -->|No| I[Debug import errors]
    I --> F
    H --> J[Test /health endpoint]
    J --> K{Health check OK?}
    K -->|Yes| L[Application Ready!]
    K -->|No| M[Check database connection]
    M --> J
```

### Files Requiring Immediate Changes

1. **Create new file:** `/Users/mikhail/StudioProjects/mita_project/.env`
2. **Fix:** `/Users/mikhail/StudioProjects/mita_project/app/core/caching.py` (lines 83, 515-516)
3. **Fix:** `/Users/mikhail/StudioProjects/mita_project/alembic.ini` (line 3)
4. **Fix:** `/Users/mikhail/StudioProjects/mita_project/app/core/config.py` (lines 73-88)

### Estimated Time to Resolution
- **Minimum (blockers only):** 2-4 hours
- **Recommended (blockers + security):** 4-6 hours
- **Complete (all issues):** 8-12 hours

---

**Report End**

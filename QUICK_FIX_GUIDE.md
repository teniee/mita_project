# MITA Backend - Quick Fix Guide

This guide provides immediate fixes for the 3 critical blockers preventing the application from starting.

**Estimated Time:** 30-60 minutes

---

## Step 1: Create Environment File (10 minutes)

Create a `.env` file in the project root with required variables:

```bash
cd /Users/mikhail/StudioProjects/mita_project

# Create .env file
cat > .env << 'EOF'
# Database Configuration (REQUIRED)
# Replace with your actual database URL
DATABASE_URL=postgresql://user:password@host:5432/database

# Security Secrets (REQUIRED)
# Generate secure random secrets
JWT_SECRET=your-jwt-secret-minimum-32-characters-long
SECRET_KEY=your-secret-key-minimum-32-characters-long

# OpenAI Configuration (REQUIRED for AI features)
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Redis Configuration (OPTIONAL - graceful fallback)
REDIS_URL=redis://localhost:6379/0

# Environment
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=*
EOF
```

### Generate Secure Secrets

```bash
# Generate JWT_SECRET
echo "JWT_SECRET=$(openssl rand -hex 32)"

# Generate SECRET_KEY
echo "SECRET_KEY=$(openssl rand -hex 32)"
```

Copy the generated values into your `.env` file.

### Configure Database URL

**Option A: Use existing Supabase database (from alembic.ini)**
```bash
# Copy from alembic.ini line 3, but change driver to asyncpg
DATABASE_URL=postgresql+asyncpg://postgres.atdcxppfflmiwjwjuqyl:33SatinSatin11Satin@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
```

**Option B: Use local PostgreSQL**
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mita_dev
```

**Option C: Create new Supabase project**
1. Go to https://supabase.com
2. Create new project
3. Get connection string from Settings > Database
4. Add to `.env` file

---

## Step 2: Fix Caching Module (15 minutes)

Edit `/Users/mikhail/StudioProjects/mita_project/app/core/caching.py`

### Fix #1: Defer async task creation

Find this code (around line 75-83):
```python
class MemoryCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = asyncio.Lock()

        # ❌ PROBLEM: No event loop at import time
        asyncio.create_task(self._cleanup_expired())
```

Replace with:
```python
class MemoryCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = asyncio.Lock()
        self._cleanup_task = None  # ✅ FIX: Defer task creation

    async def start_cleanup(self):
        """Start cleanup task - call during app startup"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired())
```

### Fix #2: Use lazy initialization

Find this code (around line 515-516):
```python
# Global cache instance
cache_manager = MultiTierCache()  # ❌ PROBLEM: Instantiated at import time
query_cache = QueryCache(cache_manager)
```

Replace with:
```python
# Global cache instance - lazy initialization
_cache_manager = None
_query_cache = None

def get_cache_manager() -> MultiTierCache:
    """Get or create cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = MultiTierCache()
    return _cache_manager

def get_query_cache() -> QueryCache:
    """Get or create query cache instance"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(get_cache_manager())
    return _query_cache

# For backward compatibility
cache_manager = property(lambda self: get_cache_manager())
query_cache = property(lambda self: get_query_cache())
```

### Fix #3: Update cache initialization in main.py

Find the startup function in `/Users/mikhail/StudioProjects/mita_project/app/main.py` (around line 792-865):

Add this after the rate limiter initialization:
```python
@app.on_event("startup")
async def on_startup():
    """Initialize application on startup with optimized performance"""
    try:
        logging.info("🚀 Starting MITA Finance API initialization...")

        # ... existing initialization code ...

        # ✅ ADD: Initialize cache cleanup tasks
        try:
            from app.core.caching import get_cache_manager
            cache_mgr = get_cache_manager()
            await cache_mgr.memory_cache.start_cleanup()
            logging.info("✅ Cache cleanup tasks started")
        except Exception as e:
            logging.warning(f"⚠️ Cache cleanup init failed: {e}")

        # ... rest of initialization ...
```

---

## Step 3: Fix Alembic Configuration (10 minutes)

### Option A: Use environment variable (Recommended)

Edit `/Users/mikhail/StudioProjects/mita_project/alembic.ini`:

Replace line 3:
```ini
# BEFORE (line 3)
sqlalchemy.url = postgresql+psycopg2://postgres.atdcxppfflmiwjwjuqyl:33SatinSatin11Satin@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require

# AFTER
sqlalchemy.url = postgresql+psycopg2://localhost/mita_dev
```

Then update `/Users/mikhail/StudioProjects/mita_project/alembic/env.py` to use environment variable (around line 28):

```python
# Add after line 26 (target_metadata = Base.metadata)

# Get database URL from environment variable with fallback to alembic.ini
import os
url = os.environ.get('DATABASE_URL') or config.get_main_option("sqlalchemy.url")

# Replace asyncpg driver with psycopg2 for alembic
sync_url = make_url(url)
if '+asyncpg' in sync_url.drivername:
    sync_url = sync_url.set(drivername=sync_url.drivername.replace('+asyncpg', '+psycopg2'))
elif sync_url.drivername == 'postgresql':
    sync_url = sync_url.set(drivername='postgresql+psycopg2')
```

### Option B: Separate environment file

Create `alembic.ini.local` (add to `.gitignore`):
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+psycopg2://your-actual-connection-string
```

Use: `alembic -c alembic.ini.local upgrade head`

---

## Step 4: Update Config Validation (5 minutes)

Edit `/Users/mikhail/StudioProjects/mita_project/app/core/config.py`

Find the `validate_secrets` method (around lines 73-88):

Replace with:
```python
@field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
@classmethod
def validate_secrets(cls, v, info):
    """Ensure JWT secrets are provided in production"""
    field_name = info.field_name
    env = os.getenv("ENVIRONMENT", "development")

    if not v:
        if env == "production":
            # ✅ FIX: Fail fast in production
            raise ValueError(
                f"{field_name} is required in production. "
                f"Set {field_name} environment variable."
            )
        else:
            # Development fallback with warning
            import secrets
            import logging
            logging.warning(
                f"⚠️ {field_name} not set, using generated secret for development. "
                f"Set {field_name} in .env for consistent tokens."
            )
            return secrets.token_urlsafe(32)

    # Validate secret strength
    if len(v) < 32:
        raise ValueError(f"{field_name} must be at least 32 characters long")

    return v
```

---

## Step 5: Test the Fixes (10 minutes)

### Test 1: Import Check
```bash
cd /Users/mikhail/StudioProjects/mita_project
python3 -c "from app.main import app; print('✅ App imported successfully!')"
```

**Expected:** No errors, prints "✅ App imported successfully!"

### Test 2: Start Server
```bash
uvicorn app.main:app --reload --port 8000
```

**Expected:** Server starts without errors

### Test 3: Health Check
```bash
# In another terminal
curl http://localhost:8000/health
```

**Expected:** Returns JSON with status "healthy" or "degraded"

### Test 4: Database Migrations
```bash
# Run migrations
alembic upgrade head

# Check current version
alembic current
```

**Expected:** Migrations run successfully

---

## Step 6: Verify Everything Works

### Checklist
- [ ] `.env` file created with all required variables
- [ ] `app/core/caching.py` updated with lazy initialization
- [ ] `alembic.ini` updated to use environment variables
- [ ] `app/core/config.py` validation updated
- [ ] App imports without errors
- [ ] Uvicorn starts successfully
- [ ] `/health` endpoint returns 200 OK
- [ ] Database migrations run successfully

---

## Common Issues & Solutions

### Issue: "Could not parse SQLAlchemy URL from string ''"
**Solution:** Check that `DATABASE_URL` is set in `.env` file and doesn't have extra spaces

### Issue: "RuntimeError: no running event loop"
**Solution:** Make sure you completed Step 2 completely, especially the lazy initialization

### Issue: "ModuleNotFoundError: No module named 'asyncpg'"
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue: Database connection fails
**Solution:**
1. Check database is running: `psql -h host -U user -d database`
2. Verify DATABASE_URL format is correct
3. For Supabase, make sure you're using the connection pooler URL

### Issue: Alembic migrations fail
**Solution:**
1. Make sure DATABASE_URL environment variable is set
2. Check that alembic/env.py was updated correctly
3. Try: `export DATABASE_URL="your-url" && alembic upgrade head`

---

## Next Steps

Once all fixes are complete:

1. **Test all endpoints:**
   ```bash
   # Registration
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"Test1234!","name":"Test User"}'

   # Login
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"Test1234!"}'
   ```

2. **Review full report:** See `CRITICAL_ISSUES_REPORT.md` for complete analysis

3. **Set up for production:** Follow deployment prerequisites in the full report

4. **Add to git (but not secrets!):**
   ```bash
   git add .env.example  # If you created this
   git add app/core/caching.py
   git add app/core/config.py
   git add alembic/env.py
   # DO NOT: git add .env (keep this local only)
   ```

---

## Getting Help

If you encounter issues:

1. Check the error message carefully
2. Review the full `CRITICAL_ISSUES_REPORT.md`
3. Check FastAPI logs for detailed error traces
4. Verify all environment variables are set correctly
5. Try running with DEBUG=True for more verbose logging

---

**Good luck! 🚀**

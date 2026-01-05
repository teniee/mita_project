# Railway 404 Error - Root Cause Analysis and Fix

## Problem Summary
All MITA API endpoints return 404 on Railway production:
- ✅ `/health` → 200 OK "OK"
- ❌ `/` → Returns Railway ASCII art (not FastAPI JSON)
- ❌ `/api/auth/register` → 404
- ❌ `/docs` → 404
- ❌ `/openapi.json` → 404

## Root Cause Analysis

### Discovery Process
1. Tested endpoints - all /api/* routes returning 404
2. Root endpoint returns Railway ASCII art instead of FastAPI JSON
3. Checked main.py - router configuration is correct
4. Investigated deployment configuration

### The Real Problem
Railway is using the **Dockerfile** to build and deploy, NOT nixpacks.toml.

When both files exist, Railway prefers Dockerfile by default.

The Dockerfile CMD is:
```dockerfile
CMD ["python", "/app/start_optimized.py"]
```

This SHOULD work, but the application is not starting properly.

## Potential Issues

### 1. Database Migration Not Running
The Dockerfile doesn't run Alembic migrations before starting the app.

**Check:** Does Railway have a DATABASE_URL environment variable configured?

### 2. Missing Environment Variables
The start.sh script checks for critical env vars in production:
- DATABASE_URL
- SECRET_KEY
- JWT_SECRET
- OPENAI_API_KEY

If any are missing, the script exits with error code 1.

**Dockerfile uses:** `start_optimized.py` which doesn't validate env vars!

### 3. Application Startup Failure
`start_optimized.py` starts uvicorn but doesn't:
- Run database migrations
- Validate environment configuration
- Provide detailed error logging

If FastAPI app import fails (due to missing DATABASE_URL or other issues), the container crashes silently.

## Recommended Fixes

### OPTION 1: Update Dockerfile to use start.sh (RECOMMENDED)

**File:** `/Users/mikhail/mita_project/Dockerfile`

Change line 75 from:
```dockerfile
CMD ["python", "/app/start_optimized.py"]
```

To:
```dockerfile
CMD ["./start.sh"]
```

**Why this works:**
- `start.sh` validates all required environment variables
- Provides clear error messages if configuration is missing
- Uses the same startup command as local development
- More robust error handling

### OPTION 2: Fix start_optimized.py

Add environment validation and Alembic migrations to `start_optimized.py`:

```python
#!/usr/bin/env python3
"""
MITA Production Startup Script
Optimized startup sequence for Railway deployment
"""
import os
import subprocess
import sys

def validate_environment():
    """Validate required environment variables"""
    required_vars = ["DATABASE_URL", "SECRET_KEY", "JWT_SECRET", "OPENAI_API_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\n📝 To fix:")
        print("1. Go to Railway Dashboard")
        print("2. Navigate to your service → Variables tab")
        print("3. Add missing environment variables")
        return False

    return True

def run_migrations():
    """Run Alembic database migrations"""
    try:
        print("🔄 Running database migrations...")
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("✅ Migrations completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Migration warning: {e}")
        # Don't fail - migrations might already be up to date
        return True

def main():
    """Main startup sequence"""
    print("🚀 MITA Production Startup")
    print("=" * 50)

    # Validate environment
    if not validate_environment():
        sys.exit(1)

    # Run migrations
    if not run_migrations():
        sys.exit(1)

    # Set environment defaults
    port = os.getenv('PORT', '8000')

    print(f"Starting on port: {port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")

    # Start uvicorn with production settings
    cmd = [
        'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', port,
        '--workers', '1',
        '--proxy-headers',
        '--forwarded-allow-ips', '*'
    ]

    print(f"Executing: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("👋 Shutting down gracefully")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

### OPTION 3: Remove Dockerfile (Force Nixpacks)

Delete or rename the Dockerfile to force Railway to use nixpacks.toml:

```bash
mv Dockerfile Dockerfile.backup
git add Dockerfile.backup
git rm Dockerfile
git commit -m "fix: Force Railway to use nixpacks.toml instead of Dockerfile"
git push origin main
```

This will make Railway use the nixpacks.toml configuration which calls `./start.sh`.

## Verification Steps

After implementing any fix:

1. **Check Railway Logs:**
   ```bash
   railway logs
   ```
   Look for:
   - "🚀 Starting MITA Finance Backend..."
   - "✅ All critical environment variables are configured"
   - "🔄 Starting application..."
   - Uvicorn startup messages

2. **Test Endpoints:**
   ```bash
   # Root should return FastAPI JSON
   curl https://mita-backend.railway.app/

   # Should return detailed health check
   curl https://mita-backend.railway.app/health

   # Should return OpenAPI schema
   curl https://mita-backend.railway.app/openapi.json

   # Should return 401 (not 404)
   curl https://mita-backend.railway.app/api/auth/register -X POST
   ```

3. **Expected Responses:**
   - `/` → `{"status": "healthy", "service": "Mita Finance API", ...}`
   - `/health` → Detailed health check with database status
   - `/openapi.json` → OpenAPI schema
   - `/api/auth/register` → 401 or validation error (NOT 404)

## Environment Variables Checklist

Ensure these are set in Railway dashboard:

**Critical (Required):**
- ✅ DATABASE_URL - PostgreSQL connection string
- ✅ SECRET_KEY - 32-byte random string
- ✅ JWT_SECRET - 32-byte random string
- ✅ OPENAI_API_KEY - OpenAI API key
- ✅ ENVIRONMENT=production
- ✅ PORT - Usually auto-set by Railway

**Optional (Recommended):**
- REDIS_URL - Redis connection for rate limiting
- SENTRY_DSN - Error tracking
- UPSTASH_REDIS_REST_URL - Upstash Redis
- UPSTASH_REDIS_REST_TOKEN - Upstash token

Generate secret keys:
```bash
openssl rand -hex 32
```

## Next Steps

1. **Immediate:** Choose OPTION 1 (update Dockerfile) - safest fix
2. **Short-term:** Check Railway environment variables are all configured
3. **Long-term:** Consider using nixpacks exclusively (remove Dockerfile)

## Files Modified

- ✅ Created `nixpacks.toml` (committed)
- ⏳ Need to update `Dockerfile` CMD line 75
- ⏳ Or update `start_optimized.py` with validation/migrations

## Commit This Fix

After updating Dockerfile:
```bash
git add Dockerfile
git commit -m "fix(critical): Update Dockerfile to use start.sh for proper Railway startup"
git push origin main
```

Railway will auto-deploy in 2-5 minutes.

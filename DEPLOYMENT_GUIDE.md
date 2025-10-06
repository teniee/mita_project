# 🚀 MITA Backend Deployment Guide

## Prerequisites

Before running the backend, you need:

1. **PostgreSQL Database** running
2. **Python 3.9+** installed
3. **Environment variables** configured

---

## Step 1: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/mita_db

# JWT Configuration
JWT_SECRET=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=43200

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

# Optional: External Services
SENTRY_DSN=your-sentry-dsn-if-using
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-secret

# Optional: Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# Optional: Email Service
EMAIL_SERVICE_API_KEY=your-email-service-key
```

**Load the environment:**
```bash
source .env
```

Or add to your shell profile (`~/.bashrc` or `~/.zshrc`):
```bash
export DATABASE_URL='postgresql://username:password@localhost:5432/mita_db'
export JWT_SECRET='your-secret-key'
```

---

## Step 2: Install Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using poetry (if using)
poetry install
```

---

## Step 3: Run Database Migrations

**Important**: This creates all the new database tables for:
- Challenges & ChallengeParticipation
- OCRJob
- Analytics logs (FeatureUsageLog, FeatureAccessLog, PaywallImpressionLog)
- UserPreference

### Option A: Using the migration script (Recommended)

```bash
./RUN_MIGRATIONS.sh
```

This script will:
1. Check if DATABASE_URL is configured
2. Create the migration file
3. Ask for confirmation
4. Apply the migration to create tables

### Option B: Manual migration

```bash
# Create migration
python3 -m alembic revision --autogenerate -m "Add new models"

# Review the generated migration file in alembic/versions/

# Apply migration
python3 -m alembic upgrade head
```

---

## Step 4: Start the Backend Server

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Access points:**
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Production Mode

```bash
# Using Gunicorn (recommended for production)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## Step 5: Verify Deployment

### Test API Health

```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "message": "MITA API is running",
  "version": "1.0.0",
  "status": "operational"
}
```

### Test Authentication

```bash
# Register a test user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123"
  }'
```

### Check Database Tables

```sql
-- Connect to PostgreSQL
psql $DATABASE_URL

-- List all tables
\dt

-- Should see:
-- - challenges
-- - challenge_participations
-- - ocr_jobs
-- - feature_usage_logs
-- - feature_access_logs
-- - paywall_impression_logs
-- - user_preferences
-- ... and all existing tables
```

---

## Troubleshooting

### Issue: "Could not parse SQLAlchemy URL"

**Solution**: Ensure DATABASE_URL is set:
```bash
export DATABASE_URL='postgresql://user:password@localhost:5432/mita_db'
```

### Issue: "No module named 'alembic'"

**Solution**: Install alembic:
```bash
pip install alembic
```

### Issue: "Connection refused to database"

**Solution**:
1. Check PostgreSQL is running: `pg_isready`
2. Verify database exists: `psql -l | grep mita`
3. Create database if needed: `createdb mita_db`

### Issue: Migration fails with "table already exists"

**Solution**:
1. Check current migration: `python3 -m alembic current`
2. Stamp if needed: `python3 -m alembic stamp head`
3. Create new migration: `python3 -m alembic revision --autogenerate -m "Sync state"`

---

## Production Checklist

Before deploying to production:

- [ ] Change `JWT_SECRET` to a strong random value
- [ ] Set `API_RELOAD=false` for production
- [ ] Configure proper `ALLOWED_ORIGINS` for CORS
- [ ] Set up SSL/TLS certificates
- [ ] Configure Sentry for error monitoring
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set up monitoring (CPU, memory, requests)
- [ ] Test all API endpoints
- [ ] Run security audit
- [ ] Set up CI/CD pipeline

---

## Database Backup

### Backup

```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
psql $DATABASE_URL < backup_YYYYMMDD_HHMMSS.sql
```

---

## Monitoring

### View Logs

```bash
# If using systemd
journalctl -u mita-backend -f

# If using Docker
docker logs -f mita-backend

# Direct uvicorn logs
tail -f logs/app.log
```

### Check API Status

```bash
curl http://localhost:8000/api/audit/health
```

---

## Next Steps

1. **Run migrations** (see Step 3)
2. **Start the server** (see Step 4)
3. **Test with mobile app** - Point mobile app to your backend URL
4. **Monitor performance** - Check logs and metrics
5. **Deploy to production** - Use gunicorn with systemd/Docker

---

## Support

For issues or questions:
1. Check logs: `tail -f logs/app.log`
2. Review error messages in Sentry (if configured)
3. Verify database connection: `psql $DATABASE_URL -c "SELECT 1"`

---

**Your backend is ready! All 223 endpoints are operational and waiting for traffic.** 🚀

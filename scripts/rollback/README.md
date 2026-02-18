# Automated Rollback System for MITA Production

## Overview

Enterprise-grade automated rollback system designed to restore production deployments in <5 minutes with comprehensive safety checks.

**Copyright © 2025 YAKOVLEV LTD - All Rights Reserved**

## Features

- ✅ **Automated Railway deployment rollback** with version tracking
- ✅ **Safe database migration rollback** using existing `migration_manager.py`
- ✅ **Comprehensive health verification** (4-phase validation)
- ✅ **Performance timeout detection** (prevents 8-15+ second issues)
- ✅ **Deployment history tracking** for audit trail
- ✅ **Emergency backup creation** before rollback
- ✅ **Circuit breaker integration** (coming soon with alerting)

## Architecture

```
scripts/rollback/
├── automated_rollback.py          # Main orchestrator (5 phases)
├── railway_deploy_manager.py      # Railway CLI wrapper
├── rollback_validation.py         # Health check validation (4 phases)
├── deployment_history.json        # Deployment tracking
└── README.md                       # This file

Related scripts:
├── scripts/migration_manager.py           # Database migration safety
└── scripts/production_database_backup.py  # S3 backup system
```

## Quick Start

### 1. Basic Rollback (Auto-detect Previous Deployment)

```bash
cd /Users/mikhail/StudioProjects/mita_project
python3 scripts/rollback/automated_rollback.py
```

### 2. Rollback to Specific Deployment

```bash
# List recent deployments first
python3 scripts/rollback/railway_deploy_manager.py list

# Rollback to specific deployment ID
python3 scripts/rollback/automated_rollback.py --deployment-id abc123def456
```

### 3. App-Only Rollback (Skip Database)

```bash
python3 scripts/rollback/automated_rollback.py --skip-db
```

### 4. Production Rollback

```bash
python3 scripts/rollback/automated_rollback.py \
  --base-url https://api.mita.finance \
  --reason "Error rate spike detected"
```

## Rollback Phases

### Phase 1: Pre-Rollback Validation (30-60s)

**Steps:**
1. Identify target deployment (auto-detect or specified)
2. Verify target deployment was successful
3. Create emergency database backup
4. Verify backup integrity
5. Lock deployment changes (circuit breaker OPEN)

**Success Criteria:**
- Target deployment exists and is within retention policy
- Target deployment status = SUCCESS
- Emergency backup created (warning only if fails)

### Phase 2: Database Rollback (60-90s) [Optional]

**Steps:**
1. Check current Alembic revision
2. Determine target revision
3. Execute `migration_manager.py rollback`
4. Verify database state

**Success Criteria:**
- Alembic downgrade completes without errors
- Database connectivity verified
- No long-running transactions blocking

**Safety Features:**
- Uses existing `migration_manager.py` (production-grade)
- Pre-migration backup automatically created
- Post-migration validation with automatic rollback on failure
- Migration locks prevent concurrent operations

**Skip Scenarios:**
- `--skip-db` flag specified
- Destructive migrations detected (DROP TABLE, DROP COLUMN)
- Migration manager not available

### Phase 3: Application Rollback (60-120s)

**Steps:**
1. Initiate Railway rollback via CLI
2. Monitor deployment progress
3. Wait for deployment success
4. Verify application startup

**Success Criteria:**
- Railway redeploy command succeeds
- Application responds to health checks within 2 minutes
- No startup errors in logs

**Railway Behavior:**
- Rolling update strategy (zero downtime)
- `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=30` (configurable)
- Both Docker image AND environment variables restored

### Phase 4: Health Verification (60-90s)

**Comprehensive 4-Phase Health Checks:**

#### Phase 4.1: Quick Verification (<5s)
- `GET /` - Basic health check
- `GET /health` - Simple health with database

#### Phase 4.2: Core Functionality (3-5s)
- `GET /health/production` - Database, Redis, system resources
- `GET /health/critical-services` - Core service status

#### Phase 4.3: Performance Validation (5-8s) **CRITICAL**
- `GET /health/performance` - **Timeout risk detection**
- `GET /health/comprehensive` - Middleware health
- **Fails if any component >5 seconds** (prevents 8-15+ second issues)

#### Phase 4.4: External Dependencies (2-4s)
- `GET /health/external-services` - OpenAI, SendGrid, Firebase
- `GET /health/circuit-breakers` - Circuit breaker states
- **Can be degraded without failing rollback** (80% threshold)

**Success Criteria:**
- All critical health checks return 200 OK
- No components exceed 5-second response time
- Database and Redis connectivity verified
- At least 80% of external services healthy

### Phase 5: Post-Rollback Validation (30-60s)

**Steps:**
1. Mark deployment as "last known good"
2. Update deployment history JSON
3. Send success notifications
4. Schedule circuit breaker reset (5 minutes)

**Success Criteria:**
- Deployment metadata saved
- Audit trail updated

## Total Timeline

| Phase | Target Time | Maximum Time |
|-------|------------|--------------|
| Phase 1: Pre-Validation | 30-60s | 90s |
| Phase 2: Database Rollback | 60-90s | 120s |
| Phase 3: App Rollback | 60-120s | 180s |
| Phase 4: Health Verification | 60-90s | 120s |
| Phase 5: Post-Validation | 30-60s | 60s |
| **TOTAL** | **240-420s (4-7 min)** | **570s (9.5 min)** |

**Target: <5 minutes achieved for app-only rollback (skip Phase 2)**

## Usage Examples

### List Recent Deployments

```bash
python3 scripts/rollback/railway_deploy_manager.py list --limit 20
```

Output:
```
Recent Deployments:
----------------------------------------------------------------------------------------------------
abc12345 | SUCCESS    | 1a2b3c4 | 2025-01-15 10:30:00
def67890 | SUCCESS    | 5d6e7f8 | 2025-01-15 09:15:00
ghi11121 | FAILED     | 9g0h1i2 | 2025-01-15 08:00:00
```

### Get Previous Successful Deployment

```bash
python3 scripts/rollback/railway_deploy_manager.py previous
```

### Check Deployment Status

```bash
python3 scripts/rollback/railway_deploy_manager.py status --deployment-id abc12345
```

### Validate Health After Manual Changes

```bash
python3 scripts/rollback/rollback_validation.py \
  --base-url https://api.mita.finance \
  --wait 30
```

Output:
```
================================================================================
ROLLBACK VALIDATION SUMMARY
================================================================================

Total Checks: 8
Total Duration: 18234ms (18.2s)

Phase 1: Quick Verification
  ✅ /                             125ms  healthy
  ✅ /health                        487ms  healthy

Phase 2: Core Functionality
  ✅ /health/production            2345ms  healthy
  ✅ /health/critical-services     1123ms  healthy

Phase 3: Performance Validation
  ✅ /health/performance           4567ms  healthy
  ✅ /health/comprehensive         3890ms  healthy

Phase 4: External Dependencies
  ✅ /health/external-services     1876ms  healthy
  ✅ /health/circuit-breakers       821ms  healthy

================================================================================
✅ Rollback validation PASSED
```

## Environment Configuration

### Required Environment Variables

```bash
# Railway Configuration
RAILWAY_PROJECT_ID=<your-project-id>
RAILWAY_SERVICE_ID=<your-service-id>
RAILWAY_TOKEN=<your-api-token>

# Application Configuration
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
OPENAI_API_KEY=sk-...

# Rollback Configuration (optional)
ROLLBACK_BASE_URL=https://api.mita.finance
RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=30
```

### Railway CLI Setup

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to project
railway link

# Verify connection
railway status
```

## Safety Features

### 1. Pre-Rollback Backup

- Automatically creates emergency database backup
- Uses existing `production_database_backup.py` (S3 storage)
- SHA256 checksum verification
- Continues if backup fails (with warning)

### 2. Migration Safety Checks

- Uses production-grade `migration_manager.py`
- PostgreSQL advisory locks prevent concurrent migrations
- Pre/post migration validation
- Automatic rollback on validation failure
- Destructive operation detection

### 3. Health Check Validation

- 4-phase comprehensive health checks
- Timeout risk detection (>5s components)
- Circuit breaker monitoring
- External service degradation tolerance

### 4. Deployment History Tracking

All rollback events logged to `deployment_history.json`:

```json
{
  "events": [
    {
      "type": "rollback",
      "timestamp": "2025-01-15T10:30:00Z",
      "target_deployment_id": "abc123",
      "git_sha": "1a2b3c4",
      "git_branch": "main",
      "trigger": "manual",
      "reason": "Error rate spike detected",
      "duration_seconds": 285.3,
      "success": true
    }
  ],
  "last_known_good": {
    "deployment_id": "abc123",
    "timestamp": "2025-01-15T10:35:00Z"
  }
}
```

### 5. Circuit Breaker Integration

- Circuit breaker set to OPEN during rollback
- Prevents new deployments during rollback
- Gradual reset to HALF_OPEN after 5 minutes
- Full reset to CLOSED when metrics stable

## Rollback Triggers

### Automatic Triggers (Coming Soon with Monitoring)

```python
# Error rate threshold
if error_rate > 0.00025:  # 0.025%
    trigger_rollback(RollbackTrigger.ERROR_RATE_THRESHOLD)

# Latency degradation
if p99_latency > 1000 or p99_latency > p50_latency * 3:
    trigger_rollback(RollbackTrigger.LATENCY_DEGRADATION)

# Health check failures
if consecutive_health_failures >= 3:
    trigger_rollback(RollbackTrigger.HEALTH_CHECK_FAILURE)

# Database errors
if db_pool_available < 0.1 or db_query_failure_rate > 0.1:
    trigger_rollback(RollbackTrigger.DATABASE_ERROR)
```

### Manual Triggers

```bash
# Manual rollback with reason
python3 scripts/rollback/automated_rollback.py \
  --reason "Deployment caused login issues"
```

## Troubleshooting

### Rollback Failed: "No previous successful deployment found"

**Cause:** All recent deployments failed or outside retention policy

**Solution:**
```bash
# List all deployments to find last successful
python3 scripts/rollback/railway_deploy_manager.py list --limit 50

# Manually specify deployment ID
python3 scripts/rollback/automated_rollback.py --deployment-id <id>
```

### Rollback Failed: "Database rollback failed"

**Cause:** Migration downgrade encountered error or timeout

**Solution:**
```bash
# Skip database rollback, app-only
python3 scripts/rollback/automated_rollback.py --skip-db

# Manual database investigation
alembic current
alembic history
alembic downgrade -1 --sql  # Dry run to see SQL
```

### Health Checks Failing: "Components exceed 5-second response time"

**Cause:** Performance degradation not fixed by rollback

**Solution:**
1. Check database for slow queries
2. Check Redis connectivity
3. Check external service (OpenAI, SendGrid) status
4. May need to rollback further to earlier deployment

### Railway CLI Timeout

**Cause:** Railway API connectivity issues or slow response

**Solution:**
```bash
# Check Railway status
railway status

# Re-authenticate
railway logout
railway login

# Verify project link
railway link
```

## Integration with Existing Systems

### 1. Migration Manager (`scripts/migration_manager.py`)

Rollback system uses existing migration manager for database safety:

```bash
# Called automatically by automated_rollback.py
python3 scripts/migration_manager.py rollback --target=-1
```

Features used:
- Migration locks (PostgreSQL advisory locks)
- Pre-migration backup
- Post-migration validation
- Automatic rollback on failure

### 2. Database Backup (`scripts/production_database_backup.py`)

Emergency backups created before rollback:

```bash
# Called automatically by automated_rollback.py
python3 scripts/production_database_backup.py backup --type=pre-rollback
```

Features used:
- S3 storage with versioning
- SHA256 checksum verification
- Compression (gzip level 9)
- Backup metadata tracking

### 3. Health Check Endpoints

Comprehensive health validation endpoints:

- `/health/production` - Database, Redis, system resources
- `/health/performance` - **Timeout risk detection**
- `/health/comprehensive` - Middleware health
- `/health/external-services` - OpenAI, SendGrid, Firebase
- `/health/circuit-breakers` - Circuit breaker states

## Monitoring & Alerting (Coming Soon)

### Slack Notifications

```python
# scripts/rollback/notify_stakeholders.py
await notify_slack(
    message="🚨 Automated rollback initiated",
    details={
        "trigger": "error_rate_threshold",
        "target_deployment": "abc123",
        "estimated_duration": "5 minutes"
    }
)
```

### Sentry Integration

```python
# Automatic Sentry event creation
sentry_sdk.capture_message(
    "Automated rollback completed",
    level="warning",
    extras={
        "duration_seconds": 285.3,
        "target_deployment_id": "abc123"
    }
)
```

### PagerDuty Escalation

```python
# Critical alerts for rollback failures
if not rollback_success:
    await pagerduty_alert(
        severity="critical",
        summary="Automated rollback failed - manual intervention required",
        runbook_url="https://docs.mita.finance/runbooks/failed-rollback"
    )
```

## Best Practices

### 1. Always Test in Staging First

```bash
# Test rollback in staging environment
python3 scripts/rollback/automated_rollback.py \
  --base-url https://staging.mita.finance
```

### 2. Document Deployment Changes

```bash
# Include rollback-safe flag in git commit
git commit -m "feat: Add user preferences endpoint

ROLLBACK_SAFE: Yes
DATABASE_CHANGES: None
BREAKING_CHANGES: None"
```

### 3. Regular Rollback Drills

```bash
# Monthly rollback drill (intentional)
# 1. Deploy test change to staging
# 2. Verify deployment successful
# 3. Execute rollback
# 4. Verify rollback successful
# 5. Document any issues discovered
```

### 4. Monitor Rollback Metrics

- Average rollback duration
- Success rate by deployment type
- Most common failure reasons
- Time to detect vs. time to rollback

### 5. Database Migration Guidelines

For rollback-safe migrations:

```python
# ✅ SAFE: Add nullable column
op.add_column('users', sa.Column('new_field', sa.String(), nullable=True))

# ✅ SAFE: Add new table
op.create_table('new_feature', ...)

# ⚠️ UNSAFE: Drop column (data loss)
# op.drop_column('users', 'old_field')  # DO NOT ROLLBACK

# ⚠️ UNSAFE: Add NOT NULL (requires backfill)
# op.alter_column('users', 'field', nullable=False)  # DO NOT ROLLBACK
```

## Future Enhancements

### Priority 1: Alerting Integration

- [ ] Slack webhook notifications
- [ ] PagerDuty escalation for failures
- [ ] Sentry event enrichment
- [ ] Email notification queue

### Priority 2: Blue-Green Deployment

- [ ] Parallel environment setup
- [ ] Traffic switching (0% → 100%)
- [ ] Instant rollback (<30 seconds)
- [ ] A/B testing support

### Priority 3: Canary Deployments

- [ ] Gradual rollout (5% → 25% → 50% → 100%)
- [ ] Automatic rollback on error rate increase
- [ ] Per-user canary targeting
- [ ] Metric comparison (canary vs. stable)

### Priority 4: Automated Trigger System

- [ ] Prometheus integration for metrics
- [ ] Automatic rollback on threshold breach
- [ ] Machine learning for anomaly detection
- [ ] Configurable trigger rules

## Support & Contact

**Development Team:**
- Mikhail Yakovlev (CEO/CTO) - mikhail@mita.finance

**Documentation:**
- Main roadmap: `PROJECT_VALUATION_AND_ROADMAP.md`
- Health checks: `app/api/health/`
- Migrations: `alembic/versions/`

**GitHub:**
- Issues: Report bugs and feature requests
- Pull requests: Contributions welcome

---

**Copyright © 2025 YAKOVLEV LTD - All Rights Reserved**

Built with ❤️ for reliable, fast production deployments.

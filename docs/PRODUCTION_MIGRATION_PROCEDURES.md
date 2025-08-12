# Production Migration Procedures for MITA Financial Application

## Overview

This document provides comprehensive procedures for safely executing database migrations in production for the MITA financial application. These procedures ensure zero downtime, data integrity, and compliance with financial regulations.

## Critical Requirements

### Financial Data Protection
- **NO data loss**: All financial data must be preserved
- **Decimal precision**: All monetary values use `Numeric(12,2)` not `Float`
- **Audit trail**: All schema changes must be logged and trackable
- **Regulatory compliance**: Maintain SOX and financial audit requirements

### Deployment Standards
- **Zero downtime**: Use blue-green or rolling deployments
- **Automated rollback**: Immediate rollback capability on failure
- **Data validation**: Pre/post migration data integrity checks
- **Monitoring**: Full observability during migrations

## Pre-Migration Checklist

### 1. Environment Preparation
- [ ] Verify all environment variables are set correctly
- [ ] Confirm database connection pools are properly configured
- [ ] Validate backup and restore procedures are working
- [ ] Check monitoring and alerting systems are operational
- [ ] Ensure emergency contact list is up to date

### 2. Code and Schema Review
- [ ] All migration files reviewed by senior engineer
- [ ] Financial data types validated (no Float for money)
- [ ] Foreign key constraints properly defined
- [ ] Indexes reviewed for performance impact
- [ ] Migration tested in staging environment identical to production

### 3. Backup and Recovery
- [ ] Full database backup completed and validated
- [ ] Backup restoration tested on staging environment
- [ ] Point-in-time recovery capability confirmed
- [ ] Recovery time objective (RTO) and recovery point objective (RPO) verified

### 4. Performance and Capacity
- [ ] Migration runtime estimated and approved
- [ ] Database size and growth projections reviewed
- [ ] Lock duration minimized and tested
- [ ] Resource utilization impact assessed

## Migration Execution Procedure

### Phase 1: Pre-Migration (T-30 minutes)

```bash
# 1. Acquire migration lock
python scripts/migration_manager.py lock --operation=migration

# 2. Create pre-migration backup
python scripts/production_database_backup.py backup --type=pre-migration

# 3. Verify database readiness
python scripts/production_database_backup.py verify-readiness

# 4. Final validation
python scripts/migration_manager.py status
```

### Phase 2: Migration Execution (T-0)

```bash
# 1. Enable maintenance mode (if applicable)
# kubectl patch deployment mita-backend -p '{"spec":{"replicas":0}}'

# 2. Run migration with full monitoring
python scripts/migration_manager.py migrate --target=head

# 3. Validate migration success
python scripts/migration_manager.py status
```

### Phase 3: Post-Migration Validation (T+5 minutes)

```bash
# 1. Data integrity checks
python -c "
import psycopg2
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Verify critical data counts
queries = {
    'users': 'SELECT COUNT(*) FROM users',
    'transactions': 'SELECT COUNT(*) FROM transactions',
    'total_amount': 'SELECT SUM(amount) FROM transactions'
}

for name, query in queries.items():
    cur.execute(query)
    result = cur.fetchone()[0]
    print(f'{name}: {result}')

# Check for data integrity issues
cur.execute('''
    SELECT 
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
        COUNT(*)
    FROM (
        SELECT 1 FROM transactions WHERE amount < 0
        UNION ALL
        SELECT 1 FROM goals WHERE target_amount < 0
    ) issues
''')

integrity_check = cur.fetchone()
print(f'Data integrity: {integrity_check[0]} ({integrity_check[1]} issues)')
conn.close()
"

# 2. Application health checks
curl -f http://localhost:8000/health/production

# 3. Financial calculation validation
python scripts/validate_financial_calculations.py
```

### Phase 4: Service Restoration

```bash
# 1. Restore application services
# kubectl patch deployment mita-backend -p '{"spec":{"replicas":3}}'

# 2. Verify all services are healthy
kubectl get pods -l app=mita-backend

# 3. Run smoke tests
python tests/integration/test_critical_paths.py
```

## Rollback Procedure

### Immediate Rollback (< 5 minutes from migration)

```bash
# 1. Acquire rollback lock
python scripts/migration_manager.py lock --operation=rollback

# 2. Execute Alembic rollback
python scripts/migration_manager.py rollback --target=PREVIOUS_REVISION

# 3. Validate rollback success
python scripts/migration_manager.py status
```

### Backup-Based Rollback (> 5 minutes from migration)

```bash
# 1. Stop application services
kubectl patch deployment mita-backend -p '{"spec":{"replicas":0}}'

# 2. Restore from pre-migration backup
python scripts/production_database_backup.py restore --backup-id=BACKUP_ID

# 3. Validate restoration
python scripts/production_database_backup.py validate --backup-id=BACKUP_ID

# 4. Restart services
kubectl patch deployment mita-backend -p '{"spec":{"replicas":3}}'
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Database Performance**
   - Connection pool utilization
   - Query response time
   - Lock wait times
   - Deadlock occurrences

2. **Application Health**
   - HTTP response codes
   - API latency (p95, p99)
   - Transaction success rates
   - Error rates

3. **Financial Data Integrity**
   - Transaction totals
   - User balance consistency
   - Goal tracking accuracy

### Alert Configuration

```yaml
# Example Prometheus alerts
groups:
  - name: migration-alerts
    rules:
      - alert: MigrationInProgress
        expr: migration_lock_active == 1
        for: 0s
        labels:
          severity: warning
        annotations:
          summary: "Database migration in progress"
          
      - alert: MigrationTimeout
        expr: migration_duration_seconds > 1800
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: "Migration taking longer than 30 minutes"
          
      - alert: DataIntegrityIssue
        expr: financial_data_integrity_check == 0
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: "Financial data integrity check failed"
```

## Emergency Contacts

- **Primary DBA**: [Contact Information]
- **DevOps Engineer**: [Contact Information]
- **Platform Lead**: [Contact Information]
- **On-Call Engineer**: [Contact Information]

## Compliance and Audit

### Required Documentation

1. **Migration Plan**: Detailed steps and timeline
2. **Risk Assessment**: Potential impacts and mitigation strategies
3. **Test Results**: Staging environment validation results
4. **Approval Records**: Sign-offs from required stakeholders
5. **Execution Log**: Detailed log of all commands executed
6. **Post-Migration Report**: Results and any issues encountered

### Audit Trail

All migration activities are logged to:
- Application logs: `/var/log/mita-migration.log`
- Database audit logs: PostgreSQL audit extension
- Kubernetes events: Migration job execution logs
- Monitoring systems: Grafana/Prometheus metrics

## Troubleshooting Guide

### Common Issues and Solutions

#### Migration Hangs or Times Out
```bash
# 1. Check for blocking locks
SELECT * FROM pg_locks WHERE NOT granted;

# 2. Identify blocking processes
SELECT pid, query, state FROM pg_stat_activity 
WHERE state != 'idle' AND query != '';

# 3. If safe, terminate blocking processes
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE state = 'idle in transaction' 
AND query_start < NOW() - INTERVAL '10 minutes';
```

#### Data Type Conversion Errors
```bash
# Check current data types
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND column_name LIKE '%amount%';

# Validate data before conversion
SELECT COUNT(*) FROM table_name 
WHERE column_name::text !~ '^[0-9]+\.?[0-9]*$';
```

#### Foreign Key Constraint Violations
```bash
# Find orphaned records
SELECT t.id FROM transactions t 
LEFT JOIN users u ON t.user_id = u.id 
WHERE u.id IS NULL;

# Clean up orphaned data (with caution)
DELETE FROM transactions 
WHERE user_id NOT IN (SELECT id FROM users);
```

## Testing Framework

### Staging Environment Requirements

The staging environment must be:
- Identical to production in terms of:
  - PostgreSQL version and configuration
  - Data volume (use anonymized production data subset)
  - Resource allocation (CPU, memory, storage)
  - Network configuration

### Migration Testing Script

```bash
#!/bin/bash
# scripts/test_migration_staging.sh

set -euo pipefail

echo "Starting staging migration test..."

# 1. Create staging data snapshot
python scripts/create_staging_snapshot.py

# 2. Run migration
python scripts/migration_manager.py migrate --target=head

# 3. Validate results
python scripts/validate_migration_results.py

# 4. Test rollback
python scripts/migration_manager.py rollback --target=PREVIOUS

# 5. Re-apply migration
python scripts/migration_manager.py migrate --target=head

echo "Staging migration test completed successfully"
```

## Performance Benchmarks

### Acceptable Migration Thresholds

- **Maximum duration**: 30 minutes
- **Lock time**: < 5 minutes for any single table
- **Performance degradation**: < 20% during migration
- **Recovery time**: < 5 minutes for rollback

### Optimization Strategies

1. **Minimize lock time**:
   - Use `ADD COLUMN ... DEFAULT NULL` instead of `NOT NULL`
   - Add constraints separately after data population
   - Use `CONCURRENTLY` for index creation

2. **Batch processing**:
   - Process large data updates in batches
   - Use `VACUUM ANALYZE` between large operations
   - Monitor transaction log size

3. **Resource management**:
   - Increase `maintenance_work_mem` during migration
   - Temporarily disable unnecessary triggers
   - Schedule during low-traffic periods

## Continuous Improvement

### Post-Migration Review

After each production migration:
1. Document actual vs. estimated duration
2. Record any issues encountered
3. Update procedures based on lessons learned
4. Review and improve monitoring/alerting

### Quarterly Reviews

- Migration procedure effectiveness
- Backup and recovery testing
- Performance trend analysis
- Compliance audit preparation

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-11  
**Next Review**: 2025-11-11  
**Owner**: DevOps Team
# MITA Finance - Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying MITA Finance to production with financial-grade security, reliability, and scalability.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Security Configuration](#security-configuration)
4. [Database Setup](#database-setup)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Monitoring and Alerting](#monitoring-and-alerting)
7. [Backup and Recovery](#backup-and-recovery)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Operations and Maintenance](#operations-and-maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Infrastructure Requirements

- **Kubernetes Cluster**: v1.25+ with at least 3 nodes
- **PostgreSQL**: v15+ with read replicas and automated backups
- **Redis**: v7+ with persistence and high availability
- **Load Balancer**: AWS ALB or equivalent with SSL termination
- **Container Registry**: GitHub Container Registry or AWS ECR
- **Object Storage**: AWS S3 or equivalent for backups and file storage
- **Monitoring**: Prometheus, Grafana, and Alertmanager
- **Logging**: ELK stack or equivalent centralized logging

### Security Requirements

- **SSL Certificates**: Valid certificates for all domains
- **Secrets Management**: Kubernetes secrets or external vault
- **Network Policies**: Implemented and tested
- **RBAC**: Role-based access control configured
- **Vulnerability Scanning**: Automated container and dependency scanning

---

## Environment Setup

### 1. Environment Variables

Copy the environment template and configure for production:

```bash
cp .env.example .env.production
```

**Critical Environment Variables (Must be configured):**

```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database (Use managed service in production)
DATABASE_URL=postgresql+asyncpg://user:password@prod-db:5432/mita?sslmode=require

# Redis (Use managed service in production)
REDIS_URL=redis://:password@prod-redis:6379/0

# Security Secrets (Generate strong, unique values)
JWT_SECRET=<32-character-minimum-secret>
JWT_PREVIOUS_SECRET=<previous-secret-for-rotation>
SECRET_KEY=<32-character-minimum-secret>

# External Services
OPENAI_API_KEY=<production-openai-key>
SENTRY_DSN=<production-sentry-dsn>

# Monitoring
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

# AWS Configuration
AWS_ACCESS_KEY_ID=<production-aws-key>
AWS_SECRET_ACCESS_KEY=<production-aws-secret>
BACKUP_BUCKET=mita-production-backups
```

### 2. Generate Production Secrets

Use these commands to generate secure secrets:

```bash
# JWT Secret (32+ characters)
openssl rand -base64 32

# Secret Key (32+ characters)  
openssl rand -base64 32

# Backup Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Security Configuration

### 1. Kubernetes Secrets

Create production secrets:

```bash
# Create namespace
kubectl create namespace mita-production

# Create secrets
kubectl create secret generic mita-production-secrets \
  --from-literal=database-url="postgresql+asyncpg://user:password@prod-db:5432/mita?sslmode=require" \
  --from-literal=redis-url="redis://:password@prod-redis:6379/0" \
  --from-literal=jwt-secret="<your-jwt-secret>" \
  --from-literal=secret-key="<your-secret-key>" \
  --from-literal=openai-api-key="<your-openai-key>" \
  --from-literal=sentry-dsn="<your-sentry-dsn>" \
  --from-literal=aws-access-key-id="<your-aws-key>" \
  --from-literal=aws-secret-access-key="<your-aws-secret>" \
  --from-literal=backup-encryption-key="<your-backup-key>" \
  -n mita-production
```

### 2. Network Policies

Apply network security policies:

```bash
kubectl apply -f k8s/security/network-policies.yaml -n mita-production
```

### 3. SSL/TLS Configuration

Ensure SSL certificates are properly configured:

```bash
# Using cert-manager (recommended)
kubectl apply -f k8s/security/certificate-issuer.yaml
```

---

## Database Setup

### 1. Database Migration

Run database migrations before deployment:

```bash
# Test migration (dry run)
kubectl apply -f k8s/mita/templates/migration-job.yaml --dry-run=client -n mita-production

# Apply migration
kubectl apply -f k8s/mita/templates/migration-job.yaml -n mita-production

# Monitor migration job
kubectl logs -f job/mita-production-migration-latest -n mita-production
```

### 2. Production Data Seeding

Seed essential production data:

```bash
# Apply seeding job
kubectl apply -f k8s/mita/templates/seed-data-job.yaml -n mita-production

# Monitor seeding
kubectl logs -f job/mita-production-seed-data-latest -n mita-production
```

### 3. Database Optimization

Apply production database indexes:

```bash
# Run index creation script
kubectl exec -it deployment/mita-production -n mita-production -- \
  python scripts/apply_database_indexes.py
```

---

## Kubernetes Deployment

### 1. Helm Deployment

Deploy using Helm with production values:

```bash
# Add/update Helm chart
helm repo add mita-finance ./k8s/mita
helm repo update

# Deploy to production
helm upgrade --install mita-production ./k8s/mita \
  --namespace mita-production \
  --create-namespace \
  --values k8s/mita/values-production.yaml \
  --set image.tag=v1.0.0 \
  --wait --timeout=15m

# Verify deployment
kubectl get pods -n mita-production
kubectl get services -n mita-production
kubectl get ingress -n mita-production
```

### 2. Production Values Configuration

Create `k8s/mita/values-production.yaml`:

```yaml
replicaCount: 3
environment: production

image:
  repository: ghcr.io/mita-finance/backend
  tag: v1.0.0

resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10

ingress:
  enabled: true
  host: mita.finance
  tls:
    enabled: true

monitoring:
  enabled: true

backup:
  enabled: true
  schedule: "0 2 * * *"
  bucket: s3://mita-production-backups

security:
  runAsNonRoot: true
  networkPolicy:
    enabled: true
```

### 3. Verify Deployment

```bash
# Check pod status
kubectl get pods -n mita-production

# Check service endpoints
kubectl get endpoints -n mita-production

# Test health checks
kubectl exec -it deployment/mita-production -n mita-production -- \
  curl -f http://localhost:8000/health

# Check logs
kubectl logs -l app=mita-production -n mita-production --tail=100
```

---

## Monitoring and Alerting

### 1. Prometheus Setup

Deploy Prometheus monitoring:

```bash
# Deploy Prometheus operator
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/prometheus-values.yaml
```

### 2. Grafana Dashboards

Import production dashboards:

```bash
# Apply dashboard configs
kubectl apply -f monitoring/grafana/ -n monitoring
```

### 3. Alerting Rules

Configure production alerts:

```bash
# Apply alert rules
kubectl apply -f monitoring/app_alert_rules.yml -n monitoring
kubectl apply -f monitoring/postgres_alert_rules.yml -n monitoring
kubectl apply -f monitoring/redis_alert_rules.yml -n monitoring
```

### 4. PagerDuty Integration

Configure critical alerts to PagerDuty:

```yaml
# In alertmanager config
route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'pagerduty-critical'
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty-critical'

receivers:
- name: 'pagerduty-critical'
  pagerduty_configs:
  - routing_key: '<your-pagerduty-integration-key>'
    description: 'MITA Finance Critical Alert'
```

---

## Backup and Recovery

### 1. Automated Backups

Verify backup CronJob is running:

```bash
# Check backup schedule
kubectl get cronjobs -n mita-production

# Test backup manually
kubectl create job mita-backup-manual --from=cronjob/mita-production-backup -n mita-production

# Monitor backup job
kubectl logs -f job/mita-backup-manual -n mita-production
```

### 2. Backup Verification

Test backup integrity:

```bash
# List recent backups
aws s3 ls s3://mita-production-backups/database_backups/ --recursive --human-readable

# Test restore (to staging environment)
python scripts/restore_backup.py --backup-key database_backups/2024/01/01/mita_db_backup_20240101_020000.sql.gz.enc
```

### 3. Disaster Recovery Procedures

**RTO: 1 hour | RPO: 15 minutes**

1. **Database Recovery**:
   ```bash
   # Restore from latest backup
   python scripts/restore_backup.py --latest --target-db production-restore
   
   # Switch application to restored database
   kubectl patch deployment mita-production -n mita-production -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"backend","env":[{"name":"DATABASE_URL","value":"<restored-db-url>"}]}]}}}}'
   ```

2. **Application Recovery**:
   ```bash
   # Scale up replicas
   kubectl scale deployment mita-production --replicas=3 -n mita-production
   
   # Verify health
   kubectl exec -it deployment/mita-production -n mita-production -- \
     curl -f http://localhost:8000/health/production
   ```

---

## CI/CD Pipeline

### 1. GitHub Actions Setup

The CI/CD pipeline is configured in `.github/workflows/ci-cd-production.yml`.

**Required GitHub Secrets:**

```bash
# Repository secrets (Settings -> Secrets and variables -> Actions)
KUBE_CONFIG_STAGING=<base64-encoded-kubeconfig>
KUBE_CONFIG_PRODUCTION=<base64-encoded-kubeconfig>
SECURITY_WEBHOOK_URL=<slack-or-teams-webhook>
WEBHOOK_URL=<deployment-notification-webhook>
```

### 2. Deployment Process

1. **Development**: Push to feature branches
2. **Testing**: Create PR to main branch (triggers tests)
3. **Staging**: Merge to main (auto-deploys to staging)
4. **Production**: Create release (triggers production deployment)

### 3. Release Process

```bash
# Create production release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# This triggers production deployment via GitHub Actions
```

---

## Operations and Maintenance

### 1. Health Monitoring

Monitor application health:

```bash
# Check comprehensive health
curl -f https://mita.finance/health/production

# Check specific services
curl -f https://mita.finance/health/database
curl -f https://mita.finance/health/redis

# View metrics
curl -f https://mita.finance/metrics
```

### 2. Log Management

Access application logs:

```bash
# View recent logs
kubectl logs -l app=mita-production -n mita-production --tail=100 -f

# View specific container logs
kubectl logs deployment/mita-production -c backend -n mita-production

# View error logs only
kubectl logs -l app=mita-production -n mita-production | grep ERROR
```

### 3. Performance Monitoring

Monitor key metrics:

```bash
# CPU and memory usage
kubectl top pods -n mita-production

# Database performance
kubectl exec -it deployment/mita-production -n mita-production -- \
  python scripts/explain_slow_queries.py

# API response times (via Grafana dashboard)
# Access: https://grafana.mita.finance/d/api-performance
```

### 4. Scaling Operations

Scale the application:

```bash
# Manual scaling
kubectl scale deployment mita-production --replicas=5 -n mita-production

# Check HPA status
kubectl get hpa -n mita-production

# View scaling events
kubectl describe hpa mita-production-hpa -n mita-production
```

### 5. Database Maintenance

Regular database maintenance:

```bash
# Run VACUUM ANALYZE (monthly)
kubectl exec -it deployment/mita-production -n mita-production -- \
  python -c "
import psycopg2
import os
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()
cur.execute('VACUUM ANALYZE;')
cur.close()
conn.close()
print('VACUUM ANALYZE completed')
"

# Check database size
kubectl exec -it deployment/mita-production -n mita-production -- \
  python scripts/database_stats.py
```

---

## Troubleshooting

### Common Issues

#### 1. Pod CrashLoopBackOff

```bash
# Check pod status
kubectl describe pod <pod-name> -n mita-production

# Check logs
kubectl logs <pod-name> -n mita-production --previous

# Common causes:
# - Database connection failure
# - Missing environment variables
# - Resource limits exceeded
```

#### 2. Database Connection Issues

```bash
# Test database connectivity
kubectl exec -it deployment/mita-production -n mita-production -- \
  python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    print('Database connection successful')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
"
```

#### 3. High Memory Usage

```bash
# Check memory usage
kubectl top pods -n mita-production

# Increase memory limits if needed
kubectl patch deployment mita-production -n mita-production -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"backend","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

#### 4. SSL Certificate Issues

```bash
# Check certificate status
kubectl describe certificate mita-tls-cert -n mita-production

# Renew certificate if needed
kubectl delete certificate mita-tls-cert -n mita-production
kubectl apply -f k8s/security/certificate.yaml -n mita-production
```

### Emergency Procedures

#### 1. Emergency Shutdown

```bash
# Scale down all pods
kubectl scale deployment mita-production --replicas=0 -n mita-production

# Block all ingress traffic
kubectl patch ingress mita-production-ingress -n mita-production -p \
  '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/whitelist-source-range":"127.0.0.1/32"}}}'
```

#### 2. Emergency Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/mita-production -n mita-production

# Check rollback status
kubectl rollout status deployment/mita-production -n mita-production
```

#### 3. Database Emergency Access

```bash
# Create emergency database access pod
kubectl run db-emergency --image=postgres:15 -it --rm --restart=Never \
  --env="PGPASSWORD=<password>" \
  -n mita-production -- \
  psql -h <db-host> -U <username> -d mita
```

---

## Security Checklist

Before going to production, verify:

- [ ] All environment variables are properly configured
- [ ] SSL certificates are valid and auto-renewing
- [ ] Database connections use SSL/TLS
- [ ] Secrets are stored securely (not in code)
- [ ] Network policies are implemented
- [ ] Container images are scanned for vulnerabilities
- [ ] RBAC is properly configured
- [ ] Backup encryption is enabled
- [ ] Monitoring and alerting are working
- [ ] Incident response procedures are documented

---

## Performance Optimization

### Database Optimization

```sql
-- Create performance indexes
CREATE INDEX CONCURRENTLY idx_users_email_lower ON users (LOWER(email));
CREATE INDEX CONCURRENTLY idx_transactions_user_date ON transactions (user_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_expenses_category ON expenses (category);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM transactions WHERE user_id = 123 ORDER BY created_at DESC LIMIT 10;
```

### Application Optimization

```bash
# Enable connection pooling
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db?pool_size=20&max_overflow=30"

# Configure Redis connection pooling
export REDIS_URL="redis://host:6379/0?max_connections=20"

# Optimize Python runtime
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1
```

---

## Compliance and Auditing

### Financial Compliance

- **PCI DSS**: Payment data handling (if applicable)
- **GDPR**: User data protection and privacy
- **SOX**: Financial reporting controls
- **Audit Trails**: All financial transactions logged

### Monitoring Compliance

```bash
# Check audit logs
kubectl logs -l app=mita-production -n mita-production | grep "AUDIT"

# Generate compliance report
python scripts/generate_compliance_report.py --start-date 2024-01-01 --end-date 2024-01-31
```

---

## Maintenance Schedule

### Daily
- [ ] Check application health endpoints
- [ ] Review error logs and alerts
- [ ] Verify backup completion
- [ ] Monitor resource usage

### Weekly
- [ ] Review security scan results
- [ ] Analyze performance metrics
- [ ] Update dependencies (if needed)
- [ ] Test disaster recovery procedures

### Monthly
- [ ] Database maintenance (VACUUM, ANALYZE)
- [ ] SSL certificate renewal check
- [ ] Security audit
- [ ] Capacity planning review
- [ ] Cost optimization review

### Quarterly
- [ ] Full disaster recovery test
- [ ] Security penetration testing
- [ ] Performance optimization review
- [ ] Architecture review and planning

---

## Support and Escalation

### Contact Information

- **DevOps Team**: devops@mita.finance
- **Security Team**: security@mita.finance  
- **On-Call Engineer**: +1-XXX-XXX-XXXX
- **PagerDuty**: [MITA Finance Production](https://mita-finance.pagerduty.com)

### Escalation Matrix

1. **P0 (Critical)**: Production down, data loss, security breach
   - Response: Immediate (< 15 minutes)
   - Escalate: CTO, CEO

2. **P1 (High)**: Major functionality impaired
   - Response: < 1 hour
   - Escalate: Engineering Manager

3. **P2 (Medium)**: Minor functionality issues
   - Response: < 4 hours
   - Escalate: Team Lead

4. **P3 (Low)**: Enhancement requests, minor bugs
   - Response: < 24 hours
   - Escalate: Product Manager

---

This production deployment guide ensures MITA Finance can be deployed and operated with financial-grade reliability, security, and compliance. Regular updates to this documentation are essential as the system evolves.
# MITA Finance - Emergency Secret Rotation Runbook

## Overview

This runbook provides step-by-step procedures for emergency secret rotation in the MITA Finance platform. Emergency rotation may be required due to security breaches, suspected compromise, compliance violations, or other critical security incidents.

**🚨 CRITICAL: This is a financial services platform. All procedures must maintain 99.9% uptime and ensure zero data loss.**

## When to Use This Runbook

### Immediate Emergency Rotation Required:
- ✅ Confirmed security breach involving secrets
- ✅ Suspected secret compromise or exposure
- ✅ Unauthorized access to secret management systems
- ✅ Regulatory compliance violation involving secrets
- ✅ Former employee with secret access (termination)

### Schedule Regular Rotation Instead:
- ❌ Routine maintenance
- ❌ Planned upgrades
- ❌ Non-urgent compliance updates

## Pre-Requisites

### Personnel Requirements:
- **Primary Operator**: Senior DevOps Engineer (on-call rotation)
- **Security Officer**: Must be present for all emergency rotations
- **Compliance Officer**: Required for production rotations
- **Application Team Lead**: Available for validation

### Access Requirements:
- [ ] AWS Console access with SecretsManager:* permissions
- [ ] Kubernetes cluster admin access
- [ ] PagerDuty incident commander privileges
- [ ] Emergency contact list access

### Tools Required:
- [ ] AWS CLI configured with production credentials
- [ ] kubectl configured for production cluster
- [ ] Helm v3.12+
- [ ] Emergency rotation scripts
- [ ] Monitoring dashboard access

## Emergency Response Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Detection** | 0-15 min | Incident identification, team assembly |
| **Assessment** | 15-30 min | Impact analysis, rotation scope determination |
| **Execution** | 30-90 min | Secret rotation, application updates |
| **Validation** | 90-120 min | System validation, monitoring verification |
| **Post-Incident** | 120+ min | Documentation, lessons learned |

## Phase 1: Emergency Detection & Assembly (0-15 minutes)

### Step 1: Incident Declaration
```bash
# Create PagerDuty incident
curl -X POST "https://api.pagerduty.com/incidents" \
  -H "Authorization: Token token=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "type": "incident",
      "title": "EMERGENCY: Secret Rotation Required - MITA Finance",
      "service": {
        "id": "PXXXXXX",
        "type": "service_reference"
      },
      "priority": {
        "id": "PXXXXXX",
        "type": "priority_reference"
      },
      "urgency": "high",
      "body": {
        "type": "incident_body",
        "details": "Emergency secret rotation required. Potential security compromise."
      }
    }
  }'
```

### Step 2: Team Assembly
1. **Page the on-call rotation team**
2. **Notify security officer immediately**
3. **Alert compliance team** (for production)
4. **Brief application team leads**

### Step 3: Initial Assessment
```bash
# Quick system health check
kubectl get pods -n mita-production | grep -E "(Error|CrashLoopBackOff)"
kubectl get externalsecrets -n mita-production
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `mita-finance/production`)]'
```

## Phase 2: Impact Assessment (15-30 minutes)

### Step 1: Determine Rotation Scope

#### Critical Secrets (Rotate Immediately):
- [ ] Database credentials
- [ ] JWT signing keys
- [ ] Application encryption keys
- [ ] Redis authentication

#### High Priority Secrets (Rotate Within 1 Hour):
- [ ] OpenAI API keys
- [ ] AWS backup credentials
- [ ] Monitoring service credentials

#### Medium/Low Priority (Can Wait):
- [ ] SMTP credentials
- [ ] Apple push notification credentials
- [ ] Third-party integrations

### Step 2: Impact Analysis
```bash
# Check current secret usage
kubectl get pods -n mita-production -o json | jq '.items[] | select(.spec.containers[].env[]? | select(.valueFrom.secretKeyRef)) | .metadata.name'

# Verify External Secrets Operator health
kubectl get pods -n external-secrets-system
kubectl logs -n external-secrets-system deployment/external-secrets
```

### Step 3: Document Current State
```bash
# Save current secret versions
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `mita-finance/production`)].[Name,VersionIdsToStages]' \
  --output table > /tmp/secret-versions-before.txt
```

## Phase 3: Emergency Rotation Execution (30-90 minutes)

### Step 1: Enable Maintenance Mode (If Required)
```bash
# Scale down to minimum replicas if needed (only for critical breaches)
kubectl patch deployment mita-production -n mita-production -p '{"spec":{"replicas":1}}'

# Enable maintenance page (if absolutely necessary)
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: maintenance-mode
  namespace: mita-production
data:
  enabled: "true"
  message: "Emergency maintenance in progress. Service will be restored shortly."
EOF
```

### Step 2: Critical Secret Rotation

#### Database Credentials Rotation:
```bash
# 1. Generate new database password
NEW_DB_PASSWORD=$(openssl rand -base64 32)

# 2. Update AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/database/primary" \
  --secret-string "{
    \"username\": \"mita_app\",
    \"password\": \"$NEW_DB_PASSWORD\",
    \"host\": \"mita-prod-db.cluster-xxx.amazonaws.com\",
    \"port\": 5432,
    \"database\": \"mita\",
    \"connection_string\": \"postgresql://mita_app:$NEW_DB_PASSWORD@mita-prod-db.cluster-xxx.amazonaws.com:5432/mita\"
  }"

# 3. Update database user password
kubectl exec -it deployment/mita-production -n mita-production -- psql $DATABASE_URL -c "ALTER USER mita_app WITH PASSWORD '$NEW_DB_PASSWORD';"

# 4. Force External Secret refresh
kubectl annotate externalsecret mita-production-database-credentials -n mita-production force-sync="$(date +%s)"
```

#### JWT Secret Rotation:
```bash
# 1. Generate new JWT secret
NEW_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Move current secret to previous
CURRENT_JWT=$(aws secretsmanager get-secret-value --secret-id "mita-finance/production/auth/jwt-secret" --query SecretString --output text | jq -r '.value')

# 3. Update JWT secrets
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/auth/jwt-previous-secret" \
  --secret-string "{\"value\": \"$CURRENT_JWT\", \"rotated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

aws secretsmanager update-secret \
  --secret-id "mita-finance/production/auth/jwt-secret" \
  --secret-string "{\"value\": \"$NEW_JWT_SECRET\", \"rotated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

# 4. Force refresh
kubectl annotate externalsecret mita-production-auth-secrets -n mita-production force-sync="$(date +%s)"
```

#### Application Secret Key Rotation:
```bash
# 1. Generate new application secret
NEW_APP_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Update secret
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/app/secret-key" \
  --secret-string "{\"value\": \"$NEW_APP_SECRET\", \"rotated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

# 3. Force refresh
kubectl annotate externalsecret mita-production-auth-secrets -n mita-production force-sync="$(date +%s)"
```

### Step 3: Redis Credentials Rotation:
```bash
# 1. Generate new Redis password
NEW_REDIS_PASSWORD=$(openssl rand -base64 32)

# 2. Update Redis configuration (if using AWS ElastiCache)
aws elasticache modify-replication-group \
  --replication-group-id mita-production-redis \
  --auth-token "$NEW_REDIS_PASSWORD" \
  --auth-token-update-strategy ROTATE

# 3. Update secret in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/cache/redis-auth" \
  --secret-string "{
    \"password\": \"$NEW_REDIS_PASSWORD\",
    \"host\": \"mita-production-redis.xxx.cache.amazonaws.com\",
    \"port\": 6379,
    \"connection_string\": \"redis://:$NEW_REDIS_PASSWORD@mita-production-redis.xxx.cache.amazonaws.com:6379/0\"
  }"

# 4. Force refresh
kubectl annotate externalsecret mita-production-redis-credentials -n mita-production force-sync="$(date +%s)"
```

### Step 4: Application Restart Strategy
```bash
# Option 1: Rolling restart (preferred)
kubectl rollout restart deployment/mita-production -n mita-production

# Option 2: Immediate restart (if rolling restart fails)
kubectl scale deployment mita-production --replicas=0 -n mita-production
sleep 10
kubectl scale deployment mita-production --replicas=3 -n mita-production

# Monitor restart
kubectl rollout status deployment/mita-production -n mita-production --timeout=300s
```

## Phase 4: Validation & Verification (90-120 minutes)

### Step 1: System Health Validation
```bash
# 1. Check pod status
kubectl get pods -n mita-production -l app=mita-production

# 2. Check External Secrets sync
kubectl get externalsecrets -n mita-production -o wide

# 3. Test database connectivity
kubectl exec -it deployment/mita-production -n mita-production -- python -c "
import psycopg2
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('Database connection successful')
conn.close()
"

# 4. Test Redis connectivity
kubectl exec -it deployment/mita-production -n mita-production -- python -c "
import redis
import os
r = redis.from_url(os.environ['REDIS_URL'])
r.ping()
print('Redis connection successful')
"
```

### Step 2: Application Health Checks
```bash
# 1. Health endpoint
curl -f https://mita.finance/health

# 2. Database health
curl -f https://mita.finance/api/health/database

# 3. Authentication test (JWT)
curl -X POST https://mita.finance/api/auth/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# 4. API functionality test
curl -f https://mita.finance/api/health/services
```

### Step 3: Performance Validation
```bash
# 1. Check response times
curl -w "@curl-format.txt" -s -o /dev/null https://mita.finance/health

# 2. Load test (if available)
kubectl run load-test --rm -i --tty --image=loadimpact/k6:latest -- run - <<EOF
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  let response = http.get('https://mita.finance/health');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
EOF
```

### Step 4: Monitoring Verification
```bash
# 1. Check Grafana dashboards
open "https://grafana.mita.finance/d/mita-secret-management/mita-finance-secret-management-dashboard"

# 2. Verify Prometheus metrics
curl -s "https://prometheus.mita.finance/api/v1/query?query=up{job=\"mita-production\"}" | jq '.data.result[0].value[1]'

# 3. Check for new alerts
curl -s "https://prometheus.mita.finance/api/v1/alerts" | jq '.data.alerts[] | select(.state=="firing")'
```

## Phase 5: Post-Incident Activities (120+ minutes)

### Step 1: Security Verification
```bash
# 1. Verify old secrets are invalidated
aws secretsmanager describe-secret \
  --secret-id "mita-finance/production/auth/jwt-secret" \
  --query 'VersionIdsToStages'

# 2. Check audit logs
aws logs filter-log-events \
  --log-group-name "/aws/secretsmanager/mita/production/audit" \
  --start-time $(date -d '2 hours ago' +%s)000 \
  --query 'events[].message'

# 3. Review access patterns
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --start-time $(date -d '2 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date +%Y-%m-%dT%H:%M:%S)
```

### Step 2: Documentation & Reporting
```bash
# 1. Generate secret rotation report
python3 /opt/mita/scripts/generate-rotation-report.py \
  --environment production \
  --incident-id "$(date +%Y%m%d-%H%M%S)" \
  --output /tmp/rotation-report.html

# 2. Update compliance records
echo "$(date): Emergency secret rotation completed - Incident: $INCIDENT_ID" >> /var/log/mita/compliance-log.txt

# 3. Notify stakeholders
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "#security-alerts",
    "text": "🔒 Emergency secret rotation completed successfully",
    "attachments": [{
      "color": "good",
      "fields": [{
        "title": "Status",
        "value": "All systems operational",
        "short": true
      },{
        "title": "Rotated Secrets",
        "value": "Database, JWT, App Key, Redis",
        "short": true
      }]
    }]
  }'
```

### Step 3: Lessons Learned
1. **Document what triggered the emergency rotation**
2. **Identify any gaps in the process**
3. **Update runbooks based on learnings**
4. **Schedule team retrospective within 24 hours**

### Step 4: Disable Maintenance Mode
```bash
# Remove maintenance mode
kubectl delete configmap maintenance-mode -n mita-production

# Restore full capacity
kubectl scale deployment mita-production --replicas=3 -n mita-production

# Verify full service restoration
kubectl get deployment mita-production -n mita-production
```

## Recovery Procedures (If Rotation Fails)

### Emergency Rollback
```bash
# 1. Rollback application deployment
kubectl rollout undo deployment/mita-production -n mita-production

# 2. Restore previous secrets (if absolutely necessary)
# CAUTION: Only if new secrets are proven to be the issue
aws secretsmanager restore-secret \
  --secret-id "mita-finance/production/auth/jwt-secret" \
  --version-id "PREVIOUS_VERSION_ID"

# 3. Force immediate External Secret resync
kubectl delete pods -n external-secrets-system -l app.kubernetes.io/name=external-secrets
kubectl wait --for=condition=ready pod -n external-secrets-system -l app.kubernetes.io/name=external-secrets

# 4. Restart application
kubectl rollout restart deployment/mita-production -n mita-production
```

### Disaster Recovery
If primary AWS region is unavailable:
```bash
# 1. Switch to DR region
export AWS_DEFAULT_REGION=us-west-2
aws configure set default.region us-west-2

# 2. Activate secret replicas
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `mita-finance/production`)].Name' \
  --output text | while read secret; do
    echo "Activating DR replica for $secret"
    aws secretsmanager describe-secret --secret-id "$secret"
done

# 3. Update External Secret Store configuration
kubectl patch secretstore mita-production-secrets -n mita-production --type merge -p '{
  "spec": {
    "provider": {
      "aws": {
        "region": "us-west-2"
      }
    }
  }
}'
```

## Contact Information

### Emergency Contacts
- **DevOps On-Call**: +1-XXX-XXX-XXXX
- **Security Team**: security@mita.finance
- **Compliance Officer**: compliance@mita.finance
- **CTO**: +1-XXX-XXX-XXXX (critical incidents only)

### External Services
- **AWS Support**: Premium Support Case
- **PagerDuty**: https://mita-finance.pagerduty.com
- **Slack**: #incident-response

## Compliance Notes

This runbook ensures compliance with:
- **SOX**: All changes logged and approved
- **PCI DSS**: Secrets handling meets security requirements
- **GDPR**: Data protection maintained during rotation

**Audit Trail**: All actions in this runbook are logged automatically to `/var/log/mita/emergency-rotation.log`
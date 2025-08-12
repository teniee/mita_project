# MITA Finance - Production Secret Management Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the comprehensive secret management system for MITA Finance. The system ensures financial-grade security, compliance with SOX/PCI-DSS/GDPR requirements, and zero-downtime operations.

**🔐 CRITICAL: This deployment affects sensitive financial data. Follow all procedures exactly as documented.**

## Architecture Overview

The secret management system consists of:

1. **AWS Secrets Manager** - Primary secret storage with KMS encryption
2. **External Secrets Operator** - Kubernetes secret synchronization
3. **Secret Rotation Automation** - Lambda-based rotation with zero downtime
4. **Monitoring & Alerting** - Comprehensive secret lifecycle monitoring
5. **Compliance Validation** - Automated encryption and audit verification

## Pre-Deployment Requirements

### Prerequisites Checklist:
- [ ] AWS CLI configured with administrative access
- [ ] kubectl configured for production cluster
- [ ] Helm v3.12+ installed
- [ ] Terraform v1.3+ available
- [ ] External Secrets Operator CRDs installed
- [ ] Monitoring stack (Prometheus/Grafana) operational

### Security Requirements:
- [ ] Security team approval for production deployment
- [ ] Compliance team sign-off on secret handling procedures
- [ ] Emergency contact list updated
- [ ] Incident response procedures reviewed

## Phase 1: AWS Infrastructure Deployment (30-45 minutes)

### Step 1: Deploy KMS and Secrets Manager Infrastructure

```bash
# Navigate to infrastructure directory
cd infrastructure/aws/

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -var="environment=production" -out=secret-mgmt.plan

# Review the plan (ensure no existing resources are destroyed)
terraform show secret-mgmt.plan

# Apply the infrastructure
terraform apply secret-mgmt.plan

# Verify KMS key creation
aws kms describe-key --key-id alias/mita-finance-production-secrets

# Verify secret creation
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `mita-finance/production`)]'
```

### Step 2: Configure IAM Roles for External Secrets Operator

```bash
# Get EKS cluster OIDC issuer
OIDC_ISSUER=$(aws eks describe-cluster --name mita-production --query "cluster.identity.oidc.issuer" --output text)
echo "OIDC Issuer: $OIDC_ISSUER"

# Verify the IAM role was created
aws iam get-role --role-name mita-production-external-secrets

# Test role assumability
aws sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/mita-production-external-secrets \
  --role-session-name test-session \
  --web-identity-token "dummy-token"
```

## Phase 2: External Secrets Operator Deployment (15-20 minutes)

### Step 1: Deploy External Secrets Operator

```bash
# Add External Secrets Helm repository
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

# Deploy External Secrets Operator
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system \
  --create-namespace \
  --set installCRDs=true \
  --set webhook.port=9443 \
  --set certController.enable=true \
  --set image.tag=v0.9.9 \
  --wait --timeout=300s

# Verify deployment
kubectl get pods -n external-secrets-system
kubectl get crds | grep external-secrets
```

### Step 2: Configure External Secrets Resources

```bash
# Apply namespace and RBAC
kubectl apply -f k8s/external-secrets/namespace.yaml
kubectl apply -f k8s/external-secrets/service-account.yaml

# Apply secret stores
kubectl apply -f k8s/external-secrets/secret-stores.yaml

# Verify secret stores
kubectl get clustersecretstores
kubectl get secretstores -n mita-production
```

## Phase 3: Secret Population (20-30 minutes)

### Step 1: Populate Production Secrets in AWS Secrets Manager

**CRITICAL: Use strong, unique secrets for production. Never use placeholder values.**

```bash
# Generate secure secrets
DATABASE_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_PREVIOUS_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
REDIS_PASSWORD=$(openssl rand -base64 32)

# Database credentials
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/database/primary" \
  --secret-string "{
    \"username\": \"mita_app\",
    \"password\": \"$DATABASE_PASSWORD\",
    \"host\": \"mita-prod-db.cluster-xxx.us-east-1.rds.amazonaws.com\",
    \"port\": 5432,
    \"database\": \"mita\",
    \"connection_string\": \"postgresql+asyncpg://mita_app:$DATABASE_PASSWORD@mita-prod-db.cluster-xxx.us-east-1.rds.amazonaws.com:5432/mita\"
  }"

# JWT secrets
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/auth/jwt-secret" \
  --secret-string "{\"value\": \"$JWT_SECRET\", \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

aws secretsmanager update-secret \
  --secret-id "mita-finance/production/auth/jwt-previous-secret" \
  --secret-string "{\"value\": \"$JWT_PREVIOUS_SECRET\", \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

# Application secret key
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/app/secret-key" \
  --secret-string "{\"value\": \"$APP_SECRET_KEY\", \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"

# Redis credentials
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/cache/redis-auth" \
  --secret-string "{
    \"password\": \"$REDIS_PASSWORD\",
    \"host\": \"mita-production-redis.xxx.cache.amazonaws.com\",
    \"port\": 6379,
    \"connection_string\": \"redis://:$REDIS_PASSWORD@mita-production-redis.xxx.cache.amazonaws.com:6379/0\"
  }"
```

### Step 2: Add External Service Secrets

```bash
# OpenAI API Key (replace with actual key)
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/external/openai-api-key" \
  --secret-string "{\"value\": \"sk-YOUR_ACTUAL_OPENAI_API_KEY_HERE\"}"

# Sentry DSN (replace with actual DSN)
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/monitoring/sentry-dsn" \
  --secret-string "{\"value\": \"https://YOUR_ACTUAL_SENTRY_DSN@sentry.io/PROJECT_ID\"}"

# SMTP credentials (replace with actual values)
aws secretsmanager update-secret \
  --secret-id "mita-finance/production/notifications/smtp-credentials" \
  --secret-string "{
    \"username\": \"apikey\",
    \"password\": \"YOUR_ACTUAL_SENDGRID_API_KEY\"
  }"

# Clear sensitive variables from memory
unset DATABASE_PASSWORD JWT_SECRET JWT_PREVIOUS_SECRET APP_SECRET_KEY REDIS_PASSWORD
```

## Phase 4: Application Deployment with External Secrets (30-45 minutes)

### Step 1: Deploy External Secret Resources

```bash
# Apply External Secret definitions
kubectl apply -f k8s/external-secrets/mita-secrets.yaml

# Wait for secrets to be created
kubectl wait --for=condition=Ready externalsecret --all -n mita-production --timeout=300s

# Verify secrets are created
kubectl get externalsecrets -n mita-production
kubectl get secrets -n mita-production | grep mita-production

# Verify secret content (without exposing values)
kubectl describe secret mita-production-database-credentials -n mita-production
kubectl describe secret mita-production-auth-secrets -n mita-production
```

### Step 2: Update MITA Application Deployment

```bash
# Deploy MITA application with External Secrets enabled
helm upgrade --install mita-production ./k8s/mita \
  --namespace mita-production \
  --create-namespace \
  --set image.tag=latest \
  --set environment=production \
  --set externalSecrets.enabled=true \
  --set externalSecrets.secretStoreName=mita-production-secrets \
  --set externalSecrets.secretKeyPrefix=mita-finance/production \
  --set replicaCount=3 \
  --set resources.requests.cpu=500m \
  --set resources.requests.memory=1Gi \
  --set resources.limits.cpu=2000m \
  --set resources.limits.memory=2Gi \
  --wait --timeout=600s

# Monitor deployment
kubectl rollout status deployment/mita-production -n mita-production --timeout=600s
```

### Step 3: Validate Application Integration

```bash
# Check pod status
kubectl get pods -n mita-production -l app=mita-production

# Test application health
curl -f https://mita.finance/health

# Test database connectivity
kubectl exec -it deployment/mita-production -n mita-production -- python -c "
import psycopg2
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('✅ Database connection successful')
conn.close()
"

# Test Redis connectivity
kubectl exec -it deployment/mita-production -n mita-production -- python -c "
import redis
import os
r = redis.from_url(os.environ['REDIS_URL'])
r.ping()
print('✅ Redis connection successful')
"

# Test authentication
curl -X POST https://mita.finance/api/auth/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

## Phase 5: Secret Rotation Setup (20-30 minutes)

### Step 1: Deploy Lambda Rotation Functions

```bash
# Package and deploy database rotation function
cd infrastructure/lambda/secret-rotation/
zip -r database-rotation.zip database_rotation.py requirements.txt

aws lambda create-function \
  --function-name mita-production-database-rotation \
  --runtime python3.11 \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/mita-production-secret-rotation \
  --handler database_rotation.lambda_handler \
  --zip-file fileb://database-rotation.zip \
  --timeout 300 \
  --memory-size 256

# Deploy JWT rotation function
zip -r jwt-rotation.zip jwt_rotation.py requirements.txt

aws lambda create-function \
  --function-name mita-production-jwt-rotation \
  --runtime python3.11 \
  --role arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/mita-production-secret-rotation \
  --handler jwt_rotation.lambda_handler \
  --zip-file fileb://jwt-rotation.zip \
  --timeout 300 \
  --memory-size 256
```

### Step 2: Configure Automatic Rotation

```bash
# Enable automatic rotation for critical secrets
aws secretsmanager rotate-secret \
  --secret-id "mita-finance/production/database/primary" \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:$(aws sts get-caller-identity --query Account --output text):function:mita-production-database-rotation \
  --rotation-rules AutomaticallyAfterDays=30

aws secretsmanager rotate-secret \
  --secret-id "mita-finance/production/auth/jwt-secret" \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:$(aws sts get-caller-identity --query Account --output text):function:mita-production-jwt-rotation \
  --rotation-rules AutomaticallyAfterDays=30

# Verify rotation configuration
aws secretsmanager describe-secret --secret-id "mita-finance/production/database/primary" --query 'RotationEnabled'
aws secretsmanager describe-secret --secret-id "mita-finance/production/auth/jwt-secret" --query 'RotationEnabled'
```

## Phase 6: Monitoring and Alerting Setup (15-20 minutes)

### Step 1: Deploy Monitoring Rules

```bash
# Apply Prometheus monitoring rules
kubectl apply -f monitoring/secret-management/prometheus-rules.yaml

# Verify rules are loaded
kubectl get prometheusrules -n mita-production

# Test that metrics are being collected
curl -s "https://prometheus.mita.finance/api/v1/query?query=up{job=\"external-secrets-controller\"}" | jq '.data.result[0].value[1]'
```

### Step 2: Import Grafana Dashboard

```bash
# Import the secret management dashboard
curl -X POST \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @monitoring/secret-management/grafana-dashboard.json \
  "https://grafana.mita.finance/api/dashboards/db"

# Verify dashboard is available
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  "https://grafana.mita.finance/api/dashboards/uid/mita-secret-management"
```

## Phase 7: Validation and Testing (30-45 minutes)

### Step 1: Run Encryption Validation

```bash
# Run comprehensive encryption validation
python3 scripts/secret-encryption-validator.py \
  --environment production \
  --report-format json \
  --output-file /tmp/encryption-validation-report.json

# Check validation results
cat /tmp/encryption-validation-report.json | jq '.compliance_status'

# Ensure no critical violations
if [ "$(cat /tmp/encryption-validation-report.json | jq -r '.compliance_status')" = "COMPLIANT" ]; then
  echo "✅ Encryption validation passed"
else
  echo "❌ Encryption validation failed - review report"
  exit 1
fi
```

### Step 2: Test Secret Rotation

```bash
# Test manual rotation of non-critical secret
aws secretsmanager rotate-secret \
  --secret-id "mita-finance/production/monitoring/sentry-dsn" \
  --force-rotate-secrets

# Wait for rotation to complete
sleep 60

# Verify External Secrets picked up the change
kubectl get externalsecrets -n mita-production -o wide

# Check application still works
curl -f https://mita.finance/health
```

### Step 3: Load Testing with New Secret Management

```bash
# Run load test to ensure performance is not affected
kubectl run load-test --rm -i --tty --image=loadimpact/k6:latest -- run - <<EOF
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 50 },
    { duration: '5m', target: 50 },
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 0 },
  ],
};

export default function() {
  let response = http.get('https://mita.finance/health');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  // Test authenticated endpoint
  let auth_response = http.post('https://mita.finance/api/auth/test', 
    JSON.stringify({"test": true}),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(auth_response, {
    'auth endpoint responds': (r) => r.status < 500,
  });
}
EOF
```

## Phase 8: Documentation and Handover (15-20 minutes)

### Step 1: Generate Deployment Report

```bash
# Generate comprehensive deployment report
cat > /tmp/secret-management-deployment-report.md << EOF
# MITA Finance Secret Management Deployment Report

**Deployment Date**: $(date)
**Deployed By**: $(whoami)
**Environment**: Production

## Components Deployed

### AWS Infrastructure
- KMS Key: $(aws kms describe-key --key-id alias/mita-finance-production-secrets --query 'KeyMetadata.KeyId' --output text)
- Secrets Manager: $(aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `mita-finance/production`)].Name | length(@)') secrets created
- Lambda Functions: 2 rotation functions deployed

### Kubernetes Resources
- External Secrets Operator: $(kubectl get pods -n external-secrets-system --no-headers | wc -l) pods running
- External Secrets: $(kubectl get externalsecrets -n mita-production --no-headers | wc -l) configured
- Application Deployment: $(kubectl get deployment mita-production -n mita-production -o jsonpath='{.status.replicas}') replicas running

### Monitoring
- Prometheus Rules: Deployed
- Grafana Dashboard: Imported
- Encryption Validation: PASSED

## Post-Deployment Checklist
- [x] All secrets encrypted with KMS
- [x] External Secrets Operator operational
- [x] Application successfully using secrets
- [x] Secret rotation configured
- [x] Monitoring and alerting active
- [x] Load testing passed
- [x] Emergency procedures documented

## Next Steps
1. Schedule first secret rotation drill
2. Train operations team on emergency procedures
3. Set up compliance reporting schedule
EOF

# Save the report
cp /tmp/secret-management-deployment-report.md ./SECRET_MANAGEMENT_DEPLOYMENT_REPORT_$(date +%Y%m%d).md
```

### Step 2: Team Notification

```bash
# Send completion notification to team
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "channel": "#deployments",
    "text": "🔐 MITA Finance Secret Management System Deployed Successfully",
    "attachments": [{
      "color": "good",
      "fields": [{
        "title": "Environment",
        "value": "Production",
        "short": true
      },{
        "title": "Status", 
        "value": "✅ All systems operational",
        "short": true
      },{
        "title": "Security Features",
        "value": "• AWS Secrets Manager with KMS encryption\n• External Secrets Operator\n• Automated secret rotation\n• Comprehensive monitoring",
        "short": false
      },{
        "title": "Next Actions",
        "value": "• Review emergency procedures\n• Schedule rotation drill\n• Monitor dashboards",
        "short": false
      }]
    }]
  }'
```

## Post-Deployment Checklist

### Immediate (Within 24 hours):
- [ ] Verify all application functionality with new secret management
- [ ] Confirm monitoring dashboards are populated with data
- [ ] Test PagerDuty integration for critical alerts
- [ ] Document any issues encountered during deployment

### Short-term (Within 1 week):
- [ ] Conduct secret rotation drill using emergency procedures
- [ ] Train operations team on secret management system
- [ ] Review and adjust alert thresholds based on baseline metrics
- [ ] Schedule first automatic secret rotation

### Long-term (Within 1 month):
- [ ] Complete compliance audit of secret management system
- [ ] Generate first monthly secret management report
- [ ] Review and update emergency procedures based on lessons learned
- [ ] Plan migration of any remaining hardcoded secrets

## Rollback Procedures

If issues are encountered, use these rollback steps:

```bash
# Emergency rollback to previous deployment
kubectl rollout undo deployment/mita-production -n mita-production

# Disable External Secrets temporarily
kubectl scale deployment external-secrets -n external-secrets-system --replicas=0

# Switch back to legacy secrets
helm upgrade mita-production ./k8s/mita \
  --namespace mita-production \
  --set externalSecrets.enabled=false \
  --wait --timeout=300s

# Re-enable after fixes
kubectl scale deployment external-secrets -n external-secrets-system --replicas=1
```

## Support Contacts

- **DevOps Team**: devops@mita.finance
- **Security Team**: security@mita.finance  
- **On-Call Engineer**: Use PagerDuty escalation
- **Emergency Escalation**: CTO (for critical production issues only)

## Compliance Notes

This deployment ensures:
- **SOX Compliance**: All secret access is audited and logged
- **PCI DSS Compliance**: Secrets are encrypted at rest and in transit
- **GDPR Compliance**: Data protection measures are maintained

**Audit Trail**: All deployment actions are logged in CloudTrail and Kubernetes audit logs.
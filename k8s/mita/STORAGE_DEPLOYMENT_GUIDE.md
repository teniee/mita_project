# MITA Production Storage Infrastructure Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying production-grade storage infrastructure for the MITA financial application. The infrastructure includes managed databases, object storage, CDN, disaster recovery, backup automation, performance optimization, and security scanning.

## Architecture Overview

### Core Storage Components
- **PostgreSQL RDS**: Primary database with read replicas and automated backups
- **Redis ElastiCache**: Session store and task queue with high availability
- **S3 Storage**: Document storage with lifecycle policies and cross-region replication
- **CloudFront CDN**: Global content delivery with security headers and WAF
- **PgBouncer**: Connection pooling for database performance optimization

### Security & Compliance
- **AWS Security Hub**: Centralized security findings management
- **AWS GuardDuty**: Threat detection and monitoring
- **AWS Config**: Compliance monitoring and configuration tracking
- **KMS Encryption**: All data encrypted at rest and in transit
- **IAM Policies**: Least privilege access with service accounts

### Disaster Recovery
- **Cross-Region Replication**: Automated backup replication to DR region
- **Automated Failover**: Lambda-based DR automation with RTO of 1 hour
- **Backup Verification**: Automated testing of backup integrity
- **Runbook Procedures**: Documented recovery procedures

### Monitoring & Alerting
- **CloudWatch Dashboards**: Comprehensive storage monitoring
- **Prometheus Integration**: Custom metrics and alerting
- **PagerDuty Integration**: Critical alert escalation
- **Performance Insights**: Database performance monitoring

## Prerequisites

### AWS Account Setup
- AWS account with appropriate permissions
- AWS CLI configured with production credentials
- Terraform >= 1.5.0 installed
- kubectl configured for EKS cluster access

### Required IAM Permissions
```bash
# Create IAM user for infrastructure deployment
aws iam create-user --user-name mita-infrastructure-deploy

# Attach required policies
aws iam attach-user-policy --user-name mita-infrastructure-deploy \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

aws iam attach-user-policy --user-name mita-infrastructure-deploy \
  --policy-arn arn:aws:iam::aws:policy/IAMFullAccess
```

### Environment Variables
```bash
export AWS_ACCOUNT_ID="123456789012"
export AWS_REGION="us-east-1"
export DR_REGION="us-west-2"
export CLUSTER_NAME="mita-production"
export DOMAIN_NAME="mita.finance"
export ENVIRONMENT="production"
```

## Deployment Steps

### Phase 1: Core Infrastructure

#### 1.1 Deploy VPC and Networking (if not already done)
```bash
# Create VPC for production environment
terraform -chdir=infrastructure/vpc init
terraform -chdir=infrastructure/vpc plan -var="cluster_name=${CLUSTER_NAME}"
terraform -chdir=infrastructure/vpc apply -auto-approve
```

#### 1.2 Deploy KMS Keys for Encryption
```bash
# Apply KMS configuration from RDS config
terraform -chdir=infrastructure/kms init
terraform -chdir=infrastructure/kms plan
terraform -chdir=infrastructure/kms apply -auto-approve

# Export KMS key ARNs
export RDS_KMS_KEY_ARN=$(terraform -chdir=infrastructure/kms output -raw rds_kms_key_arn)
export REDIS_KMS_KEY_ARN=$(terraform -chdir=infrastructure/kms output -raw redis_kms_key_arn)
export S3_KMS_KEY_ARN=$(terraform -chdir=infrastructure/kms output -raw s3_kms_key_arn)
export BACKUP_KMS_KEY_ARN=$(terraform -chdir=infrastructure/kms output -raw backup_kms_key_arn)
```

### Phase 2: Managed Database Services

#### 2.1 Deploy PostgreSQL RDS
```bash
# Deploy primary PostgreSQL instance
terraform -chdir=infrastructure/rds init
terraform -chdir=infrastructure/rds plan \
  -var="vpc_id=${VPC_ID}" \
  -var="private_subnet_ids=${PRIVATE_SUBNET_IDS}" \
  -var="kms_key_arn=${RDS_KMS_KEY_ARN}"
terraform -chdir=infrastructure/rds apply -auto-approve

# Export RDS endpoints
export RDS_ENDPOINT=$(terraform -chdir=infrastructure/rds output -raw rds_endpoint)
export RDS_READ_REPLICA_ENDPOINT=$(terraform -chdir=infrastructure/rds output -raw rds_read_replica_endpoint)
export DB_SECRET_ARN=$(terraform -chdir=infrastructure/rds output -raw secret_arn)
```

#### 2.2 Deploy Redis ElastiCache
```bash
# Deploy Redis clusters
terraform -chdir=infrastructure/redis init
terraform -chdir=infrastructure/redis plan \
  -var="vpc_id=${VPC_ID}" \
  -var="private_subnet_ids=${PRIVATE_SUBNET_IDS}" \
  -var="kms_key_arn=${REDIS_KMS_KEY_ARN}"
terraform -chdir=infrastructure/redis apply -auto-approve

# Export Redis endpoints
export REDIS_ENDPOINT=$(terraform -chdir=infrastructure/redis output -raw redis_primary_endpoint)
export REDIS_TASKQUEUE_ENDPOINT=$(terraform -chdir=infrastructure/redis output -raw redis_taskqueue_primary_endpoint)
export REDIS_SECRET_ARN=$(terraform -chdir=infrastructure/redis output -raw redis_secret_arn)
```

### Phase 3: Object Storage and CDN

#### 3.1 Deploy S3 Storage Infrastructure
```bash
# Deploy S3 buckets with lifecycle policies
terraform -chdir=infrastructure/s3 init
terraform -chdir=infrastructure/s3 plan \
  -var="kms_key_arn=${S3_KMS_KEY_ARN}"
terraform -chdir=infrastructure/s3 apply -auto-approve

# Export S3 bucket details
export DOCUMENTS_BUCKET=$(terraform -chdir=infrastructure/s3 output -raw documents_bucket_name)
export DOCUMENTS_BUCKET_ARN=$(terraform -chdir=infrastructure/s3 output -raw documents_bucket_arn)
export BACKUP_BUCKET=$(terraform -chdir=infrastructure/s3 output -raw backup_bucket_name)
export BACKUP_BUCKET_ARN=$(terraform -chdir=infrastructure/s3 output -raw backup_bucket_arn)
```

#### 3.2 Deploy CloudFront CDN
```bash
# Deploy CDN with WAF protection
terraform -chdir=infrastructure/cloudfront init
terraform -chdir=infrastructure/cloudfront plan \
  -var="documents_bucket_name=${DOCUMENTS_BUCKET}" \
  -var="domain_name=${DOMAIN_NAME}"
terraform -chdir=infrastructure/cloudfront apply -auto-approve

# Export CDN details
export CDN_DOMAIN=$(terraform -chdir=infrastructure/cloudfront output -raw cloudfront_distribution_domain_name)
export WAF_ACL_ARN=$(terraform -chdir=infrastructure/cloudfront output -raw waf_web_acl_arn)
```

### Phase 4: Disaster Recovery

#### 4.1 Deploy DR Infrastructure
```bash
# Deploy disaster recovery infrastructure
terraform -chdir=infrastructure/disaster-recovery init
terraform -chdir=infrastructure/disaster-recovery plan \
  -var="dr_region=${DR_REGION}" \
  -var="primary_rds_instance_arn=arn:aws:rds:${AWS_REGION}:${AWS_ACCOUNT_ID}:db:mita-postgresql-prod" \
  -var="primary_rds_instance_identifier=mita-postgresql-prod"
terraform -chdir=infrastructure/disaster-recovery apply -auto-approve

# Export DR details
export DR_RDS_ENDPOINT=$(terraform -chdir=infrastructure/disaster-recovery output -raw dr_rds_endpoint)
export DR_LAMBDA_ARN=$(terraform -chdir=infrastructure/disaster-recovery output -raw dr_lambda_function_arn)
```

### Phase 5: Backup Orchestration

#### 5.1 Deploy Backup Automation
```bash
# Deploy backup orchestration with Step Functions
terraform -chdir=infrastructure/backup-orchestration init
terraform -chdir=infrastructure/backup-orchestration plan \
  -var="backup_bucket_name=${BACKUP_BUCKET}" \
  -var="backup_bucket_arn=${BACKUP_BUCKET_ARN}" \
  -var="documents_bucket_name=${DOCUMENTS_BUCKET}" \
  -var="documents_bucket_arn=${DOCUMENTS_BUCKET_ARN}" \
  -var="rds_instance_identifier=mita-postgresql-prod" \
  -var="redis_cluster_id=mita-redis-prod" \
  -var="backup_kms_key_arn=${BACKUP_KMS_KEY_ARN}" \
  -var="s3_kms_key_arn=${S3_KMS_KEY_ARN}"
terraform -chdir=infrastructure/backup-orchestration apply -auto-approve

# Export backup details
export BACKUP_STATE_MACHINE_ARN=$(terraform -chdir=infrastructure/backup-orchestration output -raw backup_state_machine_arn)
```

### Phase 6: Security and Compliance

#### 6.1 Deploy Security Scanning
```bash
# Deploy security scanning infrastructure
terraform -chdir=infrastructure/security-scanning init
terraform -chdir=infrastructure/security-scanning plan \
  -var="documents_bucket_name=${DOCUMENTS_BUCKET}" \
  -var="documents_bucket_arn=${DOCUMENTS_BUCKET_ARN}" \
  -var="backup_bucket_name=${BACKUP_BUCKET}" \
  -var="backup_bucket_arn=${BACKUP_BUCKET_ARN}" \
  -var="rds_instance_identifier=mita-postgresql-prod" \
  -var="redis_cluster_id=mita-redis-prod"
terraform -chdir=infrastructure/security-scanning apply -auto-approve

# Export security details
export SECURITY_HUB_ARN=$(terraform -chdir=infrastructure/security-scanning output -raw security_hub_arn)
export GUARDDUTY_DETECTOR_ID=$(terraform -chdir=infrastructure/security-scanning output -raw guardduty_detector_id)
```

#### 6.2 Deploy IAM Policies
```bash
# Deploy IAM roles and policies
terraform -chdir=infrastructure/iam-policies init
terraform -chdir=infrastructure/iam-policies plan \
  -var="eks_cluster_name=${CLUSTER_NAME}" \
  -var="eks_oidc_provider_arn=${EKS_OIDC_PROVIDER_ARN}" \
  -var="documents_bucket_arn=${DOCUMENTS_BUCKET_ARN}" \
  -var="backup_bucket_arn=${BACKUP_BUCKET_ARN}" \
  -var="database_secret_arn=${DB_SECRET_ARN}" \
  -var="redis_secret_arn=${REDIS_SECRET_ARN}" \
  -var="rds_instance_identifier=mita-postgresql-prod"
terraform -chdir=infrastructure/iam-policies apply -auto-approve
```

### Phase 7: Kubernetes Components

#### 7.1 Create Kubernetes Namespace
```bash
# Create production namespace
kubectl create namespace mita-production

# Label namespace for security
kubectl label namespace mita-production \
  environment=production \
  compliance=pci-dss \
  monitoring=enabled
```

#### 7.2 Deploy Connection Pooling
```bash
# Create database secrets
kubectl create secret generic mita-database-config \
  --from-literal=host="pgbouncer.mita-production.svc.cluster.local" \
  --from-literal=port="5432" \
  --from-literal=username="mita_app" \
  --from-literal=database="mita" \
  --from-literal=password="$(aws secretsmanager get-secret-value --secret-id ${DB_SECRET_ARN} --query SecretString --output text | jq -r .password)" \
  --namespace=mita-production

# Deploy PgBouncer
kubectl apply -f infrastructure/connection-pooling.yaml

# Wait for PgBouncer to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=pgbouncer -n mita-production --timeout=300s
```

#### 7.3 Deploy Storage Monitoring
```bash
# Apply storage monitoring configuration
kubectl apply -f infrastructure/storage-monitoring.yaml

# Apply Prometheus rules
kubectl apply -f infrastructure/prometheus-rules.yaml
```

#### 7.4 Deploy Security Scanning CronJobs
```bash
# Apply security scanning configuration
kubectl apply -f infrastructure/storage-security-scanning.yaml

# Verify security scanner service account
kubectl get serviceaccount mita-security-scanner -n mita-production
```

### Phase 8: Application Integration

#### 8.1 Update Application Configuration
```bash
# Update Helm values for storage integration
cat > storage-values.yaml << EOF
database:
  host: pgbouncer.mita-production.svc.cluster.local
  port: 5432
  name: mita
  secretName: mita-database-config

redis:
  primary:
    host: ${REDIS_ENDPOINT}
    port: 6379
    secretName: mita-redis-config
  taskqueue:
    host: ${REDIS_TASKQUEUE_ENDPOINT}
    port: 6379
    secretName: mita-redis-taskqueue-config

storage:
  documents:
    bucket: ${DOCUMENTS_BUCKET}
    region: ${AWS_REGION}
  cdn:
    domain: ${CDN_DOMAIN}

monitoring:
  enabled: true
  metrics:
    enabled: true
  alerting:
    enabled: true
EOF

# Deploy application with storage configuration
helm upgrade mita ./k8s/mita \
  --namespace mita-production \
  --values storage-values.yaml \
  --wait
```

## Verification and Testing

### 1. Database Connectivity Test
```bash
# Test database connection through PgBouncer
kubectl exec -it deployment/mita -n mita-production -- \
  psql -h pgbouncer.mita-production.svc.cluster.local -U mita_app -d mita -c "SELECT 1;"
```

### 2. Redis Connectivity Test
```bash
# Test Redis connection
kubectl exec -it deployment/mita -n mita-production -- \
  redis-cli -h ${REDIS_ENDPOINT} -p 6379 ping
```

### 3. S3 Access Test
```bash
# Test S3 access
kubectl exec -it deployment/mita -n mita-production -- \
  aws s3 ls s3://${DOCUMENTS_BUCKET}/
```

### 4. Backup Test
```bash
# Trigger manual backup
aws stepfunctions start-execution \
  --state-machine-arn ${BACKUP_STATE_MACHINE_ARN} \
  --input '{"backup_type": "manual", "test": true}'
```

### 5. DR Test
```bash
# Trigger DR test
aws lambda invoke \
  --function-name mita-dr-automation \
  --payload '{"operation": "test", "test_type": "connectivity"}' \
  /tmp/dr-test-result.json

cat /tmp/dr-test-result.json
```

### 6. Security Scan Test
```bash
# Trigger security scan
aws lambda invoke \
  --function-name mita-security-scanner \
  --payload '{"scan_type": "basic"}' \
  /tmp/security-scan-result.json

cat /tmp/security-scan-result.json
```

## Monitoring and Alerting Setup

### 1. Access CloudWatch Dashboards
```bash
# Get dashboard URLs
echo "Storage Dashboard: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=MITA-Storage-Infrastructure"
echo "Backup Dashboard: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=MITA-Backup-Operations"
echo "Security Dashboard: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=MITA-Security-Monitoring"
```

### 2. Configure PagerDuty Integration
```bash
# Create SNS topic for PagerDuty integration
aws sns create-topic --name mita-pagerduty-alerts

# Subscribe PagerDuty integration to SNS topics
aws sns subscribe \
  --topic-arn arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:mita-pagerduty-alerts \
  --protocol https \
  --notification-endpoint https://events.pagerduty.com/integration/YOUR_INTEGRATION_KEY/enqueue
```

### 3. Set Up Grafana Dashboards
```bash
# Import Grafana dashboard
kubectl apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: mita-storage-dashboard
  namespace: mita-production
  labels:
    grafana_dashboard: "1"
data:
  mita-storage.json: |
$(cat infrastructure/storage-monitoring.yaml | grep -A 1000 "mita-storage-dashboard.json" | tail -n +2)
EOF
```

## Security Configuration

### 1. Enable Security Features
```bash
# Enable GuardDuty findings export
aws guardduty create-publishing-destination \
  --detector-id ${GUARDDUTY_DETECTOR_ID} \
  --destination-type S3 \
  --destination-properties DestinationArn=arn:aws:s3:::${BACKUP_BUCKET}/guardduty-findings,KmsKeyArn=${BACKUP_KMS_KEY_ARN}
```

### 2. Configure Security Hub Integrations
```bash
# Enable Security Hub standards
aws securityhub batch-enable-standards \
  --standards-subscription-requests StandardsArn=arn:aws:securityhub:::ruleset/finding-format/aws-foundational-security \
  --standards-subscription-requests StandardsArn=arn:aws:securityhub:${AWS_REGION}::standard/pci-dss/v/3.2.1
```

## Maintenance Procedures

### 1. Regular Maintenance Tasks
```bash
# Create maintenance cron jobs
kubectl apply -f - << EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: monthly-dr-test
  namespace: mita-production
spec:
  schedule: "0 2 1 * *"  # First day of month at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: dr-test
            image: amazon/aws-cli:latest
            command:
            - aws
            - lambda
            - invoke
            - --function-name
            - mita-dr-automation
            - --payload
            - '{"operation": "test", "test_type": "full"}'
            - /tmp/result.json
EOF
```

### 2. Performance Optimization
```bash
# Schedule weekly database optimization
kubectl apply -f infrastructure/connection-pooling.yaml
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Database Connection Issues
```bash
# Check PgBouncer status
kubectl logs -l app.kubernetes.io/name=pgbouncer -n mita-production

# Check database connectivity
kubectl exec -it deployment/pgbouncer -n mita-production -- \
  psql -h ${RDS_ENDPOINT} -U mita_admin -d mita -c "SELECT 1;"
```

#### 2. Redis Connection Issues
```bash
# Check Redis cluster status
aws elasticache describe-replication-groups \
  --replication-group-id mita-redis-prod

# Check Redis connectivity
kubectl exec -it deployment/mita -n mita-production -- \
  redis-cli -h ${REDIS_ENDPOINT} -p 6379 ping
```

#### 3. Backup Failures
```bash
# Check backup state machine execution
aws stepfunctions list-executions \
  --state-machine-arn ${BACKUP_STATE_MACHINE_ARN} \
  --status-filter FAILED

# Check backup Lambda logs
aws logs describe-log-streams \
  --log-group-name /aws/lambda/mita-backup-database
```

#### 4. Security Scan Issues
```bash
# Check security scanner logs
aws logs tail /aws/lambda/mita-security-scanner --follow

# Check Security Hub findings
aws securityhub get-findings \
  --filters ProductArn=arn:aws:securityhub:${AWS_REGION}::product/mita-finance/storage-scanner
```

## Cost Optimization

### 1. Storage Cost Analysis
```bash
# Generate cost report
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

### 2. Optimization Recommendations
- Monitor S3 storage classes and lifecycle transitions
- Review RDS instance sizing based on utilization
- Optimize backup retention periods
- Use Reserved Instances for predictable workloads

## Compliance and Auditing

### 1. Compliance Reporting
```bash
# Generate compliance report
aws lambda invoke \
  --function-name mita-compliance-report \
  --payload '{"report_type": "monthly"}' \
  /tmp/compliance-report.json
```

### 2. Audit Log Access
```bash
# Access CloudTrail logs
aws s3 ls s3://mita-finance-audit-logs/storage-audit/

# Review Config compliance
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name s3-bucket-server-side-encryption-enabled
```

## Disaster Recovery Testing

### 1. Quarterly DR Test
```bash
# Schedule quarterly DR test
aws events put-rule \
  --name mita-quarterly-dr-test \
  --schedule-expression "cron(0 2 1 */3 *)" \
  --description "Quarterly disaster recovery test"

aws events put-targets \
  --rule mita-quarterly-dr-test \
  --targets Id=1,Arn=${DR_LAMBDA_ARN},Input='{"operation":"test","test_type":"full"}'
```

### 2. Recovery Procedures
Refer to `/infrastructure/disaster-recovery.yaml` ConfigMap `dr-runbook` for detailed recovery procedures.

## Support and Escalation

### Contact Information
- **Level 1 Support**: DevOps Team (24/7 on-call rotation)
- **Level 2 Support**: Senior DevOps + DBA (Business hours + critical incidents)
- **Level 3 Support**: Architecture Team + Vendor Support
- **Level 4 Escalation**: Management + Board notification

### Emergency Procedures
1. **Critical Data Loss**: Immediate escalation to Level 3
2. **Security Breach**: Immediate escalation to Security Team + Management
3. **Extended Outage (>2 hours)**: Level 4 escalation
4. **Compliance Violation**: Immediate escalation to Compliance Officer

---

## Deployment Completion Checklist

- [ ] Core infrastructure deployed and verified
- [ ] Database services operational with connection pooling
- [ ] Object storage configured with lifecycle policies
- [ ] CDN deployed with security headers and WAF
- [ ] Disaster recovery infrastructure tested
- [ ] Backup automation verified and scheduled
- [ ] Security scanning operational
- [ ] Monitoring dashboards accessible
- [ ] Alert integrations configured
- [ ] Application successfully connected to storage
- [ ] Performance benchmarks established
- [ ] Compliance checks passing
- [ ] Documentation updated
- [ ] Team training completed

---

**Document Version**: 1.0  
**Last Updated**: $(date)  
**Review Schedule**: Quarterly  
**Next Review**: $(date -d "+3 months")  

For questions or issues, contact the DevOps team or refer to the troubleshooting section above.
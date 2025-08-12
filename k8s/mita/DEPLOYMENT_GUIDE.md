# MITA Financial Application - Kubernetes Deployment Guide

This document provides a comprehensive guide for deploying the MITA financial application on Kubernetes using Helm charts with production-ready configurations.

## 🏗️ Architecture Overview

The MITA Kubernetes deployment consists of the following components:

### Core Application Services
- **Backend API**: FastAPI application with horizontal pod autoscaling
- **Worker Deployments**: Multi-tier worker system (high-priority, regular, low-priority)
- **Task Scheduler**: Centralized task orchestration and management
- **Ingress Controller**: NGINX with enhanced security and SSL termination

### Operational Components
- **External Secrets Operator**: Secure secret management with AWS Secrets Manager
- **CronJobs**: Automated maintenance, backup, and subscription refresh
- **Monitoring Stack**: Prometheus, Grafana integration with custom metrics
- **RBAC**: Role-based access control with least privilege principles

## 📋 Prerequisites

### Required Infrastructure
- Kubernetes cluster v1.24+
- Helm v3.8+
- External Secrets Operator installed
- Prometheus Operator (for monitoring)
- NGINX Ingress Controller
- cert-manager for SSL certificates

### AWS Services
- Amazon EKS cluster (recommended)
- AWS Secrets Manager for secret storage
- S3 buckets for backups
- IAM roles for service accounts (IRSA)

### External Dependencies
- PostgreSQL database with read replicas
- Redis cluster for caching and task queues
- SMTP service (SendGrid recommended)
- OpenAI API access

## 🚀 Quick Start

1. **Clone and Navigate to Chart Directory**
```bash
git clone <repository-url>
cd k8s/mita/
```

2. **Configure Values**
```bash
cp values.yaml values-production.yaml
# Edit values-production.yaml with your environment-specific settings
```

3. **Install External Secrets**
```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets --namespace external-secrets-system --create-namespace
```

4. **Deploy MITA Application**
```bash
helm install mita . -f values-production.yaml --namespace mita-production --create-namespace
```

## 🔧 Configuration

### Environment-Specific Values

Create environment-specific value files:

**Production (`values-production.yaml`)**:
```yaml
environment: production
replicaCount: 3
debug: false

ingress:
  enabled: true
  host: mita.finance
  tls:
    enabled: true

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10

externalSecrets:
  enabled: true
  secretStoreName: mita-production-secrets
```

**Staging (`values-staging.yaml`)**:
```yaml
environment: staging
replicaCount: 2
debug: true

ingress:
  enabled: true
  host: staging.mita.finance

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
```

### Secret Management Configuration

Configure AWS Secrets Manager integration:

1. **Create IAM Roles**
```bash
# External Secrets Operator role
aws iam create-role --role-name mita-external-secrets-role --assume-role-policy-document file://external-secrets-trust-policy.json

# Application service account role
aws iam create-role --role-name mita-app-role --assume-role-policy-document file://app-trust-policy.json
```

2. **Configure Secret Store**
```bash
kubectl apply -f k8s/external-secrets/
```

3. **Update values.yaml**
```yaml
aws:
  serviceAccount:
    roleArn: "arn:aws:iam::ACCOUNT:role/mita-app-role"
  externalSecrets:
    roleArn: "arn:aws:iam::ACCOUNT:role/mita-external-secrets-role"
```

## 📊 Monitoring and Observability

### Prometheus Integration

The deployment includes comprehensive monitoring:

- **ServiceMonitors**: Automatic metrics collection from all components
- **PrometheusRules**: Financial services-specific alerting rules
- **Custom Metrics**: Business logic and compliance monitoring

### Key Metrics

| Metric Category | Purpose | SLA |
|----------------|---------|-----|
| API Response Time | User experience | < 2s (95th percentile) |
| Transaction Processing | Revenue critical | 99.9% success rate |
| Database Connections | Resource monitoring | < 80% utilization |
| Queue Depth | Task processing | < 10 for high priority |
| Authentication Failures | Security monitoring | < 10/second spike detection |

### Grafana Dashboards

Import dashboard configurations from `monitoring/grafana/`:

```bash
kubectl apply -f monitoring/grafana/
```

## 🔐 Security Configuration

### RBAC and Service Accounts

The deployment creates multiple service accounts with least-privilege access:

- **mita**: Main application service account
- **mita-external-secrets**: Secret synchronization
- **mita-backup**: Backup operations
- **mita-monitoring**: Metrics collection

### Network Policies

Network policies isolate traffic:

```yaml
networkPolicy:
  enabled: true
  ingress:
    - from:
      - namespaceSelector:
          matchLabels:
            name: nginx-ingress
```

### Pod Security Standards

All pods run with restricted security contexts:

```yaml
security:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
      - ALL
```

## 🔄 Operational Procedures

### Deployment

1. **Blue-Green Deployment**
```bash
# Deploy to staging environment
helm upgrade mita . -f values-staging.yaml --namespace mita-staging

# Validate deployment
kubectl get pods -n mita-staging
kubectl logs -l app.kubernetes.io/name=mita -n mita-staging

# Promote to production
helm upgrade mita . -f values-production.yaml --namespace mita-production
```

2. **Rolling Updates**
```bash
# Update image tag
helm upgrade mita . --set image.tag=v1.2.3 --namespace mita-production
```

### Backup Operations

Automated backups run via CronJobs:

- **Database Backup**: Daily at 2 AM UTC
- **Configuration Backup**: Weekly
- **Secret Rotation**: Weekly on Mondays

Manual backup:
```bash
kubectl create job --from=cronjob/mita-backup backup-manual-$(date +%Y%m%d)
```

### Scaling Operations

**Manual Scaling**:
```bash
# Scale backend
kubectl scale deployment mita --replicas=5 -n mita-production

# Scale workers
kubectl scale deployment mita-worker-high-priority --replicas=3 -n mita-production
```

**Auto-scaling Configuration**:
```yaml
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
```

## 🚨 Troubleshooting

### Common Issues

1. **ExternalSecrets Not Syncing**
```bash
# Check External Secrets status
kubectl get externalsecrets -n mita-production
kubectl describe externalsecret mita-database-credentials -n mita-production

# Verify IAM permissions
kubectl logs -l app.kubernetes.io/name=external-secrets -n external-secrets-system
```

2. **Pods Not Starting**
```bash
# Check pod status and events
kubectl describe pod <pod-name> -n mita-production
kubectl logs <pod-name> -n mita-production --previous
```

3. **Database Connection Issues**
```bash
# Test database connectivity
kubectl exec -it deployment/mita -n mita-production -- python -c "
import asyncpg
import os
conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
print('Database connection successful')
"
```

### Monitoring and Alerts

**Access Grafana Dashboard**:
```bash
kubectl port-forward svc/grafana 3000:3000 -n monitoring
# Access http://localhost:3000
```

**Check Prometheus Metrics**:
```bash
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
# Access http://localhost:9090
```

**View Alert Manager**:
```bash
kubectl port-forward svc/alertmanager 9093:9093 -n monitoring
# Access http://localhost:9093
```

## 📈 Performance Tuning

### Resource Optimization

**Backend Pods**:
```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 2Gi
```

**Worker Optimization**:
- High Priority: More CPU for OCR/AI processing
- Regular Priority: Balanced resources
- Low Priority: Minimal resources, spot instances

### Database Optimization

- Use read replicas for read-heavy operations
- Connection pooling configuration
- Query optimization and indexing

## 🔄 Disaster Recovery

### RTO/RPO Targets
- **RTO**: 1 hour
- **RPO**: 15 minutes

### Recovery Procedures

1. **Database Recovery**
```bash
# Restore from backup
kubectl apply -f backup/restore-job.yaml
```

2. **Application Recovery**
```bash
# Redeploy from known good configuration
helm rollback mita <revision-number> -n mita-production
```

3. **Cross-Region Failover**
```bash
# Switch to DR region
kubectl config use-context mita-dr-cluster
helm install mita . -f values-dr.yaml --namespace mita-production
```

## 📚 Additional Resources

- [Helm Chart Reference](./CHART_REFERENCE.md)
- [Security Runbooks](../../runbooks/)
- [Monitoring Dashboards](../../monitoring/grafana/)
- [External Secrets Documentation](../../k8s/external-secrets/)

## 🤝 Support

For deployment issues or questions:
- **Infrastructure Team**: infrastructure@mita.finance
- **SRE On-Call**: Use PagerDuty escalation
- **Documentation**: Internal Wiki and Runbooks

---

**Last Updated**: $(date +%Y-%m-%d)
**Chart Version**: 0.1.0
**App Version**: 1.0
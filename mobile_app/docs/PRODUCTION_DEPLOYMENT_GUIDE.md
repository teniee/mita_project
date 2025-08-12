# MITA Production Deployment Guide

> **Enterprise-grade deployment guide for MITA financial mobile application**  
> **Production-ready with comprehensive security, monitoring, and scalability**

## 📋 Table of Contents

1. [Overview](#overview)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [Environment Configuration](#environment-configuration)
4. [Security Configuration](#security-configuration)
5. [Database Setup](#database-setup)
6. [Redis/Cache Configuration](#rediscache-configuration)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Monitoring & Logging](#monitoring--logging)
9. [Performance Optimization](#performance-optimization)
10. [Backup & Recovery](#backup--recovery)
11. [Compliance & Legal](#compliance--legal)
12. [Troubleshooting](#troubleshooting)

## 🌟 Overview

This guide provides comprehensive instructions for deploying the MITA financial mobile application to production environments. MITA requires enterprise-grade infrastructure to handle sensitive financial data with the highest security and compliance standards.

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Production Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Mobile Apps   │    │   Web Frontend  │    │  Admin Panel │ │
│  │  (iOS/Android)  │    │   (Optional)    │    │              │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                     │      │
│           └───────────────────────┼─────────────────────┘      │
│                                   │                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     Load Balancer                          │ │
│  │              (AWS ALB / CloudFlare)                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                   │                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   API Gateway                               │ │
│  │          (Rate Limiting, Authentication)                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                   │                            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │  Auth Service   │    │  Budget Service │    │ Analytics    │ │
│  │  (JWT, Device   │    │  (AI Engine)    │    │ Service      │ │
│  │   Security)     │    │                 │    │              │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                     │      │
│           └───────────────────────┼─────────────────────┘      │
│                                   │                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Data Layer                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │ │
│  │  │  PostgreSQL  │  │    Redis     │  │   File Storage    │ │ │
│  │  │  (Primary)   │  │  (Cache +    │  │   (Receipts +     │ │ │
│  │  │              │  │ Sessions)    │  │    Documents)     │ │ │
│  │  └──────────────┘  └──────────────┘  └───────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Firebase   │  │    Sentry    │  │      Monitoring      │  │
│  │ (Push, Crash)│  │ (Error Track)│  │  (DataDog/NewRelic)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Production Requirements

- **High Availability**: 99.9% uptime SLA
- **Security**: Enterprise-grade financial security
- **Compliance**: PCI DSS, SOX, GDPR ready
- **Performance**: <200ms API response times
- **Scalability**: Auto-scaling based on demand
- **Monitoring**: Real-time metrics and alerting

## 🏗️ Infrastructure Requirements

### Minimum Production Requirements

**Application Servers**
- **CPU**: 4 cores per instance
- **RAM**: 8GB per instance
- **Storage**: 100GB SSD per instance
- **Network**: 1Gbps bandwidth
- **Instances**: Minimum 2 (for HA)

**Database Server**
- **CPU**: 8 cores
- **RAM**: 32GB
- **Storage**: 500GB SSD (with automatic scaling)
- **Network**: 10Gbps bandwidth
- **Backup**: Daily automated backups with 30-day retention

**Redis Cache**
- **CPU**: 2 cores
- **RAM**: 16GB
- **Network**: 1Gbps bandwidth
- **Instances**: 2 (primary + replica for HA)

**Load Balancer**
- **Type**: Application Load Balancer (Layer 7)
- **SSL**: TLS 1.3 with automated certificate management
- **WAF**: Web Application Firewall enabled

### Recommended Cloud Providers

#### AWS Configuration
```yaml
# aws-infrastructure.yml
Resources:
  # ECS Fargate for containerized applications
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: mita-production
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT

  # RDS PostgreSQL with Multi-AZ
  Database:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.r6g.2xlarge
      Engine: postgres
      EngineVersion: '15.4'
      MultiAZ: true
      StorageType: gp3
      AllocatedStorage: 500
      StorageEncrypted: true
      BackupRetentionPeriod: 30
      DeletionProtection: true

  # ElastiCache Redis with clustering
  RedisCluster:
    Type: AWS::ElastiCache::ReplicationGroup
    Properties:
      ReplicationGroupDescription: MITA Redis cluster
      NodeType: cache.r7g.xlarge
      NumCacheClusters: 2
      Engine: redis
      EngineVersion: '7.0'
      TransitEncryptionEnabled: true
      AtRestEncryptionEnabled: true

  # Application Load Balancer
  LoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Type: application
      Scheme: internet-facing
      SecurityGroups: [!Ref ALBSecurityGroup]
      Subnets: [!Ref PublicSubnet1, !Ref PublicSubnet2]
```

#### Google Cloud Platform Configuration
```yaml
# gcp-infrastructure.yml
resources:
  # Cloud Run for containerized applications
  - name: mita-api-service
    type: gcp-types/run-v1:namespaces.services
    properties:
      apiVersion: serving.knative.dev/v1
      kind: Service
      metadata:
        name: mita-api
        namespace: production
      spec:
        template:
          metadata:
            annotations:
              autoscaling.knative.dev/maxScale: "100"
              autoscaling.knative.dev/minScale: "2"
          spec:
            containerConcurrency: 100
            containers:
              - image: gcr.io/PROJECT_ID/mita-api:latest
                resources:
                  limits:
                    cpu: "2"
                    memory: "4Gi"
                env:
                  - name: NODE_ENV
                    value: production

  # Cloud SQL PostgreSQL
  - name: mita-database
    type: gcp-types/sqladmin-v1beta4:instances
    properties:
      databaseVersion: POSTGRES_15
      region: us-central1
      settings:
        tier: db-custom-8-32768
        availabilityType: REGIONAL
        backupConfiguration:
          enabled: true
          pointInTimeRecoveryEnabled: true
          retainedBackups: 30
        storageAutoResize: true
        storageSize: 500
        storageType: PD_SSD
```

#### Azure Configuration
```yaml
# azure-infrastructure.yml
resources:
  # Azure Container Instances
  - type: Microsoft.ContainerInstance/containerGroups
    apiVersion: '2021-09-01'
    name: mita-api-group
    location: East US 2
    properties:
      containers:
        - name: mita-api
          properties:
            image: mitaregistry.azurecr.io/mita-api:latest
            resources:
              requests:
                cpu: 2
                memoryInGB: 4
            environmentVariables:
              - name: NODE_ENV
                value: production
      osType: Linux
      restartPolicy: Always

  # Azure Database for PostgreSQL
  - type: Microsoft.DBforPostgreSQL/flexibleServers
    apiVersion: '2021-06-01'
    name: mita-postgresql
    location: East US 2
    properties:
      administratorLogin: mitaadmin
      version: '15'
      storage:
        storageSizeGB: 512
        autoGrow: Enabled
      compute:
        tier: GeneralPurpose
        name: Standard_D4s_v3
      highAvailability:
        mode: ZoneRedundant
      backup:
        backupRetentionDays: 30
        pointInTimeRestoreEnabled: true
```

## ⚙️ Environment Configuration

### Production Environment Variables

Create a comprehensive `.env.production` file:

```bash
# API Configuration
API_BASE_URL=https://api.mita.com
API_VERSION=v1
API_TIMEOUT_SECONDS=30
NODE_ENV=production

# Database Configuration
DATABASE_HOST=mita-postgresql.amazonaws.com
DATABASE_PORT=5432
DATABASE_NAME=mita_production
DATABASE_USER=mita_app
DATABASE_PASSWORD=your-secure-database-password
DATABASE_SSL=require
DATABASE_MAX_CONNECTIONS=100
DATABASE_IDLE_TIMEOUT=30000

# Redis Configuration
REDIS_HOST=mita-redis-cluster.amazonaws.com
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-redis-password
REDIS_DATABASE=0
REDIS_CLUSTER_MODE=true
REDIS_TLS=true

# Security Configuration
JWT_SECRET_KEY=your-256-bit-jwt-secret-key
JWT_EXPIRATION=3600
JWT_REFRESH_EXPIRATION=2592000
ENCRYPTION_KEY=your-256-bit-aes-encryption-key
DEVICE_ID_SALT=your-unique-device-salt
PASSWORD_SALT_ROUNDS=12

# Firebase Configuration
FIREBASE_PROJECT_ID=mita-production
FIREBASE_PRIVATE_KEY_ID=your-firebase-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@mita-production.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-firebase-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token

# External Services
SENTRY_DSN=https://your-sentry-dsn@o123456.ingest.sentry.io/123456
MIXPANEL_TOKEN=your-mixpanel-production-token
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=whsec_your-stripe-webhook-secret

# Storage Configuration
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=mita-production-storage
CDN_BASE_URL=https://cdn.mita.com

# Email Configuration
SMTP_HOST=smtp.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=noreply@mita.com
SMTP_FROM_NAME=MITA Financial

# Rate Limiting
RATE_LIMIT_WINDOW=60000
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_SKIP_FAILED_REQUESTS=true
RATE_LIMIT_SKIP_SUCCESSFUL_REQUESTS=false

# Monitoring & Logging
LOG_LEVEL=info
LOG_FORMAT=json
ENABLE_METRICS=true
METRICS_PORT=9090
HEALTH_CHECK_PORT=8080

# Feature Flags
ENABLE_AI_INSIGHTS=true
ENABLE_PEER_COMPARISON=true
ENABLE_OCR_PROCESSING=true
ENABLE_PREDICTIVE_ANALYTICS=true
ENABLE_REAL_TIME_NOTIFICATIONS=true

# Compliance
ENABLE_AUDIT_LOGGING=true
ENABLE_DATA_ENCRYPTION=true
ENABLE_PCI_COMPLIANCE_MODE=true
DATA_RETENTION_DAYS=2555  # 7 years for financial data
```

### Mobile App Configuration

For Flutter mobile app builds:

```bash
# Production Android Build
flutter build appbundle \
  --release \
  --dart-define=API_BASE_URL=https://api.mita.com \
  --dart-define=ENVIRONMENT=production \
  --dart-define=ENABLE_LOGGING=false \
  --dart-define=ENABLE_DEBUG_FEATURES=false \
  --dart-define=FIREBASE_PROJECT_ID=mita-production \
  --dart-define=SENTRY_DSN=https://your-sentry-dsn \
  --dart-define=MIXPANEL_TOKEN=your-production-token

# Production iOS Build
flutter build ipa \
  --release \
  --dart-define=API_BASE_URL=https://api.mita.com \
  --dart-define=ENVIRONMENT=production \
  --dart-define=ENABLE_LOGGING=false \
  --dart-define=FIREBASE_PROJECT_ID=mita-production \
  --export-options-plist=ios/ExportOptions.plist
```

## 🔐 Security Configuration

### SSL/TLS Configuration

**Certificate Requirements**
- TLS 1.3 minimum
- Extended Validation (EV) SSL certificates
- HSTS headers enabled
- Certificate pinning in mobile apps

```nginx
# nginx.conf security headers
server {
    listen 443 ssl http2;
    server_name api.mita.com;

    # SSL Configuration
    ssl_certificate /path/to/mita.com.crt;
    ssl_certificate_key /path/to/mita.com.key;
    ssl_protocols TLSv1.3 TLSv1.2;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_dhparam /path/to/dhparam.pem;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; media-src 'self'; object-src 'none'; child-src 'none'; worker-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self';" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;

    location /auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://backend;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://backend;
    }
}
```

### WAF (Web Application Firewall) Rules

```yaml
# AWS WAF Rules
Rules:
  - Name: AWSManagedRulesCommonRuleSet
    Priority: 1
    Statement:
      ManagedRuleGroupStatement:
        VendorName: AWS
        Name: AWSManagedRulesCommonRuleSet
  
  - Name: AWSManagedRulesSQLiRuleSet
    Priority: 2
    Statement:
      ManagedRuleGroupStatement:
        VendorName: AWS
        Name: AWSManagedRulesSQLiRuleSet
  
  - Name: RateLimitRule
    Priority: 3
    Statement:
      RateBasedStatement:
        Limit: 2000
        AggregateKeyType: IP
    Action:
      Block: {}

  - Name: GeoBlockRule
    Priority: 4
    Statement:
      GeoMatchStatement:
        CountryCodes: [CN, RU, KP]  # Block high-risk countries
    Action:
      Block: {}
```

### API Security Configuration

```typescript
// security-middleware.ts
import rateLimit from 'express-rate-limit';
import helmet from 'helmet';
import hpp from 'hpp';

// Rate limiting configuration
const createRateLimiter = (windowMs: number, max: number) => rateLimit({
  windowMs,
  max,
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Too many requests, please try again later.',
    }
  },
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    return req.ip + ':' + req.path;
  }
});

// Authentication rate limiting (5 per minute)
export const authRateLimit = createRateLimiter(60 * 1000, 5);

// API rate limiting (100 per minute)
export const apiRateLimit = createRateLimiter(60 * 1000, 100);

// Security middleware
export const securityMiddleware = [
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        styleSrc: ["'self'", "'unsafe-inline'"],
        scriptSrc: ["'self'"],
        imgSrc: ["'self'", "data:", "https:"],
        connectSrc: ["'self'"],
        fontSrc: ["'self'"],
        objectSrc: ["'none'"],
        mediaSrc: ["'self'"],
        frameSrc: ["'none'"],
      },
    },
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true,
      preload: true
    }
  }),
  hpp(), // HTTP Parameter Pollution protection
];
```

## 🗄️ Database Setup

### PostgreSQL Production Configuration

```sql
-- postgresql.conf optimizations for production
max_connections = 200
shared_buffers = 8GB
effective_cache_size = 24GB
maintenance_work_mem = 2GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 41943kB
min_wal_size = 2GB
max_wal_size = 8GB

-- Enable logging for monitoring
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'all'
log_duration = on
log_line_prefix = '[%t] %u@%d '
```

### Database Schema Migration

```sql
-- 001_initial_schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table with enhanced security
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    income_tier VARCHAR(20) DEFAULT 'middle',
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Secure device fingerprinting
CREATE TABLE device_fingerprints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(50) UNIQUE NOT NULL,
    fingerprint_hash VARCHAR(64) NOT NULL,
    device_model VARCHAR(100),
    platform VARCHAR(20),
    os_version VARCHAR(50),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    risk_score DECIMAL(3,2) DEFAULT 0.00,
    is_trusted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- JWT token blacklist for revocation
CREATE TABLE token_blacklist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(50),
    revoked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(50),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Expenses with enhanced tracking
CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    category VARCHAR(50) NOT NULL,
    description TEXT,
    merchant_name VARCHAR(255),
    location_lat DECIMAL(10,8),
    location_lng DECIMAL(11,8),
    location_address TEXT,
    receipt_image_url TEXT,
    payment_method VARCHAR(20),
    ocr_data JSONB,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expense_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Budget configuration
CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    monthly_income DECIMAL(12,2) NOT NULL CHECK (monthly_income > 0),
    monthly_expenses DECIMAL(12,2) NOT NULL CHECK (monthly_expenses >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    categories JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Audit log for compliance
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_device_fingerprints_user_id ON device_fingerprints(user_id);
CREATE INDEX idx_device_fingerprints_device_id ON device_fingerprints(device_id);
CREATE INDEX idx_token_blacklist_token_id ON token_blacklist(token_id);
CREATE INDEX idx_token_blacklist_expires_at ON token_blacklist(expires_at);
CREATE INDEX idx_expenses_user_id ON expenses(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_expenses_created_at ON expenses(created_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_expenses_category ON expenses(category) WHERE deleted_at IS NULL;
CREATE INDEX idx_expenses_expense_date ON expenses(expense_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_budgets_user_id ON budgets(user_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_fingerprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY user_own_data ON users FOR ALL TO app_user USING (id = current_setting('app.current_user_id')::UUID);
CREATE POLICY device_own_data ON device_fingerprints FOR ALL TO app_user USING (user_id = current_setting('app.current_user_id')::UUID);
CREATE POLICY expense_own_data ON expenses FOR ALL TO app_user USING (user_id = current_setting('app.current_user_id')::UUID);
CREATE POLICY budget_own_data ON budgets FOR ALL TO app_user USING (user_id = current_setting('app.current_user_id')::UUID);
```

### Database Backup Configuration

```bash
#!/bin/bash
# backup-database.sh

set -euo pipefail

# Configuration
DB_HOST="mita-postgresql.amazonaws.com"
DB_PORT="5432"
DB_NAME="mita_production"
DB_USER="mita_backup"
BACKUP_DIR="/var/backups/postgresql"
RETENTION_DAYS=30
S3_BUCKET="mita-database-backups"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate backup filename
BACKUP_FILE="mita_production_$(date +%Y%m%d_%H%M%S).sql.gz"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

# Perform database backup
PGPASSWORD="$DB_PASSWORD" pg_dump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --no-password \
  --format=custom \
  --compress=9 \
  --verbose \
  --file="$BACKUP_PATH" \
  "$DB_NAME"

# Upload to S3
aws s3 cp "$BACKUP_PATH" "s3://$S3_BUCKET/$(date +%Y/%m/%d)/$BACKUP_FILE" \
  --storage-class STANDARD_IA \
  --server-side-encryption AES256

# Clean up local backups older than retention period
find "$BACKUP_DIR" -name "mita_production_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Verify backup integrity
PGPASSWORD="$DB_PASSWORD" pg_restore --list "$BACKUP_PATH" > /dev/null

echo "Database backup completed successfully: $BACKUP_FILE"
```

## 🚀 Redis/Cache Configuration

### Redis Production Setup

```conf
# redis.conf production configuration
bind 127.0.0.1 10.0.1.100  # Bind to private network
port 6379
timeout 0
tcp-keepalive 300

# Memory management
maxmemory 8gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Persistence
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

# Append only file
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Security
requirepass your-redis-secure-password
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command CONFIG "CONFIG_b7d4c9f5a8e2c1d9"

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 1000

# Client connections
maxclients 10000
tcp-backlog 511
```

### Redis Cluster Configuration

```yaml
# redis-cluster.yml
version: '3.8'
services:
  redis-node-1:
    image: redis:7.0-alpine
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis-cluster.conf:/usr/local/etc/redis/redis.conf
      - redis-data-1:/data
    ports:
      - "7001:6379"
      - "17001:16379"
    environment:
      - REDIS_PASSWORD=your-redis-password

  redis-node-2:
    image: redis:7.0-alpine
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis-cluster.conf:/usr/local/etc/redis/redis.conf
      - redis-data-2:/data
    ports:
      - "7002:6379"
      - "17002:16379"

  redis-node-3:
    image: redis:7.0-alpine
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis-cluster.conf:/usr/local/etc/redis/redis.conf
      - redis-data-3:/data
    ports:
      - "7003:6379"
      - "17003:16379"

volumes:
  redis-data-1:
  redis-data-2:
  redis-data-3:
```

### Caching Strategy

```typescript
// cache-service.ts
import Redis from 'ioredis';

interface CacheOptions {
  ttl?: number;
  namespace?: string;
}

class CacheService {
  private redis: Redis.Cluster;

  constructor() {
    this.redis = new Redis.Cluster([
      { host: 'redis-node-1', port: 6379 },
      { host: 'redis-node-2', port: 6379 },
      { host: 'redis-node-3', port: 6379 },
    ], {
      redisOptions: {
        password: process.env.REDIS_PASSWORD,
        tls: {
          rejectUnauthorized: false
        }
      },
      retryDelayOnFailover: 100,
      maxRetriesPerRequest: 3
    });
  }

  // Budget data caching (5 minutes)
  async cacheBudgetData(userId: string, data: any): Promise<void> {
    const key = `budget:${userId}`;
    await this.redis.setex(key, 300, JSON.stringify(data));
  }

  // User session caching (1 hour)
  async cacheUserSession(sessionId: string, userData: any): Promise<void> {
    const key = `session:${sessionId}`;
    await this.redis.setex(key, 3600, JSON.stringify(userData));
  }

  // Rate limiting
  async checkRateLimit(key: string, limit: number, window: number): Promise<boolean> {
    const current = await this.redis.incr(key);
    if (current === 1) {
      await this.redis.expire(key, window);
    }
    return current <= limit;
  }

  // Token blacklist for JWT revocation
  async blacklistToken(tokenId: string, expiresAt: Date): Promise<void> {
    const key = `blacklist:${tokenId}`;
    const ttl = Math.floor((expiresAt.getTime() - Date.now()) / 1000);
    if (ttl > 0) {
      await this.redis.setex(key, ttl, 'revoked');
    }
  }

  async isTokenBlacklisted(tokenId: string): Promise<boolean> {
    const result = await this.redis.get(`blacklist:${tokenId}`);
    return result === 'revoked';
  }
}
```

## 🔄 CI/CD Pipeline

### GitHub Actions Production Pipeline

```yaml
# .github/workflows/production-deploy.yml
name: Production Deployment

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        default: 'production'
        type: choice
        options:
          - production
          - staging

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run security scan
        uses: securecodewarrior/github-action-add-sarif@v1
        with:
          sarif-file: security-scan-results.sarif

      - name: Dependency vulnerability scan
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high

  test-mobile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.0'
          
      - name: Install dependencies
        run: flutter pub get
        
      - name: Run tests with coverage
        run: flutter test --coverage
        
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: coverage/lcov.info
          
      - name: Run integration tests
        run: flutter test integration_test/
        
  build-backend:
    needs: [security-scan, test-mobile]
    runs-on: ubuntu-latest
    outputs:
      image: ${{ steps.image.outputs.image }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3
        
      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=tag
            type=sha,prefix=sha-
            
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          platforms: linux/amd64,linux/arm64
          cache-from: type=gha
          cache-to: type=gha,mode=max
          
      - name: Output image
        id: image
        run: echo "image=${{ fromJSON(steps.meta.outputs.json).tags[0] }}" >> $GITHUB_OUTPUT

  build-mobile-android:
    needs: [security-scan, test-mobile]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.0'
          
      - name: Setup Java
        uses: actions/setup-java@v3
        with:
          java-version: '11'
          distribution: 'temurin'
          
      - name: Install dependencies
        run: flutter pub get
        
      - name: Build Android App Bundle
        run: |
          flutter build appbundle \
            --release \
            --dart-define=API_BASE_URL=${{ secrets.API_BASE_URL }} \
            --dart-define=ENVIRONMENT=production \
            --dart-define=FIREBASE_PROJECT_ID=${{ secrets.FIREBASE_PROJECT_ID }}
            
      - name: Upload to Google Play
        uses: r0adkll/upload-google-play@v1
        with:
          serviceAccountJsonPlainText: ${{ secrets.GOOGLE_PLAY_SERVICE_ACCOUNT }}
          packageName: com.mita.finance
          releaseFiles: build/app/outputs/bundle/release/app-release.aab
          track: production
          status: completed

  build-mobile-ios:
    needs: [security-scan, test-mobile]
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.0'
          
      - name: Install CocoaPods
        run: sudo gem install cocoapods
        
      - name: Install dependencies
        run: flutter pub get
        
      - name: Build iOS IPA
        run: |
          flutter build ipa \
            --release \
            --dart-define=API_BASE_URL=${{ secrets.API_BASE_URL }} \
            --dart-define=ENVIRONMENT=production \
            --export-options-plist=ios/ExportOptions.plist
            
      - name: Upload to TestFlight
        uses: apple-actions/upload-testflight-build@v1
        with:
          app-path: build/ios/ipa/mita.ipa
          issuer-id: ${{ secrets.APPSTORE_ISSUER_ID }}
          api-key-id: ${{ secrets.APPSTORE_API_KEY_ID }}
          api-private-key: ${{ secrets.APPSTORE_API_PRIVATE_KEY }}

  deploy-production:
    needs: [build-backend, build-mobile-android, build-mobile-ios]
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to AWS ECS
        run: |
          aws ecs update-service \
            --cluster mita-production \
            --service mita-api \
            --force-new-deployment \
            --task-definition mita-api:$(aws ecs describe-task-definition \
              --task-definition mita-api \
              --query 'taskDefinition.revision')
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: us-east-1
          
      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster mita-production \
            --services mita-api
            
      - name: Run health checks
        run: |
          for i in {1..30}; do
            if curl -f https://api.mita.com/health; then
              echo "Health check passed"
              exit 0
            fi
            echo "Health check failed, retrying in 10 seconds..."
            sleep 10
          done
          echo "Health check failed after 30 attempts"
          exit 1
          
      - name: Run smoke tests
        run: |
          npm install -g newman
          newman run postman/production-smoke-tests.json \
            --environment postman/production-environment.json \
            --reporters cli,json \
            --reporter-json-export test-results.json
            
      - name: Notify deployment success
        uses: 8398a7/action-slack@v3
        if: success()
        with:
          status: success
          text: "🚀 MITA production deployment successful!"
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          
      - name: Notify deployment failure
        uses: 8398a7/action-slack@v3
        if: failure()
        with:
          status: failure
          text: "❌ MITA production deployment failed!"
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Deployment Scripts

```bash
#!/bin/bash
# deploy-production.sh

set -euo pipefail

# Configuration
ENVIRONMENT="production"
IMAGE_TAG="latest"
HEALTH_CHECK_URL="https://api.mita.com/health"
MAX_HEALTH_CHECK_ATTEMPTS=30
HEALTH_CHECK_INTERVAL=10

echo "🚀 Starting MITA production deployment..."

# Validate environment variables
required_vars=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "DATABASE_PASSWORD"
    "REDIS_PASSWORD"
    "JWT_SECRET_KEY"
)

for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo "❌ Error: $var is not set"
        exit 1
    fi
done

# Pre-deployment checks
echo "🔍 Running pre-deployment checks..."

# Database connectivity check
if ! PGPASSWORD="$DATABASE_PASSWORD" pg_isready -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER"; then
    echo "❌ Database connectivity check failed"
    exit 1
fi

# Redis connectivity check
if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping > /dev/null; then
    echo "❌ Redis connectivity check failed"
    exit 1
fi

# Deploy database migrations
echo "📊 Running database migrations..."
PGPASSWORD="$DATABASE_PASSWORD" psql \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    -U "$DATABASE_USER" \
    -d "$DATABASE_NAME" \
    -f migrations/production-migrations.sql

# Update ECS service
echo "🏗️ Updating ECS service..."
aws ecs update-service \
    --cluster "mita-$ENVIRONMENT" \
    --service "mita-api" \
    --force-new-deployment

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
aws ecs wait services-stable \
    --cluster "mita-$ENVIRONMENT" \
    --services "mita-api"

# Health check
echo "🏥 Running health checks..."
for i in $(seq 1 $MAX_HEALTH_CHECK_ATTEMPTS); do
    if curl -f -s "$HEALTH_CHECK_URL" > /dev/null; then
        echo "✅ Health check passed"
        break
    fi
    
    if [[ $i -eq $MAX_HEALTH_CHECK_ATTEMPTS ]]; then
        echo "❌ Health check failed after $MAX_HEALTH_CHECK_ATTEMPTS attempts"
        exit 1
    fi
    
    echo "⏳ Health check failed, retrying in ${HEALTH_CHECK_INTERVAL}s... ($i/$MAX_HEALTH_CHECK_ATTEMPTS)"
    sleep $HEALTH_CHECK_INTERVAL
done

# Run smoke tests
echo "🧪 Running smoke tests..."
npm run test:smoke:production

echo "🎉 MITA production deployment completed successfully!"

# Send notification
curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"🚀 MITA production deployment completed successfully!"}' \
    "$SLACK_WEBHOOK_URL"
```

## 📊 Monitoring & Logging

### Application Performance Monitoring (APM)

```typescript
// monitoring-setup.ts
import { createPrometheusMetrics } from 'prom-client';
import * as Sentry from '@sentry/node';
import { DatadogRum } from '@datadog/browser-rum';

// Initialize Sentry for error tracking
Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
    new Sentry.Integrations.Express({ app }),
    new Sentry.Integrations.Postgres(),
  ],
});

// Prometheus metrics
const register = new client.Registry();

const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status'],
  buckets: [0.1, 0.5, 1, 2, 5, 10]
});

const httpRequestTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status']
});

const activeUsers = new client.Gauge({
  name: 'active_users_total',
  help: 'Number of currently active users'
});

const budgetCalculations = new client.Counter({
  name: 'budget_calculations_total',
  help: 'Total number of budget calculations performed',
  labelNames: ['user_tier']
});

const expenseProcessing = new client.Histogram({
  name: 'expense_processing_duration_seconds',
  help: 'Time taken to process expenses',
  labelNames: ['category', 'ocr_enabled'],
  buckets: [0.5, 1, 2, 5, 10, 30]
});

register.registerMetric(httpRequestDuration);
register.registerMetric(httpRequestTotal);
register.registerMetric(activeUsers);
register.registerMetric(budgetCalculations);
register.registerMetric(expenseProcessing);

// Middleware for request metrics
export const metricsMiddleware = (req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route?.path || 'unknown';
    
    httpRequestDuration
      .labels(req.method, route, res.statusCode.toString())
      .observe(duration);
      
    httpRequestTotal
      .labels(req.method, route, res.statusCode.toString())
      .inc();
  });
  
  next();
};

// Custom business metrics
export class BusinessMetrics {
  static recordBudgetCalculation(userTier: string) {
    budgetCalculations.labels(userTier).inc();
  }
  
  static recordExpenseProcessing(category: string, ocrEnabled: boolean, duration: number) {
    expenseProcessing
      .labels(category, ocrEnabled.toString())
      .observe(duration / 1000);
  }
  
  static updateActiveUsers(count: number) {
    activeUsers.set(count);
  }
}
```

### Logging Configuration

```typescript
// logging-service.ts
import winston from 'winston';
import 'winston-daily-rotate-file';

const logFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json(),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    return JSON.stringify({
      timestamp,
      level,
      message,
      ...meta,
      service: 'mita-api',
      version: process.env.APP_VERSION,
      environment: process.env.NODE_ENV
    });
  })
);

// Production logger configuration
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: logFormat,
  defaultMeta: {
    service: 'mita-api',
    environment: process.env.NODE_ENV
  },
  transports: [
    // Console output for container logs
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    }),
    
    // File rotation for persistent logs
    new winston.transports.DailyRotateFile({
      filename: '/var/log/mita/application-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      zippedArchive: true,
      maxSize: '20m',
      maxFiles: '14d'
    }),
    
    // Error-only file
    new winston.transports.DailyRotateFile({
      filename: '/var/log/mita/error-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      level: 'error',
      zippedArchive: true,
      maxSize: '20m',
      maxFiles: '30d'
    }),
    
    // Audit log for compliance
    new winston.transports.DailyRotateFile({
      filename: '/var/log/mita/audit-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      zippedArchive: true,
      maxSize: '50m',
      maxFiles: '7y', // Keep for 7 years for compliance
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
      )
    })
  ],
  
  // Handle uncaught exceptions
  exceptionHandlers: [
    new winston.transports.File({ filename: '/var/log/mita/exceptions.log' })
  ],
  
  // Handle unhandled promise rejections
  rejectionHandlers: [
    new winston.transports.File({ filename: '/var/log/mita/rejections.log' })
  ]
});

// Audit logging for compliance
export class AuditLogger {
  static logUserAction(userId: string, action: string, resource: string, metadata: any = {}) {
    logger.info('USER_ACTION', {
      userId,
      action,
      resource,
      metadata,
      category: 'audit',
      timestamp: new Date().toISOString()
    });
  }
  
  static logSecurityEvent(event: string, severity: string, metadata: any = {}) {
    logger.warn('SECURITY_EVENT', {
      event,
      severity,
      metadata,
      category: 'security',
      timestamp: new Date().toISOString()
    });
  }
  
  static logFinancialTransaction(userId: string, type: string, amount: number, metadata: any = {}) {
    logger.info('FINANCIAL_TRANSACTION', {
      userId,
      type,
      amount,
      metadata,
      category: 'financial',
      timestamp: new Date().toISOString()
    });
  }
}

export default logger;
```

### Grafana Dashboard Configuration

```yaml
# grafana-dashboard.json
{
  "dashboard": {
    "id": null,
    "title": "MITA Production Dashboard",
    "description": "Comprehensive monitoring dashboard for MITA financial application",
    "tags": ["mita", "production", "financial"],
    "timezone": "UTC",
    "panels": [
      {
        "title": "API Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ],
        "yAxes": [
          {
            "label": "Response Time (seconds)",
            "max": 5
          }
        ],
        "alert": {
          "conditions": [
            {
              "query": {
                "queryType": "",
                "refId": "A"
              },
              "reducer": {
                "params": [],
                "type": "last"
              },
              "evaluator": {
                "params": [2],
                "type": "gt"
              }
            }
          ],
          "executionErrorState": "alerting",
          "noDataState": "no_data",
          "frequency": "10s",
          "handler": 1,
          "name": "API Response Time Alert",
          "message": "API response time is above 2 seconds"
        }
      },
      {
        "title": "Active Users",
        "type": "stat",
        "targets": [
          {
            "expr": "active_users_total",
            "legendFormat": "Active Users"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m]) * 100",
            "legendFormat": "5xx Error Rate"
          },
          {
            "expr": "rate(http_requests_total{status=~\"4..\"}[5m]) / rate(http_requests_total[5m]) * 100",
            "legendFormat": "4xx Error Rate"
          }
        ]
      },
      {
        "title": "Database Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "pg_stat_database_tup_fetched[5m]",
            "legendFormat": "Rows Fetched"
          },
          {
            "expr": "pg_stat_database_tup_inserted[5m]",
            "legendFormat": "Rows Inserted"
          }
        ]
      },
      {
        "title": "Budget Calculations",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(budget_calculations_total[5m])",
            "legendFormat": "Calculations per second"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

---

**📊 Status**: Production Ready | **🔒 Security**: Enterprise Grade | **♿ Accessibility**: WCAG 2.1 AA | **🌍 Localization**: Multi-language**

*Deployment guide prepared by the MITA Engineering Team*
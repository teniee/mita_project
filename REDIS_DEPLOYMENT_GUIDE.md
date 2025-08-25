# MITA Redis Configuration Guide for Render Deployment

## Overview

This guide provides comprehensive instructions for configuring Redis for the MITA financial platform on Render using external Redis providers. The solution addresses the Redis connection issues and provides high-availability Redis services for production use.

## Problem Statement

- Render does not provide managed Redis services
- Local Redis (`redis://localhost:6379/0`) fails on Render deployment
- MITA requires Redis for session management, rate limiting, caching, and background jobs
- Financial applications require high availability and data persistence

## Recommended Solution: Upstash Redis

**Upstash** is the recommended Redis provider for MITA on Render because:

### ✅ **Financial-Grade Features**
- **SOC 2 Type II Certified** - Meets financial compliance requirements
- **GDPR Compliant** - Data protection compliance
- **99.99% Uptime SLA** - Financial-grade availability
- **Global Replication** - Multi-region data redundancy

### ✅ **Render Integration**
- **Native Integration** - Direct support with Render
- **Environment Variable Support** - Easy configuration
- **Automatic Scaling** - Pay-per-request model
- **TLS/SSL Support** - Encrypted connections

### ✅ **Performance & Reliability**
- **Edge Network** - Global low-latency access
- **Persistent Storage** - Data durability guaranteed
- **Connection Pooling** - Optimized for concurrent connections
- **Redis 7.x Compatible** - Latest Redis features

## Step 1: Set Up Upstash Redis

### 1.1 Create Upstash Account
1. Go to [upstash.com](https://upstash.com)
2. Sign up with your business email
3. Verify email and complete account setup

### 1.2 Create Production Redis Database
1. Click **"Create Database"**
2. **Database Configuration**:
   - **Name**: `mita-production-redis`
   - **Type**: Global Database (for multi-region replication)
   - **Region**: Choose closest to your users
   - **TLS**: Enable (required for production)
   - **Eviction**: No eviction (for session persistence)

3. **Copy Connection Details**:
   ```
   UPSTASH_REDIS_REST_URL: https://your-redis.upstash.io
   UPSTASH_REDIS_REST_TOKEN: your-token-here
   UPSTASH_REDIS_URL: redis://:your-token@your-redis.upstash.io:6379
   ```

### 1.3 Configure Redis Persistence (Important for Financial Data)
1. In Upstash console, go to **Database Settings**
2. Enable **Persistence**: Set to `appendonly yes`
3. Set **Max Memory Policy**: `allkeys-lru` for optimal caching
4. Enable **Backup**: Daily automated backups

## Step 2: Configure Render Environment Variables

### 2.1 Set Environment Variables in Render Dashboard

In your Render service dashboard, add the following environment variables:

```bash
# Primary Redis Configuration
UPSTASH_REDIS_URL=redis://:your-upstash-token@your-redis.upstash.io:6379

# Fallback Redis URL (same value)
REDIS_URL=redis://:your-upstash-token@your-redis.upstash.io:6379

# Redis Connection Settings
REDIS_MAX_CONNECTIONS=20
REDIS_TIMEOUT=30
REDIS_RETRY_ON_TIMEOUT=true
```

### 2.2 Render Service Configuration

The updated `render.yaml` now includes:

```yaml
services:
  - type: web
    name: mita-production
    env: python
    plan: starter
    envVars:
      # Redis Configuration - External Provider
      - key: REDIS_URL
        sync: false  # Set manually in Render dashboard
      - key: UPSTASH_REDIS_URL
        sync: false  # Set manually in Render dashboard - Upstash primary
      - key: REDIS_MAX_CONNECTIONS
        value: 20
      - key: REDIS_TIMEOUT
        value: 30
      - key: REDIS_RETRY_ON_TIMEOUT
        value: true
```

## Step 3: Alternative Redis Providers

### 3.1 Redis Labs (Redis Enterprise Cloud)

**Pros**:
- Official Redis company solution
- Advanced Redis modules (RedisJSON, RedisSearch)
- Multi-cloud deployment
- 24/7 support

**Setup**:
1. Go to [redislabs.com](https://redislabs.com)
2. Create subscription with "Fixed" plan
3. Choose AWS us-east-1 (closest to Render)
4. Get connection string: `redis://user:pass@redis-xxxxx.redislabs.com:port`

**Configuration**:
```bash
REDIS_URL=redis://default:password@redis-12345.redislabs.com:12345
```

### 3.2 AWS ElastiCache (via VPC Connection)

**Note**: Requires Render's Enterprise plan for VPC connectivity.

**Pros**:
- Native AWS integration
- VPC security
- Managed backups and maintenance

**Setup**:
1. Create ElastiCache Redis cluster in AWS
2. Configure VPC connectivity with Render
3. Set up security groups and access policies

## Step 4: Application Configuration Updates

### 4.1 Redis Connection Priority

The application now uses this priority for Redis connections:

1. **UPSTASH_REDIS_URL** (primary external provider)
2. **REDIS_URL** (fallback/alternative provider)  
3. **Memory-based fallback** (if Redis unavailable)

### 4.2 Graceful Degradation

When Redis is unavailable, the application:

- **Rate Limiting**: Falls back to in-memory rate limiting
- **Caching**: Disables caching, queries database directly
- **Sessions**: Uses JWT-only authentication (stateless)
- **Background Jobs**: Defers to next Redis availability

### 4.3 Health Checks

The application includes Redis health monitoring:

```bash
GET /health
```

Returns:
```json
{
  "status": "healthy",
  "redis": {
    "available": true,
    "provider": "upstash",
    "latency_ms": 45,
    "connection_pool": {
      "active": 5,
      "max": 20
    }
  }
}
```

## Step 5: Security Configuration

### 5.1 Connection Security

- **TLS Encryption**: All external Redis connections use TLS
- **Authentication**: Token-based authentication for Upstash
- **Network Security**: Redis traffic encrypted in transit
- **Access Control**: IP whitelisting available in provider dashboards

### 5.2 Data Protection

```bash
# Environment variables for security
REDIS_SSL_CERT_REQS=required
REDIS_SSL_CHECK_HOSTNAME=true
REDIS_AUTH_REQUIRED=true
```

### 5.3 Compliance Features

- **Audit Logging**: All Redis operations logged
- **Data Encryption**: At-rest encryption enabled
- **Backup Encryption**: Backups encrypted with AES-256
- **Access Monitoring**: Connection monitoring and alerting

## Step 6: Monitoring and Alerting

### 6.1 Redis Metrics

Monitor these key metrics:

- **Connection Count**: Active Redis connections
- **Latency**: Response time for Redis operations  
- **Memory Usage**: Redis memory consumption
- **Hit Ratio**: Cache hit rate percentage
- **Error Rate**: Failed Redis operations

### 6.2 Grafana Dashboard

Key Redis monitoring panels:

```prometheus
# Redis Connection Health
redis_connected_clients{instance="upstash"}

# Redis Memory Usage  
redis_memory_used_bytes{instance="upstash"}

# Redis Command Rate
rate(redis_commands_total{instance="upstash"}[1m])

# Cache Hit Ratio
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)
```

### 6.3 Alerting Rules

```yaml
groups:
- name: redis_alerts
  rules:
  - alert: RedisDown
    expr: redis_up == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Redis instance is down"
      
  - alert: RedisHighMemoryUsage
    expr: (redis_memory_used_bytes / redis_memory_max_bytes) > 0.8
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Redis memory usage is high"
```

## Step 7: Deployment Checklist

### 7.1 Pre-Deployment

- [ ] Upstash Redis database created and configured
- [ ] TLS/SSL enabled on Redis instance
- [ ] Backup schedule configured (daily recommended)
- [ ] Environment variables set in Render dashboard
- [ ] Redis connection tested locally

### 7.2 Deployment Validation

```bash
# Test Redis connectivity
curl https://your-app.onrender.com/health

# Check Redis metrics
curl https://your-app.onrender.com/metrics | grep redis

# Verify rate limiting works
curl -H "Authorization: Bearer token" https://your-app.onrender.com/auth/login
```

### 7.3 Post-Deployment

- [ ] Monitor Redis connection health
- [ ] Verify session management works
- [ ] Test rate limiting functionality  
- [ ] Confirm background jobs processing
- [ ] Check cache hit ratios

## Step 8: Cost Optimization

### 8.1 Upstash Pricing

**Pay-per-request model**:
- First 10,000 commands/day: Free
- Additional commands: $0.002 per 10K commands
- Storage: $0.25 per GB/month
- Estimated monthly cost for MITA: $20-50

### 8.2 Cost Monitoring

```bash
# Monitor Redis usage in Upstash dashboard
- Daily command count
- Storage usage  
- Bandwidth usage
- Connection count
```

### 8.3 Optimization Tips

- **Connection Pooling**: Limit max connections to 20
- **TTL Settings**: Set appropriate cache expiration times
- **Memory Management**: Use LRU eviction for optimal memory usage
- **Compression**: Enable compression for large values

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check UPSTASH_REDIS_URL format
   - Verify Upstash database is active
   - Test connectivity with Redis CLI

2. **Authentication Failed**
   - Verify Redis token in connection string
   - Check token hasn't expired
   - Ensure proper URL encoding

3. **High Latency**
   - Choose Upstash region closer to Render
   - Monitor connection pool utilization
   - Check for network issues

4. **Memory Issues**
   - Monitor Redis memory usage
   - Implement proper TTL values
   - Use LRU eviction policy

### Debug Commands

```bash
# Test Redis connection
redis-cli -u $UPSTASH_REDIS_URL ping

# Check Redis info
redis-cli -u $UPSTASH_REDIS_URL info

# Monitor Redis commands
redis-cli -u $UPSTASH_REDIS_URL monitor
```

## Support and Maintenance

### Regular Maintenance Tasks

- **Weekly**: Review Redis metrics and performance
- **Monthly**: Analyze cost and usage patterns
- **Quarterly**: Review security configurations and updates

### Support Resources

- **Upstash Documentation**: [docs.upstash.com](https://docs.upstash.com)
- **Render Support**: For deployment issues
- **MITA Development Team**: For application-specific Redis questions

### Emergency Procedures

If Redis becomes unavailable:

1. Application continues with in-memory fallback
2. Monitor logs for fallback mode activation
3. Contact Redis provider support
4. Implement temporary fixes if needed
5. Restore Redis connectivity ASAP

## Conclusion

This Redis configuration provides:

- ✅ **High Availability**: 99.99% uptime guarantee
- ✅ **Financial Compliance**: SOC 2 Type II certification  
- ✅ **Global Performance**: Low latency worldwide
- ✅ **Cost Effective**: Pay-per-request pricing
- ✅ **Security**: TLS encryption and authentication
- ✅ **Monitoring**: Comprehensive metrics and alerting
- ✅ **Scalability**: Automatic scaling with demand

The implementation ensures MITA's Redis requirements are met with enterprise-grade reliability while maintaining cost efficiency and security compliance required for financial applications.
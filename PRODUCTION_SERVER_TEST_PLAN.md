# MITA Finance API - Production Server Test Plan

## Current Status (2025-09-08 15:58 UTC)

**🔴 SERVER DOWN**: The production server at `https://mita-docker-ready-project-manus.onrender.com` is completely unresponsive, timing out after 10+ seconds.

**Issue Details:**
- Root endpoint `/` - Connection timeout
- Health endpoint `/health` - Connection timeout  
- API endpoints `/api/*` - Connection timeout
- WebFetch earlier showed healthy status, but now completely unreachable

**Possible Causes:**
1. Render.com deployment in progress or failed
2. Server crashed due to the 500 errors observed earlier
3. Resource exhaustion or memory issues
4. Database connection failures causing app to crash
5. Cold start issues if server spun down

## Deployment Monitoring Tools

### 1. Automated Monitoring Script

Use the provided monitoring script to check deployment status:

```bash
# Monitor deployment with 30-second intervals
python3 deployment_monitor.py

# Quick health check
python3 deployment_monitor.py --quick-check

# Test authentication once server is up
python3 deployment_monitor.py --test-auth

# Generate curl commands
python3 deployment_monitor.py --generate-curl
```

### 2. Manual Testing Commands

#### Basic Health Checks
```bash
# Test root endpoint with timeout
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/" \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n" \
  --max-time 15

# Test health endpoint
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/health" \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n" \
  --max-time 15

# Performance monitoring
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/" \
  -w "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nSSL: %{time_appconnect}s\nTotal: %{time_total}s\n"
```

## Authentication Testing Plan

### Phase 1: Server Accessibility
- [ ] Root endpoint responds (Status: 200)
- [ ] Health endpoint responds with server details
- [ ] Basic API endpoints return structured errors (not 500)

### Phase 2: Authentication System Testing

#### 2.1 User Registration
```bash
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@mita.finance",
    "password": "TestPassword123!",
    "password_confirm": "TestPassword123!",
    "first_name": "Test",
    "last_name": "User"
  }' \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n"
```

**Expected Results:**
- Status: 201 (Created) for successful registration
- Response includes access_token and refresh_token
- BCrypt hashing with rounds=10 (97% performance improvement)

#### 2.2 User Login
```bash
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@mita.finance", 
    "password": "TestPassword123!"
  }' \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n"
```

**Expected Results:**
- Status: 200 for successful login
- Login time should be significantly faster (97% improvement)
- Response includes fresh tokens

#### 2.3 Protected Endpoint Access
```bash
# Replace TOKEN with actual access token from login
curl -X GET "https://mita-docker-ready-project-manus.onrender.com/api/users/me" \
  -H "Authorization: Bearer TOKEN" \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n"
```

**Expected Results:**
- Status: 200 with user profile data
- Status: 401 if token expired or invalid

#### 2.4 Token Refresh
```bash
# Replace REFRESH_TOKEN with actual refresh token
curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "REFRESH_TOKEN"
  }' \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n"
```

### Phase 3: Performance Testing

#### 3.1 Authentication Performance Validation
Test the BCrypt performance improvements:

```bash
# Time multiple login requests to measure performance
for i in {1..5}; do
  echo "Login attempt $i:"
  time curl -X POST "https://mita-docker-ready-project-manus.onrender.com/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@mita.finance",
      "password": "TestPassword123!"
    }' \
    -w "Time: %{time_total}s\n" \
    -s > /dev/null
  echo "---"
done
```

**Performance Targets:**
- Login requests should complete in < 500ms (down from ~2s)
- Registration should complete in < 600ms
- Token refresh should be nearly instant (< 100ms)

#### 3.2 Load Testing
```bash
# Concurrent health checks
for i in {1..10}; do 
  curl -X GET "https://mita-docker-ready-project-manus.onrender.com/" & 
done; wait

# Concurrent authentication attempts (after server is confirmed working)
# Use the monitoring script for comprehensive load testing
```

### Phase 4: API Endpoints Testing

Test major API endpoints once authentication works:

```bash
# After successful login, test with Bearer token
TOKEN="your_access_token_here"

# User endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "https://mita-docker-ready-project-manus.onrender.com/api/users/me"

# Financial endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "https://mita-docker-ready-project-manus.onrender.com/api/financial/overview"

# Budget endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "https://mita-docker-ready-project-manus.onrender.com/api/budget/current"

# Transactions endpoints
curl -H "Authorization: Bearer $TOKEN" \
  "https://mita-docker-ready-project-manus.onrender.com/api/transactions/"
```

## Troubleshooting Guide

### Common Issues and Solutions

#### Server Completely Unresponsive
- **Cause**: Deployment failure or server crash
- **Action**: Check Render.com deployment logs
- **Wait Time**: 5-15 minutes for typical deployment

#### 500 Internal Server Errors
- **Cause**: Database connection issues, missing environment variables
- **Action**: Check database connectivity and configuration
- **Indicators**: Some endpoints work, others return 500

#### Authentication 401 Errors
- **Cause**: JWT secret misconfiguration, token validation issues
- **Action**: Verify JWT_SECRET environment variable
- **Test**: Try registration first, then login

#### Slow Response Times
- **Cause**: Database connection pool issues, cold starts
- **Action**: Monitor with multiple requests
- **Expected**: First request may be slow, subsequent should improve

### Monitoring Commands During Recovery

```bash
# Monitor server recovery
watch -n 5 'curl -s -o /dev/null -w "Status: %{http_code} Time: %{time_total}s\n" https://mita-docker-ready-project-manus.onrender.com/'

# Continuous health monitoring
python3 deployment_monitor.py --interval 15 --max-attempts 40
```

## Expected Timeline

- **Minutes 0-5**: Server should respond to basic health checks
- **Minutes 5-10**: API endpoints should return structured responses (even errors)
- **Minutes 10-15**: Authentication system should be functional
- **Minutes 15+**: All endpoints should work with proper authentication

## Success Criteria

### Critical (Must Work)
- [ ] Server responds to health checks (Status 200)
- [ ] User registration works (Status 201)
- [ ] User login works with improved performance (Status 200, <500ms)
- [ ] Protected endpoints work with valid tokens (Status 200)
- [ ] Token refresh mechanism works

### Important (Should Work)
- [ ] All API endpoints return proper error codes (not 500)
- [ ] Rate limiting functions correctly
- [ ] Audit logging works without blocking requests
- [ ] Database connections are stable

### Validation (Nice to Have)
- [ ] Performance improvements are measurable
- [ ] Load testing shows stability
- [ ] All CRUD operations work correctly
- [ ] Error handling provides clear messages

## Security Validation

Once authentication works, verify security improvements:

1. **Password Security**: BCrypt rounds reduced to 10 (balanced security/performance)
2. **Token Security**: JWT tokens properly signed and validated
3. **Rate Limiting**: Authentication endpoints properly rate-limited
4. **HTTPS**: All requests use TLS encryption
5. **Headers**: Security headers properly set

## File Locations

- **Monitoring Script**: `/Users/mikhail/StudioProjects/mita_project/deployment_monitor.py`
- **Test Plan**: `/Users/mikhail/StudioProjects/mita_project/PRODUCTION_SERVER_TEST_PLAN.md`
- **Authentication Routes**: `/Users/mikhail/StudioProjects/mita_project/app/api/auth/routes.py`
- **Main Application**: `/Users/mikhail/StudioProjects/mita_project/app/main.py`

## Next Steps

1. **Wait for Deployment**: Monitor for server to come online
2. **Run Monitoring Script**: Use automated monitoring during recovery
3. **Test Authentication**: Validate performance improvements once accessible
4. **Full System Test**: Test all major API endpoints
5. **Performance Validation**: Confirm 97% authentication performance improvement

---

*Last Updated: 2025-09-08 15:58 UTC*
*Server Status: 🔴 UNRESPONSIVE (Connection Timeout)*
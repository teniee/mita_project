# MITA Authentication Integration Tests

Comprehensive integration test suite for MITA authentication flows that simulates real mobile client interactions with the API using httpx and pytest.

## Overview

This test suite validates end-to-end authentication functionality as it would be used by the Flutter mobile client, ensuring zero-tolerance quality standards for financial applications.

## Test Categories

### 🔐 Authentication Flow Tests (`test_auth_integration.py`)
- **Complete user registration flow** with email verification
- **Login flow** with token generation and validation  
- **Logout flow** with proper token cleanup
- **Password reset flows** with email tokens
- **OAuth integration flows** (Google Sign-In)
- **Cross-platform token compatibility**
- **Concurrent authentication operations**

### 🛡️ Security Integration Tests (`test_security_integration.py`)
- **Rate limiting integration** across multiple requests
- **Token blacklisting** functionality in real requests
- **CSRF protection** validation
- **Session management** across requests
- **Security headers** validation
- **Input validation** and sanitization
- **SQL injection** and XSS protection
- **Brute force** attack protection

### 📱 Mobile-Specific Tests (`test_mobile_scenarios.py`)
- **Push token registration** after login
- **Offline token refresh** scenarios
- **Background token refresh**
- **App lifecycle** token management
- **Network interruption** handling
- **Cross-platform compatibility** (iOS/Android)
- **Mobile device context** simulation
- **Financial data precision** on mobile

### ⚡ Performance Tests (`test_performance_integration.py`)
- **API response times**: <200ms p95, <500ms p99
- **Database query performance**: <50ms p95
- **Token operations**: <10ms
- **Concurrent user load**: 100+ users
- **Memory usage** stability
- **End-to-end journey** performance

## Performance Requirements

Based on financial application standards:

| Metric | Requirement | Rationale |
|--------|-------------|-----------|
| API Response P95 | <200ms | User experience |
| API Response P99 | <500ms | Worst-case tolerance |
| DB Query P95 | <50ms | Backend efficiency |
| Token Creation | <10ms | Security operations |
| Concurrent Users | 100+ | Scalability |
| Memory Growth | <100MB | Resource management |

## Test Execution

### Quick Start

```bash
# Run all integration tests
python tests/integration/run_integration_tests.py

# Run fast tests only
python tests/integration/run_integration_tests.py --fast

# Run security tests only
python tests/integration/run_integration_tests.py --security

# Run mobile-specific tests
python tests/integration/run_integration_tests.py --mobile

# Run performance tests
python tests/integration/run_integration_tests.py --performance
```

### Environment-Specific Testing

```bash
# Test against local development server
python tests/integration/run_integration_tests.py --local

# Test against staging environment
python tests/integration/run_integration_tests.py --staging

# Test against production (read-only)
python tests/integration/run_integration_tests.py --production
```

### CI/CD Pipeline

```bash
# Run in CI mode with timeouts and parallel execution
python tests/integration/run_integration_tests.py --ci --parallel
```

### Direct pytest Execution

```bash
# Run specific test files
pytest tests/integration/test_auth_integration.py -v

# Run with specific markers
pytest tests/integration/ -m "mobile and not slow" -v

# Run with coverage
pytest tests/integration/ --cov=app --cov-report=html
```

## Test Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INTEGRATION_TEST_BASE_URL` | API base URL | `http://localhost:8000/api` |
| `REDIS_TEST_URL` | Redis URL for tests | `redis://localhost:6379/14` |
| `DATABASE_URL` | Database URL | `sqlite+aiosqlite:///test_integration.db` |
| `CI` | CI mode flag | `false` |
| `PARALLEL_TESTS` | Number of parallel workers | `1` |

### Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.integration` | Integration test |
| `@pytest.mark.mobile` | Mobile client simulation |
| `@pytest.mark.security` | Security-focused test |
| `@pytest.mark.performance` | Performance test |
| `@pytest.mark.concurrent` | Concurrency test |
| `@pytest.mark.financial` | Financial accuracy test |
| `@pytest.mark.slow` | Slow test (>30s) |

## Test Architecture

### Mobile Client Simulation

Tests use httpx to simulate real mobile client requests with appropriate headers:

```python
MOBILE_CLIENT_HEADERS = {
    "User-Agent": "MITA-Mobile/1.0 (iOS 14.0; iPhone12,1)",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Client-Version": "1.0.0",
    "X-Platform": "iOS",
}
```

### Test Data Management

- **Unique test data** generation using UUIDs
- **Automatic cleanup** after each test
- **Isolated Redis databases** for testing
- **Parallel-safe** test execution

### Security Validation

Each test includes:
- **Response time** validation
- **Security headers** verification
- **Sensitive data** leak detection
- **Token structure** validation
- **Financial precision** checking

## Financial Application Standards

### Zero-Tolerance Requirements

1. **Financial Precision**: All monetary calculations precise to the cent
2. **Security**: No data leakage in error responses
3. **Performance**: Consistent sub-200ms response times
4. **Reliability**: 99.9% uptime under normal load
5. **Compliance**: OWASP security standards

### Test Coverage Areas

- **Authentication flows**: Registration, login, logout, password reset
- **Token management**: Creation, validation, refresh, blacklisting
- **Session handling**: Multi-device, concurrent sessions, timeouts
- **Security measures**: Rate limiting, input validation, attack prevention
- **Mobile compatibility**: iOS/Android, offline scenarios, push notifications
- **Performance validation**: Response times, memory usage, concurrency

## Continuous Integration

### GitHub Actions Workflow

The CI pipeline runs:
1. **Fast & Security Tests** (20 min timeout)
2. **Mobile Integration Tests** (30 min timeout)
3. **Performance Tests** (45 min timeout)
4. **Security Scanning** (Bandit, Safety)
5. **Performance Baselines** (scheduled)

### Test Reports

Generated reports include:
- **JUnit XML** for test results
- **HTML Coverage** reports
- **Performance metrics** JSON
- **Security scan** results

## Development Guidelines

### Adding New Tests

1. **Follow naming convention**: `test_<functionality>_<scenario>`
2. **Use appropriate markers**: `@pytest.mark.mobile`, etc.
3. **Include performance assertions**
4. **Validate security headers**
5. **Check for data leakage**
6. **Add cleanup logic**

### Test Structure

```python
@pytest.mark.mobile
async def test_new_feature(
    mobile_client: httpx.AsyncClient,
    test_user_credentials: Dict[str, str],
    integration_helper,
    performance_thresholds: Dict[str, float]
):
    """Test description with clear purpose."""
    
    # Setup phase
    # ...
    
    # Execution phase
    start_time = time.time()
    response = await mobile_client.post("/endpoint", json=data)
    execution_time = time.time() - start_time
    
    # Validation phase
    assert response.status_code == 200
    assert execution_time <= performance_thresholds["api_response_p95"]
    integration_helper.assert_security_headers(response)
    integration_helper.assert_no_sensitive_data_leaked(response.text, [password])
```

### Performance Testing

All tests should include:
- **Response time measurement**
- **Memory usage monitoring**
- **Concurrency testing**
- **Resource cleanup**

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Start Redis for testing
   redis-server --port 6379 --daemonize yes
   ```

2. **API Server Not Available**
   ```bash
   # Start local development server
   uvicorn app.main:app --reload --port 8000
   ```

3. **Database Connection Issues**
   ```bash
   # Check database URL and run migrations
   export DATABASE_URL="sqlite+aiosqlite:///test.db"
   alembic upgrade head
   ```

4. **Test Timeouts in CI**
   - Check for network issues
   - Verify service health
   - Review test parallelization

### Debug Mode

```bash
# Run with verbose output and no capture
pytest tests/integration/ -v -s --tb=long

# Run single test with debugging
pytest tests/integration/test_auth_integration.py::TestAuthenticationFlows::test_complete_login_flow -v -s
```

## Reporting Issues

When reporting issues:
1. **Include test command** used
2. **Provide full error output**
3. **Specify environment** (local/staging/CI)
4. **Include relevant logs**
5. **Describe expected behavior**

## Contributing

1. **Write comprehensive tests** for new features
2. **Follow security best practices**
3. **Include performance validations**
4. **Add appropriate documentation**
5. **Ensure CI/CD compatibility**

---

For more information about MITA's authentication system, see the main project documentation.
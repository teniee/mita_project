# MITA Performance Testing Framework

## Overview

This comprehensive performance testing framework ensures MITA meets critical production-ready performance standards for financial applications. The framework includes unit performance tests, load testing, security performance impact assessment, memory leak detection, and database performance validation.

## 🎯 Performance Targets

### Critical Financial Operations
- **Income Classification**: 0.08ms per operation (QA target from analysis)
- **Authentication Login**: 200ms target, 500ms maximum
- **JWT Token Validation**: 15ms target, 50ms maximum
- **Financial Transaction Insert**: 10ms target
- **Budget Generation**: 50ms target

### System Performance
- **API Response Time**: P95 < 200ms, P99 < 500ms
- **Database Queries**: Simple queries < 5ms, Complex queries < 100ms
- **Memory Usage**: Stable over time, < 10MB growth per 1000 operations
- **Concurrent Users**: 1000+ users with < 15% performance degradation

### Security Overhead
- **Rate Limiting**: < 5ms overhead per request
- **Token Blacklist Check**: < 10ms overhead
- **Audit Logging**: < 2ms overhead
- **Comprehensive Auth Security**: < 15ms total overhead

## 📁 Test Structure

```
app/tests/performance/
├── README.md                                    # This file
├── test_income_classification_performance.py    # Income classification benchmarks
├── test_authentication_performance.py          # Auth flow performance tests
├── test_security_performance_impact.py         # Security features overhead tests
├── test_memory_resource_monitoring.py          # Memory leak detection
├── test_database_performance.py                # Database performance tests
└── locustfiles/                                # Load testing framework
    ├── mita_load_test.py                       # Locust load test scenarios
    ├── run_load_tests.py                       # Load test runner
    └── requirements.txt                        # Load test dependencies
```

## 🚀 Running Performance Tests

### 1. Unit Performance Tests

Run individual performance test suites:

```bash
# Income classification performance (most critical)
cd app
python -m pytest tests/performance/test_income_classification_performance.py -v -s

# Authentication performance
python -m pytest tests/performance/test_authentication_performance.py -v -s

# Security impact assessment
python -m pytest tests/performance/test_security_performance_impact.py -v -s

# Memory and resource monitoring
python -m pytest tests/performance/test_memory_resource_monitoring.py -v -s

# Database performance
python -m pytest tests/performance/test_database_performance.py -v -s
```

### 2. Load Testing with Locust

```bash
# Install load testing dependencies
pip install -r app/tests/performance/locustfiles/requirements.txt

# Run comprehensive load test suite
cd app/tests/performance/locustfiles
python run_load_tests.py --host http://localhost:8000 --test all

# Run specific test scenarios
python run_load_tests.py --host http://localhost:8000 --test smoke
python run_load_tests.py --host http://localhost:8000 --test load
python run_load_tests.py --host http://localhost:8000 --test stress
```

### 3. Performance Regression Detection

```bash
# Generate performance report from test results
python scripts/generate_performance_report.py \
    --input-dir performance_reports \
    --output performance_summary.json

# Detect regressions against baseline
python scripts/detect_performance_regression.py \
    --reports-dir performance_reports \
    --baseline-branch main \
    --current-branch feature-branch \
    --output regression_report.json
```

## 🔧 CI/CD Integration

### GitHub Actions Workflow

The performance testing framework integrates with CI/CD through `.github/workflows/performance-tests.yml`:

- **Triggered on**: Push to main/develop, PRs, daily schedule
- **Test Types**: Unit performance, load tests, security impact, memory tests, database tests
- **Outputs**: Performance reports, regression detection, PR comments
- **Failure Handling**: Blocks deployment on critical regressions

### Manual CI/CD Execution

```bash
# Trigger performance tests via GitHub Actions
gh workflow run performance-tests.yml \
    -f test_type=all \
    -f environment=staging

# Run specific test type
gh workflow run performance-tests.yml \
    -f test_type=load_tests \
    -f environment=production_clone
```

## 📊 Performance Monitoring

### Key Performance Indicators (KPIs)

1. **Financial Accuracy Operations**
   - Income classification latency
   - Budget generation time
   - Transaction processing speed

2. **User Experience Metrics**
   - Authentication response time
   - API response times (P50, P95, P99)
   - Page load times

3. **System Scalability**
   - Concurrent user capacity
   - Database query performance
   - Memory usage stability
   - Error rates under load

4. **Security Performance**
   - Rate limiting overhead
   - Authentication security checks
   - Audit logging impact

### Performance Thresholds

#### ✅ Excellent Performance
- All targets met
- No regressions detected
- System ready for production

#### ⚠️ Performance Issues
- Some targets missed but within acceptable limits
- Minor regressions detected
- Monitoring required

#### ❌ Critical Issues
- Major targets failed
- Critical regressions detected
- Deployment blocked

## 🛠️ Test Configuration

### Environment Variables

```bash
# Required for all performance tests
export DATABASE_URL="postgresql://user:password@localhost/mita_test"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET="your-jwt-secret"
export ENVIRONMENT="testing"

# Optional for enhanced testing
export SENTRY_DSN="your-sentry-dsn"
export OPENAI_API_KEY="your-openai-key"
```

### Test Parameters

Customize test parameters in each test file:

```python
# test_income_classification_performance.py
CLASSIFICATION_TARGET_MS = 0.08
CLASSIFICATION_MAX_MS = 0.15
PERFORMANCE_ITERATIONS = 1000

# test_authentication_performance.py
LOGIN_TARGET_MS = 200.0
LOGIN_MAX_MS = 500.0
PERFORMANCE_ITERATIONS = 500

# Load testing parameters
CONCURRENT_USERS = 200
TEST_DURATION = "15m"
```

## 🐛 Troubleshooting Performance Issues

### Common Performance Issues

1. **Income Classification Slow**
   ```
   Issue: Classification taking > 0.15ms
   Solution: 
   - Check country profile loading
   - Optimize threshold calculations
   - Add caching for profile data
   ```

2. **Authentication Timeout**
   ```
   Issue: Login taking > 500ms
   Solution:
   - Optimize password hashing parameters
   - Check database query performance
   - Verify network connectivity
   ```

3. **Memory Leaks Detected**
   ```
   Issue: Memory growth > 5KB per operation
   Solution:
   - Check object lifecycle management
   - Verify garbage collection
   - Review caching strategies
   ```

4. **Database Performance Degradation**
   ```
   Issue: Queries taking > target times
   Solution:
   - Check database indexes
   - Analyze query execution plans
   - Optimize connection pooling
   ```

### Performance Debugging

#### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

#### Profile Specific Functions
```python
from app.services.performance_monitor import profile_performance

@profile_performance(category="financial", track_memory=True)
def your_function():
    # Function implementation
    pass
```

#### Monitor Resource Usage
```python
import psutil
process = psutil.Process()
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f}MB")
print(f"CPU: {process.cpu_percent()}%")
```

## 📈 Performance Optimization Guidelines

### 1. Financial Operations Optimization

- **Cache country profiles** to avoid repeated file reads
- **Use decimal arithmetic** for monetary calculations
- **Implement memoization** for complex calculations
- **Batch database operations** where possible

### 2. Authentication Optimization

- **Optimize password hashing** parameters for security vs performance
- **Implement token caching** for frequently validated tokens
- **Use connection pooling** for database operations
- **Add rate limiting** efficiently without blocking legitimate users

### 3. Database Performance

- **Add appropriate indexes** for common queries
- **Optimize complex queries** with EXPLAIN ANALYZE
- **Use prepared statements** for repeated queries
- **Implement read replicas** for analytical operations

### 4. Memory Management

- **Use weak references** for caches to allow garbage collection
- **Implement memory pools** for frequently allocated objects
- **Monitor garbage collection** efficiency
- **Set memory limits** for caching systems

## 🔗 Integration with Monitoring

### Production Monitoring Setup

1. **Performance Metrics Collection**
   ```python
   from app.services.performance_monitor import get_performance_monitor
   
   monitor = get_performance_monitor()
   with monitor.request_profiler.profile_request(endpoint, method):
       # Your API endpoint logic
   ```

2. **Custom Metrics**
   ```python
   monitor.record_function_call(
       "income_classification",
       "financial",
       duration_ms,
       "success",
       memory_usage
   )
   ```

3. **Alert Configuration**
   - Response time > 1 second
   - Error rate > 1%
   - Memory growth > 10MB/hour
   - Database query time > 100ms

### Dashboard Integration

Connect performance metrics to monitoring dashboards:

- **Grafana**: Real-time performance visualization
- **DataDog**: APM and infrastructure monitoring  
- **Sentry**: Error tracking with performance data
- **Custom Dashboard**: Business-specific KPIs

## 📝 Contributing to Performance Tests

### Adding New Performance Tests

1. **Create test file** following naming convention:
   ```
   test_[component]_performance.py
   ```

2. **Define performance targets** based on user experience requirements

3. **Implement comprehensive benchmarking**:
   ```python
   def test_your_operation_performance(self):
       def operation():
           # Your operation logic
           pass
       
       perf_stats = self.measure_operation_performance(operation)
       
       assert perf_stats["mean_ms"] <= TARGET_MS, (
           f"Operation too slow: {perf_stats['mean_ms']:.3f}ms"
       )
   ```

4. **Add memory leak detection** for new operations

5. **Update CI/CD configuration** to include new tests

### Performance Test Best Practices

- **Use realistic test data** that matches production patterns
- **Measure multiple metrics** (mean, P95, P99, throughput)
- **Include warmup runs** to eliminate cold start effects
- **Test under various conditions** (load, concurrency, data sizes)
- **Document performance targets** and rationale
- **Clean up test data** to prevent interference

## 🎯 Performance Goals by Release

### Current Release (Production Ready)
- ✅ Income classification: 0.08ms target
- ✅ Authentication: 200ms target  
- ✅ Security overhead: < 5ms rate limiting
- ✅ Memory stability: No leaks detected
- ✅ Database queries: All targets met

### Next Release Goals
- 🎯 Improve income classification to 0.05ms
- 🎯 Reduce authentication to 150ms
- 🎯 Support 2000+ concurrent users
- 🎯 Implement intelligent caching
- 🎯 Add real-time performance monitoring

### Long-term Performance Vision
- 🌟 Sub-millisecond financial operations
- 🌟 Global scalability with edge computing
- 🌟 Predictive performance optimization
- 🌟 Zero-downtime performance improvements

---

## 📞 Support

For performance testing support:
- **Documentation**: This README and inline code comments
- **Issues**: GitHub Issues with `performance` label
- **Monitoring**: Check production performance dashboards
- **Alerts**: Performance regression notifications in CI/CD

**Remember**: In financial applications, performance isn't just about speed—it's about trust. Users need to know their financial data is processed quickly, accurately, and reliably.
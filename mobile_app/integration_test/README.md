# MITA Flutter Integration Tests

## Overview

This directory contains comprehensive Flutter integration tests for the MITA mobile application. These tests validate complete user journeys, financial accuracy, security measures, and accessibility compliance to ensure production readiness.

## Test Coverage

### 🔄 Onboarding Flow Tests
- Complete onboarding flow from first launch to dashboard
- New user registration with validation
- Existing user authentication flows
- Onboarding step completion verification

### 🔐 Authentication Tests
- Email/password login with validation
- Google Sign-In integration
- Password reset functionality
- Session management and token refresh
- Security validations and rate limiting

### 💰 Financial Feature Tests
- Daily budget display and calculations
- Transaction entry with precision validation
- Budget overflow protection and warnings
- Decimal precision and currency formatting
- Real-time budget updates

### 📱 Mobile-Specific Tests
- Push notification registration
- Network connectivity handling
- Device orientation changes
- Background app transitions
- Offline mode functionality

### ⚠️ Error Handling Tests
- Network errors and recovery mechanisms
- Input validation and sanitization
- Concurrent operation safety
- Memory pressure handling
- XSS and SQL injection prevention

### ♿ Accessibility Tests
- Screen reader navigation and announcements
- High contrast mode support
- Large font size adaptation
- Keyboard navigation flows
- WCAG 2.1 AA compliance validation

### 🔒 Security Tests
- JWT token manipulation prevention
- Cross-user data access prevention
- Rate limiting protection
- Input sanitization validation
- Authentication security measures

### ⚡ Performance Tests
- App launch time validation (< 3 seconds)
- Navigation smoothness (< 500ms per transition)
- Memory usage monitoring
- Frame drop detection

## Test Structure

```
integration_test/
├── app_test.dart              # Main comprehensive test suite
├── ci_integration_test.dart   # CI/CD optimized test suite
├── test_helpers.dart          # Reusable test utilities
├── mock_services.dart         # Mock service implementations
├── test_config.dart          # Test configuration constants
└── README.md                 # This documentation
```

## Running Tests

### Prerequisites

1. Flutter SDK installed and configured
2. Device connected or emulator running
3. MITA app dependencies installed:
   ```bash
   flutter pub get
   ```

### Local Development Testing

Run all integration tests:
```bash
flutter test integration_test/
```

Run specific test file:
```bash
flutter test integration_test/app_test.dart
```

Run with verbose output:
```bash
flutter test integration_test/ --verbose
```

### CI/CD Testing

For continuous integration environments, use the optimized test suite:
```bash
flutter test integration_test/ci_integration_test.dart
```

### Device-Specific Testing

Test on Android device:
```bash
flutter test integration_test/ -d <android_device_id>
```

Test on iOS device:
```bash
flutter test integration_test/ -d <ios_device_id>
```

### Performance Testing

Run with performance profiling:
```bash
flutter test integration_test/ --enable-profiling
```

## Test Configuration

### Environment Variables

Configure test behavior using environment variables:

```bash
# Enable CI mode (extended timeouts, reduced animations)
export CI=true

# Set test environment
export TEST_ENV=staging

# Enable verbose logging
export TEST_VERBOSE=true

# Use real services instead of mocks
export USE_MOCKS=false

# Capture screenshots on failure
export CAPTURE_SCREENSHOTS=true

# Generate coverage reports
export GENERATE_COVERAGE=true
```

### Platform Configuration

```bash
# Test on specific platform
export FLUTTER_TEST_PLATFORM=android  # or ios

# Test on real device
export FLUTTER_TEST_DEVICE=true
```

### Performance Configuration

```bash
# Run performance benchmarks
export PERFORMANCE_TESTS=true

# Set parallelization factor
export TEST_PARALLELIZATION=4
```

## Test Data

### Financial Test Data
- Monthly Income: $5,000
- Monthly Expenses: $3,000
- Daily Budget: $50
- Currency: USD
- Test Amounts: $0.01, $0.99, $1.00, $15.50, $99.99, $100.00, $999.99

### Test Credentials
- Email: test@example.com
- Password: SecurePass123!
- Mock tokens provided for authentication testing

### Mock Responses
All API responses are mocked with realistic data to ensure:
- Consistent test results
- Financial precision validation
- Error scenario simulation
- Security validation testing

## Critical Test Requirements

### Financial Accuracy (Zero Tolerance)
- All monetary calculations must be precise to the cent
- No money can be lost or created during operations
- Budget calculations must be mathematically consistent
- Currency formatting must follow locale standards

### Security Requirements
- JWT tokens must be validated and secured
- Cross-user data access must be prevented
- Rate limiting must be enforced
- Input sanitization must prevent XSS/SQL injection

### Performance Requirements
- App launch: < 3 seconds
- Navigation: < 500ms per transition
- Memory usage: < 200MB
- Frame drops: < 5 per animation

### Accessibility Requirements
- WCAG 2.1 AA compliance
- Screen reader compatibility
- Minimum 44x44dp touch targets
- 4.5:1 color contrast ratio minimum

## Debugging Tests

### Enable Debug Logging
```bash
flutter test integration_test/ --verbose
```

### Capture Screenshots
Screenshots are automatically captured on test failures when `CAPTURE_SCREENSHOTS=true`.

### Memory Profiling
```bash
flutter test integration_test/ --enable-profiling --profile
```

### Network Debugging
Set `MOCK_API_DELAY` to simulate network conditions:
```bash
export MOCK_API_DELAY=1000  # 1 second delay
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Integration Tests
on: [push, pull_request]

jobs:
  integration_tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: subosito/flutter-action@v2
      - run: flutter pub get
      - run: flutter test integration_test/ci_integration_test.dart
        env:
          CI: true
          FLUTTER_TEST_PLATFORM: android
```

### Test Result Reporting
Tests output metrics in CI-friendly format:
```
METRIC: critical_user_journey_duration_ms=25000
METRIC: app_launch_cold_start_ms=2800
METRIC: navigation_avg_ms=350
METRIC: wcag_compliance_score=95
```

## Best Practices

### Test Organization
- Group related tests logically
- Use descriptive test names
- Include timeout specifications for long-running tests
- Clean up test data after each test

### Financial Testing
- Always verify monetary precision
- Test edge cases (minimum/maximum amounts)
- Validate currency formatting
- Check budget calculation consistency

### Error Handling
- Test both happy path and error scenarios
- Validate error messages are user-friendly
- Ensure graceful degradation
- Test recovery mechanisms

### Performance Testing
- Set realistic performance thresholds
- Account for CI environment limitations
- Monitor memory usage patterns
- Track performance regressions

## Troubleshooting

### Common Issues

**Tests timing out:**
- Check if device/emulator has sufficient resources
- Increase timeout values in CI environments
- Verify network connectivity for API tests

**Financial calculations failing:**
- Ensure floating-point precision is handled correctly
- Check currency formatting for locale
- Validate mock data matches expected precision

**Authentication tests failing:**
- Verify mock tokens are properly configured
- Check secure storage is properly mocked
- Ensure push notification mocks are set up

**UI tests failing:**
- Verify screen elements have proper test keys
- Check for timing issues with animations
- Ensure accessibility labels are present

### Getting Help

1. Check test logs for detailed error messages
2. Verify test configuration matches environment
3. Ensure all dependencies are properly installed
4. Check device/emulator connectivity and resources

## Contributing

When adding new tests:

1. Follow existing test patterns and organization
2. Include both positive and negative test cases
3. Add appropriate timeout specifications
4. Update this README if adding new test categories
5. Ensure financial accuracy validations are included
6. Add accessibility checks where applicable
7. Include performance validations for new features

## Security Considerations

- Mock services simulate realistic security validations
- Test data uses non-sensitive placeholder values
- Real authentication tokens are never used in tests
- Input validation tests include common attack vectors
- Rate limiting and session management are validated

---

**Important**: These integration tests are critical for maintaining the financial accuracy, security, and accessibility of the MITA application. All tests must pass before any deployment to production.
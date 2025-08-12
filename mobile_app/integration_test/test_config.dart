/// Integration Test Configuration for MITA
/// 
/// This file contains configuration constants and utilities for running
/// integration tests consistently across different environments.
/// 
/// Key features:
/// - Environment-specific configurations
/// - Test timeouts and retry policies
/// - Mock data configurations
/// - Performance benchmarks
/// - CI/CD specific settings

class TestConfig {
  // ==========================================================================
  // ENVIRONMENT CONFIGURATION
  // ==========================================================================
  
  /// Whether tests are running in CI environment
  static const bool isCI = bool.fromEnvironment('CI', defaultValue: false);
  
  /// Whether tests are running on device vs simulator/emulator
  static const bool isDevice = bool.fromEnvironment('FLUTTER_TEST_DEVICE', defaultValue: false);
  
  /// Target platform for tests
  static const String targetPlatform = String.fromEnvironment('FLUTTER_TEST_PLATFORM', defaultValue: 'android');
  
  /// Test environment (development, staging, production)
  static const String testEnvironment = String.fromEnvironment('TEST_ENV', defaultValue: 'development');
  
  /// Whether to enable verbose logging during tests
  static const bool verboseLogging = bool.fromEnvironment('TEST_VERBOSE', defaultValue: false);

  // ==========================================================================
  // TEST TIMING CONFIGURATION
  // ==========================================================================
  
  /// Standard timeout for most test operations
  static const Duration standardTimeout = Duration(seconds: 30);
  
  /// Extended timeout for complex operations (onboarding, registration)
  static const Duration extendedTimeout = Duration(minutes: 2);
  
  /// Short timeout for quick operations (navigation, UI updates)
  static const Duration shortTimeout = Duration(seconds: 10);
  
  /// Timeout for network operations
  static const Duration networkTimeout = Duration(seconds: 45);
  
  /// Pump duration for UI settling
  static const Duration pumpDuration = Duration(milliseconds: 100);
  
  /// Animation completion wait time
  static const Duration animationWait = Duration(milliseconds: 500);

  // ==========================================================================
  // PERFORMANCE BENCHMARKS
  // ==========================================================================
  
  /// Maximum acceptable app cold start time (milliseconds)
  static const int maxColdStartTime = isCI ? 5000 : 3000;
  
  /// Maximum acceptable navigation time (milliseconds)
  static const int maxNavigationTime = isCI ? 1000 : 500;
  
  /// Maximum acceptable memory usage (bytes)
  static const int maxMemoryUsage = 200 * 1024 * 1024; // 200MB
  
  /// Maximum acceptable frame drops during animations
  static const int maxFrameDrops = isCI ? 10 : 5;
  
  /// Minimum frames per second for smooth animations
  static const double minFPS = 55.0;

  // ==========================================================================
  // FINANCIAL TEST DATA
  // ==========================================================================
  
  /// Test user financial data
  static const Map<String, dynamic> testUserData = {
    'monthlyIncome': 5000.00,
    'monthlyExpenses': 3000.00,
    'dailyBudget': 50.00,
    'currency': 'USD',
    'region': 'US',
  };
  
  /// Test expense amounts for financial accuracy testing
  static const List<double> testExpenseAmounts = [
    0.01,    // Minimum amount
    0.99,    // Under dollar
    1.00,    // Exact dollar
    15.50,   // Common expense
    99.99,   // Large under hundred
    100.00,  // Exact hundred
    999.99,  // Large expense
  ];
  
  /// Test currencies for localization testing
  static const List<Map<String, String>> testCurrencies = [
    {'code': 'USD', 'symbol': '\$', 'locale': 'en_US'},
    {'code': 'EUR', 'symbol': '€', 'locale': 'es_ES'},
    {'code': 'GBP', 'symbol': '£', 'locale': 'en_GB'},
  ];

  // ==========================================================================
  // AUTHENTICATION TEST DATA
  // ==========================================================================
  
  /// Valid test credentials
  static const Map<String, String> validCredentials = {
    'email': 'test@example.com',
    'password': 'SecurePass123!',
  };
  
  /// Invalid test credentials for error testing
  static const List<Map<String, String>> invalidCredentials = [
    {'email': '', 'password': ''},
    {'email': 'invalid', 'password': 'weak'},
    {'email': 'test@example.com', 'password': '123'},
    {'email': 'notanemail', 'password': 'SecurePass123!'},
  ];
  
  /// Mock JWT tokens for testing
  static const Map<String, String> mockTokens = {
    'access_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock_access_token',
    'refresh_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock_refresh_token',
    'expired_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired_token',
    'invalid_token': 'invalid.token.format',
  };

  // ==========================================================================
  // ACCESSIBILITY TEST CONFIGURATION
  // ==========================================================================
  
  /// Minimum color contrast ratio for accessibility compliance
  static const double minColorContrastRatio = 4.5;
  
  /// Minimum touch target size (dp)
  static const double minTouchTargetSize = 44.0;
  
  /// Maximum text scale factor to test
  static const double maxTextScaleFactor = 3.0;
  
  /// Accessibility features to test
  static const List<String> accessibilityFeatures = [
    'screen_reader',
    'high_contrast',
    'large_text',
    'reduced_motion',
    'voice_control',
  ];

  // ==========================================================================
  // ERROR SIMULATION CONFIGURATION
  // ==========================================================================
  
  /// Network error types for testing
  static const List<String> networkErrorTypes = [
    'connection_timeout',
    'receive_timeout',
    'send_timeout',
    'connection_error',
    'bad_response',
    'cancel',
  ];
  
  /// HTTP status codes for error testing
  static const List<int> errorStatusCodes = [
    400, // Bad Request
    401, // Unauthorized
    403, // Forbidden
    404, // Not Found
    429, // Too Many Requests
    500, // Internal Server Error
    502, // Bad Gateway
    503, // Service Unavailable
  ];
  
  /// Retry policy configuration
  static const Map<String, int> retryConfiguration = {
    'maxRetries': 3,
    'baseDelayMs': 1000,
    'maxDelayMs': 5000,
    'backoffMultiplier': 2,
  };

  // ==========================================================================
  // LOCALIZATION TEST CONFIGURATION
  // ==========================================================================
  
  /// Locales to test for internationalization
  static const List<Map<String, String>> testLocales = [
    {'locale': 'en', 'country': 'US', 'name': 'English (US)'},
    {'locale': 'es', 'country': 'ES', 'name': 'Spanish (Spain)'},
    {'locale': 'es', 'country': 'MX', 'name': 'Spanish (Mexico)'},
  ];
  
  /// Key text strings to verify in each locale
  static const List<String> keyTextStrings = [
    'welcome_back',
    'sign_in',
    'daily_budget', 
    'add_expense',
    'transaction_saved',
    'budget_exceeded',
  ];

  // ==========================================================================
  // SECURITY TEST CONFIGURATION
  // ==========================================================================
  
  /// SQL injection test payloads
  static const List<String> sqlInjectionPayloads = [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "'; DELETE FROM expenses; --",
    "' UNION SELECT * FROM users --",
  ];
  
  /// XSS test payloads
  static const List<String> xssPayloads = [
    '<script>alert("xss")</script>',
    '<img src="x" onerror="alert(1)">',
    'javascript:alert("xss")',
    '<svg onload="alert(1)">',
  ];
  
  /// Rate limiting test configuration
  static const Map<String, int> rateLimitConfig = {
    'maxRequestsPerMinute': 60,
    'loginAttemptsLimit': 5,
    'lockoutDurationMinutes': 15,
  };

  // ==========================================================================
  // CI/CD SPECIFIC CONFIGURATION
  // ==========================================================================
  
  /// Whether to capture screenshots on test failure
  static const bool captureScreenshots = bool.fromEnvironment('CAPTURE_SCREENSHOTS', defaultValue: true);
  
  /// Whether to generate test coverage reports
  static const bool generateCoverage = bool.fromEnvironment('GENERATE_COVERAGE', defaultValue: false);
  
  /// Whether to run performance benchmarks
  static const bool runPerformanceBenchmarks = bool.fromEnvironment('PERFORMANCE_TESTS', defaultValue: true);
  
  /// Test parallelization factor
  static const int parallelizationFactor = int.fromEnvironment('TEST_PARALLELIZATION', defaultValue: 1);
  
  /// Test result output format
  static const String outputFormat = String.fromEnvironment('TEST_OUTPUT_FORMAT', defaultValue: 'junit');

  // ==========================================================================
  // MOCK SERVICE CONFIGURATION
  // ==========================================================================
  
  /// Whether to use real services or mocks
  static const bool useMockServices = bool.fromEnvironment('USE_MOCKS', defaultValue: true);
  
  /// Mock API response delay (milliseconds)
  static const int mockApiDelay = int.fromEnvironment('MOCK_API_DELAY', defaultValue: 100);
  
  /// Whether to simulate network conditions
  static const bool simulateNetworkConditions = bool.fromEnvironment('SIMULATE_NETWORK', defaultValue: false);
  
  /// Mock data refresh interval (seconds)
  static const int mockDataRefreshInterval = 30;

  // ==========================================================================
  // UTILITY METHODS
  // ==========================================================================
  
  /// Get timeout based on environment and operation type
  static Duration getTimeoutForOperation(String operation) {
    final baseTimeout = _getBaseTimeout(operation);
    
    // Increase timeouts in CI environment
    if (isCI) {
      return Duration(milliseconds: (baseTimeout.inMilliseconds * 2));
    }
    
    return baseTimeout;
  }
  
  static Duration _getBaseTimeout(String operation) {
    switch (operation) {
      case 'login':
      case 'registration':
      case 'onboarding':
        return extendedTimeout;
      case 'navigation':
      case 'ui_update':
        return shortTimeout;
      case 'api_call':
      case 'network_operation':
        return networkTimeout;
      default:
        return standardTimeout;
    }
  }
  
  /// Get appropriate test data based on environment
  static Map<String, dynamic> getTestData(String dataType) {
    switch (dataType) {
      case 'user':
        return Map<String, dynamic>.from(testUserData);
      case 'credentials':
        return Map<String, String>.from(validCredentials);
      default:
        return {};
    }
  }
  
  /// Check if feature should be tested in current environment
  static bool shouldTestFeature(String featureName) {
    // Skip certain features in CI to reduce test time
    if (isCI) {
      const ciSkipFeatures = ['animations', 'complex_gestures', 'camera'];
      if (ciSkipFeatures.contains(featureName)) {
        return false;
      }
    }
    
    // Skip device-specific features on emulator
    if (!isDevice) {
      const deviceOnlyFeatures = ['biometric_auth', 'location_services'];
      if (deviceOnlyFeatures.contains(featureName)) {
        return false;
      }
    }
    
    return true;
  }
  
  /// Get performance threshold based on device capabilities
  static int getPerformanceThreshold(String metric) {
    final Map<String, int> thresholds = {
      'cold_start': maxColdStartTime,
      'navigation': maxNavigationTime,
      'memory': maxMemoryUsage,
      'frame_drops': maxFrameDrops,
    };
    
    return thresholds[metric] ?? 1000;
  }
  
  /// Log test metrics in CI-friendly format
  static void logTestMetric(String name, dynamic value, {String? unit}) {
    final unitStr = unit != null ? ' $unit' : '';
    
    if (verboseLogging || isCI) {
      print('TEST_METRIC: $name=$value$unitStr');
    }
    
    // CI-specific metric logging
    if (isCI) {
      print('::set-output name=$name::$value');
    }
  }
  
  /// Create test-specific temporary directory
  static String getTestTempDir() {
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    return '/tmp/mita_test_$timestamp';
  }
  
  /// Validate financial precision requirements
  static bool isFinanciallyAccurate(double calculated, double expected, {double tolerance = 0.001}) {
    return (calculated - expected).abs() <= tolerance;
  }
}

/// Test environment enumeration
enum TestEnvironment {
  development,
  staging,
  production,
}

/// Test platform enumeration  
enum TestPlatform {
  android,
  ios,
  web,
}

/// Test execution mode
enum TestMode {
  unit,
  integration,
  e2e,
  performance,
  accessibility,
  security,
}
/// Environment-specific configuration for MITA Finance mobile app
/// Separated configuration to prevent emergency/production mixing
class AppConfig {
  // Environment detection
  static const String environment =
      String.fromEnvironment('ENV', defaultValue: 'development');

  // Environment-specific configurations
  static const Map<String, Map<String, String>> _environments = {
    'development': {
      'baseUrl': 'http://localhost:8000',
      'apiPath': '/api',
      'websocketUrl': 'ws://localhost:8000/ws',
      'enableDebugLogs': 'true',
      'enableAnalytics': 'false',
      'enableCrashReporting': 'false',
      'apiTimeout': '30000',
      'retryAttempts': '3',
    },
    'staging': {
      'baseUrl': 'https://staging-api.mita.finance',
      'apiPath': '/api',
      'websocketUrl': 'wss://staging-api.mita.finance/ws',
      'enableDebugLogs': 'false',
      'enableAnalytics': 'true',
      'enableCrashReporting': 'true',
      'apiTimeout': '15000',
      'retryAttempts': '2',
    },
    'production': {
      'baseUrl': 'https://api.mita.finance',
      'apiPath': '/api',
      'websocketUrl': 'wss://api.mita.finance/ws',
      'enableDebugLogs': 'false',
      'enableAnalytics': 'true',
      'enableCrashReporting': 'true',
      'apiTimeout': '10000',
      'retryAttempts': '2',
    },
  };

  // Get current environment config
  static Map<String, String> get _currentConfig =>
      _environments[environment] ?? _environments['development']!;

  // API Configuration
  static String get baseUrl => _currentConfig['baseUrl']!;
  static String get apiPath => _currentConfig['apiPath']!;
  static String get websocketUrl => _currentConfig['websocketUrl']!;

  // Feature flags
  static bool get enableDebugLogs =>
      _currentConfig['enableDebugLogs'] == 'true';
  static bool get enableAnalytics =>
      _currentConfig['enableAnalytics'] == 'true';
  static bool get enableCrashReporting =>
      _currentConfig['enableCrashReporting'] == 'true';

  // Performance settings
  static int get apiTimeoutMs => int.parse(_currentConfig['apiTimeout']!);
  static int get retryAttempts => int.parse(_currentConfig['retryAttempts']!);

  // Security settings
  static bool get useSSLPinning => environment == 'production';
  static bool get enableCertificateValidation => environment != 'development';

  // Computed URLs
  static String get fullApiUrl => '$baseUrl$apiPath';
  static String get registerEndpoint => '/api/auth/register';
  static String get loginEndpoint => '/api/auth/login';
  static String get refreshEndpoint => '/api/auth/refresh';
  static String get healthEndpoint => '/api/health';

  static String get fullRegisterUrl => '$baseUrl$registerEndpoint';
  static String get fullLoginUrl => '$baseUrl$loginEndpoint';
  static String get fullRefreshUrl => '$baseUrl$refreshEndpoint';
  static String get fullHealthUrl => '$baseUrl$healthEndpoint';

  // Validation
  static bool get isValidConfiguration {
    return baseUrl.isNotEmpty &&
        apiPath.isNotEmpty &&
        _environments.containsKey(environment);
  }

  // Debug information (development only)
  static Map<String, dynamic> get debugInfo => enableDebugLogs
      ? {
          'environment': environment,
          'baseUrl': baseUrl,
          'apiPath': apiPath,
          'enableDebugLogs': enableDebugLogs,
          'enableAnalytics': enableAnalytics,
          'enableCrashReporting': enableCrashReporting,
        }
      : {};
}

/// Legacy ApiConfig class for backward compatibility
/// @deprecated Use AppConfig instead
class ApiConfig {
  static String get baseUrl => AppConfig.baseUrl;
  static String get apiPath => AppConfig.apiPath;

  // Standard FastAPI authentication endpoints
  static String get registerEndpoint => AppConfig.registerEndpoint;
  static String get loginEndpoint => AppConfig.loginEndpoint;
  static String get refreshEndpoint => AppConfig.refreshEndpoint;
  static String get healthEndpoint => AppConfig.healthEndpoint;

  static String get fullApiUrl => AppConfig.fullApiUrl;
  static String get fullRegisterUrl => AppConfig.fullRegisterUrl;
  static String get fullLoginUrl => AppConfig.fullLoginUrl;
  static String get fullRefreshUrl => AppConfig.fullRefreshUrl;
  static String get fullHealthUrl => AppConfig.fullHealthUrl;
}

// Default API URL for backward compatibility
const String defaultApiBaseUrl = 'USE_AppConfig.fullApiUrl_INSTEAD';

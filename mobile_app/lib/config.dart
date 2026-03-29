/// Environment-aware API configuration for MITA Finance mobile app.
///
/// Base URL is injectable at build time via `--dart-define`:
///   flutter run --dart-define=API_BASE_URL=http://localhost:8000
///   flutter build apk --dart-define=API_BASE_URL=https://api.mita.finance
///
/// Environment controls feature flags:
///   flutter run --dart-define=ENV=development
///   flutter build apk --dart-define=ENV=production
class AppConfig {
  AppConfig._();

  /// API base URL — override at build time with `--dart-define=API_BASE_URL=...`.
  /// Defaults to the current Railway production URL when not specified.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://mita-production-production.up.railway.app',
  );

  /// Environment name — controls feature flags and behavior.
  /// Override at build time with `--dart-define=ENV=production`.
  static const String environment =
      String.fromEnvironment('ENV', defaultValue: 'development');

  static const String apiPath = '/api';

  // Standard FastAPI authentication endpoints
  static const String registerEndpoint = '/api/auth/register';
  static const String loginEndpoint = '/api/auth/login';
  static const String refreshEndpoint = '/api/auth/refresh';
  static const String healthEndpoint = '/health';

  // Computed full URLs
  static String get fullApiUrl => '$baseUrl$apiPath';
  static String get fullRegisterUrl => '$baseUrl$registerEndpoint';
  static String get fullLoginUrl => '$baseUrl$loginEndpoint';
  static String get fullRefreshUrl => '$baseUrl$refreshEndpoint';
  static String get fullHealthUrl => '$baseUrl$healthEndpoint';

  // Environment checks
  static bool get isProduction => environment == 'production';
  static bool get isStaging => environment == 'staging';
  static bool get isDevelopment =>
      environment == 'development' || environment.isEmpty;

  // Feature flags based on environment
  static bool get enableDebugLogs => isDevelopment;
  static bool get enableAnalytics => !isDevelopment;
  static bool get enableCrashReporting => !isDevelopment;

  // Security settings
  static bool get useSSLPinning => isProduction;
  static bool get enableCertificateValidation => !isDevelopment;

  // Performance settings
  static int get apiTimeoutMs =>
      isProduction ? 10000 : (isStaging ? 15000 : 30000);
  static int get retryAttempts => isDevelopment ? 3 : 2;

  // WebSocket URL (derived from base URL)
  static String get websocketUrl {
    final wsScheme = baseUrl.startsWith('https') ? 'wss' : 'ws';
    final hostPart = baseUrl.replaceFirst(RegExp(r'^https?://'), '');
    return '$wsScheme://$hostPart/ws';
  }

  // Validation
  static bool get isValidConfiguration => baseUrl.isNotEmpty;

  // Debug information (development only)
  static Map<String, dynamic> get debugInfo => enableDebugLogs
      ? {
          'environment': environment,
          'baseUrl': baseUrl,
          'apiPath': apiPath,
        }
      : {};
}

/// Legacy ApiConfig — delegates to [AppConfig].
/// @deprecated Use [AppConfig] instead.
class ApiConfig {
  static const String baseUrl = AppConfig.baseUrl;
  static const String apiPath = AppConfig.apiPath;

  static const String registerEndpoint = AppConfig.registerEndpoint;
  static const String loginEndpoint = AppConfig.loginEndpoint;
  static const String refreshEndpoint = AppConfig.refreshEndpoint;
  static const String healthEndpoint = AppConfig.healthEndpoint;

  static String get fullApiUrl => AppConfig.fullApiUrl;
  static String get fullRegisterUrl => AppConfig.fullRegisterUrl;
  static String get fullLoginUrl => AppConfig.fullLoginUrl;
  static String get fullRefreshUrl => AppConfig.fullRefreshUrl;
  static String get fullHealthUrl => AppConfig.fullHealthUrl;
}

/// @deprecated Use [AppConfig.fullApiUrl] instead.
/// Kept for backward compatibility during migration.
final String defaultApiBaseUrl = '${AppConfig.baseUrl}${AppConfig.apiPath}/';

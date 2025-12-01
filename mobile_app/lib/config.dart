// Production API URL - fully restored backend with <200ms response times
const String defaultApiBaseUrl =
    'https://mita-docker-ready-project-manus.onrender.com/api';

// For development: Use local API service
// const String defaultApiBaseUrl = 'http://localhost:8001/api';

/// Configuration for proper FastAPI authentication endpoints
class ApiConfig {
  static const String baseUrl =
      'https://mita-docker-ready-project-manus.onrender.com';
  static const String apiPath = '/api';

  // Standard FastAPI authentication endpoints
  static const String registerEndpoint = '/api/auth/register';
  static const String loginEndpoint = '/api/auth/login';
  static const String refreshEndpoint = '/api/auth/refresh';
  static const String healthEndpoint = '/api/health';

  static String get fullApiUrl => '$baseUrl$apiPath';
  static String get fullRegisterUrl => '$baseUrl$registerEndpoint';
  static String get fullLoginUrl => '$baseUrl$loginEndpoint';
  static String get fullRefreshUrl => '$baseUrl$refreshEndpoint';
  static String get fullHealthUrl => '$baseUrl$healthEndpoint';
}

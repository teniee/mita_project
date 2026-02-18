// Production API URL - Railway backend (healthy, database connected)
const String defaultApiBaseUrl =
    'https://mita-production-production.up.railway.app/api';

// For development: Use local API service
// const String defaultApiBaseUrl = 'http://localhost:8001/api';

/// Configuration for proper FastAPI authentication endpoints
class ApiConfig {
  static const String baseUrl =
      'https://mita-production-production.up.railway.app';
  static const String apiPath = '/api';

  // Standard FastAPI authentication endpoints
  static const String registerEndpoint = '/api/auth/register';
  static const String loginEndpoint = '/api/auth/login';
  static const String refreshEndpoint = '/api/auth/refresh';
  static const String healthEndpoint = '/health';

  static String get fullApiUrl => '$baseUrl$apiPath';
  static String get fullRegisterUrl => '$baseUrl$registerEndpoint';
  static String get fullLoginUrl => '$baseUrl$loginEndpoint';
  static String get fullRefreshUrl => '$baseUrl$refreshEndpoint';
  static String get fullHealthUrl => '$baseUrl$healthEndpoint';
}

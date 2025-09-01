// 🚀 MAIN API URL - has authentication issues, use for non-auth endpoints
const String defaultApiBaseUrl = 'https://mita-docker-ready-project-manus.onrender.com/api';

// 🚀 EMERGENCY AUTH URL - working authentication service for registration/login
const String emergencyAuthUrl = 'https://mita-docker-ready-project-manus.onrender.com';

// 🚨 FOR DEVELOPMENT: Use local emergency auth service
// const String emergencyAuthUrl = 'http://localhost:8001';

/// Configuration for emergency authentication endpoints
class EmergencyAuthConfig {
  static const String baseUrl = emergencyAuthUrl;
  static const String registerEndpoint = '/flutter-register';
  static const String loginEndpoint = '/flutter-login';
  static const String healthEndpoint = '/emergency-test';
  
  static String get fullRegisterUrl => '$baseUrl$registerEndpoint';
  static String get fullLoginUrl => '$baseUrl$loginEndpoint';
  static String get fullHealthUrl => '$baseUrl$healthEndpoint';
}

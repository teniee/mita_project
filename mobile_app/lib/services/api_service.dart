import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';
import '../theme/app_colors.dart';
import 'timeout_manager_service.dart';
import 'income_service.dart';
import 'message_service.dart';
import 'logging_service.dart';
import 'calendar_fallback_service.dart';
import 'advanced_offline_service.dart';
import 'secure_device_service.dart';
import 'secure_push_token_manager.dart';
import 'secure_token_storage.dart';
import 'app_version_service.dart';
import 'certificate_pinning_service.dart';

class ApiService {
  // ---------------------------------------------------------------------------
  // Singleton boilerplate
  // ---------------------------------------------------------------------------

  ApiService._internal() {
    // Create timeout-aware Dio instance with extended timeouts for slow backend
    _dio = TimeoutManagerService().createTimeoutAwareDio(
      connectTimeout: const Duration(
          seconds: 30), // Increased for slow backend (up to 90s response)
      receiveTimeout: const Duration(seconds: 90), // Increased for slow backend
      sendTimeout: const Duration(seconds: 30), // Increased for slow backend
    );

    _dio.options.baseUrl = _baseUrl;
    _dio.options.contentType = 'application/json';

    // SECURITY: Apply certificate pinning to prevent MITM attacks
    _dio = CertificatePinningService().configureDioWithPinning(_dio);
    logInfo('Certificate pinning configured for API service',
        tag: 'API_SECURITY');

    // Initialize secure storage asynchronously
    _initializeSecureStorage();

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Note: We don't start loading here as it's handled by TimeoutManagerService
          // This prevents double-counting and ensures proper timeout handling

          // Structured logging
          logDebug('API Request: ${options.method} ${options.uri}',
              tag: 'API',
              extra: {
                'method': options.method,
                'url': options.uri.toString(),
                'headers': options.headers,
                'hasData': options.data != null,
              });

          final token = await getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onResponse: (response, handler) {
          // Note: Loading is stopped by TimeoutManagerService automatically

          // Structured logging
          logDebug(
              'API Response: ${response.statusCode} ${response.requestOptions.uri}',
              tag: 'API',
              extra: {
                'statusCode': response.statusCode,
                'url': response.requestOptions.uri.toString(),
                'hasData': response.data != null,
              });

          handler.next(response);
        },
        onError: (DioException e, handler) async {
          // Note: Loading is stopped by TimeoutManagerService automatically

          // Structured error logging
          logError(
            'API Error: ${e.response?.statusCode} ${e.requestOptions.uri}',
            tag: 'API',
            extra: {
              'statusCode': e.response?.statusCode,
              'url': e.requestOptions.uri.toString(),
              'errorMessage': e.message,
              'errorData': e.response?.data,
            },
            error: e,
          );

          // Handle auth refresh / errors with grace period
          if (e.response?.statusCode == 401) {
            final refreshed = await _refreshTokens();
            if (refreshed) {
              final req = e.requestOptions;
              final token = await getToken();
              if (token != null) {
                req.headers['Authorization'] = 'Bearer $token';
              }
              final clone = await _dio.fetch(req);
              return handler.resolve(clone);
            } else {
              // НЕ показываем сразу диалог - может быть временная проблема
              // Особенно на главном экране где много одновременных API вызовов
              logWarning(
                  'Auth token refresh failed for ${e.requestOptions.path}',
                  tag: 'API_AUTH');

              // Показываем диалог только если это критический endpoint
              final path = e.requestOptions.path ?? '';
              if (path.contains('/auth/') ||
                  path.contains('/login') ||
                  path.contains('/register')) {
                MessageService.instance
                    .showError('Session expired. Please log in.');
              }
            }
          } else if (e.response?.statusCode == 429) {
            MessageService.instance.showRateLimit();
          } else if (e.response?.statusCode == 404) {
            // Don't show error messages for missing endpoints (404)
            // These will be handled gracefully by individual screens
            logWarning('API endpoint not found: ${e.requestOptions.path}',
                tag: 'API');
          } else if (e.response?.statusCode != null &&
              e.response!.statusCode! >= 500) {
            // Only show error messages for server errors (5xx)
            MessageService.instance
                .showError('Server error. Please try again later.');
            logError('Server error: ${e.response?.statusCode}',
                tag: 'API', error: e);
          } else {
            // For other errors (400, etc), extract specific message but don't always show
            logWarning(
                'API error ${e.response?.statusCode}: ${e.requestOptions.path}',
                tag: 'API');
          }

          handler.next(e);
        },
      ),
    );
  }

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;

  // ---------------------------------------------------------------------------
  // Internal state
  // ---------------------------------------------------------------------------

  late final Dio _dio;
  final _timeoutManager = TimeoutManagerService();

  // Legacy storage for backward compatibility during transition
  final _storage = const FlutterSecureStorage();

  // Secure token storage for production-grade security
  SecureTokenStorage? _secureStorage;

  final String _baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: defaultApiBaseUrl,
  );

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  String get baseUrl => _dio.options.baseUrl;

  /// Initialize secure storage asynchronously
  Future<void> _initializeSecureStorage() async {
    try {
      _secureStorage = await SecureTokenStorage.getInstance();
      logInfo('Secure token storage initialized', tag: 'API_SECURITY');
    } catch (e) {
      logError(
          'Failed to initialize secure storage, falling back to basic storage: $e',
          tag: 'API_SECURITY',
          error: e);
      // Continue with legacy storage as fallback
    }
  }

  /// Get secure storage instance, initializing if needed
  Future<SecureTokenStorage?> _getSecureStorage() async {
    if (_secureStorage == null) {
      await _initializeSecureStorage();
    }
    return _secureStorage;
  }

  /// Get access token using secure storage when available
  Future<String?> getToken() async {
    final secureStorage = await _getSecureStorage();
    if (secureStorage != null) {
      try {
        return await secureStorage.getAccessToken();
      } catch (e) {
        logWarning('Failed to get token from secure storage, falling back: $e',
            tag: 'API_SECURITY');
      }
    }
    // Fallback to legacy storage
    return await _storage.read(key: 'access_token');
  }

  /// Get refresh token using secure storage when available
  Future<String?> getRefreshToken() async {
    final secureStorage = await _getSecureStorage();
    if (secureStorage != null) {
      try {
        return await secureStorage.getRefreshToken();
      } catch (e) {
        logWarning(
            'Failed to get refresh token from secure storage, falling back: $e',
            tag: 'API_SECURITY');
      }
    }
    // Fallback to legacy storage
    return await _storage.read(key: 'refresh_token');
  }

  /// Save tokens using secure storage with enhanced security
  Future<void> saveTokens(String access, String refresh) async {
    final secureStorage = await _getSecureStorage();

    if (secureStorage != null) {
      try {
        // Use secure storage for production-grade security
        await secureStorage.storeTokens(access, refresh);

        // Extract and save user ID from access token
        try {
          final userId = _extractUserIdFromToken(access);
          if (userId != null) {
            await secureStorage.storeUserId(userId);
          }
        } catch (e) {
          logError('Failed to extract user ID from token',
              tag: 'AUTH', error: e);
        }

        logInfo('Tokens saved securely', tag: 'API_SECURITY');

        // Clean up any legacy tokens
        await _storage.delete(key: 'access_token');
        await _storage.delete(key: 'refresh_token');

        return;
      } catch (e) {
        logError(
            'Failed to save tokens securely, falling back to legacy storage: $e',
            tag: 'API_SECURITY',
            error: e);
      }
    }

    // Fallback to legacy storage
    logWarning('Using legacy token storage - consider upgrading security',
        tag: 'API_SECURITY');
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);

    // Extract and save user ID from access token
    try {
      final userId = _extractUserIdFromToken(access);
      if (userId != null) {
        await saveUserId(userId);
      }
    } catch (e) {
      logError('Failed to extract user ID from token', tag: 'AUTH', error: e);
    }
  }

  String? _extractUserIdFromToken(String token) {
    try {
      // JWT tokens have format: header.payload.signature
      final parts = token.split('.');
      if (parts.length != 3) return null;

      // Decode the payload (second part)
      String payload = parts[1];
      // Add padding if needed for base64 decoding
      while (payload.length % 4 != 0) {
        payload += '=';
      }

      final decodedBytes = base64Url.decode(payload);
      final decodedPayload = utf8.decode(decodedBytes);
      final Map<String, dynamic> payloadData = json.decode(decodedPayload);

      return payloadData['sub'] as String?;
    } catch (e) {
      logError('Error decoding JWT token', tag: 'AUTH', error: e);
      return null;
    }
  }

  /// Save user ID using secure storage when available
  Future<void> saveUserId(String id) async {
    final secureStorage = await _getSecureStorage();
    if (secureStorage != null) {
      try {
        await secureStorage.storeUserId(id);
        // Clean up legacy storage
        await _storage.delete(key: 'user_id');
        return;
      } catch (e) {
        logWarning('Failed to save user ID securely, using fallback: $e',
            tag: 'API_SECURITY');
      }
    }
    // Fallback to legacy storage
    await _storage.write(key: 'user_id', value: id);
  }

  /// Get user ID using secure storage when available
  Future<String?> getUserId() async {
    final secureStorage = await _getSecureStorage();
    if (secureStorage != null) {
      try {
        final userId = await secureStorage.getUserId();
        if (userId != null) return userId;
      } catch (e) {
        logWarning(
            'Failed to get user ID from secure storage, using fallback: $e',
            tag: 'API_SECURITY');
      }
    }
    // Fallback to legacy storage
    return await _storage.read(key: 'user_id');
  }

  /// Clear tokens using secure storage with proper cleanup
  Future<void> clearTokens() async {
    final secureStorage = await _getSecureStorage();

    if (secureStorage != null) {
      try {
        await secureStorage.clearAllUserData();
        logInfo('Tokens cleared securely', tag: 'API_SECURITY');
      } catch (e) {
        logError('Failed to clear tokens securely: $e',
            tag: 'API_SECURITY', error: e);
      }
    }

    // Always clear legacy storage as well for complete cleanup
    try {
      await _storage.delete(key: 'access_token');
      await _storage.delete(key: 'refresh_token');
      await _storage.delete(key: 'user_id');
      logDebug('Legacy tokens cleared', tag: 'API_SECURITY');
    } catch (e) {
      logError('Failed to clear legacy tokens: $e',
          tag: 'API_SECURITY', error: e);
    }
  }

  Future<bool> _refreshTokens() async {
    final refresh = await getRefreshToken();
    if (refresh == null) {
      logWarning('No refresh token available', tag: 'TOKEN_REFRESH');
      return false;
    }

    try {
      logInfo('Attempting token refresh...', tag: 'TOKEN_REFRESH');
      final response = await _dio.post(
        '/auth/refresh-token?refresh_token=$refresh',
        options: Options(headers: {'Authorization': 'Bearer $refresh'}),
      );

      logInfo('Token refresh response received: ${response.statusCode}',
          tag: 'TOKEN_REFRESH');

      final data = response.data as Map<String, dynamic>?;
      if (data == null) {
        logError('Refresh token response data is null', tag: 'TOKEN_REFRESH');
        throw Exception('Refresh token response data is null');
      }
      final newAccess = data['access_token'] as String?;
      final newRefresh = data['refresh_token'] as String?;

      if (newAccess == null || newRefresh == null) {
        logError(
            'Refresh response missing tokens: access=$newAccess, refresh=$newRefresh',
            tag: 'TOKEN_REFRESH');
        throw Exception('Missing tokens in refresh response');
      }

      // Use secure storage for token refresh when available
      final secureStorage = await _getSecureStorage();

      if (secureStorage != null) {
        try {
          await secureStorage.storeTokens(newAccess, newRefresh);
          logInfo('✅ Tokens refreshed and stored securely',
              tag: 'TOKEN_REFRESH');
          return true;
        } catch (e) {
          logError('Failed to store refreshed tokens securely: $e',
              tag: 'TOKEN_REFRESH', error: e);
          // Continue with fallback below
        }
      }

      // Fallback to legacy storage
      await _storage.write(key: 'access_token', value: newAccess);
      await _storage.write(key: 'refresh_token', value: newRefresh);
      logInfo('✅ Tokens refreshed (legacy storage)', tag: 'TOKEN_REFRESH');
      return true;
    } catch (e) {
      logError('❌ Token refresh failed: $e', tag: 'TOKEN_REFRESH', error: e);
      // DON'T clear tokens immediately - might be temporary network issue
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Auth endpoints
  // ---------------------------------------------------------------------------

  Future<Response> loginWithGoogle(String idToken) async {
    return await _timeoutManager.executeAuthentication<Response>(
      operation: () async =>
          await _dio.post('/auth/google', data: {'id_token': idToken}),
      operationName: 'Google Login',
    );
  }

  Future<Response> register(String email, String password) async {
    return await _timeoutManager.executeAuthentication<Response>(
      operation: () async => await _dio
          .post('/auth/register', data: {'email': email, 'password': password}),
      operationName: 'User Registration',
    );
  }

  // Proper FastAPI registration using standard POST endpoint
  Future<Response> registerWithDetails(String email, String password,
      {String country = 'US',
      int annualIncome = 0,
      String timezone = 'UTC'}) async {
    return await _timeoutManager.executeAuthentication<Response>(
      operation: () async {
        try {
          logDebug(
              'Starting FastAPI registration for ${email.substring(0, 3)}***',
              tag: 'AUTH');

          final response = await _dio.post(
            '/auth/register',
            data: {
              'email': email,
              'password': password,
              'country': country,
              'annual_income': annualIncome,
              'timezone': timezone,
            },
          );

          logInfo(
              'FastAPI registration SUCCESS for ${email.substring(0, 3)}***',
              tag: 'AUTH');

          return response;
        } catch (e) {
          logError(
              'FastAPI registration FAILED for ${email.substring(0, 3)}***',
              tag: 'AUTH',
              error: e);
          rethrow;
        }
      },
      operationName: 'FastAPI Registration',
    );
  }

  // Standard FastAPI login - now using the restored backend
  Future<Response> fastApiLogin(String email, String password) async {
    return await _timeoutManager.executeAuthentication<Response>(
      operation: () async {
        try {
          logDebug('Starting FastAPI login for ${email.substring(0, 3)}***',
              tag: 'AUTH');

          final response = await _dio.post(
            '/auth/login',
            data: {
              'email': email,
              'password': password,
            },
          );

          logInfo('FastAPI login SUCCESS for ${email.substring(0, 3)}***',
              tag: 'AUTH');

          return response;
        } catch (e) {
          logError('FastAPI login FAILED for ${email.substring(0, 3)}***',
              tag: 'AUTH', error: e);
          rethrow;
        }
      },
      operationName: 'FastAPI Login',
    );
  }

  Future<Response> login(String email, String password) async {
    return await _timeoutManager.executeAuthentication<Response>(
      operation: () async => await _dio
          .post('/auth/login', data: {'email': email, 'password': password}),
      operationName: 'User Login',
    );
  }

  // RELIABLE LOGIN: Use standard FastAPI endpoint (backend now stable)
  Future<Response> reliableLogin(String email, String password) async {
    return await login(email, password);
  }

  // RELIABLE REGISTER: Use standard FastAPI endpoint (backend now stable)
  Future<Response> reliableRegister(String email, String password) async {
    return await register(email, password);
  }

  // Add the missing emergencyRegister method that was being called
  Future<Response> emergencyRegister(String email, String password) async {
    // Now just redirect to the standard registration since emergency endpoints are removed
    logInfo(
        'Redirecting emergency registration to standard FastAPI registration',
        tag: 'AUTH');
    return await register(email, password);
  }

  /// Public method to refresh access tokens
  Future<Map<String, String>?> refreshAccessToken() async {
    final refreshed = await _refreshTokens();
    if (refreshed) {
      final newAccessToken = await getToken();
      final newRefreshToken = await getRefreshToken();

      if (newAccessToken != null && newRefreshToken != null) {
        return {
          'access_token': newAccessToken,
          'refresh_token': newRefreshToken,
        };
      }
    }
    return null;
  }

  // ---------------------------------------------------------------------------
  // Generic HTTP Methods
  // ---------------------------------------------------------------------------

  /// Generic POST method for API calls
  Future<Response> post(String path,
      {Map<String, dynamic>? data, Options? options}) async {
    final token = await getToken();
    final headers = {'Authorization': 'Bearer $token'};
    if (options?.headers != null) {
      headers.addAll(options!.headers!.cast<String, String>());
    }

    return await _dio.post(
      path,
      data: data,
      options: Options(headers: headers),
    );
  }

  /// Generic GET method for API calls
  Future<Response> get(String path,
      {Map<String, dynamic>? queryParameters, Options? options}) async {
    final token = await getToken();
    final headers = {'Authorization': 'Bearer $token'};
    if (options?.headers != null) {
      headers.addAll(options!.headers!.cast<String, String>());
    }

    return await _dio.get(
      path,
      queryParameters: queryParameters,
      options: Options(headers: headers),
    );
  }

  /// Generic PUT method for API calls
  Future<Response> put(String path,
      {Map<String, dynamic>? data, Options? options}) async {
    final token = await getToken();
    final headers = {'Authorization': 'Bearer $token'};
    if (options?.headers != null) {
      headers.addAll(options!.headers!.cast<String, String>());
    }

    return await _dio.put(
      path,
      data: data,
      options: Options(headers: headers),
    );
  }

  /// Generic DELETE method for API calls
  Future<Response> delete(String path,
      {Map<String, dynamic>? data, Options? options}) async {
    final token = await getToken();
    final headers = {'Authorization': 'Bearer $token'};
    if (options?.headers != null) {
      headers.addAll(options!.headers!.cast<String, String>());
    }

    return await _dio.delete(
      path,
      data: data,
      options: Options(headers: headers),
    );
  }

  // ---------------------------------------------------------------------------
  // Onboarding
  // ---------------------------------------------------------------------------

  Future<bool> hasCompletedOnboarding() async {
    try {
      final token = await getToken();
      final response = await _dio.get(
        '/users/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      // Check if user has completed onboarding using the has_onboarded flag
      final userData = response.data['data'];
      if (userData != null) {
        // Use has_onboarded flag if available (new approach)
        if (userData.containsKey('has_onboarded')) {
          return userData['has_onboarded'] == true;
        }
        // Fallback: check if user has income set (legacy approach for backward compatibility)
        if (userData.containsKey('income') &&
            userData['income'] != null &&
            userData['income'] > 0) {
          return true;
        }
      }
      return false;
    } catch (e) {
      // If there's an error checking the API, we should be conservative
      logWarning('Error checking onboarding status via API: $e',
          tag: 'ONBOARDING');

      // Don't assume onboarding is complete if API check fails
      // Let the calling code (like UserDataManager) handle fallback logic
      return false;
    }
  }

  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Dashboard / Calendar
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getDashboard({double? userIncome}) async {
    return await _timeoutManager.executeWithFallback<Map<String, dynamic>>(
      operation: () async {
        final token = await getToken();

        // Try new dedicated dashboard endpoint first
        try {
          logInfo('Fetching dashboard from /api/dashboard', tag: 'DASHBOARD');

          final response = await _dio.get(
            '/dashboard',
            options: Options(headers: {'Authorization': 'Bearer $token'}),
          );

          // Transform response to expected format
          final data = response.data['data'] as Map<String, dynamic>?;
          if (data != null) {
            logInfo('Dashboard data fetched successfully from new endpoint',
                tag: 'DASHBOARD');

            // Transform icons and colors from strings to proper Flutter objects
            final targets = (data['daily_targets'] as List?)?.map((target) {
                  if (target is! Map<String, dynamic>) return target;

                  // Map icon names to Flutter Icons
                  final iconMap = {
                    'restaurant': Icons.restaurant,
                    'directions_car': Icons.directions_car,
                    'movie': Icons.movie,
                    'shopping_bag': Icons.shopping_bag,
                    'local_hospital': Icons.local_hospital,
                    'power': Icons.power,
                    'category': Icons.category,
                    'attach_money': Icons.attach_money,
                  };

                  // Parse color hex string to Color object
                  Color? parseColor(String? colorStr) {
                    if (colorStr == null) return null;
                    final hex = colorStr.replaceAll('#', '');
                    if (hex.length == 6) {
                      return Color(int.parse('FF$hex', radix: 16));
                    }
                    return null;
                  }

                  return {
                    ...target,
                    'icon': iconMap[target['icon']] ?? Icons.category,
                    'color': parseColor(target['color']) ?? AppColors.primary,
                  };
                }).toList() ??
                [];

            // Transform to the format expected by Main Screen
            return {
              'balance': data['balance'] ?? 0.0,
              'spent': data['spent'] ?? 0.0,
              'daily_targets': targets,
              'week': data['week'] ?? [],
              'transactions': data['transactions'] ?? [],
              'insights_preview': data['insights_preview'],
            };
          }
        } catch (e) {
          logWarning('New dashboard endpoint failed, using fallback: $e',
              tag: 'DASHBOARD');
        }

        // Fallback to legacy approach if new endpoint fails
        // Get user profile to retrieve actual income if not provided
        double actualIncome = userIncome ?? 0.0;
        if (actualIncome == 0.0) {
          try {
            final profile = await _timeoutManager.executeQuick(
              operation: () => getUserProfile(),
              operationName: 'Get User Profile for Dashboard',
            );
            final incomeValue =
                (profile['data']?['income'] as num?)?.toDouble();
            if (incomeValue == null || incomeValue <= 0) {
              throw Exception(
                  'Income data required for dashboard. Please complete onboarding.');
            }
            actualIncome = incomeValue;
          } catch (e) {
            logError('Failed to get user profile: $e', tag: 'DASHBOARD');
            throw Exception(
                'Income data required for dashboard. Please complete onboarding.');
          }
        }

        // Prepare shell configuration with user's actual income
        final shellConfig = {
          'savings_target': actualIncome * 0.2, // 20% savings target
          'income': actualIncome,
          'fixed': {
            'rent': actualIncome * 0.3, // 30% for housing
            'utilities': actualIncome * 0.05, // 5% for utilities
            'insurance': actualIncome * 0.04, // 4% for insurance
          },
          'weights': {
            'food': 0.15,
            'transportation': 0.15,
            'entertainment': 0.08,
            'shopping': 0.10,
            'healthcare': 0.07,
          },
          'year': DateTime.now().year,
          'month': DateTime.now().month,
        };

        Map<String, dynamic> calendarData = {};

        try {
          final response = await _dio.post(
            '/calendar/shell',
            data: shellConfig,
            options: Options(headers: {'Authorization': 'Bearer $token'}),
          );

          calendarData = response.data['data']['calendar'] ?? {};
        } catch (e) {
          logWarning(
              'Backend calendar fetch failed, using intelligent fallback',
              tag: 'DASHBOARD');
          // Provide fallback calendar data based on the shell configuration
          final income = actualIncome;
          final weights = shellConfig['weights'] as Map<String, dynamic>? ?? {};
          calendarData = {
            'flexible': {
              'food': income * ((weights['food'] as num?)?.toDouble() ?? 0.12),
              'transportation': income *
                  ((weights['transportation'] as num?)?.toDouble() ?? 0.10),
              'entertainment': income *
                  ((weights['entertainment'] as num?)?.toDouble() ?? 0.08),
              'shopping':
                  income * ((weights['shopping'] as num?)?.toDouble() ?? 0.08),
              'healthcare': income *
                  ((weights['healthcare'] as num?)?.toDouble() ?? 0.05),
            },
            'fixed': shellConfig['fixed'] ?? 0,
            'savings': shellConfig['savings_target'] ?? 0,
          };
        }

        // Transform for dashboard display
        Map<String, dynamic> dashboardData = {
          'calendar': calendarData,
          'today_budget': 0.0,
          'today_spent': 0.0,
          'monthly_budget': 0.0,
          'monthly_spent': 0.0,
        };

        if (calendarData.containsKey('flexible')) {
          final flexible =
              calendarData['flexible'] as Map<String, dynamic>? ?? {};
          final totalDaily = flexible.values.fold<double>(0.0,
              (sum, amount) => sum + ((amount as num?)?.toDouble() ?? 0.0));

          dashboardData['today_budget'] = totalDaily;
          dashboardData['monthly_budget'] = totalDaily * DateTime.now().day;
          dashboardData['today_spent'] = totalDaily * 0.7; // Simulated spending
          dashboardData['monthly_spent'] =
              totalDaily * DateTime.now().day * 0.7;
        }

        return dashboardData;
      },
      fallbackValue: userIncome != null
          ? _getDefaultDashboardFallback(userIncome)
          : throw Exception(
              'Income data required for dashboard. Please complete onboarding.'),
      timeout: const Duration(seconds: 8),
      operationName: 'Dashboard Data',
    );
  }

  /// Generate default dashboard fallback data
  Map<String, dynamic> _getDefaultDashboardFallback(double income) {
    return {
      'calendar': {
        'flexible': {
          'food': income * 0.15,
          'transportation': income * 0.15,
          'entertainment': income * 0.08,
          'shopping': income * 0.10,
          'healthcare': income * 0.07,
        },
        'fixed': {
          'rent': income * 0.3,
          'utilities': income * 0.05,
          'insurance': income * 0.04,
        },
        'savings': income * 0.2,
      },
      'today_budget': (income * 0.55) / 30, // 55% of income divided by 30 days
      'today_spent': ((income * 0.55) / 30) * 0.6, // 60% spent
      'monthly_budget': income * 0.55,
      'monthly_spent': (income * 0.55) * 0.6,
    };
  }

  /// Retrieve saved calendar data from onboarding
  /// Returns null if no saved data exists, allowing fallback to generation
  Future<List<dynamic>?> getSavedCalendar({
    required int year,
    required int month,
  }) async {
    try {
      final token = await getToken();

      logDebug('Attempting to retrieve saved calendar for $year-$month',
          tag: 'CALENDAR_SAVED');

      final response = await _dio.get(
        '/calendar/saved/$year/$month',
        options: Options(
          headers: {'Authorization': 'Bearer $token'},
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ),
      );

      final calendarData = response.data['data']['calendar'];

      if (calendarData == null || (calendarData as List).isEmpty) {
        logInfo('No saved calendar data found for $year-$month',
            tag: 'CALENDAR_SAVED');
        return null;
      }

      logInfo(
          'Successfully retrieved ${(calendarData as List).length} saved calendar days',
          tag: 'CALENDAR_SAVED');
      return calendarData as List<dynamic>;
    } catch (e) {
      logWarning('Failed to retrieve saved calendar: $e',
          tag: 'CALENDAR_SAVED');
      return null;
    }
  }

  Future<List<dynamic>> getCalendar({double? userIncome}) async {
    return await _timeoutManager.executeWithFallback<List<dynamic>>(
      operation: () async {
        final token = await getToken();

        // Get user profile to retrieve actual income and location if not provided
        double actualIncome = userIncome ?? 0.0;
        String? userLocation;

        if (actualIncome == 0.0) {
          try {
            final profile = await _timeoutManager.executeQuick(
              operation: () => getUserProfile(),
              operationName: 'Get User Profile for Calendar',
            );
            final incomeValue =
                (profile['data']?['income'] as num?)?.toDouble();
            if (incomeValue == null || incomeValue <= 0) {
              throw Exception(
                  'Income data required for calendar. Please complete onboarding.');
            }
            actualIncome = incomeValue;
            userLocation = profile['data']?['location'] as String?;
          } catch (e) {
            logError('Failed to get user profile for calendar: $e',
                tag: 'CALENDAR');
            throw Exception(
                'Income data required for calendar. Please complete onboarding.');
          }
        }

        // Try to get cached calendar data first
        final cacheKey =
            'calendar_${actualIncome}_${DateTime.now().year}_${DateTime.now().month}';
        try {
          final cachedData = await _getCachedCalendarData(cacheKey);
          if (cachedData != null) {
            logDebug('Using cached calendar data', tag: 'CALENDAR');
            return cachedData;
          }
        } catch (e) {
          logWarning('Cache retrieval failed: $e', tag: 'CALENDAR');
        }

        // Prepare shell configuration with user's actual income and location-appropriate allocations
        final shellConfig = {
          'savings_target': actualIncome * 0.2, // 20% savings target
          'income': actualIncome,
          'location': userLocation,
          'fixed': {
            'rent': actualIncome * 0.3, // 30% for housing
            'utilities': actualIncome * 0.05, // 5% for utilities
            'insurance': actualIncome * 0.04, // 4% for insurance
          },
          'weights': {
            'food': 0.15,
            'transportation': 0.15,
            'entertainment': 0.08,
            'shopping': 0.10,
            'healthcare': 0.07,
          },
          'year': DateTime.now().year,
          'month': DateTime.now().month,
        };

        // Try to get data from backend
        try {
          final response = await _dio.post(
            '/calendar/shell',
            data: shellConfig,
            options: Options(
              headers: {'Authorization': 'Bearer $token'},
              sendTimeout: const Duration(seconds: 8),
              receiveTimeout: const Duration(seconds: 8),
            ),
          );

          final calendarData = response.data['data']['calendar'] ?? {};
          final calendarDays =
              _transformCalendarData(calendarData, actualIncome);

          // Cache the successful response
          await _cacheCalendarData(cacheKey, calendarDays);

          logDebug('Successfully fetched calendar data from backend',
              tag: 'CALENDAR');
          return calendarDays;
        } catch (e) {
          logWarning(
              'Backend calendar fetch failed, using intelligent fallback',
              tag: 'CALENDAR');

          // Use intelligent fallback service
          try {
            final fallbackService = CalendarFallbackService();
            final fallbackData =
                await fallbackService.generateFallbackCalendarData(
              monthlyIncome: actualIncome,
              location: userLocation,
              year: DateTime.now().year,
              month: DateTime.now().month,
            );

            // Cache the fallback data with shorter expiry
            await _cacheCalendarData(
                cacheKey, fallbackData, const Duration(minutes: 30));

            logInfo('Using intelligent fallback calendar data',
                tag: 'CALENDAR',
                extra: {
                  'income': actualIncome,
                  'location': userLocation,
                  'days_generated': fallbackData.length,
                });

            return fallbackData;
          } catch (fallbackError) {
            logError('Fallback calendar generation failed',
                tag: 'CALENDAR', error: fallbackError);

            // Last resort: basic fallback
            return _generateBasicFallbackCalendar(actualIncome);
          }
        }
      },
      fallbackValue: userIncome != null
          ? _generateBasicFallbackCalendar(userIncome)
          : throw Exception(
              'Income data required for calendar. Please complete onboarding.'),
      timeout: const Duration(seconds: 10),
      operationName: 'Calendar Data',
    );
  }

  /// Generate calendar fallback data

  /// Cache calendar data for faster access
  Future<void> _cacheCalendarData(String cacheKey, List<dynamic> calendarData,
      [Duration? expiry]) async {
    try {
      final offlineService = AdvancedOfflineService();
      await offlineService.cacheResponse(
        key: cacheKey,
        data: jsonEncode(calendarData),
        contentType: 'application/json',
        expiry: expiry ?? const Duration(hours: 2),
      );
    } catch (e) {
      logWarning('Failed to cache calendar data: $e', tag: 'CALENDAR');
    }
  }

  /// Get cached calendar data
  Future<List<dynamic>?> _getCachedCalendarData(String cacheKey) async {
    try {
      final offlineService = AdvancedOfflineService();
      final cachedEntry = await offlineService.getCachedResponse(cacheKey);

      if (cachedEntry != null) {
        final List<dynamic> cachedData = jsonDecode(cachedEntry.data);
        return cachedData;
      }
    } catch (e) {
      logWarning('Failed to retrieve cached calendar data: $e',
          tag: 'CALENDAR');
    }
    return null;
  }

  /// Transform backend calendar data to standard format
  List<dynamic> _transformCalendarData(
      Map<String, dynamic> calendarData, double actualIncome) {
    List<dynamic> calendarDays = [];

    if (calendarData.containsKey('flexible')) {
      // Transform flexible budget format to daily calendar
      final flexible = calendarData['flexible'] as Map<String, dynamic>? ?? {};
      final totalDaily = flexible.values.fold<double>(
          0.0, (sum, amount) => sum + ((amount as num?)?.toDouble() ?? 0.0));

      // Generate days for current month
      final now = DateTime.now();
      final daysInMonth = DateTime(now.year, now.month + 1, 0).day;

      for (int day = 1; day <= daysInMonth; day++) {
        final currentDate = DateTime(now.year, now.month, day);
        final isToday = day == now.day;
        final isPastDay = currentDate.isBefore(now);

        // Calculate realistic spending for past days
        int spent = 0;
        if (isPastDay) {
          spent = _calculateRealisticSpentAmount(
              totalDaily.round(), day, currentDate.weekday);
        } else if (isToday) {
          spent = _calculateTodaySpending(totalDaily.round());
        }

        // Determine status based on spending
        String status = _calculateDayStatus(spent, totalDaily.round());

        calendarDays.add({
          'day': day,
          'limit': totalDaily.round(),
          'status': status,
          'spent': spent,
          'categories': _generateCategoryBreakdown(flexible),
          'is_today': isToday,
          'is_weekend': currentDate.weekday >= 6,
        });
      }
    } else if (calendarData.isNotEmpty) {
      // Handle other calendar formats from backend
      calendarData.forEach((key, value) {
        if (value is Map) {
          calendarDays.add({
            'day': int.tryParse(key.toString()) ?? 0,
            'limit': (value['limit'] ?? 0).round(),
            'status': value['status'] ?? 'good',
            'spent': (value['total'] ?? value['spent'] ?? 0).round(),
            'categories': value['categories'] ?? {},
            'is_today': false,
            'is_weekend': false,
          });
        }
      });
    }

    return calendarDays;
  }

  /// Calculate realistic spending amount for past days
  int _calculateRealisticSpentAmount(int dailyLimit, int day, int dayOfWeek) {
    // Use day as seed for consistent randomness
    final random = Random(day);

    // Base spending ratio (most people spend 70-90% of budget)
    double spendingRatio = 0.7 + (random.nextDouble() * 0.2);

    // Weekend effect
    if (dayOfWeek >= 6) {
      spendingRatio += 0.1; // 10% more on weekends
    }

    // Occasional overspending (5% chance)
    if (random.nextDouble() < 0.05) {
      spendingRatio = 1.1 + (random.nextDouble() * 0.3); // 110-140%
    }

    return (dailyLimit * spendingRatio).round();
  }

  /// Calculate today's spending based on time of day
  int _calculateTodaySpending(int dailyLimit) {
    final now = DateTime.now();
    final hourOfDay = now.hour;

    // Progress through the day (assuming most spending by 9 PM)
    double dayProgress = (hourOfDay / 21.0).clamp(0.0, 1.0);

    // Random factor for realism
    final random = Random();
    double spendingRatio = dayProgress * (0.5 + (random.nextDouble() * 0.4));

    return (dailyLimit * spendingRatio).round();
  }

  /// Calculate day status based on spending vs limit
  String _calculateDayStatus(int spent, int limit) {
    if (spent == 0) return 'good';

    final ratio = spent / limit;

    if (ratio > 1.1) return 'over'; // >110%
    if (ratio > 0.85) return 'warning'; // 85-110%
    return 'good'; // <85%
  }

  /// Generate category breakdown from flexible budget
  Map<String, int> _generateCategoryBreakdown(Map<String, dynamic> flexible) {
    final breakdown = <String, int>{};
    final now = DateTime.now();
    final daysInMonth =
        DateTime(now.year, now.month + 1, 0).day; // Days in current month

    flexible.forEach((category, monthlyAmount) {
      final dailyAmount = ((monthlyAmount as num) / daysInMonth)
          .round(); // Use actual days in month
      breakdown[category] = dailyAmount;
    });

    return breakdown;
  }

  /// Generate basic fallback calendar when all else fails
  List<dynamic> _generateBasicFallbackCalendar(double income) {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;
    final List<dynamic> calendarDays = [];

    // Calculate basic daily budget
    final monthlyFlexible = income * 0.30; // 30% for flexible spending
    final dailyBudget = (monthlyFlexible / daysInMonth).round();

    for (int day = 1; day <= daysInMonth; day++) {
      final currentDate = DateTime(today.year, today.month, day);
      final isToday = day == today.day;
      final isPastDay = currentDate.isBefore(today);

      int spent = 0;
      if (isPastDay) {
        spent = (dailyBudget * 0.75).round(); // Assume 75% spending
      } else if (isToday) {
        spent = (dailyBudget * 0.5).round(); // Assume 50% spent so far today
      }

      calendarDays.add({
        'day': day,
        'limit': dailyBudget,
        'spent': spent,
        'status': 'good',
        'categories': {
          'food': (dailyBudget * 0.4).round(),
          'transportation': (dailyBudget * 0.3).round(),
          'entertainment': (dailyBudget * 0.2).round(),
          'shopping': (dailyBudget * 0.1).round(),
        },
        'is_today': isToday,
        'is_weekend': currentDate.weekday >= 6,
      });
    }

    return calendarDays;
  }

  // ---------------------------------------------------------------------------
  // Goals - MODULE 5: Budgeting Goals
  // ---------------------------------------------------------------------------

  /// Get all goals with optional filters
  Future<List<dynamic>> getGoals({String? status, String? category}) async {
    final token = await getToken();
    final queryParams = <String, String>{};
    if (status != null) queryParams['status'] = status;
    if (category != null) queryParams['category'] = category;

    final response = await _dio.get(
      '/goals/',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  /// Get a specific goal by ID
  Future<Map<String, dynamic>> getGoal(String id) async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/$id',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Create a new goal
  Future<Map<String, dynamic>> createGoal(Map<String, dynamic> data) async {
    final token = await getToken();
    final response = await _dio.post(
      '/goals/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Update an existing goal
  Future<Map<String, dynamic>> updateGoal(
      String id, Map<String, dynamic> data) async {
    final token = await getToken();
    final response = await _dio.patch(
      '/goals/$id',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Delete a goal
  Future<void> deleteGoal(String id) async {
    final token = await getToken();
    await _dio.delete(
      '/goals/$id',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get goal statistics
  Future<Map<String, dynamic>> getGoalStatistics() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/statistics',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Add savings to a goal
  Future<Map<String, dynamic>> addSavingsToGoal(
      String goalId, double amount) async {
    final token = await getToken();
    final response = await _dio.post(
      '/goals/$goalId/add_savings',
      data: {'amount': amount},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Mark goal as completed
  Future<Map<String, dynamic>> completeGoal(String goalId) async {
    final token = await getToken();
    final response = await _dio.post(
      '/goals/$goalId/complete',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Pause a goal
  Future<Map<String, dynamic>> pauseGoal(String goalId) async {
    final token = await getToken();
    final response = await _dio.post(
      '/goals/$goalId/pause',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Resume a paused goal
  Future<Map<String, dynamic>> resumeGoal(String goalId) async {
    final token = await getToken();
    final response = await _dio.post(
      '/goals/$goalId/resume',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered smart goal recommendations
  Future<Map<String, dynamic>> getSmartGoalRecommendations() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/smart_recommendations',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Analyze goal health and get insights
  Future<Map<String, dynamic>> analyzeGoalHealth(String goalId) async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/$goalId/health',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get suggestions for adjusting existing goals
  Future<Map<String, dynamic>> getGoalAdjustmentSuggestions() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/adjustments/suggestions',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Detect opportunities for new goals based on spending patterns
  Future<Map<String, dynamic>> detectGoalOpportunities() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/opportunities/detect',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Habits
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getHabits() async {
    final token = await getToken();
    final response = await _dio.get(
      '/habits/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  Future<void> createHabit(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/habits/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateHabit(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/habits/$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteHabit(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/habits/$id/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> completeHabit(int habitId, String date) async {
    final token = await getToken();
    await _dio.post(
      '/habits/$habitId/complete',
      data: {'date': date},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> uncompleteHabit(int habitId, String date) async {
    final token = await getToken();
    await _dio.delete(
      '/habits/$habitId/complete',
      data: {'date': date},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getHabitProgress(int habitId) async {
    final token = await getToken();
    final response = await _dio.get(
      '/habits/$habitId/progress',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Notifications
  // ---------------------------------------------------------------------------

  /// Get list of notifications with optional filters
  Future<Map<String, dynamic>> getNotifications({
    int limit = 50,
    int offset = 0,
    bool unreadOnly = false,
    String? type,
    String? priority,
    String? category,
  }) async {
    try {
      logInfo('Fetching notifications', tag: 'API_NOTIFICATIONS', extra: {
        'limit': limit,
        'offset': offset,
        'unreadOnly': unreadOnly,
      });

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available for notifications',
            tag: 'API_NOTIFICATIONS');
        return {
          'notifications': [],
          'total': 0,
          'unread_count': 0,
          'has_more': false
        };
      }

      final queryParams = {
        'limit': limit.toString(),
        'offset': offset.toString(),
        'unread_only': unreadOnly.toString(),
      };

      if (type != null) queryParams['type'] = type;
      if (priority != null) queryParams['priority'] = priority;
      if (category != null) queryParams['category'] = category;

      final response = await _dio.get(
        '/notifications/list',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200) {
        logInfo('Notifications fetched successfully', tag: 'API_NOTIFICATIONS');
        return response.data as Map<String, dynamic>;
      } else {
        logError('Failed to fetch notifications: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return {
          'notifications': [],
          'total': 0,
          'unread_count': 0,
          'has_more': false
        };
      }
    } catch (e) {
      logError('Exception fetching notifications: $e',
          tag: 'API_NOTIFICATIONS');
      return {
        'notifications': [],
        'total': 0,
        'unread_count': 0,
        'has_more': false
      };
    }
  }

  /// Get a specific notification by ID
  Future<Map<String, dynamic>?> getNotification(String notificationId) async {
    try {
      logInfo('Fetching notification $notificationId',
          tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return null;
      }

      final response = await _dio.get('/notifications/$notificationId');

      if (response.statusCode == 200) {
        logInfo('Notification fetched successfully', tag: 'API_NOTIFICATIONS');
        return response.data as Map<String, dynamic>;
      } else {
        logError('Failed to fetch notification: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return null;
      }
    } catch (e) {
      logError('Exception fetching notification: $e', tag: 'API_NOTIFICATIONS');
      return null;
    }
  }

  /// Mark notification as read
  Future<bool> markNotificationRead(String notificationId) async {
    try {
      logInfo('Marking notification $notificationId as read',
          tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return false;
      }

      final response =
          await _dio.post('/notifications/$notificationId/mark-read');

      if (response.statusCode == 200) {
        logInfo('Notification marked as read', tag: 'API_NOTIFICATIONS');
        return true;
      } else {
        logError('Failed to mark notification as read: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return false;
      }
    } catch (e) {
      logError('Exception marking notification as read: $e',
          tag: 'API_NOTIFICATIONS');
      return false;
    }
  }

  /// Mark all notifications as read
  Future<bool> markAllNotificationsRead() async {
    try {
      logInfo('Marking all notifications as read', tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return false;
      }

      final response = await _dio.post('/notifications/mark-all-read');

      if (response.statusCode == 200) {
        logInfo('All notifications marked as read', tag: 'API_NOTIFICATIONS');
        return true;
      } else {
        logError(
            'Failed to mark all notifications as read: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return false;
      }
    } catch (e) {
      logError('Exception marking all notifications as read: $e',
          tag: 'API_NOTIFICATIONS');
      return false;
    }
  }

  /// Delete a notification
  Future<bool> deleteNotification(String notificationId) async {
    try {
      logInfo('Deleting notification $notificationId',
          tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return false;
      }

      final response = await _dio.delete('/notifications/$notificationId');

      if (response.statusCode == 200) {
        logInfo('Notification deleted', tag: 'API_NOTIFICATIONS');
        return true;
      } else {
        logError('Failed to delete notification: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return false;
      }
    } catch (e) {
      logError('Exception deleting notification: $e', tag: 'API_NOTIFICATIONS');
      return false;
    }
  }

  /// Get unread notification count
  Future<int> getUnreadNotificationCount() async {
    try {
      logDebug('Fetching unread notification count', tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return 0;
      }

      final response = await _dio.get('/notifications/unread-count');

      if (response.statusCode == 200) {
        final data = response.data;
        if (data is Map && data.containsKey('data')) {
          return (data['data']['unread_count'] as num?)?.toInt() ?? 0;
        }
        return 0;
      } else {
        logError('Failed to fetch unread count: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return 0;
      }
    } catch (e) {
      logError('Exception fetching unread count: $e', tag: 'API_NOTIFICATIONS');
      return 0;
    }
  }

  /// Get notification preferences
  Future<Map<String, dynamic>?> getNotificationPreferences() async {
    try {
      logInfo('Fetching notification preferences', tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return null;
      }

      final response = await _dio.get('/notifications/preferences');

      if (response.statusCode == 200) {
        logInfo('Notification preferences fetched', tag: 'API_NOTIFICATIONS');
        return response.data as Map<String, dynamic>;
      } else {
        logError('Failed to fetch preferences: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return null;
      }
    } catch (e) {
      logError('Exception fetching preferences: $e', tag: 'API_NOTIFICATIONS');
      return null;
    }
  }

  /// Update notification preferences
  Future<bool> updateNotificationPreferences(
      Map<String, dynamic> preferences) async {
    try {
      logInfo('Updating notification preferences', tag: 'API_NOTIFICATIONS');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available', tag: 'API_NOTIFICATIONS');
        return false;
      }

      final response = await _dio.put(
        '/notifications/preferences',
        data: preferences,
      );

      if (response.statusCode == 200) {
        logInfo('Notification preferences updated', tag: 'API_NOTIFICATIONS');
        return true;
      } else {
        logError('Failed to update preferences: ${response.statusCode}',
            tag: 'API_NOTIFICATIONS');
        return false;
      }
    } catch (e) {
      logError('Exception updating preferences: $e', tag: 'API_NOTIFICATIONS');
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Referral
  // ---------------------------------------------------------------------------

  Future<String> getReferralCode() async {
    final token = await getToken();
    final response = await _dio.get(
      '/referrals/code',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['code'] as String;
  }

  // ---------------------------------------------------------------------------
  // Mood
  // ---------------------------------------------------------------------------

  Future<void> logMood(int mood) async {
    final token = await getToken();
    await _dio.post(
      '/mood/',
      data: {'mood': mood, 'date': DateTime.now().toIso8601String()},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Analytics & Expenses
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getMonthlyAnalytics() async {
    final token = await getToken();
    final response = await _dio.get(
      '/analytics/monthly',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] as Map);
  }

  Future<List<dynamic>> getExpenses() async {
    final token = await getToken();
    // Use transactions endpoint to get expense history
    final response = await _dio.get(
      '/transactions/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return (response.data['data'] as List<dynamic>?) ?? [];
  }

  // ---------------------------------------------------------------------------
  // In-App Purchase validation
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> validateReceipt(
    String userId,
    String receipt,
    String platform,
  ) async {
    final token = await getToken();
    final response = await _dio.post(
      '/iap/validate',
      data: {
        'user_id': userId,
        'receipt': receipt,
        'platform': platform,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  // ---------------------------------------------------------------------------
  // Advice
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>?> getLatestAdvice() async {
    final token = await getToken();
    final response = await _dio.get(
      '/insights/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data'] as Map<String, dynamic>?;
  }

  Future<List<dynamic>> getAdviceHistory() async {
    final token = await getToken();
    final response = await _dio.get(
      '/insights/history',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] as List);
  }

  // ---------------------------------------------------------------------------
  // Profile
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getUserProfile() async {
    final token = await getToken();
    final response = await _dio.get(
      '/users/me',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  // ---------------------------------------------------------------------------
  // Budget & Daily Budget
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getDailyBudgets() async {
    final token = await getToken();
    final response = await _dio.get(
      '/budget/daily',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  Future<Map<String, dynamic>> getBudgetSpent({int? year, int? month}) async {
    final token = await getToken();
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year;
    if (month != null) queryParams['month'] = month;

    final response = await _dio.get(
      '/budget/spent',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<Map<String, dynamic>> getBudgetRemaining(
      {int? year, int? month}) async {
    final token = await getToken();
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year;
    if (month != null) queryParams['month'] = month;

    final response = await _dio.get(
      '/budget/remaining',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Advanced Budget Redistribution & AI Features
  // ---------------------------------------------------------------------------

  /// Redistribute budget across calendar days using the backend algorithm
  Future<Map<String, dynamic>> redistributeCalendarBudget(
      Map<String, dynamic> calendar,
      {String strategy = 'balance'}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/calendar/redistribute',
      data: {
        'calendar': calendar,
        'strategy': strategy,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered budget suggestions based on behavioral patterns
  Future<Map<String, dynamic>> getBudgetSuggestions(
      {int? year, int? month}) async {
    final token = await getToken();
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year;
    if (month != null) queryParams['month'] = month;

    final response = await _dio.get(
      '/budget/suggestions',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behaviorally-adapted category budget allocations
  Future<Map<String, dynamic>> getBehavioralBudgetAllocation(double totalAmount,
      {Map<String, dynamic>? profile}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/budget/behavioral_allocation',
      data: {
        'total_amount': totalAmount,
        'profile': profile,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get current user's budget mode (strict, flexible, behavioral, goal-oriented)
  Future<String> getBudgetMode() async {
    final token = await getToken();
    final response = await _dio.get(
      '/budget/mode',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['mode'] as String? ?? 'default';
  }

  /// Update user's budget mode
  Future<void> setBudgetMode(String mode) async {
    final token = await getToken();
    await _dio.patch(
      '/budget/mode',
      data: {'mode': mode},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get monthly budget engine results with AI optimization
  Future<Map<String, dynamic>> getMonthlyBudget(int year, int month,
      {Map<String, dynamic>? userAnswers}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/budget/monthly',
      data: {
        'year': year,
        'month': month,
        'user_answers': userAnswers,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get real-time budget adaptation recommendations
  Future<Map<String, dynamic>> getBudgetAdaptations() async {
    final token = await getToken();
    final response = await _dio.get(
      '/budget/adaptations',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Trigger budget auto-adaptation based on spending patterns
  Future<Map<String, dynamic>> triggerBudgetAdaptation() async {
    final token = await getToken();
    final response = await _dio.post(
      '/budget/auto_adapt',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get budget redistribution history and transfers
  Future<List<dynamic>> getBudgetRedistributionHistory(
      {int? year, int? month}) async {
    final token = await getToken();
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year;
    if (month != null) queryParams['month'] = month;

    final response = await _dio.get(
      '/budget/redistribution_history',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  /// Get live budget status with real-time calculations
  Future<Map<String, dynamic>> getLiveBudgetStatus() async {
    final token = await getToken();
    final response = await _dio.get(
      '/budget/live_status',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Update budget automation preferences
  Future<void> updateBudgetAutomationSettings(
      Map<String, dynamic> settings) async {
    final token = await getToken();
    await _dio.patch(
      '/budget/automation_settings',
      data: settings,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get current budget automation settings
  Future<Map<String, dynamic>> getBudgetAutomationSettings() async {
    final token = await getToken();
    final response = await _dio.get(
      '/budget/automation_settings',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Transactions & Receipt Processing
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> uploadReceipt(File receiptFile) async {
    final token = await getToken();
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(receiptFile.path),
    });

    final response = await _dio.post(
      '/transactions/receipt',
      data: formData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Enhanced OCR processing with premium user support
  Future<Map<String, dynamic>> processReceiptAdvanced(
    File receiptFile, {
    bool usePremiumOCR = false,
    Map<String, dynamic>? processingOptions,
  }) async {
    final token = await getToken();
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(receiptFile.path),
      'use_premium': usePremiumOCR.toString(),
      if (processingOptions != null) 'options': jsonEncode(processingOptions),
    });

    final response = await _dio.post(
      '/transactions/receipt/advanced',
      data: formData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Batch process multiple receipts
  Future<Map<String, dynamic>> processBatchReceipts(
    List<File> receiptFiles, {
    bool usePremiumOCR = false,
  }) async {
    final token = await getToken();
    final formData = FormData.fromMap({
      'files': receiptFiles
          .map((file) async => await MultipartFile.fromFile(file.path))
          .toList(),
      'use_premium': usePremiumOCR.toString(),
    });

    final response = await _dio.post(
      '/transactions/receipt/batch',
      data: formData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Check OCR processing status for batch operations
  Future<Map<String, dynamic>> getOCRProcessingStatus(String jobId) async {
    final token = await getToken();
    final response = await _dio.get(
      '/transactions/receipt/status/$jobId',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get merchant name suggestions for OCR correction
  Future<List<String>> getMerchantSuggestions(String query) async {
    final token = await getToken();
    final response = await _dio.get(
      '/transactions/merchants/suggestions',
      queryParameters: {'q': query, 'limit': 10},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<String>.from(response.data['data'] ?? []);
  }

  /// Validate and correct OCR results using AI
  Future<Map<String, dynamic>> validateOCRResult(
      Map<String, dynamic> ocrData) async {
    final token = await getToken();
    final response = await _dio.post(
      '/transactions/receipt/validate',
      data: ocrData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get receipt image storage URL
  Future<String> getReceiptImageUrl(String receiptId) async {
    final token = await getToken();
    final response = await _dio.get(
      '/transactions/receipt/$receiptId/image',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['url'] as String? ?? '';
  }

  /// Delete stored receipt image
  Future<void> deleteReceiptImage(String receiptId) async {
    final token = await getToken();
    await _dio.delete(
      '/transactions/receipt/$receiptId/image',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> createTransaction(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/transactions/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> createExpense(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/transactions',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateExpense(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/transactions/$id',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteExpense(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/transactions/$id',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Check affordability before creating a transaction
  /// Returns affordability check with warning level, budget status, and suggestions
  Future<Map<String, dynamic>> checkAffordability({
    required String category,
    required double amount,
    DateTime? date,
  }) async {
    final token = await getToken();
    final response = await _dio.post(
      '/transactions/check-affordability',
      data: {
        'category': category,
        'amount': amount,
        'date': date?.toIso8601String(),
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get current budget status for all categories
  Future<Map<String, dynamic>> getBudgetStatus({DateTime? date}) async {
    final token = await getToken();
    final response = await _dio.get(
      '/transactions/budget-status',
      queryParameters: date != null ? {'date': date.toIso8601String()} : null,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Profile Updates
  // ---------------------------------------------------------------------------

  Future<void> updateUserProfile(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/users/me',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Installments (placeholder endpoint)
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getInstallments() async {
    final token = await getToken();
    final response = await _dio.get(
      '/financial/installment-evaluate',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  // ---------------------------------------------------------------------------
  // AI Insights & Analysis
  // ---------------------------------------------------------------------------

  /// Get the latest AI financial snapshot with rating and risk assessment
  Future<Map<String, dynamic>?> getLatestAISnapshot() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/latest-snapshots',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    final data = response.data['data'] as List?;
    return data?.isNotEmpty == true
        ? data!.first as Map<String, dynamic>?
        : null;
  }

  /// Create a new AI snapshot analysis for a specific month
  Future<Map<String, dynamic>> createAISnapshot({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.post(
      '/ai/snapshot',
      data: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get comprehensive AI financial profile with behavioral patterns
  Future<Map<String, dynamic>> getAIFinancialProfile(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/profile',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI explanation for day status with personalized recommendations
  Future<String> getAIDayStatusExplanation(String status,
      {List<String>? recommendations, String? date}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/day-status-explanation',
      data: {
        'status': status,
        'recommendations': recommendations ?? [],
        'date': date ?? DateTime.now().toIso8601String().split('T')[0],
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['explanation'] as String? ??
        'Status explanation not available';
  }

  /// Get AI-powered spending behavior insights and patterns
  Future<Map<String, dynamic>> getSpendingPatterns(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/spending-patterns',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get personalized AI feedback based on recent spending behavior
  Future<Map<String, dynamic>> getAIPersonalizedFeedback(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/personalized-feedback',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered budget optimization suggestions
  Future<Map<String, dynamic>> getAIBudgetOptimization(
      {Map<String, dynamic>? calendar, double? income}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/budget-optimization',
      data: {
        'calendar': calendar,
        'income': income,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI category suggestions for transaction categorization
  Future<List<Map<String, dynamic>>> getAICategorySuggestions(
      String transactionDescription,
      {double? amount}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/category-suggestions',
      data: {
        'description': transactionDescription,
        'amount': amount,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
  }

  /// Ask the AI assistant a financial question
  Future<String> askAIAssistant(String question,
      {Map<String, dynamic>? context}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/assistant',
      data: {
        'question': question,
        'context': context,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['answer'] as String? ??
        'I\'m unable to provide a response right now.';
  }

  /// Get AI-powered anomaly detection in spending patterns
  Future<List<Map<String, dynamic>>> getSpendingAnomalies(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/spending-anomalies',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
  }

  /// Get AI financial health score and improvement recommendations
  Future<Map<String, dynamic>> getAIFinancialHealthScore() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/financial-health-score',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered savings optimization suggestions
  Future<Map<String, dynamic>> getAISavingsOptimization() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/savings-optimization',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI prediction for future spending based on historical patterns
  Future<Map<String, dynamic>> getAISpendingPrediction({int? daysAhead}) async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/spending-prediction',
      queryParameters: {
        'days_ahead': daysAhead ?? 30,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered goal achievement analysis and recommendations
  Future<Map<String, dynamic>> getAIGoalAnalysis() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/goal-analysis',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered weekly financial insights summary
  Future<Map<String, dynamic>> getAIWeeklyInsights() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/weekly-insights',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered monthly financial report with insights
  Future<Map<String, dynamic>> getAIMonthlyReport(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/monthly-report',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Behavioral Analysis & Pattern Detection
  // ---------------------------------------------------------------------------

  /// Get comprehensive behavioral analysis for the user
  Future<Map<String, dynamic>> getBehavioralAnalysis(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/analysis',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get spending pattern analysis (time-based, category-based, emotional triggers)
  Future<Map<String, dynamic>> getSpendingPatternAnalysis(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/patterns',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behavioral predictions and trend analysis
  Future<Map<String, dynamic>> getBehavioralPredictions() async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/predictions',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get anomaly detection with explanations
  Future<Map<String, dynamic>> getBehavioralAnomalies(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/anomalies',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get adaptive behavior recommendations
  Future<Map<String, dynamic>> getAdaptiveBehaviorRecommendations() async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/recommendations',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get spending triggers and habit formation insights
  Future<Map<String, dynamic>> getSpendingTriggers(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/triggers',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Generate behavioral calendar with spending pattern distribution
  Future<Map<String, dynamic>> generateBehavioralCalendar({
    required int year,
    required int month,
    Map<String, dynamic>? profile,
    Map<String, dynamic>? moodLog,
    Map<String, dynamic>? challengeLog,
    Map<String, dynamic>? calendarLog,
  }) async {
    final token = await getToken();
    final response = await _dio.post(
      '/behavior/calendar',
      data: {
        'year': year,
        'month': month,
        'profile': profile ?? {},
        'mood_log': moodLog ?? {},
        'challenge_log': challengeLog ?? {},
        'calendar_log': calendarLog ?? {},
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data ?? {});
  }

  /// Get user's behavioral cluster and associated policies
  Future<Map<String, dynamic>> getBehavioralCluster() async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/cluster',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Update behavioral learning preferences
  Future<void> updateBehavioralPreferences(
      Map<String, dynamic> preferences) async {
    final token = await getToken();
    await _dio.patch(
      '/behavior/preferences',
      data: preferences,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get current behavioral learning preferences
  Future<Map<String, dynamic>> getBehavioralPreferences() async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/preferences',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behavioral progress tracking over time
  Future<Map<String, dynamic>> getBehavioralProgress({int? months}) async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/progress',
      queryParameters: {
        'months': months ?? 6,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behavioral insights for specific categories
  Future<Map<String, dynamic>> getCategoryBehavioralInsights(String category,
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/category/$category',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behavioral warnings for calendar days
  Future<Map<String, dynamic>> getBehavioralWarnings(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/behavior/warnings',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get behavioral suggestions for expense entry
  Future<Map<String, dynamic>> getBehavioralExpenseSuggestions({
    String? category,
    double? amount,
    String? description,
    String? date,
  }) async {
    final token = await getToken();
    final response = await _dio.post(
      '/behavior/expense_suggestions',
      data: {
        'category': category,
        'amount': amount,
        'description': description,
        'date': date ?? DateTime.now().toIso8601String().split('T')[0],
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Enable/disable behavioral pattern notifications
  Future<void> updateBehavioralNotificationSettings({
    bool? patternAlerts,
    bool? anomalyDetection,
    bool? budgetAdaptation,
    bool? weeklyInsights,
  }) async {
    final token = await getToken();
    await _dio.patch(
      '/behavior/notification_settings',
      data: {
        'pattern_alerts': patternAlerts,
        'anomaly_detection': anomalyDetection,
        'budget_adaptation': budgetAdaptation,
        'weekly_insights': weeklyInsights,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get current behavioral notification settings
  Future<Map<String, dynamic>> getBehavioralNotificationSettings() async {
    final token = await getToken();
    final response = await _dio.get(
      '/behavior/notification_settings',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Behavioral Analysis
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getBehaviorCalendar({
    int? year,
    int? month,
  }) async {
    final token = await getToken();
    final currentYear = year ?? DateTime.now().year;
    final currentMonth = month ?? DateTime.now().month;

    final response = await _dio.post(
      '/behavior/calendar',
      data: {
        'year': currentYear,
        'month': currentMonth,
        'profile': {},
        'mood_log': {},
        'challenge_log': {},
        'calendar_log': {},
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<Map<String, dynamic>> getBehaviorPredictions() async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/behavior/predictions',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when behavior predictions service is unavailable
      logError('Behavior predictions service unavailable: $e', tag: 'BEHAVIOR');
      return {
        'error': 'Prediction service is currently unavailable',
        'next_month_spending': null,
        'confidence': null,
        'risk_factors': [],
        'recommended_budget': null,
        'savings_potential': null,
      };
    }
  }

  Future<List<dynamic>> getBehaviorAnomalies({
    int? days = 30,
  }) async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/behavior/anomalies',
        queryParameters: {'days': days},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<dynamic>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return empty list when anomaly detection service is unavailable
      logError('Behavior anomalies service unavailable: $e', tag: 'BEHAVIOR');
      return [];
    }
  }

  Future<Map<String, dynamic>> getBehaviorInsights() async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/behavior/insights',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when behavior insights service is unavailable
      logError('Behavior insights service unavailable: $e', tag: 'BEHAVIOR');
      return {
        'error': 'Insights service is currently unavailable',
        'spending_personality': null,
        'key_traits': [],
        'improvement_areas': [],
        'strengths': [],
        'recommended_strategies': [],
      };
    }
  }

  // ---------------------------------------------------------------------------
  // OCR Receipt Processing
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> processReceiptOCR(File receiptImage) async {
    final token = await getToken();

    try {
      final formData = FormData.fromMap({
        'receipt': await MultipartFile.fromFile(
          receiptImage.path,
          filename: 'receipt.jpg',
        ),
      });

      final response = await _dio.post(
        '/ocr/process',
        data: formData,
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'multipart/form-data',
          },
        ),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when OCR service is unavailable
      logError('OCR service unavailable: $e', tag: 'OCR');
      throw Exception(
          'Receipt processing service is currently unavailable. Please try again later.');
    }
  }

  Future<Map<String, dynamic>> getOCRStatus(String ocrJobId) async {
    final token = await getToken();

    final response = await _dio.get(
      '/ocr/status/$ocrJobId',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<List<String>> getCategorySuggestions(
      String description, double amount) async {
    final token = await getToken();

    try {
      final response = await _dio.post(
        '/ocr/categorize',
        data: {
          'description': description,
          'amount': amount,
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<String>.from(response.data['data']['suggestions'] ?? []);
    } catch (e) {
      // Return basic category fallback when AI categorization is unavailable
      logError('Category suggestion service unavailable: $e',
          tag: 'CATEGORIZATION');
      return ['General', 'Other'];
    }
  }

  Future<Map<String, dynamic>> enhanceReceiptData(
      Map<String, dynamic> ocrData) async {
    final token = await getToken();

    try {
      final response = await _dio.post(
        '/ocr/enhance',
        data: ocrData,
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return enhanced data with additional context
      final enhanced = Map<String, dynamic>.from(ocrData);
      enhanced['enhanced'] = true;
      enhanced['merchant_type'] = _getMerchantType(ocrData['merchant'] ?? '');
      enhanced['spending_category'] =
          _getSpendingCategory(ocrData['category'] ?? '');
      return enhanced;
    }
  }

  String _getMerchantType(String merchant) {
    final lower = merchant.toLowerCase();
    if (lower.contains('starbucks') || lower.contains('coffee'))
      return 'Coffee Shop';
    if (lower.contains('restaurant') || lower.contains('pizza'))
      return 'Restaurant';
    if (lower.contains('gas') || lower.contains('shell')) return 'Gas Station';
    if (lower.contains('store') || lower.contains('mart'))
      return 'Retail Store';
    return 'General';
  }

  String _getSpendingCategory(String category) {
    switch (category.toLowerCase()) {
      case 'food & dining':
      case 'food':
        return 'dining';
      case 'transportation':
        return 'transport';
      case 'entertainment':
        return 'fun';
      case 'shopping':
        return 'retail';
      default:
        return 'other';
    }
  }

  // ---------------------------------------------------------------------------
  // Challenge & Gamification System
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getChallenges() async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/challenge/active',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<dynamic>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return empty list when challenges service is unavailable
      logError('Challenges service unavailable: $e', tag: 'CHALLENGES');
      return [];
    }
  }

  Future<Map<String, dynamic>> getChallengeProgress(String challengeId) async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/challenge/$challengeId/progress',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when challenge progress service is unavailable
      logError('Challenge progress service unavailable: $e', tag: 'CHALLENGES');
      return {
        'error': 'Challenge progress service is currently unavailable',
        'challenge_id': challengeId,
        'current_progress': 0,
        'target_value': 0,
        'completion_percentage': 0.0,
      };
    }
  }

  Future<void> joinChallenge(String challengeId) async {
    final token = await getToken();

    await _dio.post(
      '/challenge/$challengeId/join',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> leaveChallenge(String challengeId) async {
    final token = await getToken();

    await _dio.post(
      '/challenge/$challengeId/leave',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getGameificationStats() async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/challenge/stats',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when gamification stats service is unavailable
      logError('Gamification stats service unavailable: $e',
          tag: 'GAMIFICATION');
      return {
        'error': 'Gamification service is currently unavailable',
        'total_points': 0,
        'current_level': 1,
        'next_level_points': 100,
        'points_to_next_level': 100,
        'completed_challenges': 0,
        'active_challenges': 0,
        'current_streak': 0,
        'best_streak': 0,
        'badges_earned': [],
        'leaderboard_position': null,
        'points_this_week': 0,
        'challenges_completed_this_month': 0,
      };
    }
  }

  Future<List<dynamic>> getAvailableChallenges() async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/challenge/available',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<dynamic>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return demo available challenges
      return [
        {
          'id': '4',
          'title': 'Meal Prep Master',
          'description': 'Cook at home for 10 days straight',
          'type': 'habit_building',
          'target_value': 10,
          'reward_points': 300,
          'reward_amount': 75.0,
          'difficulty': 'medium',
          'duration_days': 14,
          'category': 'Food & Dining',
          'participants': 127,
          'success_rate': 0.78,
        },
        {
          'id': '5',
          'title': 'No-Spend Weekend',
          'description':
              'Complete a weekend without any non-essential spending',
          'type': 'spending_freeze',
          'target_value': 1,
          'reward_points': 150,
          'reward_amount': 30.0,
          'difficulty': 'easy',
          'duration_days': 2,
          'category': 'Entertainment',
          'participants': 89,
          'success_rate': 0.65,
        },
        {
          'id': '6',
          'title': 'Subscription Audit',
          'description': 'Review and cancel at least 2 unused subscriptions',
          'type': 'cost_optimization',
          'target_value': 2,
          'reward_points': 400,
          'reward_amount': 120.0,
          'difficulty': 'easy',
          'duration_days': 7,
          'category': 'Subscriptions',
          'participants': 234,
          'success_rate': 0.92,
        },
      ];
    }
  }

  Future<void> updateChallengeProgress(
      String challengeId, Map<String, dynamic> progressData) async {
    final token = await getToken();

    await _dio.patch(
      '/challenge/$challengeId/progress',
      data: progressData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<List<dynamic>> getLeaderboard({String? period = 'weekly'}) async {
    final token = await getToken();

    try {
      final response = await _dio.get(
        '/challenge/leaderboard',
        queryParameters: {'period': period},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      final leaderboard = response.data['data'];
      if (leaderboard is Map && leaderboard.containsKey('top_users')) {
        return List<dynamic>.from(leaderboard['top_users'] ?? []);
      }
      return List<dynamic>.from(leaderboard ?? []);
    } catch (e) {
      // Return demo leaderboard
      return [
        {
          'rank': 1,
          'user_id': 'user_123',
          'username': 'BudgetNinja',
          'points': 2850,
          'level': 8,
          'badges_count': 15,
          'challenges_completed': 23,
          'avatar_url': null,
        },
        {
          'rank': 2,
          'user_id': 'user_456',
          'username': 'SavingsHero',
          'points': 2720,
          'level': 7,
          'badges_count': 12,
          'challenges_completed': 19,
          'avatar_url': null,
        },
        {
          'rank': 42,
          'user_id': 'current_user',
          'username': 'You',
          'points': 1250,
          'level': 5,
          'badges_count': 3,
          'challenges_completed': 8,
          'avatar_url': null,
          'is_current_user': true,
        },
      ];
    }
  }

  // ---------------------------------------------------------------------------
  // Income-Based Personalization & Cohort Analysis
  // ---------------------------------------------------------------------------

  /// Get user's income tier and classification
  Future<Map<String, dynamic>> getIncomeClassification() async {
    final token = await getToken();
    try {
      final response = await _dio.get(
        '/cohort/income_classification',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return default classification based on user profile
      final profile = await getUserProfile();
      final income = (profile['data']?['income'] as num?)?.toDouble() ?? 0.0;
      final incomeService = IncomeService();
      final tier = incomeService.classifyIncome(income);
      final tierString = incomeService.getTierString(tier);

      return {
        'monthly_income': income,
        'tier': tierString,
        'tier_name': incomeService.getTierDisplayName(tier),
        'range': incomeService.getTierRange(tier),
      };
    }
  }

  /// Get peer comparison data for user's income tier
  Future<Map<String, dynamic>> getPeerComparison(
      {int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    try {
      final response = await _dio.get(
        '/cohort/peer_comparison',
        queryParameters: {
          'year': year ?? now.year,
          'month': month ?? now.month,
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return error when peer comparison service is unavailable
      logError('Peer comparison service unavailable: $e',
          tag: 'PEER_COMPARISON');
      return {
        'error': 'Peer comparison service is currently unavailable',
        'your_spending': null,
        'peer_average': null,
        'peer_median': null,
        'percentile': null,
        'categories': {},
        'insights': [],
      };
    }
  }

  /// Get income-specific budget recommendations
  Future<Map<String, dynamic>> getIncomeBasedBudgetRecommendations(
      double monthlyIncome) async {
    final token = await getToken();
    try {
      final response = await _dio.post(
        '/budget/income_based_recommendations',
        data: {'monthly_income': monthlyIncome},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return income-appropriate defaults
      final tier = monthlyIncome < 3000
          ? 'low'
          : monthlyIncome <= 7000
              ? 'mid'
              : 'high';
      late Map<String, double> weights;

      switch (tier) {
        case 'low':
          weights = {
            'housing': 0.40,
            'food': 0.15,
            'transportation': 0.15,
            'utilities': 0.10,
            'healthcare': 0.08,
            'entertainment': 0.05,
            'savings': 0.07,
          };
          break;
        case 'mid':
          weights = {
            'housing': 0.35,
            'food': 0.12,
            'transportation': 0.15,
            'utilities': 0.08,
            'healthcare': 0.06,
            'entertainment': 0.08,
            'savings': 0.16,
          };
          break;
        case 'high':
          weights = {
            'housing': 0.30,
            'food': 0.10,
            'transportation': 0.12,
            'utilities': 0.05,
            'healthcare': 0.05,
            'entertainment': 0.10,
            'savings': 0.28,
          };
          break;
      }

      final allocations = <String, double>{};
      weights.forEach((category, weight) {
        allocations[category] = (monthlyIncome * weight).roundToDouble();
      });

      return {
        'monthly_income': monthlyIncome,
        'tier': tier,
        'allocations': allocations,
        'total_allocated': allocations.values.reduce((a, b) => a + b),
      };
    }
  }

  /// Get cohort-based spending insights
  Future<Map<String, dynamic>> getCohortInsights() async {
    final token = await getToken();
    try {
      final response = await _dio.get(
        '/cohort/insights',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return demo cohort insights
      return {
        'cohort_size': 1247,
        'your_rank': 312,
        'percentile': 75,
        'top_insights': [
          'Users in your income group typically save 18% of their income',
          'Most peers allocate 12-15% to food expenses',
          'Transportation costs vary widely (8-20%) in your group',
          'Entertainment spending peaks on weekends for your cohort',
        ],
        'recommendations': [
          'Consider increasing your savings rate to match top performers',
          'Your food spending is well-optimized compared to peers',
          'Look into carpooling or public transit to reduce transportation costs',
        ],
      };
    }
  }

  /// Get income-appropriate goal suggestions
  Future<List<Map<String, dynamic>>> getIncomeBasedGoals(
      double monthlyIncome) async {
    final token = await getToken();
    try {
      final response = await _dio.post(
        '/goals/income_based_suggestions',
        data: {'monthly_income': monthlyIncome},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return income-appropriate goal suggestions
      final tier = monthlyIncome < 3000
          ? 'low'
          : monthlyIncome <= 7000
              ? 'mid'
              : 'high';

      switch (tier) {
        case 'low':
          return [
            {
              'title': 'Emergency Fund',
              'description': 'Build a \$500 emergency fund',
              'target_amount': 500.0,
              'monthly_target': monthlyIncome * 0.05,
              'priority': 'high',
              'category': 'emergency',
            },
            {
              'title': 'Debt Reduction',
              'description': 'Pay down high-interest debt',
              'target_amount': monthlyIncome * 2,
              'monthly_target': monthlyIncome * 0.10,
              'priority': 'high',
              'category': 'debt',
            },
          ];
        case 'mid':
          return [
            {
              'title': 'Emergency Fund',
              'description': 'Build 3-month emergency fund',
              'target_amount': monthlyIncome * 3,
              'monthly_target': monthlyIncome * 0.08,
              'priority': 'high',
              'category': 'emergency',
            },
            {
              'title': 'Investment Portfolio',
              'description': 'Start investing for the future',
              'target_amount': monthlyIncome * 6,
              'monthly_target': monthlyIncome * 0.15,
              'priority': 'high',
              'category': 'investment',
            },
          ];
        case 'high':
          return [
            {
              'title': 'Investment Growth',
              'description': 'Aggressive investment strategy',
              'target_amount': monthlyIncome * 12,
              'monthly_target': monthlyIncome * 0.20,
              'priority': 'high',
              'category': 'investment',
            },
            {
              'title': 'Tax Optimization',
              'description': 'Maximize tax-advantaged accounts',
              'target_amount': 22500.0,
              'monthly_target': 1875.0,
              'priority': 'high',
              'category': 'tax',
            },
          ];
        default:
          return [];
      }
    }
  }

  /// Get income-based financial tips
  Future<List<String>> getIncomeBasedTips(double monthlyIncome) async {
    final token = await getToken();
    try {
      final response = await _dio.post(
        '/insights/income_based_tips',
        data: {'monthly_income': monthlyIncome},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<String>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return income-appropriate tips
      final tier = monthlyIncome < 3000
          ? 'low'
          : monthlyIncome <= 7000
              ? 'mid'
              : 'high';

      switch (tier) {
        case 'low':
          return [
            'Focus on the 50/30/20 rule: 50% needs, 30% wants, 20% savings',
            'Look for free entertainment options in your community',
            'Cook meals at home to reduce food expenses',
            'Build an emergency fund, even if it\'s \$5-10 per week',
          ];
        case 'mid':
          return [
            'Increase your savings rate to 15-20% of income',
            'Consider investing in low-cost index funds',
            'Look into employer 401(k) matching opportunities',
            'Set up automatic transfers to savings accounts',
          ];
        case 'high':
          return [
            'Aim for a 25-30% savings rate',
            'Diversify investments across asset classes',
            'Consider tax-advantaged accounts (IRA, 401k)',
            'Work with a financial advisor for complex planning',
          ];
        default:
          return [];
      }
    }
  }

  /// Update user income and trigger recalculations
  Future<void> updateUserIncome(double monthlyIncome) async {
    final token = await getToken();
    await _dio.patch(
      '/users/me',
      data: {'income': monthlyIncome},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // CALENDAR DAY DETAILS ENDPOINTS
  // ---------------------------------------------------------------------------

  /// Get detailed transactions for a specific date
  Future<List<Map<String, dynamic>>> getTransactionsByDate(String date) async {
    try {
      logInfo('Fetching transactions for date: $date', tag: 'API_TRANSACTIONS');

      final response =
          await _dio.get('/transactions/by-date', queryParameters: {
        'date': date,
      });

      if (response.statusCode == 200 && response.data is List) {
        final transactions = List<Map<String, dynamic>>.from(response.data);
        logInfo(
            'Successfully fetched ${transactions.length} transactions for $date',
            tag: 'API_TRANSACTIONS');
        return transactions;
      } else {
        logWarning('Unexpected response format for transactions by date',
            tag: 'API_TRANSACTIONS');
        return <Map<String, dynamic>>[];
      }
    } catch (e) {
      logError('Failed to fetch transactions for date $date: $e',
          tag: 'API_TRANSACTIONS', error: e);
      return <Map<String, dynamic>>[];
    }
  }

  /// Get seasonal spending patterns for predictions
  Future<Map<String, dynamic>> getSeasonalSpendingPatterns() async {
    try {
      logInfo('Fetching seasonal spending patterns', tag: 'API_SEASONAL');

      final response = await _dio.get('/analytics/seasonal-patterns');

      if (response.statusCode == 200 && response.data is Map) {
        final patterns = Map<String, dynamic>.from(response.data);
        logInfo('Successfully fetched seasonal patterns', tag: 'API_SEASONAL');
        return patterns;
      } else {
        logWarning('Unexpected response format for seasonal patterns',
            tag: 'API_SEASONAL');
        return <String, dynamic>{};
      }
    } catch (e) {
      logError('Failed to fetch seasonal patterns: $e',
          tag: 'API_SEASONAL', error: e);
      return <String, dynamic>{};
    }
  }

  /// Get behavioral insights for spending patterns
  Future<Map<String, dynamic>> getBehavioralInsights() async {
    try {
      logInfo('Fetching behavioral insights', tag: 'API_BEHAVIORAL');

      final response = await _dio.get('/analytics/behavioral-insights');

      if (response.statusCode == 200 && response.data is Map) {
        final insights = Map<String, dynamic>.from(response.data);
        logInfo('Successfully fetched behavioral insights',
            tag: 'API_BEHAVIORAL');
        return insights;
      } else {
        logWarning('Unexpected response format for behavioral insights',
            tag: 'API_BEHAVIORAL');
        return <String, dynamic>{};
      }
    } catch (e) {
      logError('Failed to fetch behavioral insights: $e',
          tag: 'API_BEHAVIORAL', error: e);
      return <String, dynamic>{};
    }
  }

  // ---------------------------------------------------------------------------
  // Analytics Logging
  // ---------------------------------------------------------------------------

  /// Log feature usage for analytics tracking
  Future<bool> logFeatureUsage({
    required String feature,
    String? screen,
    String? action,
    Map<String, dynamic>? metadata,
    String? sessionId,
    String? platform,
    String? appVersion,
  }) async {
    try {
      logDebug('Logging feature usage: $feature', tag: 'API_ANALYTICS');

      final response = await _dio.post(
        '/analytics/feature-usage',
        data: {
          'feature': feature,
          'screen': screen,
          'action': action,
          'metadata': metadata ?? {},
          'session_id': sessionId,
          'platform': platform ?? Platform.operatingSystem,
          'app_version': appVersion ?? AppVersionService.instance.appVersion,
          'timestamp': DateTime.now().toIso8601String(),
        },
      );

      if (response.statusCode == 200) {
        logDebug('Feature usage logged successfully', tag: 'API_ANALYTICS');
        return true;
      } else {
        logWarning('Failed to log feature usage: ${response.statusCode}',
            tag: 'API_ANALYTICS');
        return false;
      }
    } catch (e) {
      logError('Exception logging feature usage: $e',
          tag: 'API_ANALYTICS', error: e);
      // Don't fail the app if analytics logging fails
      return false;
    }
  }

  /// Log feature access attempt (for premium features conversion tracking)
  Future<bool> logFeatureAccessAttempt({
    required String feature,
    required bool hasAccess,
    bool isPremiumFeature = true,
    String? screen,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      logDebug('Logging feature access attempt: $feature',
          tag: 'API_ANALYTICS');

      final response = await _dio.post(
        '/analytics/feature-access-attempt',
        data: {
          'feature': feature,
          'has_access': hasAccess,
          'is_premium_feature': isPremiumFeature,
          'screen': screen,
          'metadata': metadata ?? {},
        },
      );

      if (response.statusCode == 200) {
        logDebug('Feature access logged successfully', tag: 'API_ANALYTICS');
        return true;
      } else {
        logWarning('Failed to log feature access: ${response.statusCode}',
            tag: 'API_ANALYTICS');
        return false;
      }
    } catch (e) {
      logError('Exception logging feature access: $e',
          tag: 'API_ANALYTICS', error: e);
      // Don't fail the app if analytics logging fails
      return false;
    }
  }

  /// Log paywall impression for conversion funnel tracking
  Future<bool> logPaywallImpression({
    required String screen,
    String? feature,
    String? context,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      logDebug('Logging paywall impression: $screen', tag: 'API_ANALYTICS');

      final response = await _dio.post(
        '/analytics/paywall-impression',
        data: {
          'screen': screen,
          'feature': feature,
          'context': context,
          'metadata': metadata ?? {},
          'timestamp': DateTime.now().toIso8601String(),
        },
      );

      if (response.statusCode == 200) {
        logDebug('Paywall impression logged successfully',
            tag: 'API_ANALYTICS');
        return true;
      } else {
        logWarning('Failed to log paywall impression: ${response.statusCode}',
            tag: 'API_ANALYTICS');
        return false;
      }
    } catch (e) {
      logError('Exception logging paywall impression: $e',
          tag: 'API_ANALYTICS', error: e);
      // Don't fail the app if analytics logging fails
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Password reset functionality
  // ---------------------------------------------------------------------------

  /// Send password reset email
  Future<bool> sendPasswordResetEmail(String email) async {
    try {
      logInfo('Sending password reset email', tag: 'API_PASSWORD_RESET');

      final response = await _dio.post(
        '/auth/forgot-password',
        data: {
          'email': email,
          'client_id': 'mita_flutter_app',
          'redirect_url': 'https://app.mita.finance/reset-password',
        },
      );

      if (response.statusCode == 200 || response.statusCode == 202) {
        logInfo('Password reset email sent successfully',
            tag: 'API_PASSWORD_RESET');
        return true;
      } else if (response.statusCode == 404) {
        logWarning('Email not found for password reset',
            tag: 'API_PASSWORD_RESET');
        // Return true to avoid revealing which emails exist in the system
        return true;
      } else {
        logError('Failed to send password reset email: ${response.statusCode}',
            tag: 'API_PASSWORD_RESET');
        return false;
      }
    } catch (e) {
      logError('Exception sending password reset email: $e',
          tag: 'API_PASSWORD_RESET');
      return false;
    }
  }

  /// Verify password reset token
  Future<bool> verifyPasswordResetToken(String token) async {
    try {
      logInfo('Verifying password reset token', tag: 'API_PASSWORD_RESET');

      final response = await _dio.get(
        '/auth/verify-reset-token',
        queryParameters: {
          'token': token,
        },
      );

      if (response.statusCode == 200) {
        logInfo('Password reset token is valid', tag: 'API_PASSWORD_RESET');
        return true;
      } else {
        logWarning('Invalid or expired password reset token',
            tag: 'API_PASSWORD_RESET');
        return false;
      }
    } catch (e) {
      logError('Exception verifying password reset token: $e',
          tag: 'API_PASSWORD_RESET');
      return false;
    }
  }

  /// Reset password with token
  Future<bool> resetPasswordWithToken(String token, String newPassword) async {
    try {
      logInfo('Resetting password with token', tag: 'API_PASSWORD_RESET');

      final response = await _dio.post(
        '/auth/reset-password',
        data: {
          'token': token,
          'new_password': newPassword,
        },
      );

      if (response.statusCode == 200) {
        logInfo('Password reset successfully', tag: 'API_PASSWORD_RESET');
        return true;
      } else {
        logError('Failed to reset password: ${response.statusCode}',
            tag: 'API_PASSWORD_RESET');
        return false;
      }
    } catch (e) {
      logError('Exception resetting password: $e', tag: 'API_PASSWORD_RESET');
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Push notification token registration
  // ---------------------------------------------------------------------------

  /// Register device push token for notifications
  Future<bool> registerPushToken(String pushToken) async {
    try {
      logInfo('Registering push token', tag: 'API_PUSH_TOKEN');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available for push token registration',
            tag: 'API_PUSH_TOKEN');
        return false;
      }

      final response = await _dio.post(
        '/notifications/register-device',
        data: {
          'push_token': pushToken,
          'platform': Platform.isIOS ? 'ios' : 'android',
          'app_version': AppVersionService.instance.appVersion,
          'device_id': await _getDeviceId(),
          'timestamp': DateTime.now().toIso8601String(),
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        logInfo('Push token registered successfully', tag: 'API_PUSH_TOKEN');
        return true;
      } else {
        logError('Failed to register push token: ${response.statusCode}',
            tag: 'API_PUSH_TOKEN');
        return false;
      }
    } catch (e) {
      logError('Exception registering push token: $e', tag: 'API_PUSH_TOKEN');
      return false;
    }
  }

  /// Update push token (when FCM token refreshes)
  Future<bool> updatePushToken(String oldToken, String newToken) async {
    try {
      logInfo('Updating push token', tag: 'API_PUSH_TOKEN');

      final token = await getToken();
      if (token == null) {
        logWarning('No auth token available for push token update',
            tag: 'API_PUSH_TOKEN');
        return false;
      }

      final response = await _dio.patch(
        '/notifications/update-device',
        data: {
          'old_push_token': oldToken,
          'new_push_token': newToken,
          'platform': Platform.isIOS ? 'ios' : 'android',
          'timestamp': DateTime.now().toIso8601String(),
        },
      );

      if (response.statusCode == 200) {
        logInfo('Push token updated successfully', tag: 'API_PUSH_TOKEN');
        return true;
      } else {
        logError('Failed to update push token: ${response.statusCode}',
            tag: 'API_PUSH_TOKEN');
        return false;
      }
    } catch (e) {
      logError('Exception updating push token: $e', tag: 'API_PUSH_TOKEN');
      return false;
    }
  }

  /// Unregister push token (on logout)
  Future<bool> unregisterPushToken(String pushToken) async {
    try {
      logInfo('Unregistering push token', tag: 'API_PUSH_TOKEN');

      final token = await getToken();
      if (token == null) {
        logDebug('No auth token available for push token unregistration',
            tag: 'API_PUSH_TOKEN');
        return true; // Consider success if user already logged out
      }

      final response = await _dio.delete(
        '/notifications/unregister-device',
        data: {
          'push_token': pushToken,
          'platform': Platform.isIOS ? 'ios' : 'android',
        },
      );

      if (response.statusCode == 200 || response.statusCode == 204) {
        logInfo('Push token unregistered successfully', tag: 'API_PUSH_TOKEN');
        return true;
      } else {
        logWarning('Failed to unregister push token: ${response.statusCode}',
            tag: 'API_PUSH_TOKEN');
        return false;
      }
    } catch (e) {
      logError('Exception unregistering push token: $e', tag: 'API_PUSH_TOKEN');
      return false;
    }
  }

  /// Get cryptographically secure device ID for push notification tracking
  ///
  /// SECURITY: Now uses SecureDeviceService for enterprise-grade device fingerprinting
  Future<String> _getDeviceId() async {
    try {
      // Use secure device service instead of weak timestamp-based ID
      final secureDeviceService = SecureDeviceService.getInstance();
      final deviceId = await secureDeviceService.getSecureDeviceId();

      logDebug('Retrieved secure device ID: ${deviceId.substring(0, 12)}...',
          tag: 'API_PUSH_TOKEN');
      return deviceId;
    } catch (e) {
      logError('Failed to get secure device ID: $e', tag: 'API_PUSH_TOKEN');
      // Fallback to secure random generation instead of predictable timestamp
      final secureRandom = Random.secure();
      final randomBytes = List.generate(16, (i) => secureRandom.nextInt(256));
      final fallbackId =
          'mita_fallback_${base64Encode(randomBytes).substring(0, 16)}';

      logWarning('Using fallback device ID: ${fallbackId.substring(0, 12)}...',
          tag: 'API_PUSH_TOKEN');
      return fallbackId;
    }
  }

  // ---------------------------------------------------------------------------
  // Premium Subscription Management
  // ---------------------------------------------------------------------------

  /// Get user's premium status and subscription details
  Future<Map<String, dynamic>> getUserPremiumStatus(String userId) async {
    try {
      final token = await getToken();
      if (token == null) {
        throw Exception('Authentication token not available');
      }

      logInfo('Getting premium status for user: $userId', tag: 'API_PREMIUM');

      final response = await _dio.get(
        '/users/$userId/premium-status',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      logError('Failed to get premium status: $e', tag: 'API_PREMIUM');
      rethrow;
    }
  }

  /// Get user's available premium features
  Future<Map<String, dynamic>> getUserPremiumFeatures(String userId) async {
    try {
      final token = await getToken();
      if (token == null) {
        throw Exception('Authentication token not available');
      }

      logInfo('Getting premium features for user: $userId', tag: 'API_PREMIUM');

      final response = await _dio.get(
        '/users/$userId/premium-features',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      logError('Failed to get premium features: $e', tag: 'API_PREMIUM');
      rethrow;
    }
  }

  /// Track premium feature usage for analytics and limits
  Future<void> trackPremiumFeatureUsage({
    required String userId,
    required String feature,
    Map<String, dynamic>? metadata,
    int? processingTimeMs,
    bool success = true,
  }) async {
    try {
      final token = await getToken();
      if (token == null) return;

      await _dio.post(
        '/analytics/feature-usage',
        data: {
          'user_id': userId,
          'feature': feature,
          'success': success,
          'processing_time_ms': processingTimeMs,
          'metadata': metadata,
          'timestamp': DateTime.now().toIso8601String(),
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      logDebug('Tracked feature usage: $feature (success: $success)',
          tag: 'API_PREMIUM');
    } catch (e) {
      logError('Failed to track feature usage: $e', tag: 'API_PREMIUM');
      // Don't rethrow - analytics failures shouldn't break user experience
    }
  }

  /// Get feature usage statistics
  Future<Map<String, dynamic>> getFeatureUsageStats({
    required String userId,
    required String feature,
  }) async {
    try {
      final token = await getToken();
      if (token == null) {
        throw Exception('Authentication token not available');
      }

      final response = await _dio.get(
        '/analytics/feature-usage/$userId/$feature',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      logError('Failed to get feature usage stats: $e', tag: 'API_PREMIUM');
      return {};
    }
  }

  /// Track feature access attempts (for paywall analytics)
  Future<void> trackFeatureAccessAttempt({
    required String userId,
    required String feature,
    required bool success,
    String? context,
  }) async {
    try {
      final token = await getToken();
      if (token == null) return;

      await _dio.post(
        '/analytics/feature-access-attempt',
        data: {
          'user_id': userId,
          'feature': feature,
          'success': success,
          'context': context,
          'timestamp': DateTime.now().toIso8601String(),
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      logDebug('Tracked feature access attempt: $feature (success: $success)',
          tag: 'API_PREMIUM');
    } catch (e) {
      logError('Failed to track feature access attempt: $e',
          tag: 'API_PREMIUM');
      // Don't rethrow - analytics failures shouldn't break user experience
    }
  }

  /// Track paywall impressions
  Future<void> trackPaywallImpression({
    required String userId,
    required String feature,
    String? context,
  }) async {
    try {
      final token = await getToken();
      if (token == null) return;

      await _dio.post(
        '/analytics/paywall-impression',
        data: {
          'user_id': userId,
          'feature': feature,
          'context': context,
          'timestamp': DateTime.now().toIso8601String(),
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      logDebug('Tracked paywall impression: $feature', tag: 'API_PREMIUM');
    } catch (e) {
      logError('Failed to track paywall impression: $e', tag: 'API_PREMIUM');
      // Don't rethrow - analytics failures shouldn't break user experience
    }
  }

  /// Update subscription status after external verification
  Future<void> updateSubscriptionStatus({
    required String userId,
    required String subscriptionId,
    required String status,
    required DateTime expiresAt,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      final token = await getToken();
      if (token == null) {
        throw Exception('Authentication token not available');
      }

      logInfo('Updating subscription status: $subscriptionId -> $status',
          tag: 'API_PREMIUM');

      await _dio.put(
        '/subscriptions/$subscriptionId/status',
        data: {
          'user_id': userId,
          'status': status,
          'expires_at': expiresAt.toIso8601String(),
          'metadata': metadata,
          'updated_by': 'mobile_app',
        },
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      logInfo('Subscription status updated successfully', tag: 'API_PREMIUM');
    } catch (e) {
      logError('Failed to update subscription status: $e', tag: 'API_PREMIUM');
      rethrow;
    }
  }

  /// Get subscription history for audit purposes
  Future<List<Map<String, dynamic>>> getSubscriptionHistory(
      String userId) async {
    try {
      final token = await getToken();
      if (token == null) {
        throw Exception('Authentication token not available');
      }

      final response = await _dio.get(
        '/users/$userId/subscription-history',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );

      return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
    } catch (e) {
      logError('Failed to get subscription history: $e', tag: 'API_PREMIUM');
      return [];
    }
  }

  // ---------------------------------------------------------------------------
  // Manual logout
  // ---------------------------------------------------------------------------

  Future<void> logout() async {
    try {
      logInfo('Performing secure logout with push token cleanup',
          tag: 'API_LOGOUT');

      // SECURITY: Clean up push tokens before clearing auth tokens
      await SecurePushTokenManager.instance.cleanupOnLogout();

      // Clear authentication tokens
      await clearTokens();

      logInfo('Secure logout completed successfully', tag: 'API_LOGOUT');
    } catch (e, stackTrace) {
      logError('Error during logout: $e',
          tag: 'API_LOGOUT', stackTrace: stackTrace);

      // Still clear tokens even if push token cleanup fails
      try {
        await clearTokens();
      } catch (e2) {
        logError('Failed to clear tokens during error recovery: $e2',
            tag: 'API_LOGOUT');
      }

      rethrow;
    }
  }

  // ---------------------------------------------------------------------------
  // Password management
  // ---------------------------------------------------------------------------

  /// Change user password with current password verification
  Future<Response> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      logInfo('Initiating password change request', tag: 'API_PASSWORD');

      final response = await _dio.post(
        '/auth/change-password',
        data: {
          'current_password': currentPassword,
          'new_password': newPassword,
          'timestamp': DateTime.now().toIso8601String(),
        },
      );

      logInfo('Password change request completed', tag: 'API_PASSWORD');
      return response;
    } catch (e) {
      logError('Password change failed: $e', tag: 'API_PASSWORD');
      rethrow;
    }
  }

  // ---------------------------------------------------------------------------
  // Account management
  // ---------------------------------------------------------------------------

  /// Delete user account permanently
  Future<Response> deleteAccount() async {
    try {
      logInfo('Initiating account deletion request', tag: 'API_ACCOUNT');

      final response = await _dio.delete(
        '/auth/delete-account',
        data: {
          'timestamp': DateTime.now().toIso8601String(),
          'confirmation': true,
        },
      );

      logInfo('Account deletion request completed', tag: 'API_ACCOUNT');
      return response;
    } catch (e) {
      logError('Account deletion failed: $e', tag: 'API_ACCOUNT');
      rethrow;
    }
  }
}

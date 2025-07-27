import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';
import 'loading_service.dart';
import 'message_service.dart';

class ApiService {
  // ---------------------------------------------------------------------------
  // Singleton boilerplate
  // ---------------------------------------------------------------------------

  ApiService._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: _baseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 20),
        contentType: 'application/json',
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          LoadingService.instance.start();

          // Debug logging
          print('🚀 REQUEST: ${options.method} ${options.uri}');
          print('📤 Headers: ${options.headers}');
          print('📤 Data: ${options.data}');

          final token = await getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onResponse: (response, handler) {
          LoadingService.instance.stop();
          
          // Debug logging
          print('✅ RESPONSE: ${response.statusCode} ${response.requestOptions.uri}');
          print('📥 Data: ${response.data}');
          
          handler.next(response);
        },
        onError: (DioError e, handler) async {
          LoadingService.instance.stop();

          // Debug logging
          print('❌ ERROR: ${e.response?.statusCode} ${e.requestOptions.uri}');
          print('📥 Error Data: ${e.response?.data}');
          print('📥 Error Message: ${e.message}');

          // Handle auth refresh / errors
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
              MessageService.instance
                  .showError('Session expired. Please log in.');
            }
          } else if (e.response?.statusCode == 429) {
            MessageService.instance.showRateLimit();
          } else if (e.response?.statusCode == 404) {
            // Don't show error messages for missing endpoints (404)
            // These will be handled gracefully by individual screens
            print('API endpoint not found: ${e.requestOptions.path}');
          } else if (e.response?.statusCode != null && e.response!.statusCode! >= 500) {
            // Only show error messages for server errors (5xx)
            MessageService.instance.showError('Server error. Please try again later.');
          } else {
            // For other errors (400, etc), extract specific message but don't always show
            print('API error ${e.response?.statusCode}: ${e.requestOptions.path}');
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

  final _storage = const FlutterSecureStorage();

  final String _baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: defaultApiBaseUrl,
  );

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  String get baseUrl => _dio.options.baseUrl;

  Future<String?> getToken() async => await _storage.read(key: 'access_token');
  Future<String?> getRefreshToken() async =>
      await _storage.read(key: 'refresh_token');

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
    
    // Extract and save user ID from access token
    try {
      final userId = _extractUserIdFromToken(access);
      if (userId != null) {
        await saveUserId(userId);
      }
    } catch (e) {
      print('Failed to extract user ID from token: $e');
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
      print('Error decoding JWT token: $e');
      return null;
    }
  }

  Future<void> saveUserId(String id) async =>
      await _storage.write(key: 'user_id', value: id);
  Future<String?> getUserId() async => await _storage.read(key: 'user_id');

  Future<void> clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<bool> _refreshTokens() async {
    final refresh = await getRefreshToken();
    if (refresh == null) return false;

    try {
      final response = await _dio.post(
        '/auth/refresh',
        options: Options(headers: {'Authorization': 'Bearer $refresh'}),
      );

      final data = response.data as Map<String, dynamic>;
      final newAccess = data['access_token'] as String?;
      final newRefresh = data['refresh_token'] as String?;

      if (newAccess != null) {
        await _storage.write(key: 'access_token', value: newAccess);
      }
      if (newRefresh != null) {
        await _storage.write(key: 'refresh_token', value: newRefresh);
      }
      return true;
    } catch (_) {
      await clearTokens();
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Auth endpoints
  // ---------------------------------------------------------------------------

  Future<Response> loginWithGoogle(String idToken) async =>
      await _dio.post('/auth/google', data: {'id_token': idToken});

  Future<Response> register(String email, String password) async =>
      await _dio.post('/auth/register',
          data: {'email': email, 'password': password});

  Future<Response> login(String email, String password) async =>
      await _dio.post('/auth/login',
          data: {'email': email, 'password': password});

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
      // Check if user has basic profile data (country indicates some onboarding)
      final userData = response.data['data'];
      if (userData != null && userData['country'] != null) {
        return true;
      }
      return false;
    } catch (e) {
      // If there's an error (like 404/500), assume onboarding not completed
      print('Error checking onboarding status: $e');
      // For now, always show onboarding since backend routes aren't fully set up
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

  Future<Map<String, dynamic>> getDashboard() async {
    final token = await getToken();
    // Use calendar shell for dashboard data
    final response = await _dio.post(
      '/calendar/shell',
      data: {'year': DateTime.now().year, 'month': DateTime.now().month},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<List<dynamic>> getCalendar() async {
    final token = await getToken();
    // Use calendar shell to get calendar data
    final response = await _dio.post(
      '/calendar/shell',
      data: {'year': DateTime.now().year, 'month': DateTime.now().month},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    final calendar = response.data['data']['calendar'] ?? {};
    // Convert calendar object to list format expected by UI
    return calendar.values.toList();
  }

  // ---------------------------------------------------------------------------
  // Goals
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getGoals() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  Future<void> createGoal(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/goals/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateGoal(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/goals/$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteGoal(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/goals/$id/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
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

  // ---------------------------------------------------------------------------
  // Notifications
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get(
      '/notifications/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  // ---------------------------------------------------------------------------
  // Referral
  // ---------------------------------------------------------------------------

  Future<String> getReferralCode() async {
    final token = await getToken();
    final response = await _dio.get(
      '/referral/code',
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
    return response.data['data'] as List<dynamic>;
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
  // Manual logout
  // ---------------------------------------------------------------------------

  Future<void> logout() async {
    await clearTokens();
  }
}

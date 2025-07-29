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
        '/api/auth/refresh',
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
      await _dio.post('/api/auth/google', data: {'id_token': idToken});

  Future<Response> register(String email, String password) async =>
      await _dio.post('/api/auth/register',
          data: {'email': email, 'password': password});

  Future<Response> login(String email, String password) async =>
      await _dio.post('/api/auth/login',
          data: {'email': email, 'password': password});

  // ---------------------------------------------------------------------------
  // Onboarding
  // ---------------------------------------------------------------------------

  Future<bool> hasCompletedOnboarding() async {
    try {
      final token = await getToken();
      final response = await _dio.get(
        '/api/users/me',
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
      '/api/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Dashboard / Calendar
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getDashboard() async {
    final token = await getToken();
    
    // Prepare shell configuration with default values for dashboard
    final shellConfig = {
      'savings_target': 500.0,
      'income': 3000.0,
      'fixed': {
        'rent': 800.0,
        'utilities': 150.0,
        'insurance': 100.0,
      },
      'weights': {
        'food': 0.3,
        'transportation': 0.2,
        'entertainment': 0.15,
        'shopping': 0.2,
        'healthcare': 0.15,
      },
      'year': DateTime.now().year,
      'month': DateTime.now().month,
    };
    
    final response = await _dio.post(
      '/api/calendar/shell',
      data: shellConfig,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    
    final calendarData = response.data['data']['calendar'] ?? {};
    
    // Transform for dashboard display
    Map<String, dynamic> dashboardData = {
      'calendar': calendarData,
      'today_budget': 0.0,
      'today_spent': 0.0,
      'monthly_budget': 0.0,
      'monthly_spent': 0.0,
    };
    
    if (calendarData is Map && calendarData.containsKey('flexible')) {
      final flexible = calendarData['flexible'] as Map<String, dynamic>;
      final totalDaily = flexible.values.fold<double>(0.0, (sum, amount) => sum + (amount as num).toDouble());
      
      dashboardData['today_budget'] = totalDaily;
      dashboardData['monthly_budget'] = totalDaily * DateTime.now().day;
      dashboardData['today_spent'] = totalDaily * 0.7; // Simulated spending
      dashboardData['monthly_spent'] = totalDaily * DateTime.now().day * 0.7;
    }
    
    return dashboardData;
  }

  Future<List<dynamic>> getCalendar() async {
    final token = await getToken();
    
    // Prepare shell configuration with default values
    // These should ideally come from user preferences/onboarding data
    final shellConfig = {
      'savings_target': 500.0, // Default savings goal
      'income': 3000.0, // Default monthly income
      'fixed': {
        'rent': 800.0,
        'utilities': 150.0,
        'insurance': 100.0,
      },
      'weights': {
        'food': 0.3,
        'transportation': 0.2,
        'entertainment': 0.15,
        'shopping': 0.2,
        'healthcare': 0.15,
      },
      'year': DateTime.now().year,
      'month': DateTime.now().month,
    };
    
    final response = await _dio.post(
      '/api/calendar/shell',
      data: shellConfig,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    
    final calendarData = response.data['data']['calendar'] ?? {};
    
    // Transform the budget data into calendar day format
    List<dynamic> calendarDays = [];
    
    if (calendarData is Map && calendarData.containsKey('flexible')) {
      // This is goal budget format - transform it to daily calendar
      final flexible = calendarData['flexible'] as Map<String, dynamic>;
      final totalDaily = flexible.values.fold<double>(0.0, (sum, amount) => sum + (amount as num).toDouble());
      
      // Generate days for current month
      final now = DateTime.now();
      final daysInMonth = DateTime(now.year, now.month + 1, 0).day;
      
      for (int day = 1; day <= daysInMonth; day++) {
        // Simulate spending status based on day of month for demo
        String status = 'good';
        if (day > 25) {
          status = 'over';
        } else if (day > 20) {
          status = 'warning';
        }
        
        calendarDays.add({
          'day': day,
          'limit': totalDaily.round(),
          'status': status,
          'spent': day < DateTime.now().day ? (totalDaily * 0.7).round() : 0,
        });
      }
    } else if (calendarData is Map) {
      // Handle other calendar formats
      calendarData.forEach((key, value) {
        if (value is Map) {
          calendarDays.add({
            'day': int.tryParse(key.toString()) ?? 0,
            'limit': (value['limit'] ?? 0).round(),
            'status': value['status'] ?? 'good',
            'spent': (value['total'] ?? 0).round(),
          });
        }
      });
    }
    
    return calendarDays;
  }

  // ---------------------------------------------------------------------------
  // Goals
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getGoals() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/goals/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  Future<void> createGoal(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/goals/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateGoal(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/goals/$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteGoal(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/goals/$id/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Habits
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getHabits() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/habits/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  Future<void> createHabit(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/habits/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateHabit(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/habits/$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteHabit(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/habits/$id/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> completeHabit(int habitId, String date) async {
    final token = await getToken();
    await _dio.post(
      '/api/habits/$habitId/complete',
      data: {'date': date},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> uncompleteHabit(int habitId, String date) async {
    final token = await getToken();
    await _dio.delete(
      '/api/habits/$habitId/complete',
      data: {'date': date},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getHabitProgress(int habitId) async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/habits/$habitId/progress',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  // ---------------------------------------------------------------------------
  // Notifications
  // ---------------------------------------------------------------------------

  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/notifications/',
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
      '/api/referrals/code',
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
      '/api/mood/',
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
      '/api/analytics/monthly',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] as Map);
  }

  Future<List<dynamic>> getExpenses() async {
    final token = await getToken();
    // Use transactions endpoint to get expense history
    final response = await _dio.get(
      '/api/transactions/',
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
      '/api/iap/validate',
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
      '/api/insights/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data'] as Map<String, dynamic>?;
  }

  Future<List<dynamic>> getAdviceHistory() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/insights/history',
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
      '/api/users/me',
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
      '/api/budgets/daily',
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
      '/api/budgets/spent',
      queryParameters: queryParams,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<Map<String, dynamic>> getBudgetRemaining({int? year, int? month}) async {
    final token = await getToken();
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year;
    if (month != null) queryParams['month'] = month;
    
    final response = await _dio.get(
      '/api/budgets/remaining',
      queryParameters: queryParams,
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
      '/api/transactions/receipt',
      data: formData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  Future<void> createTransaction(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/transactions/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> updateExpense(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/transactions/$id',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> deleteExpense(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/transactions/$id',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Profile Updates
  // ---------------------------------------------------------------------------

  Future<void> updateUserProfile(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/users/me',
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
      '/api/expenses/installments',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<dynamic>.from(response.data['data'] ?? []);
  }

  // ---------------------------------------------------------------------------
  // Manual logout
  // ---------------------------------------------------------------------------

  Future<void> logout() async {
    await clearTokens();
  }
}

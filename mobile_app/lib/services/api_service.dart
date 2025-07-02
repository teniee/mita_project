import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config.dart';

class ApiService {
  ApiService() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioError e, handler) async {
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
            }
          }
          handler.next(e);
        },
      ),
    );
  }

  final String _baseUrl =
      const String.fromEnvironment('API_BASE_URL', defaultValue: defaultApiBaseUrl);

  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: _baseUrl,
      connectTimeout: const Duration(seconds: 20),
      receiveTimeout: const Duration(seconds: 20),
      contentType: 'application/json',
    ),
  );

  
  String get baseUrl => _dio.options.baseUrl;

  final _storage = const FlutterSecureStorage();

  Future<String?> getToken() async => await _storage.read(key: 'access_token');
  Future<String?> getRefreshToken() async => await _storage.read(key: 'refresh_token');

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
  }

  Future<void> saveUserId(String id) async => await _storage.write(key: 'user_id', value: id);
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
      if (newAccess != null) await _storage.write(key: 'access_token', value: newAccess);
      if (newRefresh != null) await _storage.write(key: 'refresh_token', value: newRefresh);
      return true;
    } catch (_) {
      await clearTokens();
      return false;
    }
  }

  Future<Response> loginWithGoogle(String idToken) async =>
      await _dio.post('/api/auth/google', data: {'id_token': idToken});

  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    final response = await _dio.post(
      '/api/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<Map<String, dynamic>> getDashboard() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/dashboard/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<List<dynamic>> getCalendar() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/calendar/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<void> createExpense(Map<String, dynamic> data) async {
    final token = await getToken();
    final userId = await getUserId();
    await _dio.post(
      '/api/expense/add',
      data: {...data, 'user_id': userId},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<List<dynamic>> getGoals() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/goals/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<void> createGoal(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post('/api/goals/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<void> updateGoal(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch('/api/goals/$id/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<void> deleteGoal(int id) async {
    final token = await getToken();
    await _dio.delete('/api/goals/$id/', options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<Map<String, dynamic>> getInsights() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/insights/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data);
  }

  Future<Map<String, dynamic>?> getLatestAdvice() async {
    final token = await getToken();
    final response = await _dio.get('/api/insights/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data['data'] as Map<String, dynamic>?;
  }

  Future<List<dynamic>> getAdviceHistory() async {
    final token = await getToken();
    final response = await _dio.get('/api/insights/history', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return List<dynamic>.from(response.data['data'] as List);
  }

  Future<Map<String, dynamic>> getUser() async {
    final token = await getToken();
    final response = await _dio.get('/api/user/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return Map<String, dynamic>.from(response.data);
  }

  Future<List<dynamic>> getInstallments() async {
    final token = await getToken();
    final response = await _dio.get('/api/installments/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<List<dynamic>> getExpenses() async {
    final token = await getToken();
    final userId = await getUserId();
    final response = await _dio.post(
      '/api/expense/history',
      data: {'user_id': userId},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['expenses'] as List<dynamic>;
  }

  Future<void> updateExpense(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch('/api/expenses/$id/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<void> deleteExpense(int id) async {
    final token = await getToken();
    await _dio.delete('/api/expenses/$id/', options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<Map<String, dynamic>> getUserProfile() async {
    final token = await getToken();
    final response = await _dio.get('/api/user/profile/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<void> updateUserProfile(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch('/api/user/profile/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get('/api/notifications/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<List<dynamic>> getHabits() async {
    final token = await getToken();
    final response = await _dio.get('/api/habits/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<void> createHabit(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post('/api/habits/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<void> updateHabit(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch('/api/habits/$id/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<void> deleteHabit(int id) async {
    final token = await getToken();
    await _dio.delete('/api/habits/$id/', options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<List<dynamic>> getDailyBudgets() async {
    final token = await getToken();
    final response = await _dio.get('/api/daily-budget/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<List<dynamic>> getMonthlyAnalytics() async {
    final token = await getToken();
    final response = await _dio.get('/api/analytics/monthly/', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data;
  }

  Future<void> createTransaction(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post('/api/transactions/', data: data, options: Options(headers: {'Authorization': 'Bearer $token'}));
  }

  Future<Map<String, dynamic>> uploadReceipt(File file) async {
    final token = await getToken();
    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: 'receipt.jpg'),
    });
    final response = await _dio.post(
      '/api/transactions/receipt',
      data: form,
      options: Options(
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'multipart/form-data',
        },
      ),
    );
    return Map<String, dynamic>.from(response.data['data'] as Map);
  }

  Future<void> registerPushToken(String token) async {
    final access = await getToken();
    await _dio.post(
      '/api/notifications/register-token',
      data: {'token': token},
      options: Options(headers: {'Authorization': 'Bearer $access'}),
    );
  }

  Future<Map<String, dynamic>> validateReceipt(
      String userId, String receipt, String platform) async {
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

  Future<String> getReferralCode() async {
    final token = await getToken();
    final response = await _dio.get('/api/referral/code', options: Options(headers: {'Authorization': 'Bearer $token'}));
    return response.data['data']['code'] as String;
  }

  Future<void> logMood(int mood) async {
    final token = await getToken();
    await _dio.post(
      '/api/mood/',
      data: {'mood': mood, 'date': DateTime.now().toIso8601String()},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> logout() async {
    final token = await getToken();
    if (token != null) {
      await _dio.post('/api/auth/logout', options: Options(headers: {'Authorization': 'Bearer $token'}));
    }
    await clearTokens();
    await _storage.delete(key: 'user_id');
  }
}

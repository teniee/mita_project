import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config.dart';

class ApiService {
  final String _baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: defaultApiBaseUrl,
  );

  late final Dio _dio;

  final _storage = const FlutterSecureStorage();

  ApiService() {
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

  String get baseUrl => _dio.options.baseUrl;

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
        '/auth/auth/refresh',
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
      await _dio.post('/auth/auth/google', data: {'id_token': idToken});

  Future<Response> register(String email, String password) async =>
      await _dio.post(
        '/auth/auth/register',
        data: {'email': email, 'password': password},
      );

  Future<Response> login(String email, String password) async =>
      await _dio.post(
        '/auth/auth/login',
        data: {'email': email, 'password': password},
      );

  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getDashboard() async {
    final token = await getToken();
    final response = await _dio.get(
      '/dashboard/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data);
  }

  Future<List<dynamic>> getCalendar() async {
    final token = await getToken();
    final response = await _dio.get(
      '/calendar/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<List<dynamic>> getGoals() async {
    final token = await getToken();
    final response = await _dio.get(
      '/goals/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
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

  Future<Map<String, dynamic>> getUserProfile() async {
    final token = await getToken();
    final response = await _dio.get(
      '/users/users/me',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<List<dynamic>> getHabits() async {
    final token = await getToken();
    final response = await _dio.get(
      '/habits/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
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

  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get(
      '/notifications/',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data;
  }

  Future<String> getReferralCode() async {
    final token = await getToken();
    final response = await _dio.get(
      '/referral/code',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['code'] as String;
  }

  Future<void> logMood(int mood) async {
    final token = await getToken();
    await _dio.post(
      '/mood/',
      data: {'mood': mood, 'date': DateTime.now().toIso8601String()},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getMonthlyAnalytics() async {
    final token = await getToken();
    final userId = await getUserId();
    final response = await _dio.get(
      '/analytics/monthly/$userId',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] as Map);
  }

  Future<List<dynamic>> getExpenses() async {
    final token = await getToken();
    final userId = await getUserId();
    final response = await _dio.post(
      '/expense/history',
      data: {'user_id': userId},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['expenses'] as List<dynamic>;
  }

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
}

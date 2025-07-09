import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config.dart';

class ApiService {
  final String _baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: defaultApiBaseUrl, // Example: https://yourserver.com/api
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
          print('[API] REQUEST: ${options.method} ${options.uri}');
          handler.next(options);
        },
        onError: (DioError e, handler) async {
          print('[API] ERROR: ${e.response?.statusCode} ${e.requestOptions.uri}');
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
        '/auth/refresh', // Should be /api/auth/refresh if your backend expects that
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

  /// Google sign-in
  Future<Response> loginWithGoogle(String idToken) async =>
      await _dio.post('/auth/google', data: {'id_token': idToken});

  /// Email/Password register
  Future<Response> register(String email, String password) async =>
      await _dio.post('/auth/register', data: {'email': email, 'password': password});

  /// Email/Password login
  Future<Response> login(String email, String password) async =>
      await _dio.post('/auth/login', data: {'email': email, 'password': password});

  /// Onboarding
  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  /// Get user profile
  Future<Map<String, dynamic>> getUserProfile() async {
    final token = await getToken();
    final response = await _dio.get(
      '/users/me',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data);
  }

  /// Manual logout
  Future<void> logout() async {
    await clearTokens();
  }

  /// Add any other endpoints below...
}

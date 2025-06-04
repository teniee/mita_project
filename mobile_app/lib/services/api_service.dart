
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  final Dio _dio = Dio(BaseOptions(
    baseUrl: 'https://mita-docker-ready-project-manus.onrender.com',
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 10),
    contentType: 'application/json',
  ));

  final _storage = const FlutterSecureStorage();

  Future<String?> getToken() async {
    return await _storage.read(key: 'access_token');
  }

  Future<void> saveToken(String token) async {
    await _storage.write(key: 'access_token', value: token);
  }

  Future<Response> loginWithGoogle(String idToken) async {
    return await _dio.post(
      '/api/auth/google',
      data: {'id_token': idToken},
    );
  }

  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    final response = await _dio.post(
      '/api/onboarding/onboarding/submit',
      data: data,
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }

  Future<Map<String, dynamic>> getDashboard() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/dashboard/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }


  Future<List<dynamic>> getCalendar() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/calendar/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }


  Future<void> createExpense(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/expenses/create/',
      data: data,
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
  }


  Future<List<dynamic>> getGoals() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/goals/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }

  Future<void> createGoal(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/goals/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }

  Future<void> updateGoal(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/goals/\$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }

  Future<void> deleteGoal(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/goals/\$id/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }


  Future<Map<String, dynamic>> getInsights() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/insights/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return Map<String, dynamic>.from(response.data);
  }


  Future<Map<String, dynamic>> getUser() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/user/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return Map<String, dynamic>.from(response.data);
  }


  Future<List<dynamic>> getInstallments() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/installments/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }


  Future<List<dynamic>> getExpenses() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/expenses/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
    return response.data;
  }


  Future<void> updateExpense(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/expenses/\$id/',
      data: data,
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
  }

  Future<void> deleteExpense(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/expenses/\$id/',
      options: Options(
        headers: {'Authorization': 'Bearer \$token'},
      ),
    );
  }

  Future<Map<String, dynamic>> getUserProfile() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/user/profile/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
    return response.data;
  }

  Future<void> updateUserProfile(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/user/profile/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }


  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/notifications/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
    return response.data;
  }


  Future<List<dynamic>> getHabits() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/habits/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
    return response.data;
  }

  Future<void> createHabit(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/api/habits/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }

  Future<void> updateHabit(int id, Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/api/habits/\$id/',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }

  Future<void> deleteHabit(int id) async {
    final token = await getToken();
    await _dio.delete(
      '/api/habits/\$id/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
  }


  Future<List<dynamic>> getDailyBudgets() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/daily-budget/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
    return response.data;
  }

  Future<List<dynamic>> getMonthlyAnalytics() async {
    final token = await getToken();
    final response = await _dio.get(
      '/api/analytics/monthly/',
      options: Options(headers: {'Authorization': 'Bearer \$token'}),
    );
    return response.data;
  }
}

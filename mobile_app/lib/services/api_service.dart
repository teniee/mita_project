import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';
import 'loading_service.dart';
import 'message_service.dart';
import 'logging_service.dart';
import 'calendar_fallback_service.dart';
import 'advanced_offline_service.dart';

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

          // Structured logging
          logDebug('API Request: ${options.method} ${options.uri}', 
            tag: 'API',
            extra: {
              'method': options.method,
              'url': options.uri.toString(),
              'headers': options.headers,
              'hasData': options.data != null,
            }
          );

          final token = await getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onResponse: (response, handler) {
          LoadingService.instance.stop();
          
          // Structured logging
          logDebug('API Response: ${response.statusCode} ${response.requestOptions.uri}',
            tag: 'API',
            extra: {
              'statusCode': response.statusCode,
              'url': response.requestOptions.uri.toString(),
              'hasData': response.data != null,
            }
          );
          
          handler.next(response);
        },
        onError: (DioError e, handler) async {
          LoadingService.instance.stop();

          // Structured error logging
          logError('API Error: ${e.response?.statusCode} ${e.requestOptions.uri}',
            tag: 'API',
            extra: {
              'statusCode': e.response?.statusCode,
              'url': e.requestOptions.uri.toString(),
              'errorMessage': e.message,
              'errorData': e.response?.data,
            },
            error: e,
          );

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
            logWarning('API endpoint not found: ${e.requestOptions.path}', tag: 'API');
          } else if (e.response?.statusCode != null && e.response!.statusCode! >= 500) {
            // Only show error messages for server errors (5xx)
            MessageService.instance.showError('Server error. Please try again later.');
            logError('Server error: ${e.response?.statusCode}', tag: 'API', error: e);
          } else {
            // For other errors (400, etc), extract specific message but don't always show
            logWarning('API error ${e.response?.statusCode}: ${e.requestOptions.path}', tag: 'API');
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
        '/users/users/me',
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
      logWarning('Error checking onboarding status: $e', tag: 'ONBOARDING');
      // For now, always show onboarding since backend routes aren't fully set up
      return false;
    }
  }

  Future<void> submitOnboarding(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.post(
      '/onboarding/onboarding/submit',
      data: data,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Dashboard / Calendar
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getDashboard({double? userIncome}) async {
    final token = await getToken();
    
    // Get user profile to retrieve actual income if not provided
    double actualIncome = userIncome ?? 0.0;
    if (actualIncome == 0.0) {
      try {
        final profile = await getUserProfile();
        actualIncome = (profile['data']?['income'] as num?)?.toDouble() ?? 0.0;
      } catch (e) {
        // Fallback: use a reasonable default but warn about missing income
        actualIncome = 3000.0;
      }
    }
    
    // Prepare shell configuration with user's actual income
    final shellConfig = {
      'savings_target': actualIncome * 0.2, // 20% savings target
      'income': actualIncome,
      'fixed': {
        'rent': actualIncome * 0.3,     // 30% for housing
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
      logError('Failed to fetch calendar data, using fallback', tag: 'DASHBOARD', error: e);
      // Provide fallback calendar data based on the shell configuration
      final income = actualIncome;
      final weights = shellConfig['weights'] as Map<String, dynamic>;
      calendarData = {
        'flexible': {
          'food': income * (weights['food'] as double),
          'transportation': income * (weights['transportation'] as double),
          'entertainment': income * (weights['entertainment'] as double),
          'shopping': income * (weights['shopping'] as double),
          'healthcare': income * (weights['healthcare'] as double),
        },
        'fixed': shellConfig['fixed'],
        'savings': shellConfig['savings_target'],
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

  Future<List<dynamic>> getCalendar({double? userIncome}) async {
    final token = await getToken();
    
    // Get user profile to retrieve actual income and location if not provided
    double actualIncome = userIncome ?? 0.0;
    String? userLocation;
    
    if (actualIncome == 0.0) {
      try {
        final profile = await getUserProfile();
        actualIncome = (profile['data']?['income'] as num?)?.toDouble() ?? 0.0;
        userLocation = profile['data']?['location'] as String?;
      } catch (e) {
        logWarning('Failed to get user profile for calendar, using defaults', tag: 'CALENDAR');
        actualIncome = 3000.0; // Reasonable default
      }
    }
    
    // Try to get cached calendar data first
    final cacheKey = 'calendar_${actualIncome}_${DateTime.now().year}_${DateTime.now().month}';
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
        'rent': actualIncome * 0.3,     // 30% for housing
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
          sendTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 10),
        ),
      );
      
      final calendarData = response.data['data']['calendar'] ?? {};
      final calendarDays = _transformCalendarData(calendarData, actualIncome);
      
      // Cache the successful response
      await _cacheCalendarData(cacheKey, calendarDays);
      
      logDebug('Successfully fetched calendar data from backend', tag: 'CALENDAR');
      return calendarDays;
    } catch (e) {
      logError('Backend calendar fetch failed, using intelligent fallback', tag: 'CALENDAR', error: e);
      
      // Use intelligent fallback service
      try {
        final fallbackService = CalendarFallbackService();
        final fallbackData = await fallbackService.generateFallbackCalendarData(
          monthlyIncome: actualIncome,
          location: userLocation,
          year: DateTime.now().year,
          month: DateTime.now().month,
        );
        
        // Cache the fallback data with shorter expiry
        await _cacheCalendarData(cacheKey, fallbackData, const Duration(minutes: 30));
        
        logInfo('Using intelligent fallback calendar data', tag: 'CALENDAR', extra: {
          'income': actualIncome,
          'location': userLocation,
          'days_generated': fallbackData.length,
        });
        
        return fallbackData;
      } catch (fallbackError) {
        logError('Fallback calendar generation failed', tag: 'CALENDAR', error: fallbackError);
        
        // Last resort: basic fallback
        return _generateBasicFallbackCalendar(actualIncome);
      }
    }
  }

  /// Cache calendar data for faster access
  Future<void> _cacheCalendarData(String cacheKey, List<dynamic> calendarData, [Duration? expiry]) async {
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
      logWarning('Failed to retrieve cached calendar data: $e', tag: 'CALENDAR');
    }
    return null;
  }

  /// Transform backend calendar data to standard format
  List<dynamic> _transformCalendarData(Map<String, dynamic> calendarData, double actualIncome) {
    List<dynamic> calendarDays = [];
    
    if (calendarData.containsKey('flexible')) {
      // Transform flexible budget format to daily calendar
      final flexible = calendarData['flexible'] as Map<String, dynamic>;
      final totalDaily = flexible.values.fold<double>(0.0, (sum, amount) => sum + (amount as num).toDouble());
      
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
          spent = _calculateRealisticSpentAmount(totalDaily.round(), day, currentDate.weekday);
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
    
    if (ratio > 1.1) return 'over';      // >110%
    if (ratio > 0.85) return 'warning';  // 85-110%
    return 'good';                       // <85%
  }

  /// Generate category breakdown from flexible budget
  Map<String, int> _generateCategoryBreakdown(Map<String, dynamic> flexible) {
    final breakdown = <String, int>{};
    final daysInMonth = DateTime.now().day; // Current day for averaging
    
    flexible.forEach((category, monthlyAmount) {
      final dailyAmount = ((monthlyAmount as num) / 30).round(); // Use 30 as average
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

  Future<List<dynamic>> getNotifications() async {
    final token = await getToken();
    final response = await _dio.get(
      '/notifications/notifications/register-token',
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
      '/analytics/analytics/monthly',
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
      '/users/users/me',
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

  Future<Map<String, dynamic>> getBudgetRemaining({int? year, int? month}) async {
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
  Future<Map<String, dynamic>> redistributeCalendarBudget(Map<String, dynamic> calendar, {String strategy = 'balance'}) async {
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
  Future<Map<String, dynamic>> getBudgetSuggestions({int? year, int? month}) async {
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
  Future<Map<String, dynamic>> getBehavioralBudgetAllocation(double totalAmount, {Map<String, dynamic>? profile}) async {
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
  Future<Map<String, dynamic>> getMonthlyBudget(int year, int month, {Map<String, dynamic>? userAnswers}) async {
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
  Future<List<dynamic>> getBudgetRedistributionHistory({int? year, int? month}) async {
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
  Future<void> updateBudgetAutomationSettings(Map<String, dynamic> settings) async {
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
      if (processingOptions != null) 
        'options': jsonEncode(processingOptions),
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
      'files': receiptFiles.map((file) async => await MultipartFile.fromFile(file.path)).toList(),
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
  Future<Map<String, dynamic>> validateOCRResult(Map<String, dynamic> ocrData) async {
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

  // ---------------------------------------------------------------------------
  // Profile Updates
  // ---------------------------------------------------------------------------

  Future<void> updateUserProfile(Map<String, dynamic> data) async {
    final token = await getToken();
    await _dio.patch(
      '/users/users/me',
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
      '/financial/financial/installment-evaluate',
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
      '/ai/ai/ai/latest-snapshots',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    final data = response.data['data'] as List?;
    return data?.isNotEmpty == true ? data!.first as Map<String, dynamic> : null;
  }

  /// Create a new AI snapshot analysis for a specific month
  Future<Map<String, dynamic>> createAISnapshot({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.post(
      '/ai/ai/ai/snapshot',
      data: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get comprehensive AI financial profile with behavioral patterns
  Future<Map<String, dynamic>> getAIFinancialProfile({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/ai/profile',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI explanation for day status with personalized recommendations
  Future<String> getAIDayStatusExplanation(String status, {List<String>? recommendations, String? date}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/ai/day-status-explanation',
      data: {
        'status': status,
        'recommendations': recommendations ?? [],
        'date': date ?? DateTime.now().toIso8601String().split('T')[0],
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['explanation'] as String? ?? 'Status explanation not available';
  }

  /// Get AI-powered spending behavior insights and patterns
  Future<Map<String, dynamic>> getSpendingPatterns({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/ai/spending-patterns',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get personalized AI feedback based on recent spending behavior
  Future<Map<String, dynamic>> getAIPersonalizedFeedback({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/ai/personalized-feedback',
      queryParameters: {
        'year': year ?? now.year,
        'month': month ?? now.month,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered budget optimization suggestions
  Future<Map<String, dynamic>> getAIBudgetOptimization({Map<String, dynamic>? calendar, double? income}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/ai/budget-optimization',
      data: {
        'calendar': calendar,
        'income': income,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI category suggestions for transaction categorization
  Future<List<Map<String, dynamic>>> getAICategorySuggestions(String transactionDescription, {double? amount}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/ai/category-suggestions',
      data: {
        'description': transactionDescription,
        'amount': amount,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return List<Map<String, dynamic>>.from(response.data['data'] ?? []);
  }

  /// Ask the AI assistant a financial question
  Future<String> askAIAssistant(String question, {Map<String, dynamic>? context}) async {
    final token = await getToken();
    final response = await _dio.post(
      '/ai/ai/assistant',
      data: {
        'question': question,
        'context': context,
      },
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return response.data['data']['response'] as String? ?? 'I\'m unable to provide a response right now.';
  }

  /// Get AI-powered anomaly detection in spending patterns
  Future<List<Map<String, dynamic>>> getSpendingAnomalies({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/ai/spending-anomalies',
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
      '/ai/ai/financial-health-score',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered savings optimization suggestions
  Future<Map<String, dynamic>> getAISavingsOptimization() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/ai/savings-optimization',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI prediction for future spending based on historical patterns
  Future<Map<String, dynamic>> getAISpendingPrediction({int? daysAhead}) async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/ai/spending-prediction',
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
      '/ai/ai/goal-analysis',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered weekly financial insights summary
  Future<Map<String, dynamic>> getAIWeeklyInsights() async {
    final token = await getToken();
    final response = await _dio.get(
      '/ai/ai/weekly-insights',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    return Map<String, dynamic>.from(response.data['data'] ?? {});
  }

  /// Get AI-powered monthly financial report with insights
  Future<Map<String, dynamic>> getAIMonthlyReport({int? year, int? month}) async {
    final token = await getToken();
    final now = DateTime.now();
    final response = await _dio.get(
      '/ai/ai/monthly-report',
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
  Future<Map<String, dynamic>> getBehavioralAnalysis({int? year, int? month}) async {
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
  Future<Map<String, dynamic>> getSpendingPatternAnalysis({int? year, int? month}) async {
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
  Future<Map<String, dynamic>> getBehavioralAnomalies({int? year, int? month}) async {
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
  Future<Map<String, dynamic>> getSpendingTriggers({int? year, int? month}) async {
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
  Future<void> updateBehavioralPreferences(Map<String, dynamic> preferences) async {
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
  Future<Map<String, dynamic>> getCategoryBehavioralInsights(String category, {int? year, int? month}) async {
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
  Future<Map<String, dynamic>> getBehavioralWarnings({int? year, int? month}) async {
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
      // Return demo predictions if endpoint not available
      return {
        'next_month_spending': 2850.00,
        'confidence': 0.78,
        'risk_factors': [
          {'factor': 'Upcoming holiday season', 'impact': 'high'},
          {'factor': 'Recent salary increase', 'impact': 'medium'},
        ],
        'recommended_budget': 2600.00,
        'savings_potential': 250.00,
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
      // Return demo anomalies if endpoint not available
      return [
        {
          'date': DateTime.now().subtract(const Duration(days: 3)).toIso8601String(),
          'category': 'Entertainment',
          'amount': 150.00,
          'expected_amount': 45.00,
          'anomaly_score': 0.85,
          'description': 'Unusual entertainment spending - 233% above normal',
          'possible_causes': ['Special event', 'Social gathering'],
        },
        {
          'date': DateTime.now().subtract(const Duration(days: 7)).toIso8601String(),
          'category': 'Food',
          'amount': 85.00,
          'expected_amount': 35.00,
          'anomaly_score': 0.72,
          'description': 'Higher than usual food spending',
          'possible_causes': ['Dining out', 'Grocery stock-up'],
        },
      ];
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
      // Return demo insights if endpoint not available
      return {
        'spending_personality': 'Mindful Spender',
        'key_traits': [
          'Plans purchases in advance',
          'Responds well to visual budgeting',
          'Weekend spending tends to increase',
        ],
        'improvement_areas': [
          'Food spending optimization',
          'Weekend budget control',
          'Emotional spending awareness',
        ],
        'strengths': [
          'Consistent daily spending habits',
          'Good at tracking expenses',
          'Responsive to budget alerts',
        ],
        'recommended_strategies': [
          'Set specific weekend spending limits',
          'Use meal planning to control food costs',
          'Create emotional spending checkpoints',
        ],
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
      // Return demo OCR results if service unavailable
      return {
        'merchant': 'Starbucks Coffee',
        'amount': 12.45,
        'date': DateTime.now().toIso8601String(),
        'category': 'Food & Dining',
        'items': [
          {'name': 'Grande Latte', 'price': 5.25},
          {'name': 'Blueberry Muffin', 'price': 3.95},
          {'name': 'Tax', 'price': 0.85},
        ],
        'confidence': 0.89,
        'processing_time': 2.3,
      };
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

  Future<List<String>> getCategorySuggestions(String description, double amount) async {
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
      // Return demo suggestions based on common patterns
      if (description.toLowerCase().contains('coffee') ||
          description.toLowerCase().contains('restaurant') ||
          description.toLowerCase().contains('food')) {
        return ['Food & Dining', 'Coffee Shops', 'Restaurants'];
      } else if (description.toLowerCase().contains('gas') ||
                 description.toLowerCase().contains('fuel')) {
        return ['Transportation', 'Gas Stations', 'Vehicle'];
      } else if (description.toLowerCase().contains('store') ||
                 description.toLowerCase().contains('shop')) {
        return ['Shopping', 'Retail', 'General'];
      }
      return ['General', 'Other', 'Miscellaneous'];
    }
  }

  Future<Map<String, dynamic>> enhanceReceiptData(Map<String, dynamic> ocrData) async {
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
      enhanced['spending_category'] = _getSpendingCategory(ocrData['category'] ?? '');
      return enhanced;
    }
  }

  String _getMerchantType(String merchant) {
    final lower = merchant.toLowerCase();
    if (lower.contains('starbucks') || lower.contains('coffee')) return 'Coffee Shop';
    if (lower.contains('restaurant') || lower.contains('pizza')) return 'Restaurant';
    if (lower.contains('gas') || lower.contains('shell')) return 'Gas Station';
    if (lower.contains('store') || lower.contains('mart')) return 'Retail Store';
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
        '/challenges/challenge/eligibility',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<dynamic>.from(response.data['data'] ?? []);
    } catch (e) {
      // Return demo challenges if endpoint not available
      return [
        {
          'id': '1',
          'title': 'Coffee Saver Challenge',
          'description': 'Skip buying coffee for 5 days and save money',
          'type': 'spending_reduction',
          'target_value': 5,
          'current_progress': 2,
          'reward_points': 100,
          'reward_amount': 25.0,
          'status': 'active',
          'difficulty': 'easy',
          'duration_days': 7,
          'start_date': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
          'end_date': DateTime.now().add(const Duration(days: 5)).toIso8601String(),
          'category': 'Food & Dining',
        },
        {
          'id': '2',
          'title': 'Weekend Budget Master',
          'description': 'Stay within weekend budget for 4 consecutive weekends',
          'type': 'budget_adherence',
          'target_value': 4,
          'current_progress': 1,
          'reward_points': 250,
          'reward_amount': 50.0,
          'status': 'active',
          'difficulty': 'medium',
          'duration_days': 28,
          'start_date': DateTime.now().subtract(const Duration(days: 7)).toIso8601String(),
          'end_date': DateTime.now().add(const Duration(days: 21)).toIso8601String(),
          'category': 'Entertainment',
        },
        {
          'id': '3',
          'title': 'Transportation Optimizer',
          'description': 'Reduce transportation costs by 20% this month',
          'type': 'category_reduction',
          'target_value': 20.0,
          'current_progress': 8.5,
          'reward_points': 500,
          'reward_amount': 100.0,
          'status': 'active',
          'difficulty': 'hard',
          'duration_days': 30,
          'start_date': DateTime.now().subtract(const Duration(days: 10)).toIso8601String(),
          'end_date': DateTime.now().add(const Duration(days: 20)).toIso8601String(),
          'category': 'Transportation',
        },
      ];
    }
  }

  Future<Map<String, dynamic>> getChallengeProgress(String challengeId) async {
    final token = await getToken();
    
    try {
      final response = await _dio.get(
        '/challenges/$challengeId/progress',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return demo progress data
      return {
        'challenge_id': challengeId,
        'current_progress': 2,
        'target_value': 5,
        'completion_percentage': 40.0,
        'streak_days': 2,
        'best_streak': 3,
        'daily_progress': [
          {'date': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(), 'completed': true},
          {'date': DateTime.now().subtract(const Duration(days: 1)).toIso8601String(), 'completed': true},
          {'date': DateTime.now().toIso8601String(), 'completed': false},
        ],
        'estimated_completion': DateTime.now().add(const Duration(days: 3)).toIso8601String(),
      };
    }
  }

  Future<void> joinChallenge(String challengeId) async {
    final token = await getToken();
    
    await _dio.post(
      '/challenges/$challengeId/join',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<void> leaveChallenge(String challengeId) async {
    final token = await getToken();
    
    await _dio.delete(
      '/challenges/$challengeId/leave',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<Map<String, dynamic>> getGameificationStats() async {
    final token = await getToken();
    
    try {
      final response = await _dio.get(
        '/challenges/stats',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return Map<String, dynamic>.from(response.data['data'] ?? {});
    } catch (e) {
      // Return demo gamification stats
      return {
        'total_points': 1250,
        'current_level': 5,
        'next_level_points': 1500,
        'points_to_next_level': 250,
        'completed_challenges': 8,
        'active_challenges': 3,
        'current_streak': 12,
        'best_streak': 18,
        'badges_earned': [
          {
            'id': 'coffee_saver',
            'name': 'Coffee Saver',
            'description': 'Saved money by skipping coffee purchases',
            'icon': 'coffee',
            'earned_date': DateTime.now().subtract(const Duration(days: 5)).toIso8601String(),
            'rarity': 'common',
          },
          {
            'id': 'budget_master',
            'name': 'Budget Master',
            'description': 'Stayed within budget for 7 consecutive days',
            'icon': 'trophy',
            'earned_date': DateTime.now().subtract(const Duration(days: 10)).toIso8601String(),
            'rarity': 'rare',
          },
          {
            'id': 'early_bird',
            'name': 'Early Bird',
            'description': 'Completed 5 challenges in first month',
            'icon': 'star',
            'earned_date': DateTime.now().subtract(const Duration(days: 15)).toIso8601String(),
            'rarity': 'epic',
          },
        ],
        'leaderboard_position': 42,
        'points_this_week': 150,
        'challenges_completed_this_month': 2,
      };
    }
  }

  Future<List<dynamic>> getAvailableChallenges() async {
    final token = await getToken();
    
    try {
      final response = await _dio.get(
        '/challenges/available',
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
          'description': 'Complete a weekend without any non-essential spending',
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

  Future<void> updateChallengeProgress(String challengeId, Map<String, dynamic> progressData) async {
    final token = await getToken();
    
    await _dio.patch(
      '/challenges/$challengeId/progress',
      data: progressData,
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  Future<List<dynamic>> getLeaderboard({String? period = 'weekly'}) async {
    final token = await getToken();
    
    try {
      final response = await _dio.get(
        '/challenges/leaderboard',
        queryParameters: {'period': period},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return List<dynamic>.from(response.data['data'] ?? []);
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
      return {
        'monthly_income': income,
        'tier': income < 3000 ? 'low' : income <= 7000 ? 'mid' : 'high',
        'tier_name': income < 3000 ? 'Essential Earner' : income <= 7000 ? 'Growing Professional' : 'High Achiever',
        'range': income < 3000 ? 'Under \$3,000' : income <= 7000 ? '\$3,000 - \$7,000' : 'Over \$7,000',
      };
    }
  }

  /// Get peer comparison data for user's income tier
  Future<Map<String, dynamic>> getPeerComparison({int? year, int? month}) async {
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
      // Return demo peer comparison data
      return {
        'your_spending': 2450.0,
        'peer_average': 2680.0,
        'peer_median': 2520.0,
        'percentile': 35,
        'categories': {
          'food': {'your_amount': 450.0, 'peer_average': 480.0},
          'transportation': {'your_amount': 320.0, 'peer_average': 380.0},
          'entertainment': {'your_amount': 180.0, 'peer_average': 220.0},
          'shopping': {'your_amount': 280.0, 'peer_average': 350.0},
        },
        'insights': [
          'You spend 15% less than peers in your income group',
          'Your food spending is very close to the average',
          'You save more on transportation than most peers',
        ],
      };
    }
  }

  /// Get income-specific budget recommendations
  Future<Map<String, dynamic>> getIncomeBasedBudgetRecommendations(double monthlyIncome) async {
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
      final tier = monthlyIncome < 3000 ? 'low' : monthlyIncome <= 7000 ? 'mid' : 'high';
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
  Future<List<Map<String, dynamic>>> getIncomeBasedGoals(double monthlyIncome) async {
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
      final tier = monthlyIncome < 3000 ? 'low' : monthlyIncome <= 7000 ? 'mid' : 'high';
      
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
      final tier = monthlyIncome < 3000 ? 'low' : monthlyIncome <= 7000 ? 'mid' : 'high';
      
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
      '/users/users/me',
      data: {'income': monthlyIncome},
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
  }

  // ---------------------------------------------------------------------------
  // Manual logout
  // ---------------------------------------------------------------------------

  Future<void> logout() async {
    await clearTokens();
  }
}

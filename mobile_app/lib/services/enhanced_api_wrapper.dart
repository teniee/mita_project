/*
Enhanced API Service Wrapper for MITA Flutter App
Provides robust error handling, retry mechanisms, and circuit breaker patterns
for all API operations with comprehensive error reporting and recovery
*/

import 'dart:async';
import 'dart:developer' as developer;
import 'package:dio/dio.dart';
import '../core/enhanced_error_handling.dart';
import '../core/app_error_handler.dart';
import '../core/error_handling.dart';
import 'api_service.dart';
import 'logging_service.dart';

/// Enhanced API service wrapper with comprehensive error handling
class EnhancedApiWrapper {
  static EnhancedApiWrapper? _instance;
  static EnhancedApiWrapper get instance => _instance ??= EnhancedApiWrapper._();
  
  EnhancedApiWrapper._();

  final ApiService _apiService = ApiService();
  final Map<String, DateTime> _circuitBreakerRegistry = {};
  final Map<String, int> _failureCountRegistry = {};
  
  // Circuit breaker configuration
  static const Duration _circuitBreakerTimeout = Duration(minutes: 5);
  static const int _maxFailuresBeforeCircuitBreaker = 3;
  static const Duration _defaultApiTimeout = Duration(seconds: 30);
  
  /// Execute API operation with comprehensive error handling and circuit breaker
  Future<T?> executeApiCall<T>(
    Future<T> Function() operation, {
    required String operationName,
    int maxRetries = 2,
    Duration timeout = _defaultApiTimeout,
    T? fallbackValue,
    bool enableCircuitBreaker = true,
    ErrorCategory category = ErrorCategory.network,
  }) async {
    // Check circuit breaker
    if (enableCircuitBreaker && _isCircuitOpen(operationName)) {
      logWarning('Circuit breaker open for $operationName', tag: 'ENHANCED_API');
      
      AppErrorHandler.reportError(
        'Circuit breaker triggered for $operationName',
        severity: ErrorSeverity.medium,
        category: category,
        context: {
          'operation': operationName,
          'circuit_breaker_status': 'open',
          'failure_count': _failureCountRegistry[operationName] ?? 0,
        },
      );
      
      return fallbackValue;
    }
    
    return await EnhancedErrorHandling.executeWithRetry<T>(
      () async {
        try {
          final result = await operation().timeout(timeout);
          
          // Reset circuit breaker on success
          if (enableCircuitBreaker) {
            _resetCircuitBreaker(operationName);
          }
          
          logDebug('API operation successful: $operationName', tag: 'ENHANCED_API');
          return result;
        } catch (error) {
          // Update circuit breaker on failure
          if (enableCircuitBreaker) {
            _recordFailure(operationName);
          }
          
          // Enhanced error reporting with context
          _reportApiError(error, operationName, category);
          rethrow;
        }
      },
      operationName: operationName,
      maxRetries: maxRetries,
      exponentialBackoff: true,
      retryableExceptions: [
        DioException,
        TimeoutException,
        NetworkException,
      ],
      category: category,
      fallbackValue: fallbackValue,
    );
  }
  
  /// Authentication operations with specialized error handling
  Future<Response?> authenticateUser({
    required String email,
    required String password,
    bool isLogin = true,
  }) async {
    return await executeApiCall<Response>(
      () async {
        if (isLogin) {
          return await _apiService.reliableLogin(email, password);
        } else {
          return await _apiService.reliableRegister(email, password);
        }
      },
      operationName: isLogin ? 'User Login' : 'User Registration',
      maxRetries: 1, // Limited retries for auth operations
      timeout: const Duration(seconds: 20),
      category: ErrorCategory.authentication,
    );
  }
  
  /// Google authentication with enhanced error handling
  Future<Response?> authenticateWithGoogle(String idToken) async {
    return await executeApiCall<Response>(
      () async => await _apiService.loginWithGoogle(idToken),
      operationName: 'Google Authentication',
      maxRetries: 2,
      timeout: const Duration(seconds: 25),
      category: ErrorCategory.authentication,
    );
  }
  
  /// Budget operations with financial data protection
  Future<List<dynamic>?> getDailyBudgets() async {
    return await executeApiCall<List<dynamic>>(
      () async => await _apiService.getDailyBudgets(),
      operationName: 'Get Daily Budgets',
      maxRetries: 2,
      fallbackValue: [],
      category: ErrorCategory.network,
    );
  }
  
  /// Calendar operations with enhanced reliability
  Future<List<dynamic>?> getCalendarData() async {
    return await executeApiCall<List<dynamic>>(
      () async => await _apiService.getCalendar(),
      operationName: 'Get Calendar Data',
      maxRetries: 3,
      fallbackValue: [],
      category: ErrorCategory.network,
    );
  }
  
  /// Transaction operations with data integrity protection
  Future<void> addTransaction({
    required Map<String, dynamic> transactionData,
  }) async {
    await executeApiCall<void>(
      () async => await _apiService.createExpense(transactionData),
      operationName: 'Add Transaction',
      maxRetries: 1, // Limited retries for financial operations
      timeout: const Duration(seconds: 15),
      category: ErrorCategory.network,
    );
  }
  
  /// Budget redistribution with careful error handling
  Future<Map<String, dynamic>?> redistributeBudget(Map<String, dynamic> calendarData) async {
    return await executeApiCall<Map<String, dynamic>>(
      () async => await _apiService.redistributeCalendarBudget(calendarData),
      operationName: 'Budget Redistribution',
      maxRetries: 1, // No retries for critical financial operations
      timeout: const Duration(seconds: 45),
      enableCircuitBreaker: false, // Always allow budget operations
      category: ErrorCategory.system,
    );
  }
  
  /// Profile and settings operations
  Future<Map<String, dynamic>?> getUserProfile() async {
    return await executeApiCall<Map<String, dynamic>>(
      () async => await _apiService.getUserProfile(),
      operationName: 'Get User Profile',
      maxRetries: 2,
      fallbackValue: {},
      category: ErrorCategory.network,
    );
  }
  
  /// Dashboard data with fallback handling
  Future<Map<String, dynamic>?> getDashboardData() async {
    return await executeApiCall<Map<String, dynamic>>(
      () async => await _apiService.getDashboard(),
      operationName: 'Get Dashboard Data',
      maxRetries: 3,
      fallbackValue: {},
      category: ErrorCategory.network,
    );
  }
  
  /// Transaction history with pagination support
  Future<List<dynamic>?> getTransactionsByDate(String date) async {
    return await executeApiCall<List<dynamic>>(
      () async => await _apiService.getTransactionsByDate(date),
      operationName: 'Get Transactions by Date',
      maxRetries: 2,
      fallbackValue: [],
      category: ErrorCategory.network,
    );
  }
  
  /// Live budget status with high availability
  Future<Map<String, dynamic>?> getLiveBudgetStatus() async {
    return await executeApiCall<Map<String, dynamic>>(
      () async => await _apiService.getLiveBudgetStatus(),
      operationName: 'Get Live Budget Status',
      maxRetries: 2,
      timeout: const Duration(seconds: 10),
      fallbackValue: {},
      category: ErrorCategory.network,
    );
  }
  
  /// Budget suggestions with enhanced fallback
  Future<Map<String, dynamic>?> getBudgetSuggestions() async {
    return await executeApiCall<Map<String, dynamic>>(
      () async => await _apiService.getBudgetSuggestions(),
      operationName: 'Get Budget Suggestions',
      maxRetries: 2,
      fallbackValue: {'suggestions': [], 'total_count': 0},
      category: ErrorCategory.network,
    );
  }
  
  /// Onboarding completion check
  Future<bool?> hasCompletedOnboarding() async {
    final result = await executeApiCall<bool>(
      () async => await _apiService.hasCompletedOnboarding(),
      operationName: 'Check Onboarding Status',
      maxRetries: 2,
      fallbackValue: false,
      category: ErrorCategory.network,
    );
    return result;
  }
  
  /// Token management operations
  Future<bool> saveAuthTokens(String accessToken, String? refreshToken) async {
    try {
      await _apiService.saveTokens(accessToken, refreshToken ?? '');
      return true;
    } catch (error) {
      AppErrorHandler.reportStorageError(
        error,
        operation: 'Save Auth Tokens',
        context: {'has_refresh_token': refreshToken != null},
      );
      return false;
    }
  }
  
  /// Circuit breaker implementation
  bool _isCircuitOpen(String operationName) {
    final failures = _failureCountRegistry[operationName] ?? 0;
    if (failures < _maxFailuresBeforeCircuitBreaker) return false;
    
    final breakerTime = _circuitBreakerRegistry[operationName];
    if (breakerTime == null) return false;
    
    final now = DateTime.now();
    if (now.difference(breakerTime) > _circuitBreakerTimeout) {
      // Reset circuit breaker after timeout
      _resetCircuitBreaker(operationName);
      return false;
    }
    
    return true;
  }
  
  void _recordFailure(String operationName) {
    final currentFailures = _failureCountRegistry[operationName] ?? 0;
    _failureCountRegistry[operationName] = currentFailures + 1;
    
    if (currentFailures + 1 >= _maxFailuresBeforeCircuitBreaker) {
      _circuitBreakerRegistry[operationName] = DateTime.now();
      logWarning('Circuit breaker activated for $operationName', tag: 'CIRCUIT_BREAKER');
    }
  }
  
  void _resetCircuitBreaker(String operationName) {
    _failureCountRegistry.remove(operationName);
    _circuitBreakerRegistry.remove(operationName);
  }
  
  /// Enhanced error reporting with API-specific context
  void _reportApiError(dynamic error, String operationName, ErrorCategory category) {
    Map<String, dynamic> context = {
      'operation': operationName,
      'timestamp': DateTime.now().toIso8601String(),
    };
    
    ErrorSeverity severity = ErrorSeverity.medium;
    
    if (error is DioException) {
      context.addAll({
        'dio_error_type': error.type.toString(),
        'status_code': error.response?.statusCode,
        'response_data': error.response?.data?.toString(),
        'request_path': error.requestOptions.path,
        'request_method': error.requestOptions.method,
      });
      
      // Determine severity based on error type and status code
      if (error.response?.statusCode == null) {
        severity = ErrorSeverity.high; // Network connectivity issues
      } else if (error.response!.statusCode! >= 500) {
        severity = ErrorSeverity.high; // Server errors
      } else if (error.response!.statusCode! == 401 || error.response!.statusCode! == 403) {
        severity = ErrorSeverity.high; // Auth issues
      }
    } else if (error is TimeoutException) {
      context['timeout_type'] = 'operation_timeout';
      severity = ErrorSeverity.medium;
    }
    
    AppErrorHandler.reportError(
      error,
      severity: severity,
      category: category,
      context: context,
    );
  }
  
  /// Get circuit breaker statistics
  Map<String, dynamic> getCircuitBreakerStats() {
    return {
      'active_breakers': _circuitBreakerRegistry.keys.toList(),
      'failure_counts': Map.from(_failureCountRegistry),
      'breaker_timeout_minutes': _circuitBreakerTimeout.inMinutes,
      'max_failures_threshold': _maxFailuresBeforeCircuitBreaker,
    };
  }
  
  /// Reset all circuit breakers (for testing or administrative purposes)
  void resetAllCircuitBreakers() {
    _circuitBreakerRegistry.clear();
    _failureCountRegistry.clear();
    logInfo('All circuit breakers reset', tag: 'ENHANCED_API');
  }
  
  /// Check API health with comprehensive diagnostics
  Future<Map<String, dynamic>> performHealthCheck() async {
    final healthResults = <String, dynamic>{};
    final startTime = DateTime.now();
    
    // Test basic connectivity
    try {
      await executeApiCall<Map<String, dynamic>>(
        () async => await _apiService.getDashboard(),
        operationName: 'Health Check - Dashboard',
        maxRetries: 1,
        timeout: const Duration(seconds: 10),
        enableCircuitBreaker: false,
      );
      healthResults['dashboard_api'] = {'status': 'healthy', 'response_time_ms': DateTime.now().difference(startTime).inMilliseconds};
    } catch (e) {
      healthResults['dashboard_api'] = {'status': 'unhealthy', 'error': e.toString()};
    }
    
    // Add circuit breaker status
    healthResults['circuit_breakers'] = getCircuitBreakerStats();
    
    // Add overall health score
    final healthyApis = healthResults.values.where((v) => v is Map && v['status'] == 'healthy').length;
    final totalApis = healthResults.length - 1; // Excluding circuit_breakers entry
    healthResults['overall_health_score'] = totalApis > 0 ? (healthyApis / totalApis) : 0.0;
    
    return healthResults;
  }
}

/// Convenience extensions for common API operations
extension ApiConvenience on EnhancedApiWrapper {
  /// Quick dashboard refresh with error handling
  Future<Map<String, dynamic>?> refreshDashboard() async {
    return await getDashboardData();
  }
  
  /// Quick budget refresh with error handling
  Future<List<dynamic>?> refreshBudgets() async {
    return await getDailyBudgets();
  }
  
  /// Quick calendar refresh with error handling
  Future<List<dynamic>?> refreshCalendar() async {
    return await getCalendarData();
  }
  
  /// Comprehensive data refresh for main screen
  Future<Map<String, dynamic>> refreshAllMainScreenData() async {
    final results = <String, dynamic>{};
    
    // Execute all operations concurrently with individual error handling
    final futures = [
      getDashboardData().then((data) => results['dashboard'] = data),
      getDailyBudgets().then((data) => results['budgets'] = data),
      getCalendarData().then((data) => results['calendar'] = data),
      getLiveBudgetStatus().then((data) => results['live_status'] = data),
    ];
    
    // Wait for all operations to complete (some may fail gracefully)
    await Future.wait(futures, eagerError: false);
    
    results['refresh_timestamp'] = DateTime.now().toIso8601String();
    results['success_count'] = results.values.where((v) => v != null && v != false).length - 1; // Excluding timestamp
    
    return results;
  }
}

/// Global instance for easy access throughout the app
final enhancedApi = EnhancedApiWrapper.instance;
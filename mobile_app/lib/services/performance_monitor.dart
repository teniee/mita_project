import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'dart:developer' as dev;
import 'package:sentry_flutter/sentry_flutter.dart';
import 'sentry_service.dart';

/// Performance monitoring categories for mobile app
enum MobilePerformanceCategory {
  screenRender('screen_render'),
  apiRequest('api_request'),
  databaseOperation('database_operation'),
  fileOperation('file_operation'),
  imageProcessing('image_processing'),
  financialCalculation('financial_calculation'),
  authentication('authentication'),
  navigation('navigation'),
  userInteraction('user_interaction');

  const MobilePerformanceCategory(this.value);
  final String value;
}

/// Performance thresholds for mobile operations
class MobilePerformanceThresholds {
  // Screen rendering thresholds (milliseconds)
  static const Map<String, int> screenThresholds = {
    'WelcomeScreen': 1000,
    'LoginScreen': 800,
    'RegisterScreen': 1000,
    'MainScreen': 1500,
    'DailyBudgetScreen': 1200,
    'TransactionsScreen': 1000,
    'AddExpenseScreen': 800,
    'ProfileScreen': 600,
    'SettingsScreen': 500,
  };

  // API request thresholds
  static const Map<String, int> apiThresholds = {
    'login': 2000,
    'register': 3000,
    'fetchTransactions': 1500,
    'addExpense': 1000,
    'updateProfile': 1200,
    'fetchBudget': 800,
  };

  // Financial operation thresholds
  static const Map<String, int> financialThresholds = {
    'budgetCalculation': 2000,
    'expenseCalculation': 500,
    'transactionProcessing': 1500,
    'financialAnalysis': 3000,
    'ocrProcessing': 5000,
  };

  static int getScreenThreshold(String screenName) {
    return screenThresholds[screenName] ?? 1000;
  }

  static int getApiThreshold(String operation) {
    return apiThresholds[operation] ?? 1500;
  }

  static int getFinancialThreshold(String operation) {
    return financialThresholds[operation] ?? 2000;
  }
}

/// Performance metric data
class PerformanceMetric {
  final String operationName;
  final MobilePerformanceCategory category;
  final int durationMs;
  final DateTime timestamp;
  final bool success;
  final String? userId;
  final String? screenName;
  final Map<String, dynamic>? additionalContext;

  PerformanceMetric({
    required this.operationName,
    required this.category,
    required this.durationMs,
    required this.timestamp,
    required this.success,
    this.userId,
    this.screenName,
    this.additionalContext,
  });

  Map<String, dynamic> toJson() => {
    'operation_name': operationName,
    'category': category.value,
    'duration_ms': durationMs,
    'timestamp': timestamp.toIso8601String(),
    'success': success,
    'user_id': userId,
    'screen_name': screenName,
    'additional_context': additionalContext,
    'platform': Platform.operatingSystem,
  };
}

/// Comprehensive performance monitoring service for mobile
class MobilePerformanceMonitor {
  static final MobilePerformanceMonitor _instance = MobilePerformanceMonitor._internal();
  factory MobilePerformanceMonitor() => _instance;
  MobilePerformanceMonitor._internal();

  final List<PerformanceMetric> _metrics = [];
  final Map<String, DateTime> _alertCooldown = {};
  static const int _maxMetrics = 5000;
  static const int _alertCooldownMinutes = 10;

  String? _currentUserId;
  String? _currentScreen;

  /// Set current user context
  void setUser(String? userId) {
    _currentUserId = userId;
  }

  /// Set current screen context
  void setCurrentScreen(String? screenName) {
    _currentScreen = screenName;
  }

  /// Monitor screen rendering performance
  Future<T> monitorScreenRender<T>({
    required String screenName,
    required Future<T> Function() operation,
    String? userId,
    Map<String, dynamic>? additionalContext,
  }) async {
    final stopwatch = Stopwatch()..start();
    ISentrySpan? transaction;

    try {
      // Start Sentry transaction
      transaction = sentryService.startTransaction(
        name: 'Screen: $screenName',
        operation: 'screen.render',
        description: 'Rendering $screenName',
        data: {
          'screen_name': screenName,
          'user_id': userId ?? _currentUserId,
          'platform': Platform.operatingSystem,
        },
      );

      // Add breadcrumb
      sentryService.addFinancialBreadcrumb(
        message: 'Starting to render $screenName',
        category: 'screen_render',
        data: {
          'screen_name': screenName,
          'user_id': userId ?? _currentUserId,
        },
      );

      final result = await operation();

      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record metric
      await _recordMetric(PerformanceMetric(
        operationName: 'Screen: $screenName',
        category: MobilePerformanceCategory.screenRender,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: true,
        userId: userId ?? _currentUserId,
        screenName: screenName,
        additionalContext: additionalContext,
      ));

      // Check threshold
      final threshold = MobilePerformanceThresholds.getScreenThreshold(screenName);
      if (durationMs > threshold) {
        await _handlePerformanceAlert(
          operationName: 'Screen: $screenName',
          durationMs: durationMs,
          threshold: threshold,
          category: MobilePerformanceCategory.screenRender,
          userId: userId ?? _currentUserId,
          additionalContext: {
            'screen_name': screenName,
            'render_performance': true,
            ...?additionalContext,
          },
        );
      }

      transaction?.finish();
      return result;

    } catch (error, stackTrace) {
      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record failed metric
      await _recordMetric(PerformanceMetric(
        operationName: 'Screen: $screenName',
        category: MobilePerformanceCategory.screenRender,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: false,
        userId: userId ?? _currentUserId,
        screenName: screenName,
        additionalContext: {
          'error': error.toString(),
          ...?additionalContext,
        },
      ));

      // Capture error in Sentry
      await sentryService.captureFinancialError(
        error,
        category: FinancialErrorCategory.uiError,
        severity: FinancialSeverity.high,
        stackTrace: stackTrace.toString(),
        userId: userId ?? _currentUserId,
        screenName: screenName,
        additionalContext: {
          'operation': 'screen_render',
          'screen_name': screenName,
          'duration_ms': durationMs,
          ...?additionalContext,
        },
      );

      transaction?.finish();
      rethrow;
    }
  }

  /// Monitor API request performance
  Future<T> monitorApiRequest<T>({
    required String operation,
    required Future<T> Function() request,
    String? userId,
    String? endpoint,
    Map<String, dynamic>? additionalContext,
  }) async {
    final stopwatch = Stopwatch()..start();
    ISentrySpan? transaction;

    try {
      // Start Sentry transaction
      transaction = sentryService.startTransaction(
        name: 'API: $operation',
        operation: 'http.request',
        description: 'Mobile API request: $operation',
        data: {
          'api_operation': operation,
          'endpoint': endpoint,
          'user_id': userId ?? _currentUserId,
          'screen': _currentScreen,
          'platform': Platform.operatingSystem,
        },
      );

      final result = await request();

      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record successful metric
      await _recordMetric(PerformanceMetric(
        operationName: 'API: $operation',
        category: MobilePerformanceCategory.apiRequest,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: true,
        userId: userId ?? _currentUserId,
        screenName: _currentScreen,
        additionalContext: {
          'endpoint': endpoint,
          'api_operation': operation,
          ...?additionalContext,
        },
      ));

      // Check threshold
      final threshold = MobilePerformanceThresholds.getApiThreshold(operation);
      if (durationMs > threshold) {
        await _handlePerformanceAlert(
          operationName: 'API: $operation',
          durationMs: durationMs,
          threshold: threshold,
          category: MobilePerformanceCategory.apiRequest,
          userId: userId ?? _currentUserId,
          additionalContext: {
            'endpoint': endpoint,
            'api_operation': operation,
            'screen': _currentScreen,
            'network_performance': true,
            ...?additionalContext,
          },
        );
      }

      transaction?.finish();
      return result;

    } catch (error, stackTrace) {
      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record failed metric
      await _recordMetric(PerformanceMetric(
        operationName: 'API: $operation',
        category: MobilePerformanceCategory.apiRequest,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: false,
        userId: userId ?? _currentUserId,
        screenName: _currentScreen,
        additionalContext: {
          'error': error.toString(),
          'endpoint': endpoint,
          'api_operation': operation,
          ...?additionalContext,
        },
      ));

      // Capture network error in Sentry
      await sentryService.captureNetworkError(
        error,
        endpoint: endpoint,
        method: 'POST', // Default, could be parameterized
        screenName: _currentScreen,
        stackTrace: stackTrace.toString(),
      );

      transaction?.finish();
      rethrow;
    }
  }

  /// Monitor financial operation performance
  Future<T> monitorFinancialOperation<T>({
    required String operation,
    required Future<T> Function() calculation,
    String? userId,
    String? transactionId,
    double? amount,
    String? currency,
    Map<String, dynamic>? additionalContext,
  }) async {
    final stopwatch = Stopwatch()..start();
    ISentrySpan? transaction;

    try {
      // Start Sentry transaction for financial operations
      transaction = sentryService.startTransaction(
        name: 'Financial: $operation',
        operation: 'financial.calculation',
        description: 'Financial operation: $operation',
        data: {
          'financial_operation': operation,
          'user_id': userId ?? _currentUserId,
          'transaction_id': transactionId,
          'amount': amount,
          'currency': currency,
          'screen': _currentScreen,
          'compliance_monitored': true,
        },
      );

      // Add financial breadcrumb
      sentryService.addFinancialBreadcrumb(
        message: 'Starting financial operation: $operation',
        category: 'financial',
        data: {
          'operation': operation,
          'user_id': userId ?? _currentUserId,
          'transaction_id': transactionId,
          'amount': amount,
          'currency': currency,
        },
      );

      final result = await calculation();

      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record successful metric
      await _recordMetric(PerformanceMetric(
        operationName: 'Financial: $operation',
        category: MobilePerformanceCategory.financialCalculation,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: true,
        userId: userId ?? _currentUserId,
        screenName: _currentScreen,
        additionalContext: {
          'financial_operation': operation,
          'transaction_id': transactionId,
          'amount': amount,
          'currency': currency,
          'compliance_monitored': true,
          ...?additionalContext,
        },
      ));

      // Check threshold
      final threshold = MobilePerformanceThresholds.getFinancialThreshold(operation);
      if (durationMs > threshold) {
        await _handlePerformanceAlert(
          operationName: 'Financial: $operation',
          durationMs: durationMs,
          threshold: threshold,
          category: MobilePerformanceCategory.financialCalculation,
          userId: userId ?? _currentUserId,
          additionalContext: {
            'financial_operation': operation,
            'transaction_id': transactionId,
            'amount': amount,
            'currency': currency,
            'financial_impact': 'HIGH',
            'screen': _currentScreen,
            'compliance_critical': true,
            ...?additionalContext,
          },
        );
      }

      transaction?.finish();
      return result;

    } catch (error, stackTrace) {
      stopwatch.stop();
      final durationMs = stopwatch.elapsedMilliseconds;

      // Record failed metric
      await _recordMetric(PerformanceMetric(
        operationName: 'Financial: $operation',
        category: MobilePerformanceCategory.financialCalculation,
        durationMs: durationMs,
        timestamp: DateTime.now(),
        success: false,
        userId: userId ?? _currentUserId,
        screenName: _currentScreen,
        additionalContext: {
          'error': error.toString(),
          'financial_operation': operation,
          'transaction_id': transactionId,
          'amount': amount,
          'currency': currency,
          ...?additionalContext,
        },
      ));

      // Capture financial error
      await sentryService.captureFinancialError(
        error,
        category: FinancialErrorCategory.financialAnalysis,
        severity: FinancialSeverity.high,
        stackTrace: stackTrace.toString(),
        userId: userId ?? _currentUserId,
        transactionId: transactionId,
        amount: amount,
        currency: currency,
        screenName: _currentScreen,
        additionalContext: {
          'financial_operation': operation,
          'duration_ms': durationMs,
          'performance_related': true,
          ...?additionalContext,
        },
      );

      transaction?.finish();
      rethrow;
    }
  }

  /// Monitor user interaction performance
  Future<void> monitorUserInteraction({
    required String interaction,
    required int durationMs,
    String? screenName,
    String? userId,
    Map<String, dynamic>? additionalContext,
  }) async {
    // Record interaction metric
    await _recordMetric(PerformanceMetric(
      operationName: 'Interaction: $interaction',
      category: MobilePerformanceCategory.userInteraction,
      durationMs: durationMs,
      timestamp: DateTime.now(),
      success: true,
      userId: userId ?? _currentUserId,
      screenName: screenName ?? _currentScreen,
      additionalContext: {
        'interaction': interaction,
        'user_triggered': true,
        ...?additionalContext,
      },
    ));

    // Add breadcrumb for user interaction
    sentryService.addFinancialBreadcrumb(
      message: 'User interaction: $interaction',
      category: 'user_interaction',
      data: {
        'interaction': interaction,
        'duration_ms': durationMs,
        'screen': screenName ?? _currentScreen,
        'user_id': userId ?? _currentUserId,
      },
    );

    // Log slow interactions
    if (durationMs > 1000) {
      if (kDebugMode) {
        if (kDebugMode) dev.log('Slow user interaction: $interaction took ${durationMs}ms', name: 'PerformanceMonitor');
      }
    }
  }

  /// Record performance metric
  Future<void> _recordMetric(PerformanceMetric metric) async {
    _metrics.add(metric);

    // Trim metrics list if too large
    if (_metrics.length > _maxMetrics) {
      _metrics.removeRange(0, _metrics.length - _maxMetrics);
    }

    // Log performance issues in debug mode
    if (kDebugMode) {
      if (metric.category == MobilePerformanceCategory.screenRender && 
          metric.durationMs > 1000) {
        if (kDebugMode) dev.log('Slow screen render: ${metric.operationName} took ${metric.durationMs}ms', name: 'PerformanceMonitor');
      } else if (metric.category == MobilePerformanceCategory.apiRequest && 
                 metric.durationMs > 2000) {
        if (kDebugMode) dev.log('Slow API request: ${metric.operationName} took ${metric.durationMs}ms', name: 'PerformanceMonitor');
      } else if (metric.category == MobilePerformanceCategory.financialCalculation && 
                 metric.durationMs > 1500) {
        if (kDebugMode) dev.log('Slow financial operation: ${metric.operationName} took ${metric.durationMs}ms', name: 'PerformanceMonitor');
      }
    }
  }

  /// Handle performance alert
  Future<void> _handlePerformanceAlert({
    required String operationName,
    required int durationMs,
    required int threshold,
    required MobilePerformanceCategory category,
    String? userId,
    Map<String, dynamic>? additionalContext,
  }) async {
    // Check alert cooldown
    final alertKey = '${category.value}:$operationName';
    final now = DateTime.now();

    if (_alertCooldown.containsKey(alertKey)) {
      final lastAlert = _alertCooldown[alertKey]!;
      if (now.difference(lastAlert).inMinutes < _alertCooldownMinutes) {
        return; // Still in cooldown
      }
    }

    _alertCooldown[alertKey] = now;

    // Capture performance issue in Sentry
    try {
      await Sentry.captureMessage(
        'Mobile performance threshold exceeded: $operationName took ${durationMs}ms (threshold: ${threshold}ms)',
        level: SentryLevel.warning,
        withScope: (scope) {
          scope.setTag('performance_issue', 'true');
          scope.setTag('mobile_performance', 'true');
          scope.setTag('category', category.value);
          scope.setTag('operation', operationName);
          scope.setTag('exceeded_threshold', 'true');

          if (userId != null) {
            scope.setUser(SentryUser(id: userId));
          }

          scope.setContexts('performance', {
            'operation': operationName,
            'duration_ms': durationMs,
            'threshold_ms': threshold,
            'slowdown_factor': durationMs / threshold,
            'category': category.value,
            'platform': Platform.operatingSystem,
            'timestamp': now.toIso8601String(),
          });

          if (additionalContext != null) {
            for (final entry in additionalContext.entries) {
              scope.setExtra(entry.key, entry.value);
            }
          }
        },
      );

      if (kDebugMode) {
        if (kDebugMode) dev.log(
          'Performance alert: $operationName took ${durationMs}ms '
          '(threshold: ${threshold}ms)',
        );
      }

    } catch (e) {
      if (kDebugMode) {
        if (kDebugMode) dev.log('Failed to send performance alert to Sentry: $e');
      }
    }
  }

  /// Get performance summary
  Map<String, dynamic> getPerformanceSummary({
    int lastHours = 1,
    MobilePerformanceCategory? category,
  }) {
    final cutoffTime = DateTime.now().subtract(Duration(hours: lastHours));

    // Filter metrics
    final filteredMetrics = _metrics.where((metric) {
      return metric.timestamp.isAfter(cutoffTime) &&
          (category == null || metric.category == category);
    }).toList();

    if (filteredMetrics.isEmpty) {
      return {
        'total_operations': 0,
        'avg_duration_ms': 0,
        'max_duration_ms': 0,
        'min_duration_ms': 0,
        'success_rate': 100.0,
        'threshold_breaches': 0,
      };
    }

    // Calculate statistics
    final durations = filteredMetrics.map((m) => m.durationMs).toList();
    final successfulOps = filteredMetrics.where((m) => m.success).length;

    return {
      'total_operations': filteredMetrics.length,
      'avg_duration_ms': durations.reduce((a, b) => a + b) / durations.length,
      'max_duration_ms': durations.reduce((a, b) => a > b ? a : b),
      'min_duration_ms': durations.reduce((a, b) => a < b ? a : b),
      'success_rate': (successfulOps / filteredMetrics.length) * 100,
      'operations_by_category': _groupByCategory(filteredMetrics),
      'slowest_operations': _getSlowestOperations(filteredMetrics, limit: 10),
      'platform': Platform.operatingSystem,
      'last_hours': lastHours,
    };
  }

  Map<String, int> _groupByCategory(List<PerformanceMetric> metrics) {
    final categories = <String, int>{};
    for (final metric in metrics) {
      final category = metric.category.value;
      categories[category] = (categories[category] ?? 0) + 1;
    }
    return categories;
  }

  List<Map<String, dynamic>> _getSlowestOperations(
    List<PerformanceMetric> metrics, {
    int limit = 10,
  }) {
    final sortedMetrics = List<PerformanceMetric>.from(metrics)
      ..sort((a, b) => b.durationMs.compareTo(a.durationMs));

    return sortedMetrics.take(limit).map((metric) => {
      'operation_name': metric.operationName,
      'duration_ms': metric.durationMs,
      'category': metric.category.value,
      'timestamp': metric.timestamp.toIso8601String(),
      'success': metric.success,
      'screen_name': metric.screenName,
      'user_id': metric.userId,
    }).toList();
  }
}

/// Global instance
final performanceMonitor = MobilePerformanceMonitor();
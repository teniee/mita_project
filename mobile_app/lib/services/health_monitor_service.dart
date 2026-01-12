import 'dart:async';

import 'package:flutter/material.dart';

import 'logging_service.dart';
import 'api_service.dart';

/// Health status levels matching backend enum
enum HealthStatus {
  healthy,
  degraded,
  critical,
  unhealthy;

  String get displayName {
    switch (this) {
      case HealthStatus.healthy:
        return 'Healthy';
      case HealthStatus.degraded:
        return 'Degraded';
      case HealthStatus.critical:
        return 'Critical';
      case HealthStatus.unhealthy:
        return 'Unhealthy';
    }
  }

  Color get color {
    switch (this) {
      case HealthStatus.healthy:
        return Colors.green;
      case HealthStatus.degraded:
        return Colors.orange;
      case HealthStatus.critical:
        return Colors.red;
      case HealthStatus.unhealthy:
        return Colors.red.shade800;
    }
  }

  IconData get icon {
    switch (this) {
      case HealthStatus.healthy:
        return Icons.check_circle;
      case HealthStatus.degraded:
        return Icons.warning;
      case HealthStatus.critical:
        return Icons.error;
      case HealthStatus.unhealthy:
        return Icons.dangerous;
    }
  }
}

/// Individual component health metric
class HealthMetric {
  final String name;
  final HealthStatus status;
  final String message;
  final double? responseTimeMs;
  final double? value;
  final double? thresholdWarning;
  final double? thresholdCritical;
  final DateTime timestamp;
  final Map<String, dynamic>? details;

  HealthMetric({
    required this.name,
    required this.status,
    required this.message,
    this.responseTimeMs,
    this.value,
    this.thresholdWarning,
    this.thresholdCritical,
    required this.timestamp,
    this.details,
  });

  factory HealthMetric.fromJson(Map<String, dynamic> json) {
    return HealthMetric(
      name: (json['name'] ?? '') as String,
      status: HealthStatus.values.firstWhere(
        (e) => e.name == json['status'],
        orElse: () => HealthStatus.unhealthy,
      ),
      message: (json['message'] ?? '') as String,
      responseTimeMs: (json['response_time_ms'] as num?)?.toDouble(),
      value: (json['value'] as num?)?.toDouble(),
      thresholdWarning: (json['threshold_warning'] as num?)?.toDouble(),
      thresholdCritical: (json['threshold_critical'] as num?)?.toDouble(),
      timestamp: DateTime.tryParse((json['timestamp'] ?? '') as String) ??
          DateTime.now(),
      details: json['details'] as Map<String, dynamic>?,
    );
  }

  String get displayName {
    return name
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) =>
            word.isEmpty ? word : word[0].toUpperCase() + word.substring(1))
        .join(' ');
  }

  bool get isHealthy => status == HealthStatus.healthy;
  bool get needsAttention =>
      status == HealthStatus.critical || status == HealthStatus.unhealthy;
}

/// Comprehensive health report from backend
class HealthReport {
  final HealthStatus overallStatus;
  final DateTime timestamp;
  final Map<String, HealthMetric> middlewareMetrics;
  final Map<String, dynamic> performanceSummary;
  final List<String> alerts;
  final List<String> issuesDetected;
  final List<String> recommendations;
  final double responseTimeMs;
  final String message;

  HealthReport({
    required this.overallStatus,
    required this.timestamp,
    required this.middlewareMetrics,
    required this.performanceSummary,
    required this.alerts,
    required this.issuesDetected,
    required this.recommendations,
    required this.responseTimeMs,
    required this.message,
  });

  factory HealthReport.fromJson(Map<String, dynamic> json) {
    final middlewareData = json['middleware'] ?? <String, dynamic>{};
    final metricsData = middlewareData['metrics'] ?? <String, dynamic>{};

    final Map<String, HealthMetric> metrics = <String, HealthMetric>{};
    (metricsData as Map<String, dynamic>).forEach((String key, dynamic value) {
      if (value is Map<String, dynamic>) {
        metrics[key] = HealthMetric.fromJson({
          'name': key,
          ...value,
          'timestamp': json['timestamp'],
        });
      }
    });

    return HealthReport(
      overallStatus: HealthStatus.values.firstWhere(
        (e) => e.name == json['status'],
        orElse: () => HealthStatus.unhealthy,
      ),
      timestamp: DateTime.tryParse((json['timestamp'] ?? '') as String) ??
          DateTime.now(),
      middlewareMetrics: metrics,
      performanceSummary:
          (middlewareData['performance_summary'] ?? <String, dynamic>{}) as Map<String, dynamic>,
      alerts: List<String>.from((json['alerts'] ?? <dynamic>[]) as List),
      issuesDetected:
          List<String>.from((json['issues_detected'] ?? <dynamic>[]) as List),
      recommendations:
          List<String>.from((json['recommendations'] ?? <dynamic>[]) as List),
      responseTimeMs:
          (middlewareData['response_time_ms'] as num?)?.toDouble() ?? 0.0,
      message: (json['message'] ?? '') as String,
    );
  }

  bool get hasTimeoutRisk {
    return middlewareMetrics.values.any((metric) =>
            metric.responseTimeMs != null && metric.responseTimeMs! > 5000) ||
        responseTimeMs > 10000;
  }

  bool get hasCriticalIssues {
    return overallStatus == HealthStatus.critical ||
        overallStatus == HealthStatus.unhealthy ||
        alerts.any((alert) => alert.toUpperCase().contains('CRITICAL'));
  }

  int get healthyComponentsCount {
    return middlewareMetrics.values.where((m) => m.isHealthy).length;
  }

  int get totalComponentsCount {
    return middlewareMetrics.length;
  }

  double get healthPercentage {
    if (totalComponentsCount == 0) return 0.0;
    return (healthyComponentsCount / totalComponentsCount) * 100.0;
  }
}

/// Health monitoring service for mobile app
class HealthMonitorService {
  static final HealthMonitorService _instance =
      HealthMonitorService._internal();
  factory HealthMonitorService() => _instance;
  HealthMonitorService._internal();

  final ApiService _apiService = ApiService();

  // Health monitoring state
  HealthReport? _lastHealthReport;
  DateTime? _lastHealthCheck;
  Timer? _periodicHealthCheck;
  final List<HealthReport> _healthHistory = [];
  static const int maxHistorySize = 50;

  // Health check configuration
  bool _healthMonitoringEnabled = true;
  Duration _healthCheckInterval = const Duration(minutes: 5);
  final Duration _criticalHealthCheckInterval = const Duration(minutes: 1);
  bool _isInCriticalMode = false;

  // Stream controllers for reactive updates
  final StreamController<HealthReport> _healthReportController =
      StreamController<HealthReport>.broadcast();
  final StreamController<bool> _connectionHealthController =
      StreamController<bool>.broadcast();

  // Getters
  HealthReport? get lastHealthReport => _lastHealthReport;
  DateTime? get lastHealthCheck => _lastHealthCheck;
  bool get isHealthy =>
      _lastHealthReport?.overallStatus == HealthStatus.healthy;
  bool get hasTimeoutRisk => _lastHealthReport?.hasTimeoutRisk ?? false;
  bool get hasCriticalIssues => _lastHealthReport?.hasCriticalIssues ?? false;
  List<HealthReport> get healthHistory => List.unmodifiable(_healthHistory);

  // Streams for reactive UI updates
  Stream<HealthReport> get healthReportStream => _healthReportController.stream;
  Stream<bool> get connectionHealthStream => _connectionHealthController.stream;

  /// Initialize health monitoring
  void initialize() {
    if (!_healthMonitoringEnabled) return;

    logInfo('Initializing health monitoring service', tag: 'HealthMonitor');

    // Start periodic health checks
    _startPeriodicHealthChecks();

    // Perform initial health check
    checkHealth();
  }

  /// Start periodic health checks
  void _startPeriodicHealthChecks() {
    _periodicHealthCheck?.cancel();

    final interval =
        _isInCriticalMode ? _criticalHealthCheckInterval : _healthCheckInterval;

    _periodicHealthCheck = Timer.periodic(interval, (_) {
      checkHealth();
    });

    logDebug(
        'Started periodic health checks every ${interval.inMinutes} minutes',
        tag: 'HealthMonitor');
  }

  /// Perform comprehensive health check
  Future<HealthReport?> checkHealth() async {
    if (!_healthMonitoringEnabled) return null;

    try {
      logDebug('Performing comprehensive health check', tag: 'HealthMonitor');

      final stopwatch = Stopwatch()..start();
      final response = await _apiService.get('/health/comprehensive');
      stopwatch.stop();

      if (response.statusCode == 200 || response.statusCode == 503) {
        // 503 is expected for degraded/critical health status
        final healthReport =
            HealthReport.fromJson(response.data as Map<String, dynamic>);

        // Update internal state
        _lastHealthReport = healthReport;
        _lastHealthCheck = DateTime.now();

        // Store in history
        _addToHistory(healthReport);

        // Check if we should switch to critical monitoring mode
        _updateMonitoringMode(healthReport);

        // Notify listeners
        _healthReportController.add(healthReport);
        _connectionHealthController.add(true);

        logInfo(
            'Health check completed: ${healthReport.overallStatus.name} '
            '(${stopwatch.elapsedMilliseconds}ms)',
            tag: 'HealthMonitor');

        // Log critical issues
        if (healthReport.hasCriticalIssues) {
          logWarning('Critical health issues detected: ${healthReport.alerts}',
              tag: 'HealthMonitor');
        }

        // Log timeout risks
        if (healthReport.hasTimeoutRisk) {
          logWarning('Timeout risk detected - high response times',
              tag: 'HealthMonitor');
        }

        return healthReport;
      } else {
        throw Exception(
            'Unexpected health check response: ${response.statusCode}');
      }
    } catch (e) {
      logError('Health check failed: $e', tag: 'HealthMonitor');

      // Notify connection issues
      _connectionHealthController.add(false);

      // In case of failure, assume unhealthy status
      _lastHealthReport = null;
      _lastHealthCheck = DateTime.now();

      return null;
    }
  }

  /// Check specific component health
  Future<HealthMetric?> checkComponentHealth(String component) async {
    if (!_healthMonitoringEnabled) return null;

    try {
      logDebug('Checking health for component: $component',
          tag: 'HealthMonitor');

      final response = await _apiService.get('/health/middleware/$component');

      if (response.statusCode == 200 || response.statusCode == 503) {
        return HealthMetric.fromJson(response.data as Map<String, dynamic>);
      } else {
        throw Exception(
            'Component health check failed: ${response.statusCode}');
      }
    } catch (e) {
      logError('Component health check failed for $component: $e',
          tag: 'HealthMonitor');
      return null;
    }
  }

  /// Get performance-focused health metrics
  Future<Map<String, dynamic>?> getPerformanceHealth() async {
    if (!_healthMonitoringEnabled) return null;

    try {
      logDebug('Getting performance health metrics', tag: 'HealthMonitor');

      final response = await _apiService.get('/health/performance');

      if (response.statusCode == 200) {
        return response.data as Map<String, dynamic>?;
      } else {
        throw Exception(
            'Performance health check failed: ${response.statusCode}');
      }
    } catch (e) {
      logError('Performance health check failed: $e', tag: 'HealthMonitor');
      return null;
    }
  }

  /// Get current alerts
  Future<Map<String, dynamic>?> getCurrentAlerts() async {
    if (!_healthMonitoringEnabled) return null;

    try {
      logDebug('Getting current health alerts', tag: 'HealthMonitor');

      final response = await _apiService.get('/health/alerts');

      if (response.statusCode == 200) {
        return response.data as Map<String, dynamic>?;
      } else {
        throw Exception('Alerts check failed: ${response.statusCode}');
      }
    } catch (e) {
      logError('Alerts check failed: $e', tag: 'HealthMonitor');
      return null;
    }
  }

  /// Update monitoring mode based on health status
  void _updateMonitoringMode(HealthReport healthReport) {
    final shouldBeInCriticalMode =
        healthReport.hasCriticalIssues || healthReport.hasTimeoutRisk;

    if (shouldBeInCriticalMode != _isInCriticalMode) {
      _isInCriticalMode = shouldBeInCriticalMode;

      if (_isInCriticalMode) {
        logWarning('Switching to critical health monitoring mode',
            tag: 'HealthMonitor');
      } else {
        logInfo('Switching back to normal health monitoring mode',
            tag: 'HealthMonitor');
      }

      // Restart periodic checks with new interval
      _startPeriodicHealthChecks();
    }
  }

  /// Add health report to history
  void _addToHistory(HealthReport report) {
    _healthHistory.add(report);

    // Keep only recent history
    if (_healthHistory.length > maxHistorySize) {
      _healthHistory.removeAt(0);
    }
  }

  /// Get health trend analysis
  Map<String, dynamic> getHealthTrend({int hours = 24}) {
    if (_healthHistory.isEmpty) {
      return {
        'trend': 'no_data',
        'message': 'Insufficient data for trend analysis'
      };
    }

    final cutoff = DateTime.now().subtract(Duration(hours: hours));
    final recentReports =
        _healthHistory.where((r) => r.timestamp.isAfter(cutoff)).toList();

    if (recentReports.length < 2) {
      return {
        'trend': 'insufficient_data',
        'message': 'Need more data points for trend analysis'
      };
    }

    // Analyze status changes
    final statuses = recentReports.map((r) => r.overallStatus).toList();
    final healthyCount =
        statuses.where((s) => s == HealthStatus.healthy).length;
    final degradedCount =
        statuses.where((s) => s == HealthStatus.degraded).length;
    final criticalCount =
        statuses.where((s) => s == HealthStatus.critical).length;
    final unhealthyCount =
        statuses.where((s) => s == HealthStatus.unhealthy).length;

    // Analyze response time trend
    final responseTimes = recentReports.map((r) => r.responseTimeMs).toList();
    final avgResponseTime =
        responseTimes.reduce((a, b) => a + b) / responseTimes.length;
    final firstHalfAvg =
        responseTimes.take(responseTimes.length ~/ 2).reduce((a, b) => a + b) /
            (responseTimes.length ~/ 2);
    final secondHalfAvg =
        responseTimes.skip(responseTimes.length ~/ 2).reduce((a, b) => a + b) /
            (responseTimes.length - responseTimes.length ~/ 2);

    String trend;
    String message;

    if (criticalCount > recentReports.length * 0.3) {
      trend = 'critical_issues';
      message = 'Frequent critical issues detected';
    } else if (unhealthyCount > 0) {
      trend = 'unhealthy_periods';
      message = 'System unhealthy periods detected';
    } else if (degradedCount > recentReports.length * 0.5) {
      trend = 'degrading';
      message = 'Performance degradation trend';
    } else if (secondHalfAvg > firstHalfAvg * 1.2) {
      trend = 'performance_declining';
      message = 'Response times increasing';
    } else if (healthyCount > recentReports.length * 0.8) {
      trend = 'stable_healthy';
      message = 'System stable and healthy';
    } else {
      trend = 'mixed';
      message = 'Mixed health status';
    }

    return {
      'trend': trend,
      'message': message,
      'analysis_period_hours': hours,
      'total_checks': recentReports.length,
      'health_distribution': {
        'healthy': healthyCount,
        'degraded': degradedCount,
        'critical': criticalCount,
        'unhealthy': unhealthyCount,
      },
      'average_response_time_ms': avgResponseTime,
      'performance_trend': secondHalfAvg > firstHalfAvg * 1.1
          ? 'declining'
          : secondHalfAvg < firstHalfAvg * 0.9
              ? 'improving'
              : 'stable',
    };
  }

  /// Check if system has connection-based timeout configuration
  Map<String, Duration> getRecommendedTimeouts() {
    final report = _lastHealthReport;
    if (report == null) {
      // Default conservative timeouts when health is unknown
      return {
        'connect': const Duration(seconds: 15),
        'receive': const Duration(seconds: 30),
        'send': const Duration(seconds: 15),
      };
    }

    // Adjust timeouts based on system health and performance
    Duration connectTimeout;
    Duration receiveTimeout;
    Duration sendTimeout;

    if (report.hasCriticalIssues || report.hasTimeoutRisk) {
      // Longer timeouts for critical systems to avoid false failures
      connectTimeout = const Duration(seconds: 20);
      receiveTimeout = const Duration(seconds: 45);
      sendTimeout = const Duration(seconds: 20);
    } else if (report.overallStatus == HealthStatus.degraded) {
      // Slightly longer timeouts for degraded systems
      connectTimeout = const Duration(seconds: 15);
      receiveTimeout = const Duration(seconds: 25);
      sendTimeout = const Duration(seconds: 15);
    } else if (report.responseTimeMs < 500) {
      // Shorter timeouts for high-performance systems
      connectTimeout = const Duration(seconds: 8);
      receiveTimeout = const Duration(seconds: 12);
      sendTimeout = const Duration(seconds: 8);
    } else {
      // Standard timeouts for normal systems
      connectTimeout = const Duration(seconds: 10);
      receiveTimeout = const Duration(seconds: 15);
      sendTimeout = const Duration(seconds: 10);
    }

    return {
      'connect': connectTimeout,
      'receive': receiveTimeout,
      'send': sendTimeout,
    };
  }

  /// Enable or disable health monitoring
  void setHealthMonitoringEnabled(bool enabled) {
    if (_healthMonitoringEnabled == enabled) return;

    _healthMonitoringEnabled = enabled;

    if (enabled) {
      logInfo('Health monitoring enabled', tag: 'HealthMonitor');
      initialize();
    } else {
      logInfo('Health monitoring disabled', tag: 'HealthMonitor');
      _periodicHealthCheck?.cancel();
    }
  }

  /// Set health check interval
  void setHealthCheckInterval(Duration interval) {
    if (_healthCheckInterval == interval) return;

    _healthCheckInterval = interval;
    logInfo('Health check interval changed to ${interval.inMinutes} minutes',
        tag: 'HealthMonitor');

    if (_healthMonitoringEnabled && !_isInCriticalMode) {
      _startPeriodicHealthChecks();
    }
  }

  /// Force immediate health check
  Future<HealthReport?> forceHealthCheck() async {
    logInfo('Forcing immediate health check', tag: 'HealthMonitor');
    return await checkHealth();
  }

  /// Get simple connectivity status
  Future<bool> isBackendHealthy() async {
    final report = await checkHealth();
    return report != null && report.overallStatus != HealthStatus.unhealthy;
  }

  /// Dispose resources
  void dispose() {
    logInfo('Disposing health monitoring service', tag: 'HealthMonitor');

    _periodicHealthCheck?.cancel();
    _healthReportController.close();
    _connectionHealthController.close();
  }
}

import 'dart:async';

import 'token_lifecycle_manager.dart';
import 'logging_service.dart';

/// Security monitoring service for MITA financial application
/// 
/// Provides comprehensive security monitoring including:
/// - Real-time security event tracking
/// - Anomaly detection for token operations
/// - Security metrics collection
/// - Threat detection and response
/// - Compliance reporting for financial regulations
class SecurityMonitor {
  static SecurityMonitor? _instance;
  static SecurityMonitor get instance => _instance ??= SecurityMonitor._internal();

  SecurityMonitor._internal();

  final List<SecurityEvent> _securityEvents = [];
  final List<SecurityMetric> _metrics = [];
  Timer? _monitoringTimer;
  
  // Security thresholds
  static const int _maxEventsToKeep = 1000;
  static const int _maxMetricsToKeep = 500;
  static const Duration _monitoringInterval = Duration(minutes: 5);
  
  // Anomaly detection parameters
  static const int _anomalyThreshold = 5;
  static const Duration _anomalyWindow = Duration(minutes: 15);

  bool _isInitialized = false;
  DateTime? _lastMonitoringCycle;

  /// Initialize security monitoring
  Future<void> initialize() async {
    if (_isInitialized) return;

    try {
      logInfo('Initializing security monitoring', tag: 'SECURITY_MONITOR');
      
      // Log initialization event
      await logSecurityEvent(
        SecurityEventType.systemInitialized,
        'Security monitoring system started',
        severity: SecuritySeverity.info,
      );

      // Start periodic monitoring
      _startPeriodicMonitoring();
      
      _isInitialized = true;
      logInfo('Security monitoring initialized successfully', tag: 'SECURITY_MONITOR');
    } catch (e) {
      logError('Failed to initialize security monitoring: $e', 
        tag: 'SECURITY_MONITOR', error: e);
      rethrow;
    }
  }

  /// Start periodic security monitoring
  void _startPeriodicMonitoring() {
    _monitoringTimer?.cancel();
    _monitoringTimer = Timer.periodic(_monitoringInterval, (_) {
      _performMonitoringCycle().catchError((e) {
        logError('Monitoring cycle failed: $e', 
          tag: 'SECURITY_MONITOR', error: e);
      });
    });
  }

  /// Perform security monitoring cycle
  Future<void> _performMonitoringCycle() async {
    try {
      _lastMonitoringCycle = DateTime.now();
      
      // Check for anomalies
      await _detectAnomalies();
      
      // Clean up old events and metrics
      _cleanupOldData();
      
      // Record monitoring metric
      await recordMetric(SecurityMetricType.monitoringCycle, 1);
      
    } catch (e) {
      logError('Security monitoring cycle failed: $e', 
        tag: 'SECURITY_MONITOR', error: e);
      
      await logSecurityEvent(
        SecurityEventType.systemError,
        'Security monitoring cycle failed: $e',
        severity: SecuritySeverity.high,
        metadata: {'error': e.toString()},
      );
    }
  }

  /// Log a security event
  Future<void> logSecurityEvent(
    SecurityEventType eventType,
    String description, {
    SecuritySeverity severity = SecuritySeverity.medium,
    Map<String, dynamic>? metadata,
  }) async {
    try {
      final event = SecurityEvent(
        type: eventType,
        description: description,
        severity: severity,
        timestamp: DateTime.now(),
        metadata: metadata ?? {},
      );

      _securityEvents.add(event);
      
      // Log to standard logging system based on severity
      switch (severity) {
        case SecuritySeverity.critical:
          logError('CRITICAL SECURITY EVENT: ${event.description}', 
            tag: 'SECURITY_EVENT', 
            extra: event.toJson());
          break;
        case SecuritySeverity.high:
          logError('HIGH SECURITY EVENT: ${event.description}', 
            tag: 'SECURITY_EVENT', 
            extra: event.toJson());
          break;
        case SecuritySeverity.medium:
          logWarning('MEDIUM SECURITY EVENT: ${event.description}', 
            tag: 'SECURITY_EVENT', 
            extra: event.toJson());
          break;
        case SecuritySeverity.low:
          logInfo('LOW SECURITY EVENT: ${event.description}', 
            tag: 'SECURITY_EVENT', 
            extra: event.toJson());
          break;
        case SecuritySeverity.info:
          logDebug('SECURITY INFO: ${event.description}', 
            tag: 'SECURITY_EVENT', 
            extra: event.toJson());
          break;
      }

      // Handle critical events immediately
      if (severity == SecuritySeverity.critical) {
        await _handleCriticalSecurityEvent(event);
      }

    } catch (e) {
      logError('Failed to log security event: $e', 
        tag: 'SECURITY_MONITOR', error: e);
    }
  }

  /// Record a security metric
  Future<void> recordMetric(
    SecurityMetricType metricType,
    double value, {
    Map<String, dynamic>? metadata,
  }) async {
    try {
      final metric = SecurityMetric(
        type: metricType,
        value: value,
        timestamp: DateTime.now(),
        metadata: metadata ?? {},
      );

      _metrics.add(metric);
      
      logDebug('Security metric recorded: ${metricType.name} = $value', 
        tag: 'SECURITY_METRIC');

    } catch (e) {
      logError('Failed to record security metric: $e', 
        tag: 'SECURITY_MONITOR', error: e);
    }
  }

  /// Detect security anomalies
  Future<void> _detectAnomalies() async {
    try {
      final now = DateTime.now();
      final windowStart = now.subtract(_anomalyWindow);
      
      // Get events in the detection window
      final recentEvents = _securityEvents
          .where((event) => event.timestamp.isAfter(windowStart))
          .toList();

      // Check for authentication anomalies
      await _checkAuthenticationAnomalies(recentEvents);
      
      // Check for token operation anomalies
      await _checkTokenOperationAnomalies(recentEvents);
      
      // Check for system error anomalies
      await _checkSystemErrorAnomalies(recentEvents);

    } catch (e) {
      logError('Anomaly detection failed: $e', 
        tag: 'SECURITY_MONITOR', error: e);
    }
  }

  /// Check for authentication-related anomalies
  Future<void> _checkAuthenticationAnomalies(List<SecurityEvent> recentEvents) async {
    final authEvents = recentEvents
        .where((e) => e.type == SecurityEventType.authenticationFailed ||
                     e.type == SecurityEventType.suspiciousActivity)
        .length;

    if (authEvents >= _anomalyThreshold) {
      await logSecurityEvent(
        SecurityEventType.anomalyDetected,
        'Authentication anomaly detected: $authEvents failed attempts in ${_anomalyWindow.inMinutes} minutes',
        severity: SecuritySeverity.high,
        metadata: {
          'anomaly_type': 'authentication',
          'event_count': authEvents,
          'window_minutes': _anomalyWindow.inMinutes,
        },
      );
    }
  }

  /// Check for token operation anomalies
  Future<void> _checkTokenOperationAnomalies(List<SecurityEvent> recentEvents) async {
    final tokenEvents = recentEvents
        .where((e) => e.type == SecurityEventType.tokenOperationFailed ||
                     e.type == SecurityEventType.tokenTampering)
        .length;

    if (tokenEvents >= _anomalyThreshold) {
      await logSecurityEvent(
        SecurityEventType.anomalyDetected,
        'Token operation anomaly detected: $tokenEvents failed operations in ${_anomalyWindow.inMinutes} minutes',
        severity: SecuritySeverity.high,
        metadata: {
          'anomaly_type': 'token_operations',
          'event_count': tokenEvents,
          'window_minutes': _anomalyWindow.inMinutes,
        },
      );
    }
  }

  /// Check for system error anomalies
  Future<void> _checkSystemErrorAnomalies(List<SecurityEvent> recentEvents) async {
    final errorEvents = recentEvents
        .where((e) => e.type == SecurityEventType.systemError)
        .length;

    if (errorEvents >= _anomalyThreshold) {
      await logSecurityEvent(
        SecurityEventType.anomalyDetected,
        'System error anomaly detected: $errorEvents errors in ${_anomalyWindow.inMinutes} minutes',
        severity: SecuritySeverity.medium,
        metadata: {
          'anomaly_type': 'system_errors',
          'event_count': errorEvents,
          'window_minutes': _anomalyWindow.inMinutes,
        },
      );
    }
  }

  /// Handle critical security events
  Future<void> _handleCriticalSecurityEvent(SecurityEvent event) async {
    try {
      logError('HANDLING CRITICAL SECURITY EVENT: ${event.description}', 
        tag: 'SECURITY_CRITICAL');

      // Force token cleanup for critical security events
      if (event.type == SecurityEventType.tokenTampering ||
          event.type == SecurityEventType.securityBreach) {
        await TokenLifecycleManager.instance.forceTokenCleanup(
          reason: 'Critical security event: ${event.description}',
        );
      }

      // Record critical event metric
      await recordMetric(SecurityMetricType.criticalEvents, 1);

      // TODO: Could trigger additional security measures like:
      // - Notify security team
      // - Lock user account temporarily
      // - Increase monitoring frequency
      // - Send push notification to user

    } catch (e) {
      logError('Failed to handle critical security event: $e', 
        tag: 'SECURITY_MONITOR', error: e);
    }
  }

  /// Clean up old data to prevent memory issues
  void _cleanupOldData() {
    // Remove old events
    if (_securityEvents.length > _maxEventsToKeep) {
      final toRemove = _securityEvents.length - _maxEventsToKeep;
      _securityEvents.removeRange(0, toRemove);
    }

    // Remove old metrics
    if (_metrics.length > _maxMetricsToKeep) {
      final toRemove = _metrics.length - _maxMetricsToKeep;
      _metrics.removeRange(0, toRemove);
    }
  }

  /// Get security events within time range
  List<SecurityEvent> getSecurityEvents({
    DateTime? since,
    SecuritySeverity? minSeverity,
    SecurityEventType? eventType,
  }) {
    return _securityEvents.where((event) {
      if (since != null && event.timestamp.isBefore(since)) return false;
      if (minSeverity != null && event.severity.index < minSeverity.index) return false;
      if (eventType != null && event.type != eventType) return false;
      return true;
    }).toList();
  }

  /// Get security metrics within time range
  List<SecurityMetric> getSecurityMetrics({
    DateTime? since,
    SecurityMetricType? metricType,
  }) {
    return _metrics.where((metric) {
      if (since != null && metric.timestamp.isBefore(since)) return false;
      if (metricType != null && metric.type != metricType) return false;
      return true;
    }).toList();
  }

  /// Generate security report
  Future<Map<String, dynamic>> generateSecurityReport({
    Duration? period,
  }) async {
    final reportPeriod = period ?? const Duration(days: 1);
    final since = DateTime.now().subtract(reportPeriod);

    final events = getSecurityEvents(since: since);
    final metrics = getSecurityMetrics(since: since);

    // Calculate severity distribution
    final severityDistribution = <String, int>{};
    for (final event in events) {
      severityDistribution[event.severity.name] = 
          (severityDistribution[event.severity.name] ?? 0) + 1;
    }

    // Calculate event type distribution
    final eventTypeDistribution = <String, int>{};
    for (final event in events) {
      eventTypeDistribution[event.type.name] = 
          (eventTypeDistribution[event.type.name] ?? 0) + 1;
    }

    // Calculate metric summaries
    final metricSummaries = <String, Map<String, dynamic>>{};
    for (final metricType in SecurityMetricType.values) {
      final typeMetrics = metrics.where((m) => m.type == metricType).toList();
      if (typeMetrics.isNotEmpty) {
        final values = typeMetrics.map((m) => m.value).toList();
        metricSummaries[metricType.name] = {
          'count': values.length,
          'sum': values.fold<double>(0, (a, b) => a + b),
          'average': values.fold<double>(0, (a, b) => a + b) / values.length,
          'max': values.reduce((a, b) => a > b ? a : b),
          'min': values.reduce((a, b) => a < b ? a : b),
        };
      }
    }

    return {
      'period': {
        'start': since.millisecondsSinceEpoch,
        'end': DateTime.now().millisecondsSinceEpoch,
        'durationHours': reportPeriod.inHours,
      },
      'summary': {
        'totalEvents': events.length,
        'totalMetrics': metrics.length,
        'criticalEvents': events.where((e) => e.severity == SecuritySeverity.critical).length,
        'highSeverityEvents': events.where((e) => e.severity == SecuritySeverity.high).length,
        'lastMonitoringCycle': _lastMonitoringCycle?.millisecondsSinceEpoch,
      },
      'severityDistribution': severityDistribution,
      'eventTypeDistribution': eventTypeDistribution,
      'metricSummaries': metricSummaries,
      'generatedAt': DateTime.now().millisecondsSinceEpoch,
    };
  }

  /// Stop security monitoring
  void stopMonitoring() {
    _monitoringTimer?.cancel();
    _monitoringTimer = null;
    logInfo('Security monitoring stopped', tag: 'SECURITY_MONITOR');
  }

  /// Dispose resources
  void dispose() {
    stopMonitoring();
    _securityEvents.clear();
    _metrics.clear();
    _isInitialized = false;
    logDebug('Security monitor disposed', tag: 'SECURITY_MONITOR');
  }
}

/// Security event types for comprehensive monitoring
enum SecurityEventType {
  systemInitialized,
  authenticationSuccess,
  authenticationFailed,
  tokenStored,
  tokenRetrieved,
  tokenRefreshed,
  tokenCleared,
  tokenOperationFailed,
  tokenTampering,
  deviceFingerprintMismatch,
  suspiciousActivity,
  anomalyDetected,
  securityBreach,
  systemError,
}

/// Security severity levels
enum SecuritySeverity {
  info,     // 0 - Informational
  low,      // 1 - Low priority
  medium,   // 2 - Medium priority
  high,     // 3 - High priority
  critical, // 4 - Critical - immediate action required
}

/// Security event model
class SecurityEvent {
  final SecurityEventType type;
  final String description;
  final SecuritySeverity severity;
  final DateTime timestamp;
  final Map<String, dynamic> metadata;

  SecurityEvent({
    required this.type,
    required this.description,
    required this.severity,
    required this.timestamp,
    required this.metadata,
  });

  Map<String, dynamic> toJson() => {
    'type': type.name,
    'description': description,
    'severity': severity.name,
    'timestamp': timestamp.millisecondsSinceEpoch,
    'metadata': metadata,
  };
}

/// Security metric types for monitoring
enum SecurityMetricType {
  authenticationAttempts,
  tokenOperations,
  tokenRefreshes,
  securityEvents,
  criticalEvents,
  anomaliesDetected,
  monitoringCycle,
  systemErrors,
}

/// Security metric model
class SecurityMetric {
  final SecurityMetricType type;
  final double value;
  final DateTime timestamp;
  final Map<String, dynamic> metadata;

  SecurityMetric({
    required this.type,
    required this.value,
    required this.timestamp,
    required this.metadata,
  });

  Map<String, dynamic> toJson() => {
    'type': type.name,
    'value': value,
    'timestamp': timestamp.millisecondsSinceEpoch,
    'metadata': metadata,
  };
}
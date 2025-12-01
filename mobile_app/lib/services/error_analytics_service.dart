/*
Error Analytics Service for MITA Flutter App
Provides advanced error tracking, analytics, and insights for improving app stability
*/

import 'dart:async';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/error_handling.dart';
import 'logging_service.dart';

/// Advanced error analytics service for tracking and analyzing errors
class ErrorAnalyticsService {
  static ErrorAnalyticsService? _instance;
  static ErrorAnalyticsService get instance =>
      _instance ??= ErrorAnalyticsService._();

  ErrorAnalyticsService._();

  late SharedPreferences _prefs;
  final Map<String, ErrorMetrics> _errorMetrics = {};
  final Map<String, List<ErrorOccurrence>> _recentErrors = {};
  Timer? _analyticsTimer;
  bool _initialized = false;

  /// Initialize error analytics service
  Future<void> initialize() async {
    if (_initialized) return;

    try {
      _prefs = await SharedPreferences.getInstance();
      await _loadStoredMetrics();
      _startAnalyticsCollection();
      _initialized = true;

      logInfo('Error Analytics Service initialized', tag: 'ERROR_ANALYTICS');
    } catch (e) {
      logError('Failed to initialize Error Analytics Service: $e',
          tag: 'ERROR_ANALYTICS');
    }
  }

  /// Record an error occurrence
  void recordError({
    required dynamic error,
    required ErrorSeverity severity,
    required ErrorCategory category,
    String? operationName,
    String? screenName,
    Map<String, dynamic>? context,
    StackTrace? stackTrace,
  }) {
    if (!_initialized) return;

    try {
      final errorKey = _generateErrorKey(error, operationName);
      final occurrence = ErrorOccurrence(
        error: error.toString(),
        severity: severity,
        category: category,
        operationName: operationName,
        screenName: screenName,
        context: context ?? {},
        stackTrace: stackTrace?.toString(),
        timestamp: DateTime.now(),
      );

      // Update metrics
      final metrics = _errorMetrics[errorKey] ??
          ErrorMetrics(
            errorKey: errorKey,
            errorType: error.runtimeType.toString(),
            firstOccurrence: occurrence.timestamp,
          );

      metrics.recordOccurrence(occurrence);
      _errorMetrics[errorKey] = metrics;

      // Track recent errors
      _recentErrors[errorKey] ??= [];
      _recentErrors[errorKey]!.add(occurrence);

      // Keep only last 50 occurrences per error type
      if (_recentErrors[errorKey]!.length > 50) {
        _recentErrors[errorKey]!.removeAt(0);
      }

      logDebug('Recorded error: $errorKey', tag: 'ERROR_ANALYTICS');
    } catch (e) {
      logError('Failed to record error analytics: $e', tag: 'ERROR_ANALYTICS');
    }
  }

  /// Get error analytics summary
  ErrorAnalyticsSummary getAnalyticsSummary({Duration? period}) {
    final now = DateTime.now();
    final since = period != null
        ? now.subtract(period)
        : DateTime.fromMillisecondsSinceEpoch(0);

    final relevantMetrics = _errorMetrics.values
        .where((metrics) => metrics.lastOccurrence.isAfter(since))
        .toList();

    final totalErrors = relevantMetrics.fold<int>(
        0, (sum, metrics) => sum + metrics.totalCount);
    final categoryCounts = <ErrorCategory, int>{};
    final severityCounts = <ErrorSeverity, int>{};
    final topErrors = <ErrorMetrics>[];

    for (final metrics in relevantMetrics) {
      // Count by category
      for (final occurrence in metrics.occurrences) {
        if (occurrence.timestamp.isAfter(since)) {
          categoryCounts[occurrence.category] =
              (categoryCounts[occurrence.category] ?? 0) + 1;
          severityCounts[occurrence.severity] =
              (severityCounts[occurrence.severity] ?? 0) + 1;
        }
      }
    }

    // Get top errors by frequency
    relevantMetrics.sort((a, b) => b.totalCount.compareTo(a.totalCount));
    topErrors.addAll(relevantMetrics.take(10));

    return ErrorAnalyticsSummary(
      totalErrors: totalErrors,
      uniqueErrors: relevantMetrics.length,
      categoryCounts: categoryCounts,
      severityCounts: severityCounts,
      topErrors: topErrors,
      period: period,
      generatedAt: now,
    );
  }

  /// Get error trends over time
  List<ErrorTrendPoint> getErrorTrends({
    required Duration period,
    required Duration interval,
  }) {
    final now = DateTime.now();
    final since = now.subtract(period);
    final trends = <ErrorTrendPoint>[];

    DateTime current = since;
    while (current.isBefore(now)) {
      final next = current.add(interval);
      int errorCount = 0;

      for (final metrics in _errorMetrics.values) {
        errorCount += metrics.occurrences
            .where((occurrence) =>
                occurrence.timestamp.isAfter(current) &&
                occurrence.timestamp.isBefore(next))
            .length;
      }

      trends.add(ErrorTrendPoint(
        timestamp: current,
        errorCount: errorCount,
      ));

      current = next;
    }

    return trends;
  }

  /// Get specific error details
  ErrorMetrics? getErrorDetails(String errorKey) {
    return _errorMetrics[errorKey];
  }

  /// Get error patterns (errors that often occur together)
  List<ErrorPattern> getErrorPatterns({Duration? timeWindow}) {
    final window = timeWindow ?? const Duration(minutes: 5);
    final patterns = <ErrorPattern>[];
    final errorPairs = <String, List<String>>{};

    // Group errors by time windows
    for (final entry in _recentErrors.entries) {
      final errorKey = entry.key;
      final occurrences = entry.value;

      for (final occurrence in occurrences) {
        final windowStart = DateTime(
          occurrence.timestamp.year,
          occurrence.timestamp.month,
          occurrence.timestamp.day,
          occurrence.timestamp.hour,
          (occurrence.timestamp.minute ~/ window.inMinutes) * window.inMinutes,
        );

        final windowKey = windowStart.toIso8601String();
        errorPairs[windowKey] ??= [];
        errorPairs[windowKey]!.add(errorKey);
      }
    }

    // Find patterns
    final patternCounts = <String, int>{};
    for (final errors in errorPairs.values) {
      if (errors.length > 1) {
        errors.sort();
        final patternKey = errors.join('|');
        patternCounts[patternKey] = (patternCounts[patternKey] ?? 0) + 1;
      }
    }

    // Convert to pattern objects
    for (final entry in patternCounts.entries) {
      if (entry.value >= 2) {
        // At least 2 occurrences
        patterns.add(ErrorPattern(
          errors: entry.key.split('|'),
          frequency: entry.value,
          timeWindow: window,
        ));
      }
    }

    patterns.sort((a, b) => b.frequency.compareTo(a.frequency));
    return patterns.take(10).toList();
  }

  /// Get error impact assessment
  ErrorImpactAssessment assessErrorImpact(String errorKey) {
    final metrics = _errorMetrics[errorKey];
    if (metrics == null) {
      return ErrorImpactAssessment.unknown(errorKey);
    }

    // Calculate impact score based on various factors
    double impactScore = 0.0;

    // Frequency factor (0-40 points)
    impactScore += (metrics.totalCount.clamp(0, 40)).toDouble();

    // Recency factor (0-20 points)
    final hoursSinceLastOccurrence =
        DateTime.now().difference(metrics.lastOccurrence).inHours;
    if (hoursSinceLastOccurrence < 1) {
      impactScore += 20;
    } else if (hoursSinceLastOccurrence < 24) {
      impactScore += 15;
    } else if (hoursSinceLastOccurrence < 168) {
      // 1 week
      impactScore += 10;
    } else {
      impactScore += 5;
    }

    // Severity factor (0-30 points)
    final criticalCount = metrics.occurrences
        .where((o) => o.severity == ErrorSeverity.critical)
        .length;
    final highCount = metrics.occurrences
        .where((o) => o.severity == ErrorSeverity.high)
        .length;
    impactScore += (criticalCount * 3 + highCount * 2).clamp(0, 30).toDouble();

    // User facing factor (0-10 points)
    final uiCount =
        metrics.occurrences.where((o) => o.category == ErrorCategory.ui).length;
    final authCount = metrics.occurrences
        .where((o) => o.category == ErrorCategory.authentication)
        .length;
    impactScore += ((uiCount + authCount) * 2).clamp(0, 10).toDouble();

    // Determine impact level
    ImpactLevel impactLevel;
    if (impactScore >= 80) {
      impactLevel = ImpactLevel.critical;
    } else if (impactScore >= 60) {
      impactLevel = ImpactLevel.high;
    } else if (impactScore >= 40) {
      impactLevel = ImpactLevel.medium;
    } else if (impactScore >= 20) {
      impactLevel = ImpactLevel.low;
    } else {
      impactLevel = ImpactLevel.minimal;
    }

    return ErrorImpactAssessment(
      errorKey: errorKey,
      impactLevel: impactLevel,
      impactScore: impactScore,
      frequency: metrics.totalCount,
      recency: hoursSinceLastOccurrence,
      affectedScreens: metrics.getAffectedScreens(),
      affectedOperations: metrics.getAffectedOperations(),
    );
  }

  /// Generate error key from error and context
  String _generateErrorKey(dynamic error, String? operationName) {
    final errorType = error.runtimeType.toString();
    final errorMessage = error.toString();

    // Create a stable key based on error type and core message
    String coreMessage = errorMessage.length > 100
        ? errorMessage.substring(0, 100)
        : errorMessage;

    // Remove variable parts like timestamps, IDs, etc.
    coreMessage = coreMessage.replaceAll(RegExp(r'\d{4}-\d{2}-\d{2}'), 'DATE');
    coreMessage = coreMessage.replaceAll(RegExp(r'\d{2}:\d{2}:\d{2}'), 'TIME');
    coreMessage = coreMessage.replaceAll(
        RegExp(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'),
        'UUID');

    final operationPrefix = operationName != null ? '${operationName}_' : '';
    return '${operationPrefix}${errorType}_${coreMessage.hashCode.abs()}';
  }

  /// Start analytics collection
  void _startAnalyticsCollection() {
    // Increased interval to reduce timer load - persist less frequently
    _analyticsTimer = Timer.periodic(const Duration(minutes: 15), (_) async {
      await _persistMetrics();
      await _cleanupOldData();
    });
  }

  /// Persist metrics to storage
  Future<void> _persistMetrics() async {
    try {
      final metricsJson = <String, dynamic>{};
      for (final entry in _errorMetrics.entries) {
        metricsJson[entry.key] = entry.value.toJson();
      }

      await _prefs.setString('error_metrics', jsonEncode(metricsJson));
      logDebug('Persisted ${_errorMetrics.length} error metrics',
          tag: 'ERROR_ANALYTICS');
    } catch (e) {
      logError('Failed to persist error metrics: $e', tag: 'ERROR_ANALYTICS');
    }
  }

  /// Load stored metrics
  Future<void> _loadStoredMetrics() async {
    try {
      final metricsData = _prefs.getString('error_metrics');
      if (metricsData != null) {
        final metricsJson = jsonDecode(metricsData) as Map<String, dynamic>;

        for (final entry in metricsJson.entries) {
          try {
            final metrics =
                ErrorMetrics.fromJson(entry.value as Map<String, dynamic>);
            _errorMetrics[entry.key] = metrics;

            // Populate recent errors
            _recentErrors[entry.key] = metrics.occurrences.take(50).toList();
          } catch (e) {
            logWarning('Failed to load metrics for ${entry.key}: $e',
                tag: 'ERROR_ANALYTICS');
          }
        }

        logInfo('Loaded ${_errorMetrics.length} error metrics from storage',
            tag: 'ERROR_ANALYTICS');
      }
    } catch (e) {
      logError('Failed to load stored error metrics: $e',
          tag: 'ERROR_ANALYTICS');
    }
  }

  /// Clean up old data
  Future<void> _cleanupOldData() async {
    final cutoff = DateTime.now().subtract(const Duration(days: 30));
    int removedCount = 0;

    // Remove old metrics
    _errorMetrics.removeWhere((key, metrics) {
      if (metrics.lastOccurrence.isBefore(cutoff)) {
        removedCount++;
        return true;
      }
      return false;
    });

    // Clean up recent errors
    for (final entry in _recentErrors.entries) {
      entry.value
          .removeWhere((occurrence) => occurrence.timestamp.isBefore(cutoff));
    }
    _recentErrors.removeWhere((key, occurrences) => occurrences.isEmpty);

    if (removedCount > 0) {
      logInfo('Cleaned up $removedCount old error metrics',
          tag: 'ERROR_ANALYTICS');
    }
  }

  /// Dispose resources
  void dispose() {
    _analyticsTimer?.cancel();
    _persistMetrics();
  }
}

/// Error metrics for a specific error type
class ErrorMetrics {
  final String errorKey;
  final String errorType;
  final DateTime firstOccurrence;
  DateTime lastOccurrence;
  int totalCount = 0;
  final List<ErrorOccurrence> occurrences = [];

  ErrorMetrics({
    required this.errorKey,
    required this.errorType,
    required this.firstOccurrence,
  }) : lastOccurrence = firstOccurrence;

  void recordOccurrence(ErrorOccurrence occurrence) {
    occurrences.add(occurrence);
    totalCount++;
    if (occurrence.timestamp.isAfter(lastOccurrence)) {
      lastOccurrence = occurrence.timestamp;
    }
  }

  Set<String> getAffectedScreens() {
    return occurrences
        .map((o) => o.screenName)
        .where((screen) => screen != null)
        .cast<String>()
        .toSet();
  }

  Set<String> getAffectedOperations() {
    return occurrences
        .map((o) => o.operationName)
        .where((operation) => operation != null)
        .cast<String>()
        .toSet();
  }

  Map<String, dynamic> toJson() {
    return {
      'errorKey': errorKey,
      'errorType': errorType,
      'firstOccurrence': firstOccurrence.toIso8601String(),
      'lastOccurrence': lastOccurrence.toIso8601String(),
      'totalCount': totalCount,
      'occurrences': occurrences.map((o) => o.toJson()).toList(),
    };
  }

  factory ErrorMetrics.fromJson(Map<String, dynamic> json) {
    final metrics = ErrorMetrics(
      errorKey: json['errorKey'] as String,
      errorType: json['errorType'] as String,
      firstOccurrence: DateTime.parse(json['firstOccurrence'] as String),
    );

    metrics.lastOccurrence = DateTime.parse(json['lastOccurrence'] as String);
    metrics.totalCount = json['totalCount'] as int;

    final occurrencesList = json['occurrences'] as List<dynamic>;
    for (final occurrenceJson in occurrencesList) {
      try {
        metrics.occurrences.add(
            ErrorOccurrence.fromJson(occurrenceJson as Map<String, dynamic>));
      } catch (e) {
        // Skip corrupted occurrences
      }
    }

    return metrics;
  }
}

/// Individual error occurrence
class ErrorOccurrence {
  final String error;
  final ErrorSeverity severity;
  final ErrorCategory category;
  final String? operationName;
  final String? screenName;
  final Map<String, dynamic> context;
  final String? stackTrace;
  final DateTime timestamp;

  ErrorOccurrence({
    required this.error,
    required this.severity,
    required this.category,
    this.operationName,
    this.screenName,
    required this.context,
    this.stackTrace,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() {
    return {
      'error': error,
      'severity': severity.toString(),
      'category': category.toString(),
      'operationName': operationName,
      'screenName': screenName,
      'context': context,
      'stackTrace': stackTrace,
      'timestamp': timestamp.toIso8601String(),
    };
  }

  factory ErrorOccurrence.fromJson(Map<String, dynamic> json) {
    return ErrorOccurrence(
      error: json['error'] as String,
      severity: ErrorSeverity.values.firstWhere(
        (e) => e.toString() == json['severity'],
        orElse: () => ErrorSeverity.medium,
      ),
      category: ErrorCategory.values.firstWhere(
        (e) => e.toString() == json['category'],
        orElse: () => ErrorCategory.unknown,
      ),
      operationName: json['operationName'] as String?,
      screenName: json['screenName'] as String?,
      context: Map<String, dynamic>.from((json['context'] ?? {}) as Map),
      stackTrace: json['stackTrace'] as String?,
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}

/// Error analytics summary
class ErrorAnalyticsSummary {
  final int totalErrors;
  final int uniqueErrors;
  final Map<ErrorCategory, int> categoryCounts;
  final Map<ErrorSeverity, int> severityCounts;
  final List<ErrorMetrics> topErrors;
  final Duration? period;
  final DateTime generatedAt;

  ErrorAnalyticsSummary({
    required this.totalErrors,
    required this.uniqueErrors,
    required this.categoryCounts,
    required this.severityCounts,
    required this.topErrors,
    this.period,
    required this.generatedAt,
  });
}

/// Error trend point for analytics
class ErrorTrendPoint {
  final DateTime timestamp;
  final int errorCount;

  ErrorTrendPoint({
    required this.timestamp,
    required this.errorCount,
  });
}

/// Error pattern detection
class ErrorPattern {
  final List<String> errors;
  final int frequency;
  final Duration timeWindow;

  ErrorPattern({
    required this.errors,
    required this.frequency,
    required this.timeWindow,
  });
}

/// Error impact assessment
class ErrorImpactAssessment {
  final String errorKey;
  final ImpactLevel impactLevel;
  final double impactScore;
  final int frequency;
  final int recency;
  final Set<String> affectedScreens;
  final Set<String> affectedOperations;

  ErrorImpactAssessment({
    required this.errorKey,
    required this.impactLevel,
    required this.impactScore,
    required this.frequency,
    required this.recency,
    required this.affectedScreens,
    required this.affectedOperations,
  });

  factory ErrorImpactAssessment.unknown(String errorKey) {
    return ErrorImpactAssessment(
      errorKey: errorKey,
      impactLevel: ImpactLevel.minimal,
      impactScore: 0.0,
      frequency: 0,
      recency: 0,
      affectedScreens: {},
      affectedOperations: {},
    );
  }
}

/// Impact level enumeration
enum ImpactLevel {
  minimal,
  low,
  medium,
  high,
  critical,
}

/// Extension for easy analytics integration
extension ErrorAnalyticsExtension on Exception {
  void recordAnalytics({
    ErrorSeverity severity = ErrorSeverity.medium,
    ErrorCategory category = ErrorCategory.unknown,
    String? operationName,
    String? screenName,
    Map<String, dynamic>? context,
    StackTrace? stackTrace,
  }) {
    ErrorAnalyticsService.instance.recordError(
      error: this,
      severity: severity,
      category: category,
      operationName: operationName,
      screenName: screenName,
      context: context,
      stackTrace: stackTrace,
    );
  }
}

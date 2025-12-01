/*
Central Analytics Service for MITA Flutter App
Coordinates all analytics tracking including feature usage, behavior, and errors
*/

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'error_analytics_service.dart';
import 'predictive_analytics_service.dart';
import 'logging_service.dart';
import 'secure_device_service.dart';

/// Central analytics service coordinating all analytics functionality
class AnalyticsService extends ChangeNotifier {
  static final AnalyticsService _instance = AnalyticsService._internal();
  factory AnalyticsService() => _instance;
  AnalyticsService._internal();

  final ApiService _apiService = ApiService();
  final ErrorAnalyticsService _errorAnalytics = ErrorAnalyticsService.instance;
  final PredictiveAnalyticsService _predictiveAnalytics =
      PredictiveAnalyticsService();

  bool _initialized = false;
  String? _sessionId;
  DateTime? _sessionStart;
  final Map<String, DateTime> _screenStartTimes = {};
  final Map<String, int> _featureUsageCount = {};

  /// Initialize analytics service
  Future<void> initialize() async {
    if (_initialized) return;

    try {
      logInfo('Initializing Analytics Service', tag: 'ANALYTICS');

      // Generate session ID
      _sessionId = await _generateSessionId();
      _sessionStart = DateTime.now();

      // Initialize sub-services
      await _errorAnalytics.initialize();
      await _predictiveAnalytics.initialize();

      _initialized = true;
      logInfo('Analytics Service initialized successfully', tag: 'ANALYTICS');

      // Log session start
      await logFeatureUsage(
        feature: 'app_session',
        action: 'start',
        metadata: {
          'session_id': _sessionId,
          'start_time': _sessionStart?.toIso8601String(),
        },
      );
    } catch (e) {
      logError('Failed to initialize Analytics Service: $e',
          tag: 'ANALYTICS', error: e);
    }
  }

  /// Log feature usage
  Future<void> logFeatureUsage({
    required String feature,
    String? screen,
    String? action,
    Map<String, dynamic>? metadata,
  }) async {
    if (!_initialized) {
      logWarning('Analytics not initialized, queuing event', tag: 'ANALYTICS');
      return;
    }

    try {
      // Track usage count locally
      _featureUsageCount[feature] = (_featureUsageCount[feature] ?? 0) + 1;

      // Send to backend
      await _apiService.logFeatureUsage(
        feature: feature,
        screen: screen,
        action: action,
        metadata: metadata,
        sessionId: _sessionId,
      );

      logDebug('Logged feature usage: $feature ($action)', tag: 'ANALYTICS');
    } catch (e) {
      logError('Failed to log feature usage: $e', tag: 'ANALYTICS', error: e);
    }
  }

  /// Log premium feature access attempt
  Future<void> logFeatureAccessAttempt({
    required String feature,
    required bool hasAccess,
    bool isPremiumFeature = true,
    String? screen,
    Map<String, dynamic>? metadata,
  }) async {
    if (!_initialized) return;

    try {
      await _apiService.logFeatureAccessAttempt(
        feature: feature,
        hasAccess: hasAccess,
        isPremiumFeature: isPremiumFeature,
        screen: screen,
        metadata: metadata,
      );

      logDebug('Logged feature access attempt: $feature (access: $hasAccess)',
          tag: 'ANALYTICS');
    } catch (e) {
      logError('Failed to log feature access: $e', tag: 'ANALYTICS', error: e);
    }
  }

  /// Log paywall impression
  Future<void> logPaywallImpression({
    required String screen,
    String? feature,
    String? context,
    Map<String, dynamic>? metadata,
  }) async {
    if (!_initialized) return;

    try {
      await _apiService.logPaywallImpression(
        screen: screen,
        feature: feature,
        context: context,
        metadata: metadata,
      );

      logDebug('Logged paywall impression: $screen', tag: 'ANALYTICS');
    } catch (e) {
      logError('Failed to log paywall impression: $e',
          tag: 'ANALYTICS', error: e);
    }
  }

  /// Track screen view
  Future<void> trackScreenView(String screenName) async {
    if (!_initialized) return;

    try {
      // End previous screen timing if exists
      await _endScreenTiming();

      // Start new screen timing
      _screenStartTimes[screenName] = DateTime.now();

      await logFeatureUsage(
        feature: 'screen_view',
        screen: screenName,
        action: 'view',
        metadata: {
          'screen_name': screenName,
          'session_id': _sessionId,
        },
      );

      logDebug('Tracked screen view: $screenName', tag: 'ANALYTICS');
    } catch (e) {
      logError('Failed to track screen view: $e', tag: 'ANALYTICS', error: e);
    }
  }

  /// End screen timing (called when navigating away)
  Future<void> _endScreenTiming() async {
    if (_screenStartTimes.isEmpty) return;

    final lastScreen = _screenStartTimes.keys.last;
    final startTime = _screenStartTimes[lastScreen];
    if (startTime != null) {
      final duration = DateTime.now().difference(startTime);

      await logFeatureUsage(
        feature: 'screen_duration',
        screen: lastScreen,
        action: 'end',
        metadata: {
          'duration_seconds': duration.inSeconds,
          'screen_name': lastScreen,
        },
      );
    }
  }

  /// Track button tap
  Future<void> trackButtonTap({
    required String buttonName,
    String? screen,
    Map<String, dynamic>? metadata,
  }) async {
    await logFeatureUsage(
      feature: 'button_tap',
      screen: screen,
      action: 'tap',
      metadata: {
        'button_name': buttonName,
        ...?metadata,
      },
    );
  }

  /// Track user action
  Future<void> trackUserAction({
    required String action,
    String? category,
    String? screen,
    Map<String, dynamic>? metadata,
  }) async {
    await logFeatureUsage(
      feature: 'user_action',
      screen: screen,
      action: action,
      metadata: {
        'category': category,
        'action_name': action,
        ...?metadata,
      },
    );
  }

  /// Get analytics summary
  Future<Map<String, dynamic>> getAnalyticsSummary() async {
    try {
      final errorSummary = _errorAnalytics.getAnalyticsSummary(
        period: const Duration(days: 7),
      );

      return {
        'session_id': _sessionId,
        'session_duration_minutes': _sessionStart != null
            ? DateTime.now().difference(_sessionStart!).inMinutes
            : 0,
        'features_used': _featureUsageCount.length,
        'total_interactions':
            _featureUsageCount.values.fold<int>(0, (sum, count) => sum + count),
        'errors_count': errorSummary.totalErrors,
        'unique_errors': errorSummary.uniqueErrors,
        'top_features': _getTopFeatures(5),
      };
    } catch (e) {
      logError('Failed to get analytics summary: $e',
          tag: 'ANALYTICS', error: e);
      return {};
    }
  }

  /// Get top used features
  List<Map<String, dynamic>> _getTopFeatures(int limit) {
    final sorted = _featureUsageCount.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return sorted
        .take(limit)
        .map((entry) => {
              'feature': entry.key,
              'count': entry.value,
            })
        .toList();
  }

  /// Generate unique session ID
  Future<String> _generateSessionId() async {
    try {
      final secureDeviceService = SecureDeviceService();
      final deviceId = await secureDeviceService.getSecureDeviceId();
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      return '${deviceId}_$timestamp';
    } catch (e) {
      // Fallback to timestamp-based ID
      return 'session_${DateTime.now().millisecondsSinceEpoch}';
    }
  }

  /// End current session
  Future<void> endSession() async {
    if (!_initialized || _sessionId == null) return;

    try {
      await _endScreenTiming();

      final sessionDuration = _sessionStart != null
          ? DateTime.now().difference(_sessionStart!)
          : Duration.zero;

      await logFeatureUsage(
        feature: 'app_session',
        action: 'end',
        metadata: {
          'session_id': _sessionId,
          'duration_seconds': sessionDuration.inSeconds,
          'features_used': _featureUsageCount.length,
          'total_interactions': _featureUsageCount.values
              .fold<int>(0, (sum, count) => sum + count),
        },
      );

      logInfo(
          'Session ended: $_sessionId (${sessionDuration.inMinutes} minutes)',
          tag: 'ANALYTICS');

      // Reset session
      _sessionId = null;
      _sessionStart = null;
      _screenStartTimes.clear();
      _featureUsageCount.clear();
    } catch (e) {
      logError('Failed to end session: $e', tag: 'ANALYTICS', error: e);
    }
  }

  /// Access to sub-services
  ErrorAnalyticsService get errorAnalytics => _errorAnalytics;
  PredictiveAnalyticsService get predictiveAnalytics => _predictiveAnalytics;

  @override
  void dispose() {
    endSession();
    _errorAnalytics.dispose();
    _predictiveAnalytics.dispose();
    super.dispose();
  }
}

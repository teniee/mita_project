import 'dart:async';

import 'secure_token_storage.dart';
import 'logging_service.dart';
import 'message_service.dart';
import 'api_service.dart';

/// Token lifecycle management service for MITA
///
/// This service handles:
/// - Token expiration monitoring
/// - Automatic token rotation
/// - Security health checks
/// - Token lifecycle events
/// - Performance monitoring of token operations
class TokenLifecycleManager {
  static TokenLifecycleManager? _instance;
  static TokenLifecycleManager get instance => _instance ??= TokenLifecycleManager._internal();

  TokenLifecycleManager._internal();

  Timer? _lifecycleTimer;
  SecureTokenStorage? _secureStorage;

  // Token lifecycle configuration
  static const Duration _healthCheckInterval = Duration(minutes: 15);
  static const Duration _rotationCheckInterval = Duration(hours: 6);
  // static const Duration _securityAuditInterval = Duration(days: 1); // Reserved for future use

  // Security thresholds
  static const int _maxFailedAttempts = 3;
  static const int _suspiciousAccessThreshold = 100;

  int _failedOperations = 0;
  DateTime? _lastHealthCheck;
  DateTime? _lastRotationCheck;
  DateTime? _lastSecurityAudit;

  /// Initialize token lifecycle management
  Future<void> initialize() async {
    try {
      _secureStorage = await SecureTokenStorage.getInstance();

      // Start periodic health checks
      _startLifecycleMonitoring();

      // Perform initial health check
      await _performHealthCheck();

      logInfo('Token lifecycle manager initialized', tag: 'TOKEN_LIFECYCLE');
    } catch (e) {
      logError('Failed to initialize token lifecycle manager: $e',
          tag: 'TOKEN_LIFECYCLE', error: e);
      rethrow;
    }
  }

  /// Start periodic lifecycle monitoring
  void _startLifecycleMonitoring() {
    _lifecycleTimer?.cancel();
    _lifecycleTimer = Timer.periodic(_healthCheckInterval, (_) {
      _performHealthCheck().catchError((e) {
        logError('Health check failed: $e', tag: 'TOKEN_LIFECYCLE', error: e);
        return <String, dynamic>{'error': e.toString()};
      });
    });

    logDebug('Token lifecycle monitoring started', tag: 'TOKEN_LIFECYCLE');
  }

  /// Stop lifecycle monitoring
  void stopMonitoring() {
    _lifecycleTimer?.cancel();
    _lifecycleTimer = null;
    logDebug('Token lifecycle monitoring stopped', tag: 'TOKEN_LIFECYCLE');
  }

  /// Perform comprehensive health check
  Future<Map<String, dynamic>> _performHealthCheck() async {
    final healthResult = <String, dynamic>{};

    try {
      if (_secureStorage == null) {
        healthResult['error'] = 'Secure storage not initialized';
        return healthResult;
      }

      final now = DateTime.now();
      _lastHealthCheck = now;

      // Get security health status
      final securityStatus = await _secureStorage!.getSecurityHealthStatus();
      healthResult.addAll(securityStatus);

      // Check if token rotation is needed
      final shouldRotate = await _secureStorage!.shouldRotateTokens();
      healthResult['rotationNeeded'] = shouldRotate;

      if (shouldRotate) {
        logInfo('Token rotation recommended', tag: 'TOKEN_LIFECYCLE');
        healthResult['rotationRecommended'] = true;
      }

      // Check for suspicious activity
      final accessCount = securityStatus['accessCount'] as int? ?? 0;
      if (accessCount > _suspiciousAccessThreshold) {
        logWarning('Suspicious token access detected: $accessCount accesses',
            tag: 'TOKEN_LIFECYCLE');
        healthResult['suspiciousActivity'] = true;
      }

      // Check for tampering
      final tampered = securityStatus['tampered'] as bool? ?? false;
      if (tampered) {
        logError('Token tampering detected!', tag: 'TOKEN_LIFECYCLE');
        healthResult['tampered'] = true;
        await _handleSecurityBreach();
      }

      // Reset failed operations counter on successful health check
      _failedOperations = 0;
      healthResult['healthy'] = true;

      logDebug('Token health check completed successfully', tag: 'TOKEN_LIFECYCLE');
    } catch (e) {
      _failedOperations++;
      healthResult['error'] = e.toString();
      healthResult['failedOperations'] = _failedOperations;

      logError('Token health check failed: $e', tag: 'TOKEN_LIFECYCLE', error: e);

      if (_failedOperations >= _maxFailedAttempts) {
        logError('Maximum failed operations reached - triggering security protocol',
            tag: 'TOKEN_LIFECYCLE');
        await _handleSecurityBreach();
      }
    }

    return healthResult;
  }

  /// Handle security breach by clearing tokens and notifying
  Future<void> _handleSecurityBreach() async {
    try {
      logWarning('Security breach detected - clearing all tokens', tag: 'TOKEN_LIFECYCLE');

      if (_secureStorage != null) {
        await _secureStorage!.clearAllUserData();
      }

      // Reset counters
      _failedOperations = 0;

      // Notify user about security event through system notification
      await _notifyUserSecurityEvent(
        'Security Alert',
        'Suspicious activity detected. Your account has been secured.',
      );
    } catch (e) {
      logError('Failed to handle security breach: $e', tag: 'TOKEN_LIFECYCLE', error: e);
    }
  }

  /// Perform token rotation check
  Future<bool> checkTokenRotation() async {
    try {
      if (_secureStorage == null) {
        logWarning('Cannot check token rotation - secure storage not initialized',
            tag: 'TOKEN_LIFECYCLE');
        return false;
      }

      _lastRotationCheck = DateTime.now();
      final shouldRotate = await _secureStorage!.shouldRotateTokens();

      if (shouldRotate) {
        logInfo('Token rotation is recommended', tag: 'TOKEN_LIFECYCLE');
        // Trigger token rotation through API service
        final rotationResult = await _triggerTokenRotation();
        if (rotationResult) {
          logInfo('Token rotation completed successfully', tag: 'TOKEN_LIFECYCLE');
        } else {
          logWarning('Token rotation failed or was skipped', tag: 'TOKEN_LIFECYCLE');
        }
      }

      return shouldRotate;
    } catch (e) {
      logError('Token rotation check failed: $e', tag: 'TOKEN_LIFECYCLE', error: e);
      return false;
    }
  }

  /// Perform security audit
  Future<Map<String, dynamic>> performSecurityAudit() async {
    final auditResult = <String, dynamic>{};

    try {
      if (_secureStorage == null) {
        auditResult['error'] = 'Secure storage not initialized';
        return auditResult;
      }

      _lastSecurityAudit = DateTime.now();

      // Get comprehensive security status
      final healthStatus = await _performHealthCheck();
      auditResult['healthStatus'] = healthStatus;

      // Check token validity
      final hasValidTokens = await _secureStorage!.hasValidTokens();
      auditResult['hasValidTokens'] = hasValidTokens;

      // Get rotation status
      final lastRotation = await _secureStorage!.getLastRotationTime();
      auditResult['lastTokenRotation'] = lastRotation?.millisecondsSinceEpoch;

      // Calculate audit score (0-100)
      int score = 100;

      if (healthStatus['tampered'] == true) score -= 50;
      if (healthStatus['suspiciousActivity'] == true) score -= 20;
      if (healthStatus['rotationNeeded'] == true) score -= 15;
      if (!hasValidTokens) score -= 30;

      auditResult['securityScore'] = score;
      auditResult['auditTime'] = DateTime.now().millisecondsSinceEpoch;

      if (score < 70) {
        logWarning('Security audit failed with score: $score', tag: 'TOKEN_LIFECYCLE');
        auditResult['recommendedActions'] = _generateRecommendations(auditResult);
      } else {
        logInfo('Security audit passed with score: $score', tag: 'TOKEN_LIFECYCLE');
      }
    } catch (e) {
      auditResult['error'] = e.toString();
      logError('Security audit failed: $e', tag: 'TOKEN_LIFECYCLE', error: e);
    }

    return auditResult;
  }

  /// Generate security recommendations based on audit results
  List<String> _generateRecommendations(Map<String, dynamic> auditResult) {
    final recommendations = <String>[];

    if (auditResult['healthStatus']?['tampered'] == true) {
      recommendations.add('Immediate re-authentication required due to tampering detection');
    }

    if (auditResult['healthStatus']?['suspiciousActivity'] == true) {
      recommendations.add('Monitor for unusual access patterns');
    }

    if (auditResult['healthStatus']?['rotationNeeded'] == true) {
      recommendations.add('Token rotation recommended');
    }

    if (auditResult['hasValidTokens'] != true) {
      recommendations.add('Re-authentication required');
    }

    if (auditResult['securityScore'] < 50) {
      recommendations.add('Critical security issues detected - immediate action required');
    }

    return recommendations;
  }

  /// Get lifecycle statistics
  Future<Map<String, dynamic>> getLifecycleStats() async {
    return {
      'lastHealthCheck': _lastHealthCheck?.millisecondsSinceEpoch,
      'lastRotationCheck': _lastRotationCheck?.millisecondsSinceEpoch,
      'lastSecurityAudit': _lastSecurityAudit?.millisecondsSinceEpoch,
      'failedOperations': _failedOperations,
      'monitoringActive': _lifecycleTimer?.isActive ?? false,
      'healthCheckInterval': _healthCheckInterval.inMinutes,
      'rotationCheckInterval': _rotationCheckInterval.inHours,
    };
  }

  /// Force token cleanup (for logout or security breach)
  Future<void> forceTokenCleanup({required String reason}) async {
    try {
      logInfo('Forcing token cleanup: $reason', tag: 'TOKEN_LIFECYCLE');

      if (_secureStorage != null) {
        await _secureStorage!.clearAllUserData();
      }

      // Reset all counters and timers
      _failedOperations = 0;
      _lastHealthCheck = null;
      _lastRotationCheck = null;
      _lastSecurityAudit = null;

      logInfo('Token cleanup completed successfully', tag: 'TOKEN_LIFECYCLE');
    } catch (e) {
      logError('Failed to force token cleanup: $e', tag: 'TOKEN_LIFECYCLE', error: e);
      rethrow;
    }
  }

  /// Check if immediate action is required
  Future<bool> requiresImmediateAction() async {
    try {
      final healthStatus = await _performHealthCheck();

      return healthStatus['tampered'] == true ||
          healthStatus['error'] != null ||
          _failedOperations >= _maxFailedAttempts;
    } catch (e) {
      logError('Failed to check immediate action requirement: $e',
          tag: 'TOKEN_LIFECYCLE', error: e);
      return true; // Safe default - assume action is required
    }
  }

  /// Dispose resources
  void dispose() {
    stopMonitoring();
    _secureStorage = null;
    logDebug('Token lifecycle manager disposed', tag: 'TOKEN_LIFECYCLE');
  }

  /// Notify user about security events through local notifications
  Future<void> _notifyUserSecurityEvent(String title, String body) async {
    try {
      // Use the message service for consistent messaging
      final MessageService messageService = MessageService();

      // Show in-app notification
      messageService.showMessage(
        '$title - $body',
        type: MessageType.warning,
        duration: const Duration(seconds: 5),
      );

      // Also log for security audit
      logInfo('Security notification sent to user: $title', tag: 'TOKEN_LIFECYCLE');
    } catch (e) {
      logError('Failed to send security notification: $e', tag: 'TOKEN_LIFECYCLE');
    }
  }

  /// Trigger token rotation through API service
  Future<bool> _triggerTokenRotation() async {
    try {
      logInfo('Starting token rotation process', tag: 'TOKEN_LIFECYCLE');

      if (_secureStorage == null) {
        logWarning('Cannot rotate tokens - secure storage not initialized', tag: 'TOKEN_LIFECYCLE');
        return false;
      }

      // Get current refresh token
      final refreshToken = await _secureStorage!.getRefreshToken();
      if (refreshToken == null) {
        logWarning('No refresh token available for rotation', tag: 'TOKEN_LIFECYCLE');
        return false;
      }

      // Use ApiService to refresh tokens (this also rotates them)
      final ApiService apiService = ApiService();
      final newTokens = await apiService.refreshAccessToken();

      if (newTokens != null) {
        logInfo('Token rotation successful', tag: 'TOKEN_LIFECYCLE');
        _lastRotationCheck = DateTime.now();
        return true;
      } else {
        logWarning('Token rotation returned null response', tag: 'TOKEN_LIFECYCLE');
        return false;
      }
    } catch (e) {
      logError('Token rotation failed: $e', tag: 'TOKEN_LIFECYCLE', error: e);
      return false;
    }
  }
}

/// Token lifecycle events for monitoring and callbacks
enum TokenLifecycleEvent {
  initialized,
  healthCheckPassed,
  healthCheckFailed,
  rotationRecommended,
  securityBreachDetected,
  tokensCleared,
  auditCompleted,
}

/// Token lifecycle event data
class TokenLifecycleEventData {
  final TokenLifecycleEvent event;
  final DateTime timestamp;
  final Map<String, dynamic> data;
  final String? error;

  TokenLifecycleEventData({
    required this.event,
    required this.timestamp,
    required this.data,
    this.error,
  });

  Map<String, dynamic> toJson() => {
        'event': event.toString(),
        'timestamp': timestamp.millisecondsSinceEpoch,
        'data': data,
        if (error != null) 'error': error,
      };
}

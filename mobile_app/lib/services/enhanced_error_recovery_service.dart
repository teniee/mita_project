/*
Enhanced Error Recovery Service for MITA Flutter App
Provides advanced error recovery patterns, intelligent retry logic, and user experience continuity
*/

import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import '../core/error_handling.dart';
import '../core/app_error_handler.dart';
import 'logging_service.dart';

/// Enhanced error recovery service with intelligent recovery patterns
class EnhancedErrorRecoveryService {
  static EnhancedErrorRecoveryService? _instance;
  static EnhancedErrorRecoveryService get instance =>
      _instance ??= EnhancedErrorRecoveryService._();

  EnhancedErrorRecoveryService._();

  final Map<String, RecoveryContext> _recoveryContexts = {};
  final Map<String, Timer> _recoveryTimers = {};
  final Map<Type, RecoveryStrategy> _recoveryStrategies = {};

  /// Initialize the error recovery service
  void initialize() {
    _setupDefaultRecoveryStrategies();
    logInfo('Enhanced Error Recovery Service initialized',
        tag: 'ERROR_RECOVERY');
  }

  /// Set up default recovery strategies for common error types
  void _setupDefaultRecoveryStrategies() {
    // Network error recovery
    _recoveryStrategies[DioException] = NetworkRecoveryStrategy();

    // Authentication error recovery
    _recoveryStrategies[AuthenticationException] = AuthRecoveryStrategy();

    // Storage error recovery
    _recoveryStrategies[StorageException] = StorageRecoveryStrategy();

    // Validation error recovery
    _recoveryStrategies[ValidationException] = ValidationRecoveryStrategy();

    // Generic error recovery
    _recoveryStrategies[Exception] = GenericRecoveryStrategy();
  }

  /// Execute operation with enhanced error recovery
  Future<T?> executeWithRecovery<T>({
    required Future<T> Function() operation,
    required String operationId,
    String? operationName,
    int maxRetries = 3,
    Duration initialDelay = const Duration(seconds: 1),
    bool exponentialBackoff = true,
    List<Type>? retryableExceptions,
    T? fallbackValue,
    RecoveryOptions? customRecovery,
    VoidCallback? onRecoveryAttempt,
    void Function(T result)? onSuccess,
    void Function(dynamic error)? onFinalFailure,
  }) async {
    // Default retryable exceptions
    retryableExceptions ??= [
      DioException,
      TimeoutException,
      SocketException,
    ];

    final context = RecoveryContext(
      operationId: operationId,
      operationName: operationName ?? operationId,
      maxRetries: maxRetries,
      initialDelay: initialDelay,
      exponentialBackoff: exponentialBackoff,
      retryableExceptions: retryableExceptions,
      fallbackValue: fallbackValue,
      customRecovery: customRecovery,
    );

    _recoveryContexts[operationId] = context;

    try {
      for (int attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          logDebug(
              'Executing ${context.operationName} - Attempt $attempt/$maxRetries',
              tag: 'ERROR_RECOVERY');

          final result = await operation();

          // Success - clean up recovery context
          _cleanupRecoveryContext(operationId);
          onSuccess?.call(result);

          logInfo(
              'Operation ${context.operationName} succeeded on attempt $attempt',
              tag: 'ERROR_RECOVERY');
          return result;
        } catch (error, stackTrace) {
          context.addAttempt(error, stackTrace);

          bool shouldRetry =
              attempt < maxRetries && _shouldRetry(error, retryableExceptions);

          logWarning(
            'Error in ${context.operationName} - Attempt $attempt/$maxRetries: $error',
            tag: 'ERROR_RECOVERY',
          );

          // Report error with recovery context
          AppErrorHandler.reportError(
            error,
            stackTrace: stackTrace,
            severity: _determineSeverity(error, attempt, maxRetries),
            category: _categorizeError(error),
            context: {
              'operation': context.operationName,
              'operationId': operationId,
              'attempt': attempt,
              'maxRetries': maxRetries,
              'willRetry': shouldRetry,
              'recoveryContext': context.toJson(),
            },
          );

          if (shouldRetry) {
            // Attempt recovery before retry
            final recoveryResult = await _attemptRecovery(error, context);
            if (recoveryResult.shouldProceed) {
              onRecoveryAttempt?.call();

              // Calculate delay with optional exponential backoff
              Duration delay = exponentialBackoff
                  ? Duration(
                      milliseconds:
                          (initialDelay.inMilliseconds * (attempt * attempt))
                              .clamp(1000, 30000))
                  : initialDelay;

              logDebug(
                  'Retrying ${context.operationName} in ${delay.inSeconds}s after recovery attempt',
                  tag: 'ERROR_RECOVERY');
              await Future<void>.delayed(delay);
            } else {
              // Recovery failed, stop retrying
              logError(
                  'Recovery failed for ${context.operationName}, stopping retries',
                  tag: 'ERROR_RECOVERY');
              break;
            }
          } else {
            logError(
                'Final failure for ${context.operationName} after $attempt attempts',
                tag: 'ERROR_RECOVERY');
            break;
          }
        }
      }

      // All retries exhausted
      _cleanupRecoveryContext(operationId);
      onFinalFailure?.call(context.lastError);

      return fallbackValue;
    } catch (error, stackTrace) {
      // Unexpected error
      _cleanupRecoveryContext(operationId);

      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.critical,
        category: ErrorCategory.system,
        context: {
          'operation': context.operationName,
          'operationId': operationId,
          'phase': 'recovery_execution',
        },
      );

      onFinalFailure?.call(error);
      return fallbackValue;
    }
  }

  /// Attempt to recover from an error
  Future<RecoveryResult> _attemptRecovery(
      dynamic error, RecoveryContext context) async {
    try {
      // Use custom recovery if available
      if (context.customRecovery != null) {
        logDebug('Attempting custom recovery for ${context.operationName}',
            tag: 'ERROR_RECOVERY');
        return await context.customRecovery!.attemptRecovery(error, context);
      }

      // Find appropriate recovery strategy
      final strategy = _findRecoveryStrategy(error);
      if (strategy != null) {
        logDebug(
            'Attempting ${strategy.runtimeType} recovery for ${context.operationName}',
            tag: 'ERROR_RECOVERY');
        return await strategy.attemptRecovery(error, context);
      }

      // No recovery strategy available
      logDebug('No recovery strategy available for ${error.runtimeType}',
          tag: 'ERROR_RECOVERY');
      return RecoveryResult.proceed();
    } catch (recoveryError, stackTrace) {
      logError('Recovery attempt failed: $recoveryError',
          tag: 'ERROR_RECOVERY', error: recoveryError);

      AppErrorHandler.reportError(
        recoveryError,
        stackTrace: stackTrace,
        severity: ErrorSeverity.medium,
        category: ErrorCategory.system,
        context: {
          'operation': context.operationName,
          'originalError': error.toString(),
          'phase': 'recovery_attempt',
        },
      );

      return RecoveryResult.stop('Recovery failed: $recoveryError');
    }
  }

  /// Find appropriate recovery strategy for error type
  RecoveryStrategy? _findRecoveryStrategy(dynamic error) {
    // Check for exact type match
    final exactStrategy = _recoveryStrategies[error.runtimeType];
    if (exactStrategy != null) return exactStrategy;

    // Check for inheritance matches
    for (final entry in _recoveryStrategies.entries) {
      if (error.runtimeType.toString().contains(entry.key.toString())) {
        return entry.value;
      }
    }

    // Return generic strategy as fallback
    return _recoveryStrategies[Exception];
  }

  /// Determine error severity based on attempt and context
  ErrorSeverity _determineSeverity(dynamic error, int attempt, int maxRetries) {
    if (attempt == maxRetries) {
      return ErrorSeverity.high; // Final attempt failed
    } else if (error is DioException && error.response?.statusCode == 500) {
      return ErrorSeverity.high; // Server errors are high severity
    } else {
      return ErrorSeverity.medium; // Retryable errors are medium
    }
  }

  /// Categorize error for proper handling
  ErrorCategory _categorizeError(dynamic error) {
    if (error is DioException ||
        error is SocketException ||
        error is TimeoutException) {
      return ErrorCategory.network;
    } else if (error is AuthenticationException) {
      return ErrorCategory.authentication;
    } else if (error is ValidationException) {
      return ErrorCategory.validation;
    } else if (error is StorageException) {
      return ErrorCategory.storage;
    } else {
      return ErrorCategory.unknown;
    }
  }

  /// Check if error should trigger retry
  bool _shouldRetry(dynamic error, List<Type> retryableExceptions) {
    return retryableExceptions
        .any((type) => error.runtimeType == type || error is DioException);
  }

  /// Clean up recovery context
  void _cleanupRecoveryContext(String operationId) {
    _recoveryContexts.remove(operationId);
    _recoveryTimers[operationId]?.cancel();
    _recoveryTimers.remove(operationId);
  }

  /// Get recovery statistics
  Map<String, dynamic> getRecoveryStats() {
    return {
      'activeRecoveries': _recoveryContexts.length,
      'registeredStrategies': _recoveryStrategies.length,
      'activeTimers': _recoveryTimers.length,
      'recoveryContexts':
          _recoveryContexts.map((key, value) => MapEntry(key, value.toJson())),
    };
  }

  /// Register custom recovery strategy
  void registerRecoveryStrategy(Type errorType, RecoveryStrategy strategy) {
    _recoveryStrategies[errorType] = strategy;
    logInfo('Registered recovery strategy for ${errorType.toString()}',
        tag: 'ERROR_RECOVERY');
  }

  /// Dispose resources
  void dispose() {
    for (final timer in _recoveryTimers.values) {
      timer.cancel();
    }
    _recoveryTimers.clear();
    _recoveryContexts.clear();
    _recoveryStrategies.clear();
  }
}

/// Recovery context for tracking operation state
class RecoveryContext {
  final String operationId;
  final String operationName;
  final int maxRetries;
  final Duration initialDelay;
  final bool exponentialBackoff;
  final List<Type> retryableExceptions;
  final dynamic fallbackValue;
  final RecoveryOptions? customRecovery;

  final List<ErrorAttempt> attempts = [];
  dynamic lastError;
  StackTrace? lastStackTrace;
  DateTime startTime = DateTime.now();

  RecoveryContext({
    required this.operationId,
    required this.operationName,
    required this.maxRetries,
    required this.initialDelay,
    required this.exponentialBackoff,
    required this.retryableExceptions,
    required this.fallbackValue,
    this.customRecovery,
  });

  void addAttempt(dynamic error, StackTrace stackTrace) {
    attempts.add(ErrorAttempt(
      error: error,
      stackTrace: stackTrace,
      timestamp: DateTime.now(),
      attemptNumber: attempts.length + 1,
    ));
    lastError = error;
    lastStackTrace = stackTrace;
  }

  Map<String, dynamic> toJson() {
    return {
      'operationId': operationId,
      'operationName': operationName,
      'maxRetries': maxRetries,
      'initialDelay': initialDelay.inMilliseconds,
      'exponentialBackoff': exponentialBackoff,
      'attempts': attempts.length,
      'startTime': startTime.toIso8601String(),
      'lastError': lastError?.toString(),
    };
  }
}

/// Individual error attempt record
class ErrorAttempt {
  final dynamic error;
  final StackTrace stackTrace;
  final DateTime timestamp;
  final int attemptNumber;

  ErrorAttempt({
    required this.error,
    required this.stackTrace,
    required this.timestamp,
    required this.attemptNumber,
  });
}

/// Recovery result indicating next action
class RecoveryResult {
  final bool shouldProceed;
  final String? reason;
  final Duration? suggestedDelay;
  final Map<String, dynamic>? context;

  RecoveryResult({
    required this.shouldProceed,
    this.reason,
    this.suggestedDelay,
    this.context,
  });

  factory RecoveryResult.proceed(
      {Duration? delay, Map<String, dynamic>? context}) {
    return RecoveryResult(
      shouldProceed: true,
      suggestedDelay: delay,
      context: context,
    );
  }

  factory RecoveryResult.stop(String reason, {Map<String, dynamic>? context}) {
    return RecoveryResult(
      shouldProceed: false,
      reason: reason,
      context: context,
    );
  }
}

/// Abstract recovery strategy
abstract class RecoveryStrategy {
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context);
}

/// Custom recovery options interface
abstract class RecoveryOptions {
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context);
}

/// Network error recovery strategy
class NetworkRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    if (error is DioException) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.sendTimeout:
          // For timeout errors, suggest longer delay
          return RecoveryResult.proceed(
            delay: Duration(seconds: 5 + (context.attempts.length * 2)),
            context: {'recovery_type': 'timeout_backoff'},
          );

        case DioExceptionType.connectionError:
          // For connection errors, check network status
          // This could be expanded to actually check connectivity
          return RecoveryResult.proceed(
            delay: Duration(seconds: 3 + context.attempts.length),
            context: {'recovery_type': 'connection_retry'},
          );

        case DioExceptionType.badResponse:
          final statusCode = error.response?.statusCode;
          if (statusCode != null && statusCode >= 500) {
            // Server errors - retry with backoff
            return RecoveryResult.proceed(
              delay: Duration(seconds: 10 + (context.attempts.length * 5)),
              context: {'recovery_type': 'server_error_backoff'},
            );
          } else if (statusCode == 429) {
            // Rate limiting - wait longer
            return RecoveryResult.proceed(
              delay: Duration(seconds: 30 + (context.attempts.length * 15)),
              context: {'recovery_type': 'rate_limit_backoff'},
            );
          } else {
            // Client errors - don't retry
            return RecoveryResult.stop('Client error: $statusCode');
          }

        default:
          return RecoveryResult.proceed(
            context: {'recovery_type': 'generic_network'},
          );
      }
    }

    return RecoveryResult.proceed();
  }
}

/// Authentication error recovery strategy
class AuthRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    // This could attempt token refresh, re-authentication, etc.
    // For now, we'll just suggest stopping for auth errors
    return RecoveryResult.stop(
      'Authentication error requires user intervention',
      context: {'recovery_type': 'auth_intervention_required'},
    );
  }
}

/// Storage error recovery strategy
class StorageRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    // Could attempt to clear cache, check disk space, etc.
    return RecoveryResult.proceed(
      delay: Duration(seconds: 2),
      context: {'recovery_type': 'storage_retry'},
    );
  }
}

/// Validation error recovery strategy
class ValidationRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    // Validation errors typically shouldn't be retried
    return RecoveryResult.stop(
      'Validation error requires data correction',
      context: {'recovery_type': 'validation_no_retry'},
    );
  }
}

/// Generic error recovery strategy
class GenericRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    // Generic retry with simple backoff
    return RecoveryResult.proceed(
      delay: Duration(seconds: 1 + context.attempts.length),
      context: {'recovery_type': 'generic_backoff'},
    );
  }
}

/// Extension for easy error recovery integration
extension ErrorRecoveryExtension<T> on Future<T> {
  /// Execute with error recovery
  Future<T?> withRecovery({
    required String operationId,
    String? operationName,
    int maxRetries = 3,
    T? fallbackValue,
    RecoveryOptions? customRecovery,
    VoidCallback? onRecoveryAttempt,
    void Function(T result)? onSuccess,
    void Function(dynamic error)? onFinalFailure,
  }) async {
    return await EnhancedErrorRecoveryService.instance.executeWithRecovery<T>(
      operation: () => this,
      operationId: operationId,
      operationName: operationName,
      maxRetries: maxRetries,
      fallbackValue: fallbackValue,
      customRecovery: customRecovery,
      onRecoveryAttempt: onRecoveryAttempt,
      onSuccess: onSuccess,
      onFinalFailure: onFinalFailure,
    );
  }
}

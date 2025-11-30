import 'dart:async';
import 'package:dio/dio.dart';
import 'logging_service.dart';
import 'loading_service.dart';

/// Robust timeout manager with exponential backoff and intelligent retry logic
class TimeoutManagerService {
  static final TimeoutManagerService _instance = TimeoutManagerService._internal();
  factory TimeoutManagerService() => _instance;
  TimeoutManagerService._internal();

  // Timeout configurations - adjusted for slow backend (up to 90 seconds response times)
  static const Duration _shortTimeout = Duration(seconds: 10);
  static const Duration _mediumTimeout = Duration(seconds: 30);
  static const Duration _longTimeout = Duration(seconds: 90);
  static const Duration _maxTimeout = Duration(seconds: 120);

  // Retry configurations
  static const int _maxRetries = 3;
  static const Duration _baseRetryDelay = Duration(milliseconds: 500);
  static const double _backoffMultiplier = 2.0;

  /// Execute a function with timeout and retry logic
  Future<T> executeWithTimeout<T>({
    required Future<T> Function() operation,
    Duration? timeout,
    int? maxRetries,
    String? operationName,
    bool useLoading = true,
    bool enableRetry = true,
    List<Type>? retryOnExceptions,
  }) async {
    final effectiveTimeout = timeout ?? _mediumTimeout;
    final effectiveMaxRetries = enableRetry ? (maxRetries ?? _maxRetries) : 0;
    final name = operationName ?? 'API Operation';

    String? loadingId;
    if (useLoading) {
      loadingId = LoadingService.instance.start(
        timeout: effectiveTimeout,
        description: name,
      );
    }

    try {
      return await _executeWithRetry<T>(
        operation: operation,
        timeout: effectiveTimeout,
        maxRetries: effectiveMaxRetries,
        operationName: name,
        retryOnExceptions: retryOnExceptions,
      );
    } finally {
      if (loadingId != null) {
        LoadingService.instance.stop(loadingId);
      }
    }
  }

  /// Execute with exponential backoff retry
  Future<T> _executeWithRetry<T>({
    required Future<T> Function() operation,
    required Duration timeout,
    required int maxRetries,
    required String operationName,
    List<Type>? retryOnExceptions,
  }) async {
    int attempt = 0;
    Duration currentDelay = _baseRetryDelay;

    while (attempt <= maxRetries) {
      try {
        logDebug(
          'Executing $operationName (attempt ${attempt + 1}/${maxRetries + 1})',
          tag: 'TIMEOUT_MANAGER',
          extra: {
            'timeout_seconds': timeout.inSeconds,
            'attempt': attempt + 1,
            'max_attempts': maxRetries + 1,
          },
        );

        return await _executeWithTimeoutOnly<T>(
          operation: operation,
          timeout: timeout,
          operationName: operationName,
        );
      } catch (e) {
        final shouldRetry = attempt < maxRetries && _shouldRetryException(e, retryOnExceptions);

        if (shouldRetry) {
          logWarning(
            '$operationName failed, retrying in ${currentDelay.inMilliseconds}ms',
            tag: 'TIMEOUT_RETRY',
            extra: {
              'attempt': attempt + 1,
              'error': e.toString(),
              'retry_delay_ms': currentDelay.inMilliseconds,
              'remaining_attempts': maxRetries - attempt,
            },
          );

          await Future.delayed(currentDelay);
          currentDelay = Duration(
            milliseconds: (currentDelay.inMilliseconds * _backoffMultiplier).round(),
          );
          attempt++;
        } else {
          logError(
            '$operationName failed permanently',
            tag: 'TIMEOUT_MANAGER',
            extra: {
              'total_attempts': attempt + 1,
              'final_error': e.toString(),
            },
            error: e,
          );
          rethrow;
        }
      }
    }

    throw Exception('Maximum retries exceeded for $operationName');
  }

  /// Execute with timeout only (no retry)
  Future<T> _executeWithTimeoutOnly<T>({
    required Future<T> Function() operation,
    required Duration timeout,
    required String operationName,
  }) async {
    final completer = Completer<T>();
    late Timer timeoutTimer;

    // Set up timeout
    timeoutTimer = Timer(timeout, () {
      if (!completer.isCompleted) {
        final timeoutError = TimeoutException(
          '$operationName timed out after ${timeout.inSeconds} seconds',
          timeout,
        );
        completer.completeError(timeoutError);
      }
    });

    try {
      // Execute the operation
      final result = await operation();

      if (!completer.isCompleted) {
        completer.complete(result);
      }

      return await completer.future;
    } catch (e) {
      if (!completer.isCompleted) {
        completer.completeError(e);
      }
      rethrow;
    } finally {
      timeoutTimer.cancel();
    }
  }

  /// Determine if an exception should trigger a retry
  bool _shouldRetryException(dynamic exception, List<Type>? retryOnExceptions) {
    // If specific exceptions are specified, only retry on those
    if (retryOnExceptions != null && retryOnExceptions.isNotEmpty) {
      return retryOnExceptions.any((type) => exception.runtimeType == type);
    }

    // Default retry conditions
    if (exception is TimeoutException) return true;
    if (exception is DioException) {
      switch (exception.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.connectionError:
          return true;
        case DioExceptionType.badResponse:
          // Retry on server errors (5xx)
          final statusCode = exception.response?.statusCode;
          return statusCode != null && statusCode >= 500;
        default:
          return false;
      }
    }

    return false;
  }

  /// Quick timeout for non-critical operations
  Future<T> executeQuick<T>({
    required Future<T> Function() operation,
    String? operationName,
  }) async {
    return executeWithTimeout<T>(
      operation: operation,
      timeout: _shortTimeout,
      maxRetries: 1,
      operationName: operationName ?? 'Quick Operation',
    );
  }

  /// Long timeout for critical operations
  Future<T> executeCritical<T>({
    required Future<T> Function() operation,
    String? operationName,
  }) async {
    return executeWithTimeout<T>(
      operation: operation,
      timeout: _longTimeout,
      maxRetries: _maxRetries,
      operationName: operationName ?? 'Critical Operation',
    );
  }

  /// Execute without loading indicator (background operation)
  Future<T> executeBackground<T>({
    required Future<T> Function() operation,
    Duration? timeout,
    String? operationName,
  }) async {
    return executeWithTimeout<T>(
      operation: operation,
      timeout: timeout ?? _mediumTimeout,
      operationName: operationName ?? 'Background Operation',
      useLoading: false,
    );
  }

  /// Execute authentication operation with extended timeout
  Future<T> executeAuthentication<T>({
    required Future<T> Function() operation,
    String? operationName,
  }) async {
    return executeWithTimeout<T>(
      operation: operation,
      timeout: getRecommendedTimeout(OperationType.authentication),
      maxRetries: 1, // Reduced retries for slow server to avoid extremely long wait times
      operationName: operationName ?? 'Authentication Operation',
    );
  }

  /// Execute with fallback value on failure
  Future<T> executeWithFallback<T>({
    required Future<T> Function() operation,
    required T fallbackValue,
    Duration? timeout,
    String? operationName,
  }) async {
    try {
      return await executeWithTimeout<T>(
        operation: operation,
        timeout: timeout ?? _shortTimeout,
        maxRetries: 1,
        operationName: operationName ?? 'Operation with Fallback',
      );
    } catch (e) {
      logWarning(
        'Operation failed, using fallback value',
        tag: 'TIMEOUT_FALLBACK',
        extra: {
          'operation': operationName ?? 'Unknown',
          'error': e.toString(),
        },
      );
      return fallbackValue;
    }
  }

  /// Race multiple operations with timeout
  Future<T> raceWithTimeout<T>({
    required List<Future<T> Function()> operations,
    Duration? timeout,
    String? operationName,
  }) async {
    final effectiveTimeout = timeout ?? _mediumTimeout;
    final name = operationName ?? 'Race Operations';

    final loadingId = LoadingService.instance.start(
      timeout: effectiveTimeout,
      description: name,
    );

    try {
      final futures = operations.map((op) => op()).toList();
      return await Future.any(futures).timeout(effectiveTimeout);
    } catch (e) {
      if (e is TimeoutException) {
        logError('Race operation timed out: $name', tag: 'TIMEOUT_RACE');
      }
      rethrow;
    } finally {
      LoadingService.instance.stop(loadingId);
    }
  }

  /// Cancel all pending operations (emergency stop)
  void cancelAllOperations() {
    // Reset loading service to cancel all tracked operations
    LoadingService.instance.reset(reason: 'cancel_all_operations');

    logWarning(
      'All pending operations cancelled',
      tag: 'TIMEOUT_MANAGER',
    );
  }

  /// Get recommended timeout based on operation type - adjusted for slow backend
  Duration getRecommendedTimeout(OperationType type) {
    switch (type) {
      case OperationType.authentication:
        return const Duration(seconds: 90); // Increased to handle slow server
      case OperationType.dataSync:
        return const Duration(seconds: 45); // Increased from 10s
      case OperationType.fileUpload:
        return const Duration(seconds: 120); // Increased from 20s
      case OperationType.backgroundSync:
        return const Duration(seconds: 15); // Increased from 3s
      case OperationType.userAction:
        return const Duration(seconds: 30); // Increased from 6s
      case OperationType.criticalData:
        return const Duration(seconds: 60); // Increased from 15s
      default:
        return _mediumTimeout;
    }
  }

  /// Create a timeout-aware Dio instance
  Dio createTimeoutAwareDio({
    Duration? connectTimeout,
    Duration? receiveTimeout,
    Duration? sendTimeout,
  }) {
    return Dio(BaseOptions(
      connectTimeout: connectTimeout ?? _mediumTimeout,
      receiveTimeout: receiveTimeout ?? _mediumTimeout,
      sendTimeout: sendTimeout ?? _mediumTimeout,
    ));
  }
}

/// Operation types for timeout recommendations
enum OperationType {
  authentication,
  dataSync,
  fileUpload,
  backgroundSync,
  userAction,
  criticalData,
  quickAction,
}

/// Custom timeout exception with more context
class TimeoutException implements Exception {
  final String message;
  final Duration timeout;
  final DateTime occurredAt;

  TimeoutException(this.message, this.timeout) : occurredAt = DateTime.now();

  @override
  String toString() => 'TimeoutException: $message (timeout: ${timeout.inSeconds}s)';
}

/// Timeout configuration for specific operations
class TimeoutConfig {
  final Duration timeout;
  final int maxRetries;
  final Duration baseRetryDelay;
  final bool enableLoading;
  final List<Type> retryOnExceptions;

  const TimeoutConfig({
    required this.timeout,
    this.maxRetries = 3,
    this.baseRetryDelay = const Duration(milliseconds: 500),
    this.enableLoading = true,
    this.retryOnExceptions = const [],
  });

  static const TimeoutConfig quick = TimeoutConfig(
    timeout: Duration(seconds: 5),
    maxRetries: 1,
  );

  static const TimeoutConfig normal = TimeoutConfig(
    timeout: Duration(seconds: 10),
    maxRetries: 2,
  );

  static const TimeoutConfig critical = TimeoutConfig(
    timeout: Duration(seconds: 20),
    maxRetries: 3,
  );

  static const TimeoutConfig background = TimeoutConfig(
    timeout: Duration(seconds: 5),
    maxRetries: 1,
    enableLoading: false,
  );
}

import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';

import 'logging_service.dart';

/// Context describing one recoverable operation.
class RecoveryContext {
  final String operationId;
  final String operationName;
  final int maxRetries;
  final Duration initialDelay;
  final bool exponentialBackoff;
  final List<Type> retryableExceptions;
  final dynamic fallbackValue;
  final int attempt;

  const RecoveryContext({
    required this.operationId,
    this.operationName = '',
    this.maxRetries = 3,
    this.initialDelay = const Duration(seconds: 1),
    this.exponentialBackoff = true,
    this.retryableExceptions = const [],
    this.fallbackValue,
    this.attempt = 1,
  });

  RecoveryContext nextAttempt() => RecoveryContext(
        operationId: operationId,
        operationName: operationName,
        maxRetries: maxRetries,
        initialDelay: initialDelay,
        exponentialBackoff: exponentialBackoff,
        retryableExceptions: retryableExceptions,
        fallbackValue: fallbackValue,
        attempt: attempt + 1,
      );

  /// Backoff delay for the current attempt.
  Duration delayForAttempt() {
    if (!exponentialBackoff) return initialDelay;
    final multiplier = 1 << (attempt - 1); // 1, 2, 4, 8 ...
    return initialDelay * multiplier;
  }
}

/// Outcome of a strategy's recovery attempt.
class RecoveryResult {
  /// Whether the operation should be retried.
  final bool shouldProceed;

  /// How long to wait before the retry (null = retry immediately).
  final Duration? suggestedDelay;

  /// Optional strategy-specific metadata (diagnostics only).
  final Map<String, dynamic> context;

  const RecoveryResult({
    required this.shouldProceed,
    this.suggestedDelay,
    this.context = const {},
  });

  factory RecoveryResult.proceed({
    Duration? delay,
    Map<String, dynamic> context = const {},
  }) =>
      RecoveryResult(
        shouldProceed: true,
        suggestedDelay: delay,
        context: context,
      );

  factory RecoveryResult.abort({Map<String, dynamic> context = const {}}) =>
      RecoveryResult(shouldProceed: false, context: context);
}

/// A pluggable policy deciding whether/how to retry after a failure.
abstract class RecoveryStrategy {
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context);
}

/// Network failures: retry with (exponential) backoff. Client errors that a
/// retry cannot fix (4xx except 408/429) abort immediately.
class NetworkRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    if (error is DioException) {
      final status = error.response?.statusCode;
      if (status != null &&
          status >= 400 &&
          status < 500 &&
          status != 408 &&
          status != 429) {
        return RecoveryResult.abort(
          context: {'reason': 'non-retryable client error $status'},
        );
      }
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.connectionError:
          return RecoveryResult.proceed(
            delay: context.delayForAttempt(),
            context: {'recovery_type': 'network_backoff'},
          );
        default:
          return RecoveryResult.proceed(delay: context.delayForAttempt());
      }
    }
    if (error is SocketException || error is TimeoutException) {
      return RecoveryResult.proceed(
        delay: context.delayForAttempt(),
        context: {'recovery_type': 'network_backoff'},
      );
    }
    return RecoveryResult.proceed(delay: context.delayForAttempt());
  }
}

/// Timeouts: always worth one more try with growing delay.
class TimeoutRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    return RecoveryResult.proceed(
      delay: context.delayForAttempt(),
      context: {'recovery_type': 'timeout_backoff'},
    );
  }
}

/// Auth errors (401/403): retrying with the same credentials cannot help —
/// the caller must re-authenticate first.
class AuthRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    return RecoveryResult.abort(
        context: {'reason': 'reauthentication required'});
  }
}

/// Local storage/filesystem hiccups: a short fixed delay then retry.
class StorageRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    return RecoveryResult.proceed(
      delay: const Duration(milliseconds: 200),
      context: {'recovery_type': 'storage_retry'},
    );
  }
}

/// Central retry/recovery executor.
///
/// Wraps an async operation with strategy-driven retries, exponential
/// backoff and an optional fallback value, so network blips and transient
/// failures do not surface as user-facing errors.
class EnhancedErrorRecoveryService {
  EnhancedErrorRecoveryService._();

  static final EnhancedErrorRecoveryService instance =
      EnhancedErrorRecoveryService._();

  final Map<Type, RecoveryStrategy> _strategies = {};
  bool _initialized = false;
  int _recoveredOperations = 0;
  int _failedOperations = 0;

  /// Register the default strategy set. Idempotent.
  void initialize() {
    if (_initialized) return;
    _strategies[DioException] = NetworkRecoveryStrategy();
    _strategies[SocketException] = NetworkRecoveryStrategy();
    _strategies[TimeoutException] = TimeoutRecoveryStrategy();
    _strategies[FileSystemException] = StorageRecoveryStrategy();
    _initialized = true;
    logDebug('Error recovery service initialized '
        '(${_strategies.length} strategies)');
  }

  /// Register (or replace) the strategy for an exception type.
  void registerRecoveryStrategy(Type errorType, RecoveryStrategy strategy) {
    _strategies[errorType] = strategy;
  }

  Map<String, dynamic> getRecoveryStats() => {
        'registeredStrategies': _strategies.length,
        'recoveredOperations': _recoveredOperations,
        'failedOperations': _failedOperations,
      };

  RecoveryStrategy _strategyFor(dynamic error) {
    for (final entry in _strategies.entries) {
      if (error.runtimeType == entry.key) return entry.value;
    }
    // Subtype match (e.g. platform-specific SocketException subclasses).
    if (error is DioException && _strategies.containsKey(DioException)) {
      return _strategies[DioException]!;
    }
    if (error is SocketException && _strategies.containsKey(SocketException)) {
      return _strategies[SocketException]!;
    }
    if (error is TimeoutException &&
        _strategies.containsKey(TimeoutException)) {
      return _strategies[TimeoutException]!;
    }
    return NetworkRecoveryStrategy();
  }

  /// Run [operation]; on failure consult the matching strategy and retry up
  /// to [maxRetries] attempts in total. Returns [fallbackValue] (when
  /// provided) if every attempt fails, otherwise rethrows the last error.
  Future<T> executeWithRecovery<T>({
    required Future<T> Function() operation,
    required String operationId,
    String operationName = '',
    int maxRetries = 3,
    Duration initialDelay = const Duration(milliseconds: 50),
    bool exponentialBackoff = true,
    T? fallbackValue,
  }) async {
    var context = RecoveryContext(
      operationId: operationId,
      operationName: operationName,
      maxRetries: maxRetries,
      initialDelay: initialDelay,
      exponentialBackoff: exponentialBackoff,
      fallbackValue: fallbackValue,
    );

    Object? lastError;
    while (context.attempt <= maxRetries) {
      try {
        final result = await operation();
        if (context.attempt > 1) _recoveredOperations++;
        return result;
      } catch (error) {
        lastError = error;
        if (context.attempt >= maxRetries) break;

        final recovery = await _strategyFor(error).attemptRecovery(
          error,
          context,
        );
        if (!recovery.shouldProceed) break;

        final delay = recovery.suggestedDelay;
        if (delay != null && delay > Duration.zero) {
          await Future<void>.delayed(delay);
        }
        context = context.nextAttempt();
      }
    }

    _failedOperations++;
    logWarning(
      'Operation $operationId failed after ${context.attempt} attempt(s): '
      '$lastError',
      tag: 'ERROR_RECOVERY',
    );
    if (fallbackValue != null) return fallbackValue;
    // ignore: only_throw_errors
    throw lastError!;
  }
}

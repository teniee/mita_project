import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'logging_service.dart';

/// Enhanced loading service with timeout management and proper counter balancing
class LoadingService {
  LoadingService._();
  static final LoadingService instance = LoadingService._();

  final ValueNotifier<int> _counter = ValueNotifier<int>(0);
  final ValueNotifier<bool> _isForceHidden = ValueNotifier<bool>(false);

  // Track loading operations with unique IDs and timeouts
  final Map<String, LoadingOperation> _operations = {};
  final Duration _defaultTimeout = const Duration(seconds: 15);
  final Duration _maxLoadingTime = const Duration(seconds: 20); // Reduced for fast backend

  Timer? _timeoutWatchdog;
  DateTime? _firstLoadingStart;

  ValueNotifier<int> get notifier => _counter;
  ValueNotifier<bool> get forceHiddenNotifier => _isForceHidden;

  /// Start loading with optional timeout and unique identifier
  String start({
    String? operationId,
    Duration? timeout,
    String? description,
  }) {
    final id = operationId ?? _generateOperationId();
    final timeoutDuration = timeout ?? _defaultTimeout;

    // Track first loading start for global timeout
    _firstLoadingStart ??= DateTime.now();

    // Create operation tracker
    _operations[id] = LoadingOperation(
      id: id,
      description: description ?? 'Loading',
      startTime: DateTime.now(),
      timeout: timeoutDuration,
    );

    // Increment counter
    _counter.value++;

    // Set up operation timeout
    Timer(timeoutDuration, () {
      if (_operations.containsKey(id)) {
        logWarning(
          'Loading operation timed out: $description (${timeoutDuration.inSeconds}s)',
          tag: 'LOADING_TIMEOUT',
          extra: {'operation_id': id, 'timeout_seconds': timeoutDuration.inSeconds},
        );
        _forceStopOperation(id, reason: 'timeout');
      }
    });

    // Start watchdog timer if needed
    _startTimeoutWatchdog();

    logDebug(
      'Loading started: $description',
      tag: 'LOADING',
      extra: {'operation_id': id, 'total_operations': _operations.length},
    );

    return id;
  }

  /// Stop loading operation by ID
  void stop(String operationId) {
    if (_operations.containsKey(operationId)) {
      final operation = _operations[operationId]!;
      final duration = DateTime.now().difference(operation.startTime);

      logDebug(
        'Loading completed: ${operation.description} (${duration.inMilliseconds}ms)',
        tag: 'LOADING',
        extra: {'operation_id': operationId, 'duration_ms': duration.inMilliseconds},
      );

      _operations.remove(operationId);

      if (_counter.value > 0) {
        _counter.value--;
      }

      _checkStopWatchdog();
    }
  }

  /// Stop loading without ID (legacy support)
  void stopLegacy() {
    if (_counter.value > 0) {
      _counter.value--;
      logDebug('Legacy loading stopped', tag: 'LOADING');
    }
    _checkStopWatchdog();
  }

  /// Force stop an operation (for timeouts)
  void _forceStopOperation(String operationId, {required String reason}) {
    if (_operations.containsKey(operationId)) {
      final operation = _operations[operationId]!;
      logError(
        'Force stopping loading operation: ${operation.description} - $reason',
        tag: 'LOADING_FORCE_STOP',
        extra: {'operation_id': operationId, 'reason': reason},
      );

      _operations.remove(operationId);

      if (_counter.value > 0) {
        _counter.value--;
      }

      _checkStopWatchdog();
    }
  }

  /// Reset all loading states (emergency stop)
  void reset({String reason = 'manual_reset'}) {
    final hadOperations = _operations.isNotEmpty;
    final previousCounter = _counter.value;

    _operations.clear();
    _counter.value = 0;
    _isForceHidden.value = false;
    _firstLoadingStart = null;
    _stopTimeoutWatchdog();

    if (hadOperations || previousCounter > 0) {
      logWarning(
        'Loading service reset: $reason',
        tag: 'LOADING_RESET',
        extra: {
          'previous_counter': previousCounter,
          'active_operations': hadOperations ? 'yes' : 'no',
        },
      );
    }
  }

  /// Force hide loading overlay (emergency escape)
  void forceHide({String reason = 'user_action'}) {
    _isForceHidden.value = true;
    logWarning(
      'Loading overlay force hidden: $reason',
      tag: 'LOADING_FORCE_HIDE',
      extra: {'active_counter': _counter.value, 'active_operations': _operations.length},
    );

    // Auto-restore after a delay
    Timer(const Duration(seconds: 3), () {
      _isForceHidden.value = false;
    });
  }

  /// Start timeout watchdog to prevent infinite loading
  void _startTimeoutWatchdog() {
    _stopTimeoutWatchdog();

    _timeoutWatchdog = Timer.periodic(const Duration(seconds: 5), (timer) {
      final now = DateTime.now();

      // Check global timeout
      if (_firstLoadingStart != null &&
          now.difference(_firstLoadingStart!).compareTo(_maxLoadingTime) > 0) {
        logError(
          'Global loading timeout reached, force resetting all operations',
          tag: 'LOADING_GLOBAL_TIMEOUT',
          extra: {
            'max_timeout_seconds': _maxLoadingTime.inSeconds,
            'active_operations': _operations.length,
          },
        );
        reset(reason: 'global_timeout');
        return;
      }

      // Check individual operation timeouts
      final timedOutOperations = <String>[];
      _operations.forEach((id, operation) {
        if (now.difference(operation.startTime).compareTo(operation.timeout) > 0) {
          timedOutOperations.add(id);
        }
      });

      for (final id in timedOutOperations) {
        _forceStopOperation(id, reason: 'watchdog_timeout');
      }

      // Check for stuck counters (counter > 0 but no tracked operations)
      if (_counter.value > 0 && _operations.isEmpty) {
        logWarning(
          'Detected stuck loading counter, resetting',
          tag: 'LOADING_STUCK_COUNTER',
          extra: {'stuck_counter_value': _counter.value},
        );
        _counter.value = 0;
        _firstLoadingStart = null;
      }
    });
  }

  /// Stop timeout watchdog
  void _stopTimeoutWatchdog() {
    _timeoutWatchdog?.cancel();
    _timeoutWatchdog = null;
  }

  /// Check if we should stop the watchdog
  void _checkStopWatchdog() {
    if (_operations.isEmpty && _counter.value == 0) {
      _stopTimeoutWatchdog();
      _firstLoadingStart = null;
    }
  }

  /// Generate unique operation ID
  String _generateOperationId() {
    return 'op_${DateTime.now().millisecondsSinceEpoch}_${_operations.length}';
  }

  /// Get current loading status
  LoadingStatus getStatus() {
    return LoadingStatus(
      isLoading: _counter.value > 0,
      isForceHidden: _isForceHidden.value,
      activeOperations: _operations.length,
      counterValue: _counter.value,
      operations: List.from(_operations.values),
      globalLoadingDuration:
          _firstLoadingStart != null ? DateTime.now().difference(_firstLoadingStart!) : null,
    );
  }

  /// Check if should show loading (considering force hide)
  bool get shouldShowLoading => _counter.value > 0 && !_isForceHidden.value;

  /// Dispose resources
  void dispose() {
    _stopTimeoutWatchdog();
    _operations.clear();
    _counter.dispose();
    _isForceHidden.dispose();
  }
}

/// Loading operation tracker
class LoadingOperation {
  final String id;
  final String description;
  final DateTime startTime;
  final Duration timeout;

  LoadingOperation({
    required this.id,
    required this.description,
    required this.startTime,
    required this.timeout,
  });

  Duration get elapsedTime => DateTime.now().difference(startTime);
  bool get isTimedOut => elapsedTime.compareTo(timeout) > 0;
}

/// Loading status information
class LoadingStatus {
  final bool isLoading;
  final bool isForceHidden;
  final int activeOperations;
  final int counterValue;
  final List<LoadingOperation> operations;
  final Duration? globalLoadingDuration;

  LoadingStatus({
    required this.isLoading,
    required this.isForceHidden,
    required this.activeOperations,
    required this.counterValue,
    required this.operations,
    this.globalLoadingDuration,
  });

  bool get hasInconsistentState =>
      (counterValue > 0 && activeOperations == 0) || (counterValue == 0 && activeOperations > 0);

  @override
  String toString() {
    return 'LoadingStatus(loading: $isLoading, hidden: $isForceHidden, '
        'operations: $activeOperations, counter: $counterValue)';
  }
}

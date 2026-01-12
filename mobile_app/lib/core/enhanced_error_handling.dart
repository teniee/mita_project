/*
Enhanced Error Handling Extensions for MITA Flutter App
Provides additional error handling utilities and patterns for robust error management
*/

import 'dart:async';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../services/logging_service.dart';
import '../services/financial_error_service.dart';
import 'app_error_handler.dart';
import 'error_handling.dart';

/// Enhanced error handling patterns for Flutter operations
class EnhancedErrorHandling {
  /// Execute operation with comprehensive error handling and automatic retry
  static Future<T?> executeWithRetry<T>(
    Future<T> Function() operation, {
    String? operationName,
    int maxRetries = 3,
    Duration retryDelay = const Duration(seconds: 2),
    bool exponentialBackoff = true,
    List<Type> retryableExceptions = const [
      SocketException,
      TimeoutException,
      DioException,
    ],
    ErrorCategory category = ErrorCategory.unknown,
    T? fallbackValue,
  }) async {
    String opName = operationName ?? 'Unknown Operation';

    for (int attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        logDebug('Executing $opName - Attempt $attempt/$maxRetries',
            tag: 'ENHANCED_ERROR_HANDLING');
        return await operation();
      } catch (error, stackTrace) {
        bool shouldRetry = attempt < maxRetries &&
            retryableExceptions.any(
                (type) => error.runtimeType == type || error is DioException);

        logWarning(
          'Error in $opName - Attempt $attempt/$maxRetries: $error',
          tag: 'ENHANCED_ERROR_HANDLING',
        );

        // Report error to error handler
        AppErrorHandler.reportError(
          error,
          stackTrace: stackTrace,
          severity:
              attempt == maxRetries ? ErrorSeverity.high : ErrorSeverity.medium,
          category: category,
          context: {
            'operation': opName,
            'attempt': attempt,
            'maxRetries': maxRetries,
            'willRetry': shouldRetry,
          },
        );

        if (shouldRetry) {
          // Calculate delay with optional exponential backoff
          Duration delay = exponentialBackoff
              ? Duration(
                  milliseconds:
                      (retryDelay.inMilliseconds * (attempt * attempt))
                          .clamp(1000, 30000))
              : retryDelay;

          logDebug('Retrying $opName in ${delay.inSeconds}s',
              tag: 'ENHANCED_ERROR_HANDLING');
          await Future<void>.delayed(delay);
        } else {
          logError('Final failure for $opName after $attempt attempts',
              tag: 'ENHANCED_ERROR_HANDLING');
          return fallbackValue;
        }
      }
    }

    return fallbackValue;
  }

  /// Execute operation with timeout and circuit breaker pattern
  static Future<T?> executeWithCircuitBreaker<T>(
    Future<T> Function() operation, {
    Duration timeout = const Duration(seconds: 30),
    String? operationName,
    ErrorCategory category = ErrorCategory.unknown,
    T? fallbackValue,
  }) async {
    String opName = operationName ?? 'Circuit Breaker Operation';

    try {
      logDebug('Executing $opName with ${timeout.inSeconds}s timeout',
          tag: 'CIRCUIT_BREAKER');

      return await operation().timeout(timeout);
    } on TimeoutException catch (error, stackTrace) {
      logError('Timeout in $opName after ${timeout.inSeconds}s',
          tag: 'CIRCUIT_BREAKER');

      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.high,
        category: category,
        context: {
          'operation': opName,
          'timeout': timeout.inSeconds,
          'error_type': 'timeout',
        },
      );

      return fallbackValue;
    } catch (error, stackTrace) {
      logError('Error in $opName: $error',
          tag: 'CIRCUIT_BREAKER', error: error);

      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.high,
        category: category,
        context: {
          'operation': opName,
          'timeout': timeout.inSeconds,
          'error_type': 'general',
        },
      );

      return fallbackValue;
    }
  }

  /// Safe widget builder that catches and handles rendering errors
  static Widget safeBuilder(
    Widget Function() builder, {
    String? widgetName,
    Widget? fallbackWidget,
  }) {
    try {
      return builder();
    } catch (error) {
      String name = widgetName ?? 'Unknown Widget';

      logError('Widget rendering error in $name: $error',
          tag: 'SAFE_WIDGET_BUILDER', error: error);

      AppErrorHandler.reportUIError(
        error,
        widgetName: name,
        context: {
          'error_type': 'widget_rendering',
          'has_fallback': fallbackWidget != null,
        },
      );

      return fallbackWidget ?? const SizedBox.shrink();
    }
  }

  /// Enhanced network error handler with specific error categorization
  static String handleNetworkError(dynamic error) {
    if (error is DioException) {
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
          return 'Connection timeout. Please check your internet connection and try again.';
        case DioExceptionType.sendTimeout:
          return 'Upload timeout. Please check your connection and try again.';
        case DioExceptionType.receiveTimeout:
          return 'Response timeout. The server is taking too long to respond.';
        case DioExceptionType.badResponse:
          final statusCode = error.response?.statusCode;
          switch (statusCode) {
            case 400:
              return 'Invalid request. Please check your input and try again.';
            case 401:
              return 'Authentication required. Please log in again.';
            case 403:
              return 'Access denied. You don\'t have permission for this action.';
            case 404:
              return 'Resource not found. The requested data may no longer exist.';
            case 409:
              return 'Conflict detected. This action may have already been completed.';
            case 422:
              return 'Validation failed. Please check your input format.';
            case 429:
              return 'Too many requests. Please wait a moment and try again.';
            case 500:
              return 'Server error. Our team has been notified and is working on a fix.';
            case 502:
              return 'Service temporarily unavailable. Please try again in a few minutes.';
            case 503:
              return 'Service maintenance in progress. Please try again later.';
            default:
              return 'Network error ($statusCode). Please try again.';
          }
        case DioExceptionType.cancel:
          return 'Request was cancelled.';
        case DioExceptionType.connectionError:
          return 'Connection failed. Please check your internet connection.';
        case DioExceptionType.unknown:
        default:
          return 'Network error occurred. Please try again.';
      }
    } else if (error is SocketException) {
      return 'No internet connection. Please check your network settings.';
    } else if (error is TimeoutException) {
      return 'Operation timed out. Please try again.';
    } else if (error is HandshakeException) {
      return 'Secure connection failed. Please check your internet connection.';
    } else {
      return 'Network error: ${error.toString()}';
    }
  }
}

/// Enhanced error handling widget wrapper
class RobustErrorBoundary extends StatelessWidget {
  final Widget child;
  final String? name;
  final Widget Function(
      BuildContext context, Object error, StackTrace? stackTrace)? errorBuilder;
  final VoidCallback? onRetry;
  final bool showRetryButton;
  final ErrorCategory category;

  const RobustErrorBoundary({
    super.key,
    required this.child,
    this.name,
    this.errorBuilder,
    this.onRetry,
    this.showRetryButton = true,
    this.category = ErrorCategory.ui,
  });

  @override
  Widget build(BuildContext context) {
    return AppErrorBoundary(
      screenName: name,
      child: child,
    );
  }
}

/// Mixin for screens requiring robust error handling with financial context
mixin RobustErrorHandlingMixin<T extends StatefulWidget> on State<T> {
  bool _isLoading = false;
  String? _errorMessage;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  /// Access to financial error service
  FinancialErrorService get errorService => FinancialErrorService.instance;

  /// Execute an async operation with comprehensive error handling
  Future<U?> executeRobustly<U>(
    Future<U> Function() operation, {
    String? operationName,
    bool showLoadingState = true,
    bool showErrorState = true,
    U? fallbackValue,
    VoidCallback? onSuccess,
    VoidCallback? onError,
  }) async {
    final String opName = operationName ?? 'Operation';

    if (showLoadingState) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });
    }

    try {
      logDebug('Executing robust operation: $opName', tag: 'ROBUST_MIXIN');

      final result = await EnhancedErrorHandling.executeWithRetry<U>(
        operation,
        operationName: opName,
        category: ErrorCategory.ui,
        fallbackValue: fallbackValue,
      );

      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = null;
        });

        onSuccess?.call();
      }

      return result;
    } catch (error, stackTrace) {
      logError('Robust operation failed: $opName - $error',
          tag: 'ROBUST_MIXIN', error: error);

      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.medium,
        category: ErrorCategory.ui,
        context: {
          'widget': T.toString(),
          'operation': opName,
        },
      );

      if (mounted && showErrorState) {
        setState(() {
          _isLoading = false;
          _errorMessage = EnhancedErrorHandling.handleNetworkError(error);
        });
      }

      onError?.call();
      return fallbackValue;
    }
  }

  /// Clear error state
  void clearError() {
    if (mounted && _errorMessage != null) {
      setState(() {
        _errorMessage = null;
      });
    }
  }

  /// Show enhanced error dialog with financial context and retry functionality
  Future<void> showEnhancedErrorDialog(
    String title,
    String message, {
    VoidCallback? onRetry,
    bool canRetry = true,
    Map<String, dynamic>? additionalContext,
  }) async {
    if (!mounted) return;

    // Create error with financial context
    final error = Exception(message);

    await errorService.showError(
      context,
      error,
      additionalContext: {
        'screen': T.toString(),
        'title': title,
        'can_retry': canRetry,
        ...?additionalContext,
      },
      onRetry: onRetry,
      forceDialog: true,
    );
  }

  /// Build error state widget
  Widget buildErrorState({
    String? title,
    String? message,
    VoidCallback? onRetry,
    IconData? icon,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon ?? Icons.error_outline_rounded,
              size: 64,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              title ?? 'Something went wrong',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              message ??
                  _errorMessage ??
                  'An unexpected error occurred. Please try again.',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            if (onRetry != null)
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Try Again'),
                style: FilledButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// Build loading state widget
  Widget buildLoadingState({String? message}) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(
            color: Theme.of(context).colorScheme.primary,
          ),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(
              message,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }
}

/// Enhanced error handling for form validation
class FormErrorHandler {
  static final Map<String, String> _fieldErrors = {};

  /// Add field-specific error
  static void addFieldError(String field, String message) {
    _fieldErrors[field] = message;

    AppErrorHandler.reportValidationError(
      message,
      field: field,
      context: {
        'validation_type': 'field_error',
        'field_count': _fieldErrors.length,
      },
    );
  }

  /// Get field error
  static String? getFieldError(String field) {
    return _fieldErrors[field];
  }

  /// Clear field error
  static void clearFieldError(String field) {
    _fieldErrors.remove(field);
  }

  /// Clear all errors
  static void clearAllErrors() {
    _fieldErrors.clear();
  }

  /// Check if form has errors
  static bool hasErrors() {
    return _fieldErrors.isNotEmpty;
  }

  /// Get all errors
  static Map<String, String> getAllErrors() {
    return Map.from(_fieldErrors);
  }

  /// Validate email with enhanced error reporting
  static String? validateEmail(String? value, {bool reportError = true}) {
    if (value == null || value.isEmpty) {
      const error = 'Email is required';
      if (reportError) addFieldError('email', error);
      return error;
    }

    final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    if (!emailRegex.hasMatch(value)) {
      const error = 'Please enter a valid email address';
      if (reportError) addFieldError('email', error);
      return error;
    }

    if (reportError) clearFieldError('email');
    return null;
  }

  /// Validate password with enhanced error reporting
  static String? validatePassword(String? value, {bool reportError = true}) {
    if (value == null || value.isEmpty) {
      const error = 'Password is required';
      if (reportError) addFieldError('password', error);
      return error;
    }

    if (value.length < 8) {
      const error = 'Password must be at least 8 characters long';
      if (reportError) addFieldError('password', error);
      return error;
    }

    if (!RegExp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)').hasMatch(value)) {
      const error = 'Password must contain uppercase, lowercase, and number';
      if (reportError) addFieldError('password', error);
      return error;
    }

    if (reportError) clearFieldError('password');
    return null;
  }
}

/// Extension methods for easier error handling
extension SafeAsyncExecution<T> on Future<T> {
  /// Execute with automatic error handling and retry
  Future<T?> executeSafely({
    String? operationName,
    T? fallbackValue,
    int maxRetries = 1,
    ErrorCategory category = ErrorCategory.unknown,
  }) async {
    return await EnhancedErrorHandling.executeWithRetry<T>(
      () => this,
      operationName: operationName,
      fallbackValue: fallbackValue,
      maxRetries: maxRetries,
      category: category,
    );
  }

  /// Execute with circuit breaker
  Future<T?> executeWithBreaker({
    Duration timeout = const Duration(seconds: 30),
    String? operationName,
    T? fallbackValue,
    ErrorCategory category = ErrorCategory.unknown,
  }) async {
    return await EnhancedErrorHandling.executeWithCircuitBreaker<T>(
      () => this,
      timeout: timeout,
      operationName: operationName,
      fallbackValue: fallbackValue,
      category: category,
    );
  }
}

/// Extension for BuildContext error handling with financial context
extension ContextErrorHandling on BuildContext {
  /// Access to financial error service
  FinancialErrorService get errorService => FinancialErrorService.instance;

  /// Show enhanced error with financial context
  Future<void> showErrorSnack(
    dynamic error, {
    VoidCallback? onRetry,
    Duration duration = const Duration(seconds: 4),
    Map<String, dynamic>? context,
  }) async {
    await errorService.showError(
      this,
      error,
      additionalContext: context,
      onRetry: onRetry,
    );
  }

  /// Show success snackbar with financial context
  void showSuccessSnack(
    String message, {
    Duration duration = const Duration(seconds: 3),
    String? financialContext,
  }) {
    errorService.showSuccess(
      this,
      message,
      financialContext: financialContext,
      duration: duration,
    );
  }

  /// Show financial warning
  void showFinancialWarning(
    String title,
    String message, {
    String? financialContext,
    List<String>? tips,
    VoidCallback? onAction,
    String? actionLabel,
  }) {
    errorService.showWarning(
      this,
      title,
      message,
      financialContext: financialContext,
      tips: tips,
      onAction: onAction,
      actionLabel: actionLabel,
    );
  }
}

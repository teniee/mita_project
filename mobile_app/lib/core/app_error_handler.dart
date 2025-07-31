/*
Application-wide Error Handler Setup
Initializes and configures the error handling system for the MITA app
*/

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'error_handling.dart';

class AppErrorHandler {
  static bool _initialized = false;

  /// Initialize the error handling system
  static Future<void> initialize({String? userId}) async {
    if (_initialized) return;

    try {
      // Initialize the error handler
      await ErrorHandler.instance.initialize(userId: userId);
      
      _initialized = true;
      debugPrint('AppErrorHandler initialized successfully');
    } catch (e) {
      debugPrint('Failed to initialize AppErrorHandler: $e');
    }
  }

  /// Update user ID for error tracking
  static void updateUserId(String? userId) {
    if (_initialized) {
      ErrorHandler.instance.updateUserId(userId);
    }
  }

  /// Get error statistics
  static Map<String, dynamic> getErrorStats() {
    if (_initialized) {
      return ErrorHandler.instance.getErrorStats();
    }
    return {};
  }

  /// Manually report an error with context
  static void reportError(
    dynamic error, {
    StackTrace? stackTrace,
    ErrorSeverity severity = ErrorSeverity.medium,
    ErrorCategory category = ErrorCategory.unknown,
    Map<String, dynamic>? context,
  }) {
    if (_initialized) {
      ErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: severity,
        category: category,
        context: context,
      );
    } else {
      debugPrint('Error reported before initialization: $error');
    }
  }

  /// Report network-related errors
  static void reportNetworkError(
    dynamic error, {
    String? endpoint,
    int? statusCode,
    Map<String, dynamic>? requestData,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.medium,
      category: ErrorCategory.network,
      context: {
        'endpoint': endpoint,
        'statusCode': statusCode,
        'requestData': requestData,
      },
    );
  }

  /// Report authentication errors
  static void reportAuthError(
    dynamic error, {
    String? action,
    Map<String, dynamic>? context,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.high,
      category: ErrorCategory.authentication,
      context: {
        'action': action,
        ...?context,
      },
    );
  }

  /// Report UI/UX related errors
  static void reportUIError(
    dynamic error, {
    String? widgetName,
    String? screenName,
    Map<String, dynamic>? context,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.medium,
      category: ErrorCategory.ui,
      context: {
        'widgetName': widgetName,
        'screenName': screenName,
        ...?context,
      },
    );
  }

  /// Report storage/database errors
  static void reportStorageError(
    dynamic error, {
    String? operation,
    String? tableName,
    Map<String, dynamic>? context,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.medium,
      category: ErrorCategory.storage,
      context: {
        'operation': operation,
        'tableName': tableName,
        ...?context,
      },
    );
  }

  /// Report validation errors
  static void reportValidationError(
    String message, {
    String? field,
    dynamic value,
    Map<String, dynamic>? context,
  }) {
    reportError(
      message,
      severity: ErrorSeverity.low,
      category: ErrorCategory.validation,
      context: {
        'field': field,
        'value': value?.toString(),
        ...?context,
      },
    );
  }

  /// Clean up resources
  static void dispose() {
    if (_initialized) {
      ErrorHandler.instance.dispose();
      _initialized = false;
    }
  }
}

/// Wrapper widget that provides error boundaries for the entire app
class AppErrorBoundary extends StatelessWidget {
  final Widget child;
  final String? screenName;

  const AppErrorBoundary({
    Key? key,
    required this.child,
    this.screenName,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ErrorBoundary(
      onError: (error, stackTrace) {
        AppErrorHandler.reportUIError(
          error,
          screenName: screenName,
          context: {
            'route': ModalRoute.of(context)?.settings.name,
            'timestamp': DateTime.now().toIso8601String(),
          },
        );
      },
      errorBuilder: (context, error, stackTrace) {
        return _buildErrorScreen(context, error, stackTrace);
      },
      child: child,
    );
  }

  Widget _buildErrorScreen(BuildContext context, Object error, StackTrace? stackTrace) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.error_outline_rounded,
                size: 80,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 24),
              Text(
                'Oops! Something went wrong',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              Text(
                'We\'ve been notified about this issue and are working to fix it. Please try again.',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    // Try to rebuild the widget tree
                    if (context.mounted) {
                      Navigator.of(context).pushReplacementNamed('/');
                    }
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try Again'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () {
                    if (context.mounted) {
                      Navigator.of(context).pushNamedAndRemoveUntil(
                        '/',
                        (route) => false,
                      );
                    }
                  },
                  icon: const Icon(Icons.home),
                  label: const Text('Go to Home'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              // Show error details in debug mode
              if (kDebugMode) ...[
                ExpansionTile(
                  title: const Text('Error Details'),
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      margin: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surfaceVariant,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Error:',
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              error.toString(),
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                fontFamily: 'monospace',
                              ),
                            ),
                            if (stackTrace != null) ...[
                              const SizedBox(height: 16),
                              Text(
                                'Stack Trace:',
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                stackTrace.toString(),
                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Extension methods for easier error reporting
extension ErrorReporting on Exception {
  void report({
    ErrorSeverity severity = ErrorSeverity.medium,
    ErrorCategory category = ErrorCategory.unknown,
    Map<String, dynamic>? context,
  }) {
    AppErrorHandler.reportError(
      this,
      severity: severity,
      category: category,
      context: context,
    );
  }
}

/// Mixin for widgets that need error handling
mixin ErrorHandlingMixin<T extends StatefulWidget> on State<T> {
  void handleError(
    dynamic error, {
    ErrorSeverity severity = ErrorSeverity.medium,
    ErrorCategory category = ErrorCategory.ui,
    Map<String, dynamic>? context,
  }) {
    AppErrorHandler.reportError(
      error,
      severity: severity,
      category: category,
      context: {
        'widget': T.toString(),
        'screen': widget.runtimeType.toString(),
        ...?context,
      },
    );
  }

  void handleNetworkError(dynamic error, String endpoint) {
    AppErrorHandler.reportNetworkError(
      error,
      endpoint: endpoint,
      context: {
        'widget': T.toString(),
        'screen': widget.runtimeType.toString(),
      },
    );
  }

  void handleValidationError(String field, String message) {
    AppErrorHandler.reportValidationError(
      message,
      field: field,
      context: {
        'widget': T.toString(),
        'screen': widget.runtimeType.toString(),
      },
    );
  }
}

/// Safe execution wrapper that catches and reports errors
class SafeExecution {
  static Future<T?> run<T>(
    Future<T> Function() operation, {
    String? operationName,
    ErrorCategory category = ErrorCategory.unknown,
    T? fallbackValue,
    bool rethrow = false,
  }) async {
    try {
      return await operation();
    } catch (error, stackTrace) {
      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.medium,
        category: category,
        context: {
          'operation': operationName,
          'hasFallback': fallbackValue != null,
        },
      );

      if (rethrow) {
        rethrow;
      }

      return fallbackValue;
    }
  }

  static T? runSync<T>(
    T Function() operation, {
    String? operationName,
    ErrorCategory category = ErrorCategory.unknown,
    T? fallbackValue,
    bool rethrow = false,
  }) {
    try {
      return operation();
    } catch (error, stackTrace) {
      AppErrorHandler.reportError(
        error,
        stackTrace: stackTrace,
        severity: ErrorSeverity.medium,
        category: category,
        context: {
          'operation': operationName,
          'hasFallback': fallbackValue != null,
        },
      );

      if (rethrow) {
        rethrow;
      }

      return fallbackValue;
    }
  }
}

/// Utility for showing user-friendly error messages
class ErrorMessageUtils {
  static String getUserFriendlyMessage(dynamic error) {
    if (error is NetworkException) {
      return 'Please check your internet connection and try again.';
    } else if (error is AuthenticationException) {
      return 'Please log in again to continue.';
    } else if (error is ValidationException) {
      return 'Please check your input and try again.';
    } else if (error is StorageException) {
      return 'Unable to save your data. Please try again.';
    } else {
      return 'Something went wrong. Please try again.';
    }
  }

  static void showErrorSnackBar(
    BuildContext context,
    dynamic error, {
    Duration duration = const Duration(seconds: 4),
  }) {
    if (!context.mounted) return;

    final message = getUserFriendlyMessage(error);
    
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              Icons.error_outline,
              color: Theme.of(context).colorScheme.onError,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onError,
                ),
              ),
            ),
          ],
        ),
        backgroundColor: Theme.of(context).colorScheme.error,
        duration: duration,
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: 'Dismiss',
          textColor: Theme.of(context).colorScheme.onError,
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
          },
        ),
      ),
    );
  }
}

// Custom exception types for better error categorization
class NetworkException implements Exception {
  final String message;
  final int? statusCode;
  final String? endpoint;

  NetworkException(this.message, {this.statusCode, this.endpoint});

  @override
  String toString() => 'NetworkException: $message';
}

class AuthenticationException implements Exception {
  final String message;
  final String? action;

  AuthenticationException(this.message, {this.action});

  @override
  String toString() => 'AuthenticationException: $message';
}

class ValidationException implements Exception {
  final String message;
  final String? field;

  ValidationException(this.message, {this.field});

  @override
  String toString() => 'ValidationException: $message';
}

class StorageException implements Exception {
  final String message;
  final String? operation;

  StorageException(this.message, {this.operation});

  @override
  String toString() => 'StorageException: $message';
}
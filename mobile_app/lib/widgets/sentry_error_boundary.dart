import 'dart:developer' as dev;
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import '../services/sentry_service.dart';

/// Enhanced error boundary widget with comprehensive Sentry integration
class SentryErrorBoundary extends StatefulWidget {
  const SentryErrorBoundary({
    super.key,
    required this.child,
    required this.screenName,
    this.userId,
    this.additionalContext,
    this.onError,
    this.fallbackWidget,
  });

  final Widget child;
  final String screenName;
  final String? userId;
  final Map<String, dynamic>? additionalContext;
  final void Function(Object error, StackTrace stackTrace)? onError;
  final Widget Function(Object error)? fallbackWidget;

  @override
  State<SentryErrorBoundary> createState() => _SentryErrorBoundaryState();
}

class _SentryErrorBoundaryState extends State<SentryErrorBoundary> {
  Object? _error;
  StackTrace? _stackTrace; // Kept for potential future use

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return widget.fallbackWidget?.call(_error!) ??
          _DefaultErrorWidget(
            error: _error!,
            screenName: widget.screenName,
            onRetry: _clearError,
          );
    }

    return ErrorBoundary(
      onError: _handleError,
      child: widget.child,
    );
  }

  void _handleError(Object error, StackTrace stackTrace) {
    setState(() {
      _error = error;
      _stackTrace = stackTrace;
    });

    // Report to all error monitoring services
    _reportError(error, stackTrace);

    // Call custom error handler if provided
    widget.onError?.call(error, stackTrace);
  }

  Future<void> _reportError(Object error, StackTrace stackTrace) async {
    try {
      // Determine error category based on error type and screen
      final category = _categorizeError(error, widget.screenName);
      final severity = _determineSeverity(error);

      // Report to Sentry with comprehensive context
      await sentryService.captureFinancialError(
        error,
        category: category,
        severity: severity,
        stackTrace: stackTrace.toString(),
        userId: widget.userId,
        screenName: widget.screenName,
        additionalContext: {
          'error_boundary': true,
          'screen_name': widget.screenName,
          'user_triggered': true,
          'recovery_possible': true,
          ...?widget.additionalContext,
        },
        tags: {
          'error_boundary': 'true',
          'screen': widget.screenName,
          'recoverable': 'true',
        },
      );

      // Add breadcrumb for error boundary activation
      sentryService.addFinancialBreadcrumb(
        message: 'Error boundary activated on ${widget.screenName}',
        category: 'error_boundary',
        level: SentryLevel.error,
        data: {
          'screen_name': widget.screenName,
          'error_type': error.runtimeType.toString(),
          'user_id': widget.userId,
        },
      );
    } catch (e) {
      // Don't let error reporting crash the error boundary
      if (kDebugMode) {
        dev.log('Failed to report error to Sentry: $e',
            name: 'SentryErrorBoundary');
      }
    }
  }

  FinancialErrorCategory _categorizeError(Object error, String screenName) {
    // Categorize based on error type
    if (error.toString().toLowerCase().contains('auth')) {
      return FinancialErrorCategory.authentication;
    } else if (error.toString().toLowerCase().contains('permission')) {
      return FinancialErrorCategory.authorization;
    } else if (error.toString().toLowerCase().contains('network') ||
        error.toString().toLowerCase().contains('http')) {
      return FinancialErrorCategory.networkError;
    } else if (error.toString().toLowerCase().contains('transaction')) {
      return FinancialErrorCategory.transactionProcessing;
    } else if (error.toString().toLowerCase().contains('payment')) {
      return FinancialErrorCategory.paymentProcessing;
    } else if (error.toString().toLowerCase().contains('validation')) {
      return FinancialErrorCategory.dataValidation;
    }

    // Categorize based on screen name
    final lowerScreenName = screenName.toLowerCase();
    if (lowerScreenName.contains('login') ||
        lowerScreenName.contains('register') ||
        lowerScreenName.contains('auth')) {
      return FinancialErrorCategory.authentication;
    } else if (lowerScreenName.contains('transaction') ||
        lowerScreenName.contains('expense') ||
        lowerScreenName.contains('payment')) {
      return FinancialErrorCategory.transactionProcessing;
    } else if (lowerScreenName.contains('budget') ||
        lowerScreenName.contains('goal')) {
      return FinancialErrorCategory.budgetCalculation;
    } else if (lowerScreenName.contains('profile') ||
        lowerScreenName.contains('account')) {
      return FinancialErrorCategory.accountManagement;
    }

    return FinancialErrorCategory.uiError;
  }

  FinancialSeverity _determineSeverity(Object error) {
    final errorString = error.toString().toLowerCase();

    // Critical errors
    if (errorString.contains('security') ||
        errorString.contains('unauthorized') ||
        errorString.contains('payment') ||
        errorString.contains('transaction failed')) {
      return FinancialSeverity.critical;
    }

    // High severity errors
    if (errorString.contains('auth') ||
        errorString.contains('network') ||
        errorString.contains('database') ||
        errorString.contains('server')) {
      return FinancialSeverity.high;
    }

    // Medium severity for UI errors
    return FinancialSeverity.medium;
  }

  void _clearError() {
    setState(() {
      _error = null;
      _stackTrace = null;
    });

    // Add breadcrumb for error recovery
    sentryService.addFinancialBreadcrumb(
      message: 'User recovered from error on ${widget.screenName}',
      category: 'error_recovery',
      level: SentryLevel.info,
      data: {
        'screen_name': widget.screenName,
        'recovery_method': 'user_retry',
        'user_id': widget.userId,
      },
    );
  }
}

/// Simple error boundary that catches Flutter errors
class ErrorBoundary extends StatefulWidget {
  const ErrorBoundary({
    super.key,
    required this.child,
    required this.onError,
  });

  final Widget child;
  final void Function(Object error, StackTrace stackTrace) onError;

  @override
  State<ErrorBoundary> createState() => _ErrorBoundaryState();
}

class _ErrorBoundaryState extends State<ErrorBoundary> {
  @override
  Widget build(BuildContext context) {
    return Builder(
      builder: (context) {
        try {
          return widget.child;
        } catch (error, stackTrace) {
          // This catches synchronous errors during build
          widget.onError(error, stackTrace);
          rethrow;
        }
      },
    );
  }
}

/// Default error widget shown when an error boundary is triggered
class _DefaultErrorWidget extends StatelessWidget {
  const _DefaultErrorWidget({
    required this.error,
    required this.screenName,
    required this.onRetry,
  });

  final Object error;
  final String screenName;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Oops! Something went wrong'),
        backgroundColor: theme.colorScheme.errorContainer,
        foregroundColor: theme.colorScheme.onErrorContainer,
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline_rounded,
              size: 80,
              color: theme.colorScheme.error,
            ),
            const SizedBox(height: 24),
            Text(
              'Something went wrong',
              style: theme.textTheme.headlineSmall?.copyWith(
                color: theme.colorScheme.error,
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            Text(
              'We\'re sorry, but something unexpected happened on the $screenName screen. '
              'Our team has been notified and will work to fix this issue.',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try Again'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () {
                Navigator.of(context).pushNamedAndRemoveUntil(
                  '/',
                  (route) => false,
                );
              },
              child: const Text('Go to Home'),
            ),
            if (kDebugMode) ...[
              const SizedBox(height: 24),
              const Divider(),
              const SizedBox(height: 16),
              Text(
                'Debug Info:',
                style: theme.textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  error.toString(),
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Enhanced AppErrorBoundary that replaces the existing one
class EnhancedAppErrorBoundary extends StatelessWidget {
  const EnhancedAppErrorBoundary({
    super.key,
    required this.child,
    required this.screenName,
    this.userId,
    this.additionalContext,
    this.onError,
  });

  final Widget child;
  final String screenName;
  final String? userId;
  final Map<String, dynamic>? additionalContext;
  final void Function(Object error, StackTrace stackTrace)? onError;

  @override
  Widget build(BuildContext context) {
    return SentryErrorBoundary(
      screenName: screenName,
      userId: userId,
      additionalContext: additionalContext,
      onError: onError,
      child: child,
    );
  }
}

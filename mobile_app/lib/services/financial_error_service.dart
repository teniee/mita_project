/*
Financial Error Management Service for MITA
Centralizes error handling, formatting, and display logic for financial contexts
*/

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/financial_error_messages.dart';
import '../widgets/financial_error_widgets.dart';
import 'accessibility_service.dart';
import 'logging_service.dart';

/// Centralized service for managing financial error messages
class FinancialErrorService {
  static FinancialErrorService? _instance;
  static FinancialErrorService get instance =>
      _instance ??= FinancialErrorService._();

  FinancialErrorService._();

  final AccessibilityService _accessibility = AccessibilityService.instance;

  /// Display error with appropriate UI based on severity and context
  Future<void> showError(
    BuildContext context,
    dynamic error, {
    Map<String, dynamic>? additionalContext,
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
    bool forceDialog = false,
  }) async {
    // Temporary workaround for compilation issue
    final errorInfo = FinancialErrorInfo(
      title: 'Error',
      message: error.toString(),
      actions: [],
      icon: Icons.error,
      severity: FinancialErrorSeverity.medium,
      category: 'unknown',
    );

    // Log error for analytics
    logError(
      'Financial error displayed: ${errorInfo.title}',
      tag: 'FINANCIAL_ERROR_SERVICE',
      error: error,
      extra: {
        'error_type': errorInfo.category,
        'severity': errorInfo.severity.toString(),
        'has_retry': errorInfo.allowsRetry,
        ...?additionalContext,
      },
    );

    // Announce error to screen readers
    await _announceError(errorInfo);

    // Provide appropriate haptic feedback
    _provideHapticFeedback(errorInfo.severity);

    // Show error with appropriate UI
    if (forceDialog || errorInfo.severity == FinancialErrorSeverity.critical) {
      await _showErrorDialog(context, errorInfo,
          onRetry: onRetry, onDismiss: onDismiss);
    } else if (errorInfo.severity == FinancialErrorSeverity.high) {
      await _showErrorBottomSheet(context, errorInfo,
          onRetry: onRetry, onDismiss: onDismiss);
    } else {
      _showErrorSnackBar(context, errorInfo, onRetry: onRetry);
    }
  }

  /// Show success message with financial context
  void showSuccess(
    BuildContext context,
    String message, {
    String? financialContext,
    Duration duration = const Duration(seconds: 3),
  }) {
    _provideHapticFeedback(FinancialErrorSeverity.low, isSuccess: true);

    _accessibility.announceToScreenReader(
      'Success: $message',
      isImportant: true,
    );

    ScaffoldMessenger.of(context).showSnackBar(
      _createSuccessSnackBar(context, message, financialContext, duration),
    );
  }

  /// Show warning with financial context
  void showWarning(
    BuildContext context,
    String title,
    String message, {
    String? financialContext,
    List<String>? tips,
    VoidCallback? onAction,
    String? actionLabel,
  }) {
    final warningInfo = FinancialErrorInfo(
      title: title,
      message: message,
      actions: onAction != null && actionLabel != null
          ? [
              FinancialErrorAction(
                label: actionLabel,
                action: FinancialErrorActionType.retry,
                isPrimary: true,
                onTap: onAction,
              ),
            ]
          : [
              FinancialErrorAction(
                label: 'OK',
                action: FinancialErrorActionType.cancel,
                isPrimary: true,
              ),
            ],
      icon: Icons.warning_outlined,
      severity: FinancialErrorSeverity.medium,
      category: 'Warning',
      financialContext: financialContext,
      tips: tips,
    );

    _showErrorBottomSheet(context, warningInfo, onRetry: onAction);
  }

  /// Show inline error for form validation
  Widget buildInlineError(
    dynamic error, {
    Map<String, dynamic>? context,
    VoidCallback? onRetry,
  }) {
    // Temporary workaround for compilation issue
    final errorInfo = FinancialErrorInfo(
      title: 'Error',
      message: error.toString(),
      actions: [],
      icon: Icons.error,
      severity: FinancialErrorSeverity.medium,
      category: 'unknown',
    );

    return FinancialInlineError(
      errorInfo: errorInfo,
      onRetry: onRetry,
    );
  }

  /// Build empty state with error context
  Widget buildEmptyState({
    required String title,
    required String message,
    required IconData icon,
    String? actionLabel,
    VoidCallback? onAction,
    bool hasError = false,
  }) {
    return FinancialEmptyState(
      title: title,
      message: message,
      icon: icon,
      actionLabel: actionLabel,
      onAction: onAction,
      hasError: hasError,
    );
  }

  /// Build loading state with financial context
  Widget buildLoadingState({
    String? message,
    String? operation,
    bool hasError = false,
    VoidCallback? onCancel,
  }) {
    return FinancialLoadingState(
      message: message,
      operation: operation,
      hasError: hasError,
      onCancel: onCancel,
    );
  }

  /// Validate financial input and return user-friendly error if invalid
  String? validateFinancialAmount(
    String? value, {
    double? maxAmount,
    bool required = true,
  }) {
    if (required && (value == null || value.isEmpty)) {
      return 'Please enter an amount';
    }

    if (value != null && value.isNotEmpty) {
      final amount = double.tryParse(value.replaceAll(RegExp(r'[^\d.-]'), ''));

      if (amount == null) {
        return 'Please enter a valid amount (numbers only)';
      }

      if (amount <= 0) {
        return 'Amount must be greater than zero';
      }

      if (amount > (maxAmount ?? double.maxFinite)) {
        return 'Amount cannot exceed \$${maxAmount?.toStringAsFixed(2)}';
      }

      // Check decimal places
      if (value.contains('.')) {
        final decimalPart = value.split('.').last;
        if (decimalPart.length > 2) {
          return 'Maximum 2 decimal places for cents';
        }
      }
    }

    return null;
  }

  /// Validate email with financial context
  String? validateFinancialEmail(String? value) {
    if (value == null || value.isEmpty) {
      return 'Email is required for secure account access';
    }

    final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    if (!emailRegex.hasMatch(value)) {
      return 'Please enter a valid email for account security';
    }

    return null;
  }

  /// Show budget exceeded warning with specific context
  Future<bool> showBudgetExceededDialog(
    BuildContext context, {
    required double exceededAmount,
    required double dailyBudget,
    required String category,
    VoidCallback? onProceed,
    VoidCallback? onAdjust,
  }) async {
    final errorInfo = FinancialErrorInfo(
      title: 'Budget Alert',
      message:
          'This ${category.toLowerCase()} expense would exceed your daily budget by \$${exceededAmount.toStringAsFixed(2)}.',
      actions: [
        FinancialErrorAction(
          label: 'Adjust Amount',
          action: FinancialErrorActionType.edit,
          isPrimary: true,
          onTap: onAdjust,
        ),
        FinancialErrorAction(
          label: 'Proceed Anyway',
          action: FinancialErrorActionType.override,
          isPrimary: false,
          onTap: onProceed,
        ),
        FinancialErrorAction(
          label: 'View Budget',
          action: FinancialErrorActionType.navigate,
          navigationRoute: '/budget',
          isPrimary: false,
        ),
      ],
      icon: Icons.savings_outlined,
      severity: FinancialErrorSeverity.medium,
      category: 'Budget Management',
      financialContext:
          'Your daily budget is \$${dailyBudget.toStringAsFixed(2)}. Staying within budget helps achieve your financial goals.',
      tips: [
        'Consider if this expense is necessary right now',
        'Look for ways to reduce the amount',
        'Check if you can postpone this purchase',
        'Review your spending in other categories',
      ],
    );

    return await _showErrorDialog(context, errorInfo) == true;
  }

  /// Private helper methods

  Future<void> _announceError(FinancialErrorInfo errorInfo) async {
    await _accessibility.announceToScreenReader(
      '${errorInfo.category} error: ${errorInfo.title}. ${errorInfo.message}',
      isImportant: errorInfo.severity == FinancialErrorSeverity.critical ||
          errorInfo.severity == FinancialErrorSeverity.high,
    );
  }

  void _provideHapticFeedback(FinancialErrorSeverity severity,
      {bool isSuccess = false}) {
    if (isSuccess) {
      HapticFeedback.lightImpact();
    } else {
      switch (severity) {
        case FinancialErrorSeverity.low:
          HapticFeedback.selectionClick();
          break;
        case FinancialErrorSeverity.medium:
          HapticFeedback.mediumImpact();
          break;
        case FinancialErrorSeverity.high:
        case FinancialErrorSeverity.critical:
          HapticFeedback.heavyImpact();
          break;
      }
    }
  }

  Future<bool?> _showErrorDialog(
    BuildContext context,
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) async {
    return await showDialog<bool>(
      context: context,
      barrierDismissible: errorInfo.severity != FinancialErrorSeverity.critical,
      builder: (context) => FinancialErrorDialog(
        errorInfo: errorInfo,
        onRetry: onRetry,
        onDismiss: onDismiss,
      ),
    );
  }

  Future<void> _showErrorBottomSheet(
    BuildContext context,
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      isDismissible: errorInfo.severity != FinancialErrorSeverity.critical,
      enableDrag: errorInfo.severity != FinancialErrorSeverity.critical,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (context) => FinancialErrorBottomSheet(
        errorInfo: errorInfo,
        onRetry: onRetry,
        onDismiss: onDismiss,
      ),
    );
  }

  void _showErrorSnackBar(
    BuildContext context,
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
  }) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      FinancialErrorSnackBar.create(
        errorInfo: errorInfo,
        context: context,
        onRetry: onRetry,
      ),
    );
  }

  SnackBar _createSuccessSnackBar(
    BuildContext context,
    String message,
    String? financialContext,
    Duration duration,
  ) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SnackBar(
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.check_circle_outline_rounded,
                color: colorScheme.onPrimary,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(
                    color: colorScheme.onPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          if (financialContext != null) ...[
            const SizedBox(height: 4),
            Text(
              financialContext,
              style: TextStyle(
                color: colorScheme.onPrimary.withValues(alpha: 0.9),
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
      backgroundColor: colorScheme.primary,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      margin: const EdgeInsets.all(16),
      duration: duration,
    );
  }
}

/// Mixin for easy error handling in screens
mixin FinancialErrorHandling<T extends StatefulWidget> on State<T> {
  FinancialErrorService get errorService => FinancialErrorService.instance;

  /// Show error with automatic context detection
  Future<void> showError(
    dynamic error, {
    Map<String, dynamic>? context,
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
    bool forceDialog = false,
  }) async {
    if (!mounted) return;

    await errorService.showError(
      this.context,
      error,
      additionalContext: {
        'screen': T.toString(),
        'route': ModalRoute.of(this.context)?.settings.name,
        ...?context,
      },
      onRetry: onRetry,
      onDismiss: onDismiss,
      forceDialog: forceDialog,
    );
  }

  /// Show success message
  void showSuccess(
    String message, {
    String? financialContext,
  }) {
    if (!mounted) return;
    errorService.showSuccess(context, message,
        financialContext: financialContext);
  }

  /// Show warning
  void showWarning(
    String title,
    String message, {
    String? financialContext,
    List<String>? tips,
    VoidCallback? onAction,
    String? actionLabel,
  }) {
    if (!mounted) return;
    errorService.showWarning(
      context,
      title,
      message,
      financialContext: financialContext,
      tips: tips,
      onAction: onAction,
      actionLabel: actionLabel,
    );
  }

  /// Validate amount input
  String? validateAmount(
    String? value, {
    double? maxAmount,
    bool required = true,
  }) {
    return errorService.validateFinancialAmount(
      value,
      maxAmount: maxAmount,
      required: required,
    );
  }

  /// Validate email input
  String? validateEmail(String? value) {
    return errorService.validateFinancialEmail(value);
  }
}

/// Extension for BuildContext error handling
extension FinancialErrorContext on BuildContext {
  /// Quick access to error service
  FinancialErrorService get errorService => FinancialErrorService.instance;

  /// Show financial error
  Future<void> showFinancialError(
    dynamic error, {
    Map<String, dynamic>? context,
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) async {
    await errorService.showError(
      this,
      error,
      additionalContext: context,
      onRetry: onRetry,
      onDismiss: onDismiss,
    );
  }

  /// Show success message
  void showFinancialSuccess(
    String message, {
    String? financialContext,
  }) {
    errorService.showSuccess(this, message, financialContext: financialContext);
  }
}

/// Global error handler for unhandled financial operations
class GlobalFinancialErrorHandler {
  static void handleError(
    dynamic error, {
    Map<String, dynamic>? context,
    String? operation,
  }) {
    logError(
      'Global financial error: $error',
      tag: 'GLOBAL_FINANCIAL_ERROR',
      error: error,
      extra: {
        'operation': operation,
        ...?context,
      },
    );

    // Additional global error handling logic can be added here
    // For example: crash reporting, analytics, etc.
  }
}

/// Error message constants for consistent messaging
class FinancialErrorMessages {
  static const String genericNetworkError =
      'Please check your internet connection and try again.';
  static const String sessionExpiredError =
      'Your session has expired. Please sign in again.';
  static const String invalidAmountError = 'Please enter a valid amount.';
  static const String budgetExceededError =
      'This transaction would exceed your budget.';
  static const String duplicateTransactionError =
      'A similar transaction was already recorded.';
  static const String permissionDeniedError =
      'Permission is required to continue.';
  static const String serverMaintenanceError =
      'Service temporarily unavailable. Please try again later.';

  // Success messages
  static const String transactionSavedSuccess =
      'Transaction saved successfully!';
  static const String budgetUpdatedSuccess = 'Budget updated successfully!';
  static const String profileUpdatedSuccess = 'Profile updated successfully!';

  // Financial context messages
  static const String dataSecurityContext =
      'Your financial data remains secure and private.';
  static const String budgetHelpContext =
      'Staying within budget helps achieve your financial goals.';
  static const String accuracyContext =
      'Accurate records help you make better financial decisions.';
}

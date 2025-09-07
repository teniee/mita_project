/*
Financial-Specific Error Message System for MITA
Provides user-friendly, actionable error messages with financial context
*/

import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'dart:io';
import 'dart:async';
import '../l10n/generated/app_localizations.dart';
import '../widgets/financial_error_widgets.dart';

/// Categories of errors specific to financial applications
enum FinancialErrorType {
  // Authentication & Security
  sessionExpired,
  invalidCredentials,
  accountLocked,
  twoFactorRequired,
  biometricFailed,
  
  // Financial Operations
  budgetExceeded,
  insufficientBudget,
  invalidAmount,
  transactionFailed,
  duplicateTransaction,
  
  // Data & Sync
  syncFailed,
  dataCorrupted,
  offlineMode,
  
  // Network & Connectivity
  noInternet,
  serverMaintenance,
  requestTimeout,
  
  // Validation
  invalidEmail,
  weakPassword,
  requiredField,
  invalidFormat,
  
  // System & Device
  storageFullError,
  cameraPermission,
  locationPermission,
  deviceNotSupported,
  
  // Generic
  unknown,
}

/// Comprehensive error message provider with financial context
class FinancialErrorMessages {
  /// Get user-friendly error message with actionable guidance
  static FinancialErrorInfo getErrorInfo(
    dynamic error, {
    BuildContext? context,
    Map<String, dynamic>? additionalContext,
  }) {
    final errorType = _categorizeError(error, additionalContext);
    final l10n = context != null ? AppLocalizations.of(context) : null;
    
    return _getErrorInfoForType(errorType, error, l10n, additionalContext);
  }
  
  /// Categorize error into financial error types
  static FinancialErrorType _categorizeError(
    dynamic error,
    Map<String, dynamic>? context,
  ) {
    final errorString = error.toString().toLowerCase();
    final contextOperation = context?['operation']?.toString().toLowerCase() ?? '';
    final contextEndpoint = context?['endpoint']?.toString().toLowerCase() ?? '';
    
    // Authentication & Security errors
    if (errorString.contains('session expired') || 
        errorString.contains('token expired') ||
        errorString.contains('unauthorized') ||
        (error is DioException && error.response?.statusCode == 401)) {
      return FinancialErrorType.sessionExpired;
    }
    
    if (errorString.contains('invalid credentials') || 
        errorString.contains('login failed') ||
        errorString.contains('wrong password') ||
        (error is DioException && error.response?.statusCode == 403)) {
      return FinancialErrorType.invalidCredentials;
    }
    
    if (errorString.contains('account locked') || 
        errorString.contains('too many attempts')) {
      return FinancialErrorType.accountLocked;
    }
    
    if (errorString.contains('biometric') || errorString.contains('fingerprint')) {
      return FinancialErrorType.biometricFailed;
    }
    
    // Financial operation errors
    if (errorString.contains('budget') && errorString.contains('exceed')) {
      return FinancialErrorType.budgetExceeded;
    }
    
    if (contextOperation.contains('transaction') || contextEndpoint.contains('transaction')) {
      if (errorString.contains('duplicate')) {
        return FinancialErrorType.duplicateTransaction;
      }
      return FinancialErrorType.transactionFailed;
    }
    
    if (errorString.contains('invalid amount') || 
        errorString.contains('amount') && errorString.contains('invalid')) {
      return FinancialErrorType.invalidAmount;
    }
    
    // Network & connectivity errors
    if (error is SocketException || errorString.contains('no internet') ||
        errorString.contains('network unreachable')) {
      return FinancialErrorType.noInternet;
    }
    
    if (error is TimeoutException || 
        (error is DioException && error.type == DioExceptionType.connectionTimeout)) {
      return FinancialErrorType.requestTimeout;
    }
    
    if (error is DioException && error.response?.statusCode == 503) {
      return FinancialErrorType.serverMaintenance;
    }
    
    // Validation errors
    if (errorString.contains('email') && errorString.contains('invalid')) {
      return FinancialErrorType.invalidEmail;
    }
    
    if (errorString.contains('password') && 
        (errorString.contains('weak') || errorString.contains('short'))) {
      return FinancialErrorType.weakPassword;
    }
    
    if (errorString.contains('required')) {
      return FinancialErrorType.requiredField;
    }
    
    // System errors
    if (errorString.contains('storage') || errorString.contains('disk full')) {
      return FinancialErrorType.storageFullError;
    }
    
    if (errorString.contains('camera permission')) {
      return FinancialErrorType.cameraPermission;
    }
    
    if (errorString.contains('location permission')) {
      return FinancialErrorType.locationPermission;
    }
    
    // Data & sync errors
    if (contextOperation.contains('sync') || errorString.contains('sync')) {
      return FinancialErrorType.syncFailed;
    }
    
    if (errorString.contains('offline')) {
      return FinancialErrorType.offlineMode;
    }
    
    return FinancialErrorType.unknown;
  }
  
  /// Get detailed error information for each error type
  static FinancialErrorInfo _getErrorInfoForType(
    FinancialErrorType type,
    dynamic originalError,
    AppLocalizations? l10n,
    Map<String, dynamic>? context,
  ) {
    switch (type) {
      case FinancialErrorType.sessionExpired:
        return FinancialErrorInfo(
          title: 'Session Expired',
          message: 'Your secure session has expired for your protection. Please sign in again to continue managing your finances.',
          actions: [
            FinancialErrorAction(
              label: 'Sign In Again',
              action: FinancialErrorActionType.reauth,
              isPrimary: true,
            ),
          ],
          icon: Icons.lock_clock_outlined,
          severity: FinancialErrorSeverity.medium,
          category: 'Authentication',
          financialContext: 'Your financial data remains secure while your session is refreshed.',
        );
        
      case FinancialErrorType.invalidCredentials:
        return FinancialErrorInfo(
          title: 'Login Failed',
          message: 'We couldn\'t verify your credentials. Please check your email and password, then try again.',
          actions: [
            FinancialErrorAction(
              label: 'Try Again',
              action: FinancialErrorActionType.retry,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Forgot Password?',
              action: FinancialErrorActionType.resetPassword,
              isPrimary: false,
            ),
          ],
          icon: Icons.person_off_outlined,
          severity: FinancialErrorSeverity.medium,
          category: 'Authentication',
          financialContext: 'Your financial data is protected by secure authentication.',
        );
        
      case FinancialErrorType.budgetExceeded:
        final amount = context?['amount'] ?? '\$0.00';
        return FinancialErrorInfo(
          title: 'Budget Alert',
          message: 'This transaction would exceed your daily budget by $amount. You can still proceed, or consider adjusting the amount.',
          actions: [
            FinancialErrorAction(
              label: 'Adjust Amount',
              action: FinancialErrorActionType.edit,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Proceed Anyway',
              action: FinancialErrorActionType.override,
              isPrimary: false,
            ),
            FinancialErrorAction(
              label: 'View Budget',
              action: FinancialErrorActionType.navigate,
              navigationRoute: '/budget',
              isPrimary: false,
            ),
          ],
          icon: Icons.savings_outlined,
          severity: FinancialErrorSeverity.low,
          category: 'Budget Management',
          financialContext: 'Staying within budget helps achieve your financial goals. Consider if this expense is necessary.',
          tips: [
            'Review your spending categories to find areas to save',
            'Consider postponing non-essential purchases',
            'Check if you can use a different payment method or account',
          ],
        );
        
      case FinancialErrorType.transactionFailed:
        return FinancialErrorInfo(
          title: 'Transaction Failed',
          message: 'We couldn\'t save your transaction right now. Your data is safe, and you can try again.',
          actions: [
            FinancialErrorAction(
              label: 'Try Again',
              action: FinancialErrorActionType.retry,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Save Draft',
              action: FinancialErrorActionType.saveDraft,
              isPrimary: false,
            ),
          ],
          icon: Icons.sync_problem_outlined,
          severity: FinancialErrorSeverity.medium,
          category: 'Transaction',
          financialContext: 'Your financial records remain accurate and secure.',
          tips: [
            'Check your internet connection',
            'Verify all required fields are filled correctly',
            'Try again in a few moments',
          ],
        );
        
      case FinancialErrorType.noInternet:
        return FinancialErrorInfo(
          title: 'No Internet Connection',
          message: 'You\'re currently offline. Your transactions will be saved locally and synced when you reconnect.',
          actions: [
            FinancialErrorAction(
              label: 'Continue Offline',
              action: FinancialErrorActionType.continueOffline,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Check Connection',
              action: FinancialErrorActionType.retry,
              isPrimary: false,
            ),
          ],
          icon: Icons.wifi_off_outlined,
          severity: FinancialErrorSeverity.low,
          category: 'Connectivity',
          financialContext: 'Your financial data is safely stored locally until connection is restored.',
          tips: [
            'Check your WiFi or mobile data connection',
            'You can still record transactions offline',
            'Data will sync automatically when reconnected',
          ],
        );
        
      case FinancialErrorType.invalidAmount:
        return FinancialErrorInfo(
          title: 'Invalid Amount',
          message: 'The amount entered is not valid. Please enter a positive number with up to 2 decimal places.',
          actions: [
            FinancialErrorAction(
              label: 'Fix Amount',
              action: FinancialErrorActionType.edit,
              isPrimary: true,
            ),
          ],
          icon: Icons.money_off_outlined,
          severity: FinancialErrorSeverity.low,
          category: 'Input Validation',
          financialContext: 'Accurate amounts help maintain precise financial records.',
          tips: [
            'Use numbers only (e.g., 25.50)',
            'Don\'t include currency symbols',
            'Maximum 2 decimal places for cents',
          ],
        );
        
      case FinancialErrorType.duplicateTransaction:
        return FinancialErrorInfo(
          title: 'Duplicate Transaction Detected',
          message: 'A similar transaction was already recorded today. Is this a new expense or the same one?',
          actions: [
            FinancialErrorAction(
              label: 'It\'s New',
              action: FinancialErrorActionType.override,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'View Existing',
              action: FinancialErrorActionType.navigate,
              navigationRoute: '/transactions',
              isPrimary: false,
            ),
            FinancialErrorAction(
              label: 'Cancel',
              action: FinancialErrorActionType.cancel,
              isPrimary: false,
            ),
          ],
          icon: Icons.content_copy_outlined,
          severity: FinancialErrorSeverity.low,
          category: 'Transaction',
          financialContext: 'Avoiding duplicates keeps your financial records accurate.',
        );
        
      case FinancialErrorType.cameraPermission:
        return FinancialErrorInfo(
          title: 'Camera Access Needed',
          message: 'To scan receipts and capture expenses, MITA needs access to your camera.',
          actions: [
            FinancialErrorAction(
              label: 'Grant Access',
              action: FinancialErrorActionType.openSettings,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Enter Manually',
              action: FinancialErrorActionType.alternative,
              isPrimary: false,
            ),
          ],
          icon: Icons.camera_alt_outlined,
          severity: FinancialErrorSeverity.low,
          category: 'Permissions',
          financialContext: 'Receipt scanning makes expense tracking faster and more accurate.',
          tips: [
            'Go to Settings > Privacy > Camera',
            'Find MITA and toggle camera access on',
            'You can always enter expenses manually',
          ],
        );
        
      case FinancialErrorType.serverMaintenance:
        return FinancialErrorInfo(
          title: 'Service Temporarily Unavailable',
          message: 'We\'re performing maintenance to improve your experience. This usually takes just a few minutes.',
          actions: [
            FinancialErrorAction(
              label: 'Try Again Later',
              action: FinancialErrorActionType.retry,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Work Offline',
              action: FinancialErrorActionType.continueOffline,
              isPrimary: false,
            ),
          ],
          icon: Icons.build_outlined,
          severity: FinancialErrorSeverity.medium,
          category: 'Service',
          financialContext: 'Your financial data remains secure during maintenance.',
          tips: [
            'Try again in a few minutes',
            'You can still use offline features',
            'Check our status page for updates',
          ],
        );
        
      default:
        return FinancialErrorInfo(
          title: 'Something Went Wrong',
          message: 'We encountered an unexpected issue. Your financial data is safe, and our team has been notified.',
          actions: [
            FinancialErrorAction(
              label: 'Try Again',
              action: FinancialErrorActionType.retry,
              isPrimary: true,
            ),
            FinancialErrorAction(
              label: 'Contact Support',
              action: FinancialErrorActionType.contactSupport,
              isPrimary: false,
            ),
          ],
          icon: Icons.error_outline,
          severity: FinancialErrorSeverity.medium,
          category: 'System',
          financialContext: 'Your financial records and personal information remain secure.',
          tips: [
            'Try the action again in a moment',
            'Check your internet connection',
            'Contact support if the issue persists',
          ],
        );
    }
  }
}

/// Comprehensive error information with financial context
class FinancialErrorInfo {
  final String title;
  final String message;
  final List<FinancialErrorAction> actions;
  final IconData icon;
  final FinancialErrorSeverity severity;
  final String category;
  final String? financialContext;
  final List<String>? tips;
  final Map<String, dynamic>? metadata;
  
  const FinancialErrorInfo({
    required this.title,
    required this.message,
    required this.actions,
    required this.icon,
    required this.severity,
    required this.category,
    this.financialContext,
    this.tips,
    this.metadata,
  });
  
  /// Get appropriate color for the error severity
  Color getColor(ColorScheme colorScheme) {
    switch (severity) {
      case FinancialErrorSeverity.low:
        return colorScheme.primary;
      case FinancialErrorSeverity.medium:
        return colorScheme.tertiary;
      case FinancialErrorSeverity.high:
        return colorScheme.error;
      case FinancialErrorSeverity.critical:
        return colorScheme.error;
    }
  }
  
  /// Check if error should be displayed immediately
  bool get shouldShowImmediately => 
      severity == FinancialErrorSeverity.high || 
      severity == FinancialErrorSeverity.critical;
      
  /// Check if error allows retry
  bool get allowsRetry => actions.any((action) => action.action == FinancialErrorActionType.retry);
}

/// Severity levels for financial errors
enum FinancialErrorSeverity {
  low,     // Info/warning, doesn't block user flow
  medium,  // Prevents action completion, needs user attention
  high,    // Significant issue, may affect financial data
  critical // Critical security/data issue
}

/// Types of actions users can take to resolve errors
enum FinancialErrorActionType {
  retry,
  reauth,
  edit,
  override,
  cancel,
  navigate,
  contactSupport,
  openSettings,
  resetPassword,
  saveDraft,
  continueOffline,
  alternative,
}

/// Action that users can take to resolve an error
class FinancialErrorAction {
  final String label;
  final FinancialErrorActionType action;
  final bool isPrimary;
  final String? navigationRoute;
  final Map<String, dynamic>? parameters;
  final VoidCallback? onTap;
  
  const FinancialErrorAction({
    required this.label,
    required this.action,
    this.isPrimary = false,
    this.navigationRoute,
    this.parameters,
    this.onTap,
  });
}

/// Extension for easy error handling in widgets
extension FinancialErrorHandling on BuildContext {
  /// Show financial error with appropriate UI
  void showFinancialError(
    dynamic error, {
    Map<String, dynamic>? context,
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) {
    final errorInfo = FinancialErrorMessages.getErrorInfo(
      error,
      context: this,
      additionalContext: context,
    );
    
    if (errorInfo.severity == FinancialErrorSeverity.critical) {
      _showErrorDialog(errorInfo, onRetry: onRetry, onDismiss: onDismiss);
    } else if (errorInfo.severity == FinancialErrorSeverity.high) {
      _showErrorBottomSheet(errorInfo, onRetry: onRetry, onDismiss: onDismiss);
    } else {
      _showErrorSnackBar(errorInfo, onRetry: onRetry);
    }
  }
  
  void _showErrorDialog(
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) {
    showDialog<void>(
      context: this,
      barrierDismissible: false,
      builder: (context) => FinancialErrorDialog(
        errorInfo: errorInfo,
        onRetry: onRetry,
        onDismiss: onDismiss,
      ),
    );
  }
  
  void _showErrorBottomSheet(
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
  }) {
    showModalBottomSheet<void>(
      context: this,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => FinancialErrorBottomSheet(
        errorInfo: errorInfo,
        onRetry: onRetry,
        onDismiss: onDismiss,
      ),
    );
  }
  
  void _showErrorSnackBar(
    FinancialErrorInfo errorInfo, {
    VoidCallback? onRetry,
  }) {
    ScaffoldMessenger.of(this).showSnackBar(
      FinancialErrorSnackBar.create(
        errorInfo: errorInfo,
        context: this,
        onRetry: onRetry,
      ),
    );
  }
}
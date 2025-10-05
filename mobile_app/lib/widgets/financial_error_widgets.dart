/*
Financial Error UI Components for MITA
Material 3 compliant error display widgets with financial context
*/

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/financial_error_messages.dart';
import '../services/accessibility_service.dart';

/// Material 3 dialog for critical financial errors
class FinancialErrorDialog extends StatefulWidget {
  final FinancialErrorInfo errorInfo;
  final VoidCallback? onRetry;
  final VoidCallback? onDismiss;

  const FinancialErrorDialog({
    super.key,
    required this.errorInfo,
    this.onRetry,
    this.onDismiss,
  });

  @override
  State<FinancialErrorDialog> createState() => _FinancialErrorDialogState();
}

class _FinancialErrorDialogState extends State<FinancialErrorDialog>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _announceError();
  }

  void _initializeAnimations() {
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(
      begin: 0.8,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOutCubic,
    ));

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    ));

    _animationController.forward();
  }

  void _announceError() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      AccessibilityService.instance.announceToScreenReader(
        '${widget.errorInfo.category} Error: ${widget.errorInfo.title}. ${widget.errorInfo.message}',
        isImportant: true,
      );
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return AnimatedBuilder(
      animation: _animationController,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimation,
          child: ScaleTransition(
            scale: _scaleAnimation,
            child: AlertDialog(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(28),
              ),
              clipBehavior: Clip.antiAlias,
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: widget.errorInfo.getColor(colorScheme).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      widget.errorInfo.icon,
                      color: widget.errorInfo.getColor(colorScheme),
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Text(
                      widget.errorInfo.title,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.errorInfo.message,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                        height: 1.4,
                      ),
                    ),
                    if (widget.errorInfo.financialContext != null) ...[
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: colorScheme.primary.withValues(alpha: 0.2),
                            width: 1,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.security_outlined,
                              color: colorScheme.primary,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                widget.errorInfo.financialContext!,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: colorScheme.primary,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (widget.errorInfo.tips?.isNotEmpty == true) ...[
                      const SizedBox(height: 16),
                      Text(
                        'What you can do:',
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 8),
                      ...widget.errorInfo.tips!.map((tip) => Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  margin: const EdgeInsets.only(top: 8),
                                  width: 4,
                                  height: 4,
                                  decoration: BoxDecoration(
                                    color: colorScheme.onSurfaceVariant,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    tip,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      color: colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          )),
                    ],
                  ],
                ),
              ),
              actions: _buildActions(context),
            ),
          ),
        );
      },
    );
  }

  List<Widget> _buildActions(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final actions = <Widget>[];

    // Add secondary actions first (left-aligned)
    for (final action in widget.errorInfo.actions.where((a) => !a.isPrimary)) {
      actions.add(
        TextButton(
          onPressed: () => _handleAction(context, action),
          child: Text(action.label),
        ),
      );
    }

    // Add primary actions last (right-aligned)
    for (final action in widget.errorInfo.actions.where((a) => a.isPrimary)) {
      actions.add(
        FilledButton(
          onPressed: () => _handleAction(context, action),
          style: FilledButton.styleFrom(
            backgroundColor: widget.errorInfo.getColor(colorScheme),
            foregroundColor: colorScheme.onPrimary,
          ),
          child: Text(action.label),
        ),
      );
    }

    return actions;
  }

  void _handleAction(BuildContext context, FinancialErrorAction action) {
    // Provide haptic feedback
    HapticFeedback.lightImpact();

    // Handle the action
    switch (action.action) {
      case FinancialErrorActionType.retry:
        Navigator.of(context).pop();
        widget.onRetry?.call();
        break;
      case FinancialErrorActionType.cancel:
        Navigator.of(context).pop();
        widget.onDismiss?.call();
        break;
      case FinancialErrorActionType.navigate:
        if (action.navigationRoute != null) {
          Navigator.of(context).pop();
          Navigator.of(context).pushNamed(action.navigationRoute!);
        }
        break;
      case FinancialErrorActionType.openSettings:
        Navigator.of(context).pop();
        // Open system settings - implementation depends on platform
        break;
      default:
        Navigator.of(context).pop();
        action.onTap?.call();
        break;
    }
  }
}

/// Material 3 bottom sheet for medium-severity financial errors
class FinancialErrorBottomSheet extends StatefulWidget {
  final FinancialErrorInfo errorInfo;
  final VoidCallback? onRetry;
  final VoidCallback? onDismiss;

  const FinancialErrorBottomSheet({
    super.key,
    required this.errorInfo,
    this.onRetry,
    this.onDismiss,
  });

  @override
  State<FinancialErrorBottomSheet> createState() => _FinancialErrorBottomSheetState();
}

class _FinancialErrorBottomSheetState extends State<FinancialErrorBottomSheet>
    with TickerProviderStateMixin {
  late AnimationController _slideController;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _announceError();
  }

  void _initializeAnimations() {
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutCubic,
    ));

    _slideController.forward();
  }

  void _announceError() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      AccessibilityService.instance.announceToScreenReader(
        'Error occurred: ${widget.errorInfo.title}',
        isImportant: true,
      );
    });
  }

  @override
  void dispose() {
    _slideController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SlideTransition(
      position: _slideAnimation,
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 32,
                  height: 4,
                  decoration: BoxDecoration(
                    color: colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              
              // Header with icon and title
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: widget.errorInfo.getColor(colorScheme).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Icon(
                      widget.errorInfo.icon,
                      color: widget.errorInfo.getColor(colorScheme),
                      size: 28,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.errorInfo.category,
                          style: theme.textTheme.labelMedium?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          widget.errorInfo.title,
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              
              // Error message
              Text(
                widget.errorInfo.message,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                  height: 1.4,
                ),
              ),
              
              // Financial context
              if (widget.errorInfo.financialContext != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.info_outline,
                        color: colorScheme.primary,
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          widget.errorInfo.financialContext!,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: colorScheme.primary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              
              // Tips
              if (widget.errorInfo.tips?.isNotEmpty == true) ...[
                const SizedBox(height: 20),
                Text(
                  'What you can do:',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 12),
                ...widget.errorInfo.tips!.take(3).map((tip) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            margin: const EdgeInsets.only(top: 8),
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: widget.errorInfo.getColor(colorScheme),
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              tip,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: colorScheme.onSurface,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )),
              ],
              
              const SizedBox(height: 24),
              
              // Actions
              Row(
                children: [
                  // Secondary actions
                  ...widget.errorInfo.actions
                      .where((action) => !action.isPrimary)
                      .map((action) => Padding(
                            padding: const EdgeInsets.only(right: 12),
                            child: OutlinedButton(
                              onPressed: () => _handleAction(context, action),
                              child: Text(action.label),
                            ),
                          )),
                  const Spacer(),
                  // Primary actions
                  ...widget.errorInfo.actions
                      .where((action) => action.isPrimary)
                      .map((action) => FilledButton(
                            onPressed: () => _handleAction(context, action),
                            style: FilledButton.styleFrom(
                              backgroundColor: widget.errorInfo.getColor(colorScheme),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 24,
                                vertical: 12,
                              ),
                            ),
                            child: Text(action.label),
                          )),
                ],
              ),
              
              // Additional bottom padding for safe area
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  void _handleAction(BuildContext context, FinancialErrorAction action) {
    HapticFeedback.selectionClick();
    
    switch (action.action) {
      case FinancialErrorActionType.retry:
        Navigator.of(context).pop();
        widget.onRetry?.call();
        break;
      case FinancialErrorActionType.cancel:
        Navigator.of(context).pop();
        widget.onDismiss?.call();
        break;
      case FinancialErrorActionType.navigate:
        if (action.navigationRoute != null) {
          Navigator.of(context).pop();
          Navigator.of(context).pushNamed(action.navigationRoute!);
        }
        break;
      default:
        Navigator.of(context).pop();
        action.onTap?.call();
        break;
    }
  }
}

/// Material 3 SnackBar for low-severity financial errors
class FinancialErrorSnackBar {
  static SnackBar create({
    required FinancialErrorInfo errorInfo,
    required BuildContext context,
    VoidCallback? onRetry,
    Duration duration = const Duration(seconds: 6),
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SnackBar(
      content: Row(
        children: [
          Icon(
            errorInfo.icon,
            color: colorScheme.onErrorContainer,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  errorInfo.title,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: colorScheme.onErrorContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (errorInfo.message.length < 60) ...[
                  const SizedBox(height: 2),
                  Text(
                    errorInfo.message,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onErrorContainer.withValues(alpha: 0.9),
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
      backgroundColor: colorScheme.errorContainer,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      margin: const EdgeInsets.all(16),
      duration: duration,
      action: errorInfo.allowsRetry && onRetry != null
          ? SnackBarAction(
              label: 'Retry',
              textColor: colorScheme.error,
              onPressed: onRetry,
            )
          : SnackBarAction(
              label: 'Dismiss',
              textColor: colorScheme.onErrorContainer.withValues(alpha: 0.7),
              onPressed: () {
                ScaffoldMessenger.of(context).hideCurrentSnackBar();
              },
            ),
    );
  }
}

/// In-line error display for forms and inputs
class FinancialInlineError extends StatelessWidget {
  final FinancialErrorInfo errorInfo;
  final VoidCallback? onRetry;

  const FinancialInlineError({
    super.key,
    required this.errorInfo,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: colorScheme.error.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            errorInfo.icon,
            color: colorScheme.error,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              errorInfo.message,
              style: theme.textTheme.bodySmall?.copyWith(
                color: colorScheme.error,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (onRetry != null && errorInfo.allowsRetry) ...[
            const SizedBox(width: 8),
            TextButton(
              onPressed: onRetry,
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Text(
                'Try Again',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colorScheme.error,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Loading state with error-aware messaging
class FinancialLoadingState extends StatelessWidget {
  final String? message;
  final String? operation;
  final bool hasError;
  final VoidCallback? onCancel;

  const FinancialLoadingState({
    super.key,
    this.message,
    this.operation,
    this.hasError = false,
    this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Center(
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: colorScheme.surface,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: colorScheme.shadow.withValues(alpha: 0.1),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 48,
              height: 48,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                color: hasError ? colorScheme.error : colorScheme.primary,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              message ?? _getDefaultMessage(operation),
              style: theme.textTheme.bodyLarge?.copyWith(
                fontWeight: FontWeight.w500,
                color: colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            if (operation != null) ...[
              const SizedBox(height: 8),
              Text(
                _getFinancialContext(operation!),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ],
            if (onCancel != null) ...[
              const SizedBox(height: 16),
              TextButton(
                onPressed: onCancel,
                child: const Text('Cancel'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _getDefaultMessage(String? operation) {
    switch (operation?.toLowerCase()) {
      case 'login':
        return 'Signing you in securely...';
      case 'transaction':
        return 'Saving your transaction...';
      case 'sync':
        return 'Syncing your financial data...';
      case 'budget':
        return 'Calculating your budget...';
      default:
        return 'Processing...';
    }
  }

  String _getFinancialContext(String operation) {
    switch (operation.toLowerCase()) {
      case 'login':
        return 'Your financial data is encrypted and secure';
      case 'transaction':
        return 'Your transaction will be recorded accurately';
      case 'sync':
        return 'Ensuring all your data is up to date';
      case 'budget':
        return 'Updating your spending plan';
      default:
        return 'Your financial information remains secure';
    }
  }
}

/// Empty state with error-aware messaging for financial screens
class FinancialEmptyState extends StatelessWidget {
  final String title;
  final String message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool hasError;

  const FinancialEmptyState({
    super.key,
    required this.title,
    required this.message,
    required this.icon,
    this.actionLabel,
    this.onAction,
    this.hasError = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: (hasError ? colorScheme.errorContainer : colorScheme.primaryContainer)
                    .withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: 64,
                color: hasError ? colorScheme.error : colorScheme.primary,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              title,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 32),
              FilledButton.icon(
                onPressed: onAction,
                icon: Icon(hasError ? Icons.refresh : Icons.add),
                label: Text(actionLabel!),
                style: FilledButton.styleFrom(
                  backgroundColor: hasError ? colorScheme.error : colorScheme.primary,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
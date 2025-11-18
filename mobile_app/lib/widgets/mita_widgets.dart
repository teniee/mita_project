import 'package:flutter/material.dart';
import '../theme/mita_theme.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/accessibility_service.dart';
import '../core/error_handling.dart';

/// Production-ready widget library for MITA
/// Provides consistent, Material 3 compliant components
class MitaWidgets {
  
  /// Creates a skeleton loading card with shimmer effect
  static Widget buildSkeletonCard({
    double? width,
    double height = 120,
    EdgeInsetsGeometry? margin,
    String? semanticLabel,
  }) {
    return Semantics(
      label: semanticLabel ?? 'Loading content placeholder',
      child: Container(
        width: width,
        height: height,
        margin: margin ?? const EdgeInsets.symmetric(vertical: 8),
        child: Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(
              color: Colors.grey.withValues(alpha: 0.2),
              width: 1,
            ),
          ),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.grey.withValues(alpha: 0.1),
                  Colors.grey.withValues(alpha: 0.05),
                  Colors.grey.withValues(alpha: 0.1),
                ],
                stops: const [0.0, 0.5, 1.0],
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// Creates a loading screen with MITA branding
  static Widget buildLoadingScreen({
    String? message,
    bool showLogo = true,
  }) {
    final accessibilityService = AccessibilityService.instance;
    final loadingMessage = message ?? 'Loading MITA financial data';
    
    return Scaffold(
      backgroundColor: const AppColors.background,
      body: Semantics(
        label: '$loadingMessage. Please wait.',
        liveRegion: true,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (showLogo) ...[
                Semantics(
                  label: 'MITA app logo. Financial wallet icon.',
                  child: Container(
                    width: 80,
                    height: 80,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.primary,
                    ),
                    child: const Icon(
                      Icons.account_balance_wallet,
                      color: AppColors.secondary,
                      size: 40,
                    ),
                  ),
                ),
                const SizedBox(height: 24),
              ],
              MitaTheme.createLoadingIndicator(message: message),
            ],
          ),
        ),
      ),
    );
  }

  /// Creates an enhanced Material 3 error screen with retry functionality
  static Widget buildErrorScreen({
    required String title,
    required String message,
    VoidCallback? onRetry,
    VoidCallback? onGoHome,
    IconData icon = Icons.error_outline_rounded,
    String? actionLabel,
    BuildContext? context,
  }) {
    return Builder(
      builder: (BuildContext builderContext) {
        final theme = Theme.of(builderContext);
        final colorScheme = theme.colorScheme;
        
        return Scaffold(
          backgroundColor: colorScheme.surface,
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Enhanced Material 3 error icon with proper tonal colors
                    Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: colorScheme.errorContainer.withValues(alpha: 0.3),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        icon,
                        size: 64,
                        color: colorScheme.error,
                        semanticLabel: 'Error occurred',
                      ),
                    ),
                    const SizedBox(height: 32),
                    
                    // Enhanced title with Material 3 typography
                    Text(
                      title,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    
                    // Enhanced message with Material 3 typography
                    Text(
                      message,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                        height: 1.5,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 32),
                    
                    // Enhanced action buttons with Material 3 styling
                    if (onRetry != null) ...[
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: onRetry,
                          icon: const Icon(Icons.refresh_rounded),
                          label: Text(actionLabel ?? 'Try Again'),
                          style: FilledButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    
                    // Go to home button
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: onGoHome ?? () {
                          if (context != null && Navigator.of(context).canPop()) {
                            Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
                          }
                        },
                        icon: const Icon(Icons.home_rounded),
                        label: const Text('Go to Home'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          side: BorderSide(color: colorScheme.outline),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  /// Creates an empty state widget
  static Widget buildEmptyState({
    required String title,
    required String message,
    IconData icon = Icons.inbox_outlined,
    Widget? action,
  }) {
    return Semantics(
      label: 'Empty state: $title. $message',
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Semantics(
                label: 'Empty state icon',
                child: Icon(
                  icon,
                  size: 64,
                  color: Colors.grey[400],
                ),
              ),
              const SizedBox(height: 24),
              Semantics(
                header: true,
                child: Text(
                  title,
                  style: const TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                message,
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  color: Colors.grey[600],
                  height: 1.5,
                ),
                textAlign: TextAlign.center,
              ),
              if (action != null) ...[
                const SizedBox(height: 24),
                action,
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// Creates a responsive app bar with MITA styling
  static PreferredSizeWidget buildAppBar({
    required String title,
    List<Widget>? actions,
    Widget? leading,
    bool centerTitle = true,
    double elevation = 0,
  }) {
    return AppBar(
      title: Semantics(
        header: true,
        label: title,
        child: Text(
          title,
          style: const TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.w700,
            fontSize: 20,
            color: AppColors.primary,
          ),
        ),
      ),
      backgroundColor: const AppColors.background,
      foregroundColor: const AppColors.primary,
      elevation: elevation,
      centerTitle: centerTitle,
      leading: leading,
      actions: actions,
      scrolledUnderElevation: 1,
    );
  }

  /// Creates a budget progress ring widget
  static Widget buildBudgetProgressRing({
    required double progress,
    required double size,
    required String label,
    required String amount,
    Color? progressColor,
    double strokeWidth = 8,
  }) {
    final accessibilityService = AccessibilityService.instance;
    final color = progressColor ?? MitaTheme.getSpendingStatusColor(progress);
    final percentage = (progress * 100).round();
    
    String statusDescription;
    if (progress >= 1.0) {
      statusDescription = 'Budget exceeded';
    } else if (progress >= 0.8) {
      statusDescription = 'Near budget limit';
    } else if (progress >= 0.6) {
      statusDescription = 'Moderate spending';
    } else {
      statusDescription = 'Good spending level';
    }
    
    return Semantics(
      label: 'Budget progress ring for $label. $amount. $percentage percent used. $statusDescription.',
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Semantics(
              label: 'Progress indicator: $percentage percent',
              child: SizedBox(
                width: size,
                height: size,
                child: CircularProgressIndicator(
                  value: progress.clamp(0.0, 1.0),
                  strokeWidth: strokeWidth,
                  backgroundColor: Colors.grey.withValues(alpha: 0.2),
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                ),
              ),
            ),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Semantics(
                  label: accessibilityService.createFinancialSemanticLabel(
                    label: 'Amount',
                    amount: double.tryParse(amount.replaceAll(RegExp(r'[^\d.]'), '')) ?? 0.0,
                    category: label,
                  ),
                  child: Text(
                    amount,
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w700,
                      fontSize: size * 0.12,
                      color: const AppColors.primary,
                    ),
                  ),
                ),
                Semantics(
                  label: 'Category: $label',
                  child: Text(
                    label,
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: size * 0.08,
                      color: Colors.grey[600],
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Creates a financial metric card
  static Widget buildMetricCard({
    required String title,
    required String value,
    required IconData icon,
    String? subtitle,
    Color? color,
    VoidCallback? onTap,
  }) {
    final accessibilityService = AccessibilityService.instance;
    final cardColor = color ?? const AppColors.primary;
    
    final numericValue = double.tryParse(value.replaceAll(RegExp(r'[^\d.]'), '')) ?? 0.0;
    final semanticLabel = accessibilityService.createFinancialSemanticLabel(
      label: title,
      amount: numericValue,
      status: subtitle,
    );
    
    return Semantics(
      label: onTap != null 
        ? '$semanticLabel. Tap for more details.'
        : semanticLabel,
      button: onTap != null,
      child: MitaTheme.createElevatedCard(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Semantics(
                  label: '$title icon',
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: cardColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      icon,
                      color: cardColor,
                      size: 20,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      color: Colors.grey[600],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                if (onTap != null)
                  Semantics(
                    label: 'More details arrow',
                    child: Icon(
                      Icons.arrow_forward_ios,
                      size: 16,
                      color: Colors.grey[400],
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Semantics(
              label: 'Value: $value',
              child: Text(
                value,
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: cardColor,
                ),
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 4),
              Semantics(
                label: 'Subtitle: $subtitle',
                child: Text(
                  subtitle,
                  style: TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 12,
                    color: Colors.grey[500],
                  ),
                ),
              ),
            ],
          ],
        ),
      ).withMinimumTouchTarget(),
    );
  }

  /// Creates a responsive grid layout
  static Widget buildResponsiveGrid({
    required List<Widget> children,
    int crossAxisCount = 2,
    double childAspectRatio = 1.0,
    double crossAxisSpacing = 16,
    double mainAxisSpacing = 16,
  }) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isTablet = constraints.maxWidth > 600;
        final adjustedCrossAxisCount = isTablet ? crossAxisCount * 2 : crossAxisCount;
        
        return GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: adjustedCrossAxisCount,
          childAspectRatio: childAspectRatio,
          crossAxisSpacing: crossAxisSpacing,
          mainAxisSpacing: mainAxisSpacing,
          children: children,
        );
      },
    );
  }

  /// Creates a section header with optional action
  static Widget buildSectionHeader({
    required String title,
    String? subtitle,
    Widget? action,
  }) {
    return Semantics(
      header: true,
      label: subtitle != null ? '$title. $subtitle' : title,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primary,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 14,
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (action != null) action,
          ],
        ),
      ),
    );
  }

  /// Creates an enhanced Material 3 error banner with actionable feedback
  static Widget buildErrorBanner({
    required String message,
    VoidCallback? onRetry,
    VoidCallback? onDismiss,
    ErrorSeverity severity = ErrorSeverity.medium,
    bool showIcon = true,
    BuildContext? context,
  }) {
    return Builder(
      builder: (BuildContext builderContext) {
        final theme = Theme.of(builderContext);
        final colorScheme = theme.colorScheme;
        
        Color backgroundColor;
        Color foregroundColor;
        IconData icon;
        
        switch (severity) {
          case ErrorSeverity.low:
            backgroundColor = colorScheme.secondaryContainer;
            foregroundColor = colorScheme.onSecondaryContainer;
            icon = Icons.info_outline_rounded;
            break;
          case ErrorSeverity.medium:
            backgroundColor = colorScheme.errorContainer;
            foregroundColor = colorScheme.onErrorContainer;
            icon = Icons.warning_outlined;
            break;
          case ErrorSeverity.high:
            backgroundColor = colorScheme.error;
            foregroundColor = colorScheme.onError;
            icon = Icons.error_outline_rounded;
            break;
          case ErrorSeverity.critical:
            backgroundColor = colorScheme.error;
            foregroundColor = colorScheme.onError;
            icon = Icons.dangerous_outlined;
            break;
        }
        
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          margin: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: backgroundColor,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: foregroundColor.withValues(alpha: 0.2),
              width: 1,
            ),
          ),
          child: Row(
            children: [
              if (showIcon) ...[
                Icon(
                  icon,
                  color: foregroundColor,
                  size: 20,
                ),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: foregroundColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              if (onRetry != null) ...[
                const SizedBox(width: 8),
                TextButton(
                  onPressed: onRetry,
                  style: TextButton.styleFrom(
                    foregroundColor: foregroundColor,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  child: const Text('Retry'),
                ),
              ],
              if (onDismiss != null) ...[
                const SizedBox(width: 4),
                IconButton(
                  onPressed: onDismiss,
                  icon: const Icon(Icons.close_rounded),
                  iconSize: 18,
                  color: foregroundColor,
                  padding: const EdgeInsets.all(4),
                  constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  /// Creates an inline error message for forms and inputs
  static Widget buildInlineError({
    required String message,
    IconData icon = Icons.error_outline_rounded,
    Color? color,
    BuildContext? context,
  }) {
    return Builder(
      builder: (BuildContext builderContext) {
        final theme = Theme.of(builderContext);
        final errorColor = color ?? theme.colorScheme.error;
        
        return Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                icon,
                size: 16,
                color: errorColor,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: errorColor,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  /// Creates a loading state with error recovery
  static Widget buildLoadingWithError({
    required bool isLoading,
    String? error,
    VoidCallback? onRetry,
    String loadingMessage = 'Loading...',
    Widget? child,
    BuildContext? context,
  }) {
    return Builder(
      builder: (BuildContext builderContext) {
        final theme = Theme.of(builderContext);
        final colorScheme = theme.colorScheme;
        
        if (isLoading) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(
                  color: colorScheme.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  loadingMessage,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          );
        }
        
        if (error != null) {
          return buildErrorScreen(
            title: 'Something went wrong',
            message: error,
            onRetry: onRetry,
            context: builderContext,
          );
        }
        
        return child ?? const SizedBox.shrink();
      },
    );
  }

  /// Creates an enhanced network status indicator
  static Widget buildNetworkStatusIndicator({
    required bool isConnected,
    bool showWhenConnected = false,
    BuildContext? context,
  }) {
    if (isConnected && !showWhenConnected) {
      return const SizedBox.shrink();
    }
    
    return Builder(
      builder: (BuildContext builderContext) {
        final theme = Theme.of(builderContext);
        final colorScheme = theme.colorScheme;
        
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          color: isConnected 
            ? colorScheme.primaryContainer 
            : colorScheme.errorContainer,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                isConnected 
                  ? Icons.wifi_rounded 
                  : Icons.wifi_off_rounded,
                size: 16,
                color: isConnected 
                  ? colorScheme.onPrimaryContainer 
                  : colorScheme.onErrorContainer,
              ),
              const SizedBox(width: 8),
              Text(
                isConnected 
                  ? 'Connected' 
                  : 'No internet connection',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: isConnected 
                    ? colorScheme.onPrimaryContainer 
                    : colorScheme.onErrorContainer,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
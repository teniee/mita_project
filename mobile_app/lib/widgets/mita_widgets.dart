import 'package:flutter/material.dart';
import '../theme/mita_theme.dart';
import '../services/accessibility_service.dart';

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
      backgroundColor: const Color(0xFFFFF9F0),
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
                      color: Color(0xFF193C57),
                    ),
                    child: const Icon(
                      Icons.account_balance_wallet,
                      color: Color(0xFFFFD25F),
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

  /// Creates an error screen with retry functionality
  static Widget buildErrorScreen({
    required String title,
    required String message,
    VoidCallback? onRetry,
    IconData icon = Icons.error_outline,
  }) {
    final accessibilityService = AccessibilityService.instance;
    
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Semantics(
                  label: 'Error icon',
                  child: Icon(
                    icon,
                    size: 64,
                    color: Colors.grey[400],
                  ),
                ),
                const SizedBox(height: 24),
                Semantics(
                  header: true,
                  label: 'Error: $title',
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF193C57),
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 12),
                Semantics(
                  label: 'Error message: $message',
                  child: Text(
                    message,
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 16,
                      color: Colors.grey[600],
                      height: 1.5,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                if (onRetry != null) ...[
                  const SizedBox(height: 32),
                  Semantics(
                    label: accessibilityService.createButtonSemanticLabel(
                      action: 'Try Again',
                      context: 'Retry the failed operation',
                    ),
                    button: true,
                    child: FilledButton.icon(
                      onPressed: () {
                        accessibilityService.announceToScreenReader(
                          'Retrying operation',
                          isImportant: true,
                        );
                        onRetry();
                      },
                      icon: const Icon(Icons.refresh),
                      label: const Text('Try Again'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 12,
                        ),
                      ),
                    ).withMinimumTouchTarget(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
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
                    fontFamily: 'Sora',
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF193C57),
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                message,
                style: TextStyle(
                  fontFamily: 'Manrope',
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
            fontFamily: 'Sora',
            fontWeight: FontWeight.w700,
            fontSize: 20,
            color: Color(0xFF193C57),
          ),
        ),
      ),
      backgroundColor: const Color(0xFFFFF9F0),
      foregroundColor: const Color(0xFF193C57),
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
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w700,
                      fontSize: size * 0.12,
                      color: const Color(0xFF193C57),
                    ),
                  ),
                ),
                Semantics(
                  label: 'Category: $label',
                  child: Text(
                    label,
                    style: TextStyle(
                      fontFamily: 'Manrope',
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
    final cardColor = color ?? const Color(0xFF193C57);
    
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
                      fontFamily: 'Manrope',
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
                  fontFamily: 'Sora',
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
                    fontFamily: 'Manrope',
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
                      fontFamily: 'Sora',
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontFamily: 'Manrope',
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
}
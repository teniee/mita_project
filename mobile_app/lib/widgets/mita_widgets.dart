import 'package:flutter/material.dart';
import '../theme/mita_theme.dart';

/// Production-ready widget library for MITA
/// Provides consistent, Material 3 compliant components
class MitaWidgets {
  
  /// Creates a skeleton loading card with shimmer effect
  static Widget buildSkeletonCard({
    double? width,
    double height = 120,
    EdgeInsetsGeometry? margin,
  }) {
    return Container(
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
    );
  }

  /// Creates a loading screen with MITA branding
  static Widget buildLoadingScreen({
    String? message,
    bool showLogo = true,
  }) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (showLogo) ...[
              Container(
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
              const SizedBox(height: 24),
            ],
            MitaTheme.createLoadingIndicator(message: message),
          ],
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
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icon,
                  size: 64,
                  color: Colors.grey[400],
                ),
                const SizedBox(height: 24),
                Text(
                  title,
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF193C57),
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  message,
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 16,
                    color: Colors.grey[600],
                    height: 1.5,
                  ),
                  textAlign: TextAlign.center,
                ),
                if (onRetry != null) ...[
                  const SizedBox(height: 32),
                  FilledButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Try Again'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 24,
                        vertical: 12,
                      ),
                    ),
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
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 64,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 24),
            Text(
              title,
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: Color(0xFF193C57),
              ),
              textAlign: TextAlign.center,
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
      title: Text(
        title,
        style: const TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 20,
          color: Color(0xFF193C57),
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
    final color = progressColor ?? MitaTheme.getSpendingStatusColor(progress);
    
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: size,
            height: size,
            child: CircularProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              strokeWidth: strokeWidth,
              backgroundColor: Colors.grey.withValues(alpha: 0.2),
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                amount,
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w700,
                  fontSize: size * 0.12,
                  color: const Color(0xFF193C57),
                ),
              ),
              Text(
                label,
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: size * 0.08,
                  color: Colors.grey[600],
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ],
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
    final cardColor = color ?? const Color(0xFF193C57);
    
    return MitaTheme.createElevatedCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
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
                Icon(
                  Icons.arrow_forward_ios,
                  size: 16,
                  color: Colors.grey[400],
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              fontFamily: 'Sora',
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: cardColor,
            ),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 12,
                color: Colors.grey[500],
              ),
            ),
          ],
        ],
      ),
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
    return Padding(
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
    );
  }
}
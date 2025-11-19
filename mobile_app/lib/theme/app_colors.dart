import 'package:flutter/material.dart';

/// Centralized color definitions for MITA app
/// Use these instead of hardcoded Color(0xFF...) values
///
/// Usage:
/// ```dart
/// import '../theme/app_colors.dart';
///
/// Container(
///   color: AppColors.background,
///   child: Text('Hello', style: TextStyle(color: AppColors.textPrimary)),
/// )
/// ```
class AppColors {
  // Private constructor to prevent instantiation
  AppColors._();

  // ═══════════════════════════════════════════════════════════════════════════
  // BRAND COLORS - Primary palette
  // ═══════════════════════════════════════════════════════════════════════════

  /// Primary brand color - Deep navy blue (most used: 316 times)
  static const Color primary = Color(0xFF193C57);

  /// Primary light variant - For gradients
  static const Color primaryLight = Color(0xFF2B5876);

  /// Secondary brand color - Warm yellow/gold
  static const Color secondary = Color(0xFFFFD25F);

  /// Accent color - Purple
  static const Color accent = Color(0xFF6B73FF);

  /// Background color - Warm cream (used: 77 times)
  static const Color background = Color(0xFFFFF9F0);

  /// Surface color - White for cards and elevated surfaces
  static const Color surface = Color(0xFFFFFFFF);

  // ═══════════════════════════════════════════════════════════════════════════
  // TEXT COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Primary text color - Dark navy
  static const Color textPrimary = Color(0xFF193C57);

  /// Secondary text color - Gray
  static const Color textSecondary = Color(0xFF666666);

  /// Light text color - For use on dark backgrounds
  static const Color textLight = Color(0xFFFFFFFF);

  /// Muted text color - For placeholders and hints
  static const Color textMuted = Color(0xFF79747E);

  /// Disabled text color
  static const Color textDisabled = Color(0xFF49454F);

  // ═══════════════════════════════════════════════════════════════════════════
  // STATUS COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Success color - Green (used: 40 times)
  static const Color success = Color(0xFF4CAF50);

  /// Success dark - Darker green for emphasis
  static const Color successDark = Color(0xFF2E7D32);

  /// Success light - Light green for backgrounds
  static const Color successLight = Color(0xFF84FAA1);

  /// Warning color - Orange (used: 20 times)
  static const Color warning = Color(0xFFFF9800);

  /// Warning dark - Darker orange
  static const Color warningDark = Color(0xFFFF5722);

  /// Error color - Red (used: 11 times)
  static const Color error = Color(0xFFF44336);

  /// Error dark - Darker red
  static const Color errorDark = Color(0xFFBA1A1A);

  /// Error light - Light red for backgrounds
  static const Color errorLight = Color(0xFFFFDAD6);

  /// Error text on light background
  static const Color errorOnLight = Color(0xFF410002);

  /// Danger color - Bright red for critical warnings
  static const Color danger = Color(0xFFFF5C5C);

  /// Info color - Blue (used: 17 times)
  static const Color info = Color(0xFF2196F3);

  // ═══════════════════════════════════════════════════════════════════════════
  // CATEGORY COLORS - For expense/transaction categories
  // ═══════════════════════════════════════════════════════════════════════════

  /// Food category
  static const Color categoryFood = Color(0xFFFF9800);

  /// Transport category
  static const Color categoryTransport = Color(0xFF2196F3);

  /// Entertainment category
  static const Color categoryEntertainment = Color(0xFF9C27B0);

  /// Shopping category
  static const Color categoryShopping = Color(0xFFFF5722);

  /// Health category
  static const Color categoryHealth = Color(0xFF4CAF50);

  /// Education category
  static const Color categoryEducation = Color(0xFF673AB7);

  /// Utilities category
  static const Color categoryUtilities = Color(0xFF607D8B);

  /// Other category
  static const Color categoryOther = Color(0xFF795548);

  // ═══════════════════════════════════════════════════════════════════════════
  // CHART COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Chart color 1 - Primary
  static const Color chart1 = Color(0xFF193C57);

  /// Chart color 2 - Secondary
  static const Color chart2 = Color(0xFFFFD25F);

  /// Chart color 3 - Green
  static const Color chart3 = Color(0xFF4CAF50);

  /// Chart color 4 - Blue
  static const Color chart4 = Color(0xFF2196F3);

  /// Chart color 5 - Purple
  static const Color chart5 = Color(0xFF9C27B0);

  /// Chart color 6 - Orange
  static const Color chart6 = Color(0xFFFF9800);

  /// Chart color 7 - Cyan
  static const Color chart7 = Color(0xFF00BCD4);

  /// Chart color 8 - Deep purple
  static const Color chart8 = Color(0xFF673AB7);

  // ═══════════════════════════════════════════════════════════════════════════
  // UI ELEMENT COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Divider color
  static const Color divider = Color(0xFFE7E0EC);

  /// Border/outline color
  static const Color outline = Color(0xFF79747E);

  /// Light outline for subtle borders
  static const Color outlineLight = Color(0xFFCAC4D0);

  /// Card shadow color
  static const Color shadow = Color(0x1A000000);

  /// Overlay color for modals
  static const Color overlay = Color(0x80000000);

  /// Tab indicator color
  static const Color tabIndicator = Color(0xFFFFD25F);

  /// Input field background
  static const Color inputBackground = Color(0xFFF5F5F5);

  // ═══════════════════════════════════════════════════════════════════════════
  // SPECIAL PURPOSE COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Premium/Gold color for premium features
  static const Color premium = Color(0xFFFFD25F);

  /// Slate purple for special elements
  static const Color slatePurple = Color(0xFF6A5ACD);

  /// Dark surface for dark mode elements
  static const Color darkSurface = Color(0xFF1A1C18);

  // ═══════════════════════════════════════════════════════════════════════════
  // GRADIENT COLORS - For gradient effects
  // ═══════════════════════════════════════════════════════════════════════════

  /// Light info background
  static const Color infoLight = Color(0xFFF0F4FF);

  /// Info light variant for gradients
  static const Color infoLightVariant = Color(0xFF42A5F5);

  /// Success light variant for gradients
  static const Color successLightVariant = Color(0xFF66BB6A);

  /// Entertainment light variant for gradients
  static const Color entertainmentLightVariant = Color(0xFFBA68C8);

  /// Education light variant for gradients
  static const Color educationLightVariant = Color(0xFF9575CD);

  /// Emerald/teal green
  static const Color emerald = Color(0xFF10B981);

  /// Emerald dark
  static const Color emeraldDark = Color(0xFF059669);

  /// Deep blue
  static const Color deepBlue = Color(0xFF1E3A8A);

  /// Deep blue light
  static const Color deepBlueLight = Color(0xFF1E40AF);

  /// Indigo
  static const Color indigo = Color(0xFF6366F1);

  /// Violet
  static const Color violet = Color(0xFF8B5CF6);

  /// Gray fallback
  static const Color grayFallback = Color(0xFF757575);

  // ═══════════════════════════════════════════════════════════════════════════
  // RISK LEVEL COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// High risk - Light red (equivalent to Colors.red.shade300)
  static const Color riskHigh = Color(0xFFE57373);

  /// Moderate risk - Light yellow (equivalent to Colors.yellow.shade300)
  static const Color riskModerate = Color(0xFFFFF176);

  /// Low risk - Light green (equivalent to Colors.green.shade300)
  static const Color riskLow = Color(0xFF81C784);

  // ═══════════════════════════════════════════════════════════════════════════
  // TRANSPARENCY VARIANTS
  // ═══════════════════════════════════════════════════════════════════════════

  /// White with 70% opacity (equivalent to Colors.white70)
  static const Color textLightMuted = Color(0xB3FFFFFF);

  /// White with 80% opacity
  static const Color textLightSubtle = Color(0xCCFFFFFF);

  /// White with 20% opacity - for backgrounds on dark surfaces
  static const Color surfaceLight20 = Color(0x33FFFFFF);

  /// White with 10% opacity - for subtle backgrounds
  static const Color surfaceLight10 = Color(0x1AFFFFFF);

  /// White with 50% opacity
  static const Color surfaceLight50 = Color(0x80FFFFFF);

  /// White with 60% opacity
  static const Color textLightDimmed = Color(0x99FFFFFF);

  /// White with 90% opacity
  static const Color textLightBright = Color(0xE6FFFFFF);

  // ═══════════════════════════════════════════════════════════════════════════
  // BORDER COLORS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Standard border color
  static const Color border = Color(0xFFE0E0E0);

  /// Unread notification background
  static const Color notificationUnread = Color(0xFFFFEEC0);

  // ═══════════════════════════════════════════════════════════════════════════
  // HELPER METHODS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Get spending status color based on percentage of budget used
  /// - <= 70%: success (green)
  /// - 70-90%: warning (orange)
  /// - > 90%: error (red)
  static Color getSpendingStatus(double percentage) {
    if (percentage <= 0.7) return success;
    if (percentage <= 0.9) return warning;
    return error;
  }

  /// Get progress color based on completion percentage
  /// - >= 70%: success (green)
  /// - 40-70%: warning (orange)
  /// - < 40%: error (red)
  static Color getProgressColor(double percentage) {
    if (percentage >= 0.7) return success;
    if (percentage >= 0.4) return warning;
    return error;
  }

  /// Get color for a category by name
  static Color getCategoryColor(String category) {
    switch (category.toLowerCase()) {
      case 'food':
        return categoryFood;
      case 'transport':
      case 'transportation':
        return categoryTransport;
      case 'entertainment':
        return categoryEntertainment;
      case 'shopping':
        return categoryShopping;
      case 'health':
      case 'healthcare':
        return categoryHealth;
      case 'education':
        return categoryEducation;
      case 'utilities':
        return categoryUtilities;
      default:
        return categoryOther;
    }
  }

  /// Get chart color by index (cycles through available colors)
  static Color getChartColor(int index) {
    final colors = [chart1, chart2, chart3, chart4, chart5, chart6, chart7, chart8];
    return colors[index % colors.length];
  }

  /// Create a color with opacity
  static Color withOpacity(Color color, double opacity) {
    return color.withValues(alpha: opacity);
  }

  /// Get risk level color based on risk level string
  /// - 'high': riskHigh (red)
  /// - 'moderate': riskModerate (yellow)
  /// - 'low': riskLow (green)
  static Color getRiskColor(String riskLevel) {
    switch (riskLevel.toLowerCase()) {
      case 'high':
        return riskHigh;
      case 'moderate':
        return riskModerate;
      case 'low':
      default:
        return riskLow;
    }
  }

  /// Get risk icon based on risk level string
  static IconData getRiskIcon(String riskLevel) {
    switch (riskLevel.toLowerCase()) {
      case 'high':
        return Icons.warning;
      case 'moderate':
        return Icons.info;
      case 'low':
      default:
        return Icons.check_circle;
    }
  }
}

import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Centralized typography definitions for MITA app
/// Use these instead of hardcoded TextStyle with fontFamily
///
/// Usage:
/// ```dart
/// import '../theme/app_typography.dart';
///
/// Text('Hello', style: AppTypography.heading1),
/// Text('Body text', style: AppTypography.bodyLarge),
/// ```
class AppTypography {
  // Private constructor to prevent instantiation
  AppTypography._();

  // ═══════════════════════════════════════════════════════════════════════════
  // FONT FAMILIES
  // ═══════════════════════════════════════════════════════════════════════════

  /// Primary heading font - Sora
  static const String fontHeading = 'Sora';

  /// Body text font - Manrope
  static const String fontBody = 'Manrope';

  // ═══════════════════════════════════════════════════════════════════════════
  // HEADING STYLES - Use Sora font
  // ═══════════════════════════════════════════════════════════════════════════

  /// Display Large - 57px, for hero sections
  static const TextStyle displayLarge = TextStyle(
    fontFamily: fontHeading,
    fontSize: 57,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.25,
    color: AppColors.textPrimary,
  );

  /// Display Medium - 45px
  static const TextStyle displayMedium = TextStyle(
    fontFamily: fontHeading,
    fontSize: 45,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  /// Display Small - 36px
  static const TextStyle displaySmall = TextStyle(
    fontFamily: fontHeading,
    fontSize: 36,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  /// Heading 1 - 32px, bold, for main page titles
  static const TextStyle heading1 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  /// Heading 2 - 24px, bold, for section titles
  static const TextStyle heading2 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 24,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  /// Heading 3 - 22px, semibold, for AppBar titles
  static const TextStyle heading3 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 22,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Heading 4 - 18px, semibold, for card titles
  static const TextStyle heading4 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Heading 5 - 16px, semibold, for list item titles
  static const TextStyle heading5 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Heading 6 - 14px, semibold, for small headings
  static const TextStyle heading6 = TextStyle(
    fontFamily: fontHeading,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // BODY STYLES - Use Manrope font
  // ═══════════════════════════════════════════════════════════════════════════

  /// Body Large - 16px, for primary body text
  static const TextStyle bodyLarge = TextStyle(
    fontFamily: fontBody,
    fontSize: 16,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.5,
    color: AppColors.textPrimary,
  );

  /// Body Medium - 14px, for secondary body text
  static const TextStyle bodyMedium = TextStyle(
    fontFamily: fontBody,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.25,
    color: AppColors.textPrimary,
  );

  /// Body Small - 12px, for captions and footnotes
  static const TextStyle bodySmall = TextStyle(
    fontFamily: fontBody,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.4,
    color: AppColors.textSecondary,
  );

  /// Body Large Medium Weight - 16px, medium
  static const TextStyle bodyLargeMedium = TextStyle(
    fontFamily: fontBody,
    fontSize: 16,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.5,
    color: AppColors.textPrimary,
  );

  /// Body Medium Weight - 14px, medium
  static const TextStyle bodyMediumWeight = TextStyle(
    fontFamily: fontBody,
    fontSize: 14,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.25,
    color: AppColors.textPrimary,
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // LABEL STYLES - For buttons, tabs, chips
  // ═══════════════════════════════════════════════════════════════════════════

  /// Label Large - 16px, for primary buttons
  static const TextStyle labelLarge = TextStyle(
    fontFamily: fontHeading,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    color: AppColors.textPrimary,
  );

  /// Label Medium - 14px, for secondary buttons
  static const TextStyle labelMedium = TextStyle(
    fontFamily: fontHeading,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
    color: AppColors.textPrimary,
  );

  /// Label Small - 12px, for chips and badges
  static const TextStyle labelSmall = TextStyle(
    fontFamily: fontHeading,
    fontSize: 12,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.5,
    color: AppColors.textPrimary,
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // SPECIAL PURPOSE STYLES
  // ═══════════════════════════════════════════════════════════════════════════

  /// Button text style
  static const TextStyle button = TextStyle(
    fontFamily: fontHeading,
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  /// Button small text style
  static const TextStyle buttonSmall = TextStyle(
    fontFamily: fontHeading,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Caption style for very small text
  static const TextStyle caption = TextStyle(
    fontFamily: fontBody,
    fontSize: 11,
    fontWeight: FontWeight.w400,
    letterSpacing: 0.5,
    color: AppColors.textSecondary,
  );

  /// Overline style for labels above inputs
  static const TextStyle overline = TextStyle(
    fontFamily: fontBody,
    fontSize: 10,
    fontWeight: FontWeight.w500,
    letterSpacing: 1.5,
    color: AppColors.textSecondary,
  );

  /// Number display - Large numbers for amounts
  static const TextStyle numberLarge = TextStyle(
    fontFamily: fontHeading,
    fontSize: 36,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  /// Number medium - For card amounts
  static const TextStyle numberMedium = TextStyle(
    fontFamily: fontHeading,
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Number small - For inline amounts
  static const TextStyle numberSmall = TextStyle(
    fontFamily: fontHeading,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  /// Link style
  static const TextStyle link = TextStyle(
    fontFamily: fontBody,
    fontSize: 14,
    fontWeight: FontWeight.w500,
    color: AppColors.info,
    decoration: TextDecoration.underline,
  );

  /// Error text style
  static const TextStyle error = TextStyle(
    fontFamily: fontBody,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: AppColors.error,
  );

  /// Hint/placeholder text style
  static const TextStyle hint = TextStyle(
    fontFamily: fontBody,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AppColors.textMuted,
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // HELPER METHODS
  // ═══════════════════════════════════════════════════════════════════════════

  /// Get a text style with custom color
  static TextStyle withColor(TextStyle style, Color color) {
    return style.copyWith(color: color);
  }

  /// Get a text style for light background (inverted colors)
  static TextStyle onDark(TextStyle style) {
    return style.copyWith(color: AppColors.textLight);
  }

  /// Get a text style with success color
  static TextStyle asSuccess(TextStyle style) {
    return style.copyWith(color: AppColors.success);
  }

  /// Get a text style with warning color
  static TextStyle asWarning(TextStyle style) {
    return style.copyWith(color: AppColors.warning);
  }

  /// Get a text style with error color
  static TextStyle asError(TextStyle style) {
    return style.copyWith(color: AppColors.error);
  }

  /// Get a muted version of a text style
  static TextStyle asMuted(TextStyle style) {
    return style.copyWith(color: AppColors.textSecondary);
  }
}

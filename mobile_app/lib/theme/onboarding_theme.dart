import 'package:flutter/material.dart';

/// Unified design system constants for onboarding screens
/// Ensures consistent look and feel across all onboarding steps
class OnboardingTheme {
  // Colors
  static const Color backgroundColor = Color(0xFFFFF9F0);
  static const Color primaryColor = Color(0xFF193C57);
  static const Color accentColor = Color(0xFFFFD25F);
  static const Color textPrimary = Color(0xFF193C57);
  static final Color textSecondary = Colors.grey.shade700;
  static const Color cardBackground = Colors.white;

  // Card styles
  static const double cardElevation = 2.0;
  static const double cardBorderRadius = 20.0;
  static const double cardPadding = 20.0;

  // Border radius
  static const double buttonBorderRadius = 18.0;
  static const double inputBorderRadius = 14.0;
  static const double smallBorderRadius = 12.0;

  // Spacing
  static const double spacingXS = 8.0;
  static const double spacingS = 12.0;
  static const double spacingM = 16.0;
  static const double spacingL = 20.0;
  static const double spacingXL = 24.0;

  // Text styles
  static const TextStyle headingStyle = TextStyle(
    fontFamily: 'Sora',
    fontWeight: FontWeight.w700,
    fontSize: 22,
    color: textPrimary,
  );

  static TextStyle bodyStyle = TextStyle(
    fontFamily: 'Manrope',
    color: textSecondary,
    fontSize: 14,
  );

  static const TextStyle buttonTextStyle = TextStyle(
    fontFamily: 'Sora',
    fontWeight: FontWeight.w600,
    fontSize: 16,
  );

  // Button styles
  static ButtonStyle primaryButtonStyle = ElevatedButton.styleFrom(
    backgroundColor: primaryColor,
    foregroundColor: Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(buttonBorderRadius),
    ),
    padding: const EdgeInsets.symmetric(vertical: 16),
    textStyle: buttonTextStyle,
    elevation: 0,
  );

  static ButtonStyle secondaryButtonStyle = TextButton.styleFrom(
    foregroundColor: Colors.grey,
    textStyle: const TextStyle(
      fontFamily: 'Sora',
      fontSize: 15,
    ),
  );

  // Input decoration
  static InputDecoration inputDecoration({
    required String labelText,
    String? hintText,
    String? prefixText,
    IconData? prefixIcon,
  }) {
    return InputDecoration(
      labelText: labelText,
      hintText: hintText,
      prefixText: prefixText,
      prefixIcon:
          prefixIcon != null ? Icon(prefixIcon, color: primaryColor) : null,
      filled: true,
      fillColor: cardBackground,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(inputBorderRadius),
        borderSide: BorderSide(color: Colors.grey.shade300),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(inputBorderRadius),
        borderSide: BorderSide(color: Colors.grey.shade300),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(inputBorderRadius),
        borderSide: const BorderSide(color: primaryColor, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
    );
  }

  // Card decoration
  static BoxDecoration cardDecoration({bool isSelected = false}) {
    return BoxDecoration(
      color: isSelected ? accentColor.withOpacity(0.2) : cardBackground,
      borderRadius: BorderRadius.circular(cardBorderRadius),
      border: Border.all(
        color: isSelected ? primaryColor : Colors.grey.shade300,
        width: isSelected ? 2 : 1,
      ),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withOpacity(0.05),
          blurRadius: cardElevation * 2,
          offset: const Offset(0, 2),
        ),
      ],
    );
  }

  // AppBar
  static AppBar buildAppBar({VoidCallback? onBack}) {
    return AppBar(
      backgroundColor: backgroundColor,
      elevation: 0,
      leading: onBack != null
          ? IconButton(
              icon: const Icon(Icons.arrow_back, color: primaryColor),
              onPressed: onBack,
            )
          : null,
    );
  }
}

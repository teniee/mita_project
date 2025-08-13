import 'package:flutter/material.dart';
import '../services/income_service.dart';

/// Income-based theme system for MITA
/// Provides Material 3 color schemes based on user's income tier
class IncomeTheme {
  static final IncomeService _incomeService = IncomeService();

  /// Get themed color scheme based on income tier
  static ColorScheme getIncomeColorScheme(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return _getLowIncomeColorScheme();
      case IncomeTier.lowerMiddle:
        return _getLowerMiddleIncomeColorScheme();
      case IncomeTier.middle:
        return _getMidIncomeColorScheme();
      case IncomeTier.upperMiddle:
        return _getUpperMiddleIncomeColorScheme();
      case IncomeTier.high:
        return _getHighIncomeColorScheme();
    }
  }

  /// Essential Earner (Low Income) - Green Growth Theme
  static ColorScheme _getLowIncomeColorScheme() {
    return const ColorScheme.light(
      primary: Color(0xFF2E7D32),        // Deep green
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFA5D6A7), // Light green container
      onPrimaryContainer: Color(0xFF1B5E20),
      secondary: Color(0xFF66BB6A),       // Medium green
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFC8E6C9),
      onSecondaryContainer: Color(0xFF2E7D32),
      tertiary: Color(0xFF81C784),        // Lighter green
      onTertiary: Color(0xFF1B5E20),
      tertiaryContainer: Color(0xFFE8F5E8),
      onTertiaryContainer: Color(0xFF2E7D32),
      surface: Color(0xFFFFFFFE),
      onSurface: Color(0xFF1A1C18),
      surfaceContainerHighest: Color(0xFFE7E0EC),
      onSurfaceVariant: Color(0xFF49454F),
      outline: Color(0xFF79747E),
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
    );
  }

  /// Rising Saver (Lower Middle Income) - Cyan Rising Theme
  static ColorScheme _getLowerMiddleIncomeColorScheme() {
    return const ColorScheme.light(
      primary: Color(0xFF00BCD4),        // Cyan
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFB2EBF2), // Light cyan container
      onPrimaryContainer: Color(0xFF006064),
      secondary: Color(0xFF26C6DA),       // Medium cyan
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFE0F7FA),
      onSecondaryContainer: Color(0xFF00BCD4),
      tertiary: Color(0xFF4DD0E1),        // Lighter cyan
      onTertiary: Color(0xFF006064),
      tertiaryContainer: Color(0xFFE0F2F1),
      onTertiaryContainer: Color(0xFF00BCD4),
      surface: Color(0xFFFFFFFE),
      onSurface: Color(0xFF1A1C18),
      surfaceContainerHighest: Color(0xFFE7E0EC),
      onSurfaceVariant: Color(0xFF49454F),
      outline: Color(0xFF79747E),
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
    );
  }

  /// Growing Professional (Mid Income) - Blue Professional Theme
  static ColorScheme _getMidIncomeColorScheme() {
    return const ColorScheme.light(
      primary: Color(0xFF1976D2),        // Professional blue
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFBBDEFB), // Light blue container
      onPrimaryContainer: Color(0xFF0D47A1),
      secondary: Color(0xFF42A5F5),       // Medium blue
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFE3F2FD),
      onSecondaryContainer: Color(0xFF1976D2),
      tertiary: Color(0xFF64B5F6),        // Lighter blue
      onTertiary: Color(0xFF0D47A1),
      tertiaryContainer: Color(0xFFE1F5FE),
      onTertiaryContainer: Color(0xFF1976D2),
      surface: Color(0xFFFFFFFE),
      onSurface: Color(0xFF1A1C18),
      surfaceContainerHighest: Color(0xFFE7E0EC),
      onSurfaceVariant: Color(0xFF49454F),
      outline: Color(0xFF79747E),
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
    );
  }

  /// Established Professional (Upper Middle Income) - Deep Purple Established Theme
  static ColorScheme _getUpperMiddleIncomeColorScheme() {
    return const ColorScheme.light(
      primary: Color(0xFF673AB7),        // Deep purple
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFD1C4E9), // Light deep purple container
      onPrimaryContainer: Color(0xFF311B92),
      secondary: Color(0xFF7986CB),       // Medium deep purple
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFEDE7F6),
      onSecondaryContainer: Color(0xFF673AB7),
      tertiary: Color(0xFF9575CD),        // Lighter deep purple
      onTertiary: Color(0xFF311B92),
      tertiaryContainer: Color(0xFFF3E5F5),
      onTertiaryContainer: Color(0xFF673AB7),
      surface: Color(0xFFFFFFFE),
      onSurface: Color(0xFF1A1C18),
      surfaceContainerHighest: Color(0xFFE7E0EC),
      onSurfaceVariant: Color(0xFF49454F),
      outline: Color(0xFF79747E),
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
    );
  }

  /// High Achiever (High Income) - Purple Premium Theme
  static ColorScheme _getHighIncomeColorScheme() {
    return const ColorScheme.light(
      primary: Color(0xFF7B1FA2),        // Deep purple
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFE1BEE7), // Light purple container
      onPrimaryContainer: Color(0xFF4A148C),
      secondary: Color(0xFF9C27B0),       // Medium purple
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFF3E5F5),
      onSecondaryContainer: Color(0xFF7B1FA2),
      tertiary: Color(0xFFBA68C8),        // Lighter purple
      onTertiary: Color(0xFF4A148C),
      tertiaryContainer: Color(0xFFFCE4EC),
      onTertiaryContainer: Color(0xFF7B1FA2),
      surface: Color(0xFFFFFFFE),
      onSurface: Color(0xFF1A1C18),
      surfaceContainerHighest: Color(0xFFE7E0EC),
      onSurfaceVariant: Color(0xFF49454F),
      outline: Color(0xFF79747E),
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
    );
  }

  /// Get theme data for specific income tier
  static ThemeData getIncomeTheme(IncomeTier tier) {
    final colorScheme = getIncomeColorScheme(tier);
    
    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      fontFamily: 'Manrope',
      
      // App Bar Theme
      appBarTheme: AppBarTheme(
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 20,
          color: colorScheme.onSurface,
        ),
      ),
      
      // Card Theme
      cardTheme: CardThemeData(
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        color: colorScheme.surface,
      ),
      
      // Elevated Button Theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colorScheme.primary,
          foregroundColor: colorScheme.onPrimary,
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        ),
      ),
      
      // Input Decoration Theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: colorScheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: colorScheme.error, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: colorScheme.error, width: 2),
        ),
        labelStyle: TextStyle(
          fontFamily: 'Manrope',
          color: colorScheme.onSurface,
        ),
        hintStyle: TextStyle(
          fontFamily: 'Manrope',
          color: colorScheme.onSurface.withValues(alpha: 0.6),
        ),
      ),
      
      // Text Theme
      textTheme: TextTheme(
        displayLarge: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 32,
          color: colorScheme.onSurface,
        ),
        displayMedium: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 28,
          color: colorScheme.onSurface,
        ),
        displaySmall: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 24,
          color: colorScheme.onSurface,
        ),
        headlineLarge: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 22,
          color: colorScheme.onSurface,
        ),
        headlineMedium: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 20,
          color: colorScheme.onSurface,
        ),
        headlineSmall: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 18,
          color: colorScheme.onSurface,
        ),
        titleLarge: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 16,
          color: colorScheme.onSurface,
        ),
        titleMedium: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w500,
          fontSize: 14,
          color: colorScheme.onSurface,
        ),
        titleSmall: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w500,
          fontSize: 12,
          color: colorScheme.onSurface,
        ),
        bodyLarge: TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w400,
          fontSize: 16,
          color: colorScheme.onSurface,
        ),
        bodyMedium: TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w400,
          fontSize: 14,
          color: colorScheme.onSurface,
        ),
        bodySmall: TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w400,
          fontSize: 12,
          color: colorScheme.onSurface.withValues(alpha: 0.8),
        ),
        labelLarge: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 14,
          color: colorScheme.onSurface,
        ),
        labelMedium: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w500,
          fontSize: 12,
          color: colorScheme.onSurface,
        ),
        labelSmall: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w500,
          fontSize: 10,
          color: colorScheme.onSurface,
        ),
      ),
    );
  }

  /// Get spending status colors based on income tier
  static Map<String, Color> getSpendingStatusColors(IncomeTier tier) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    
    return {
      'good': primary,
      'warning': Colors.orange.shade600,
      'over': Colors.red.shade600,
      'excellent': primary.withValues(alpha: 0.8),
    };
  }

  /// Get budget category colors based on income tier
  static Map<String, Color> getBudgetCategoryColors(IncomeTier tier) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    final secondary = _incomeService.getIncomeTierSecondaryColor(tier);
    
    switch (tier) {
      case IncomeTier.low:
        return {
          'housing': const Color(0xFF388E3C),    // Deep green
          'food': const Color(0xFF66BB6A),       // Medium green
          'transportation': const Color(0xFF81C784), // Light green
          'utilities': const Color(0xFF4CAF50),  // Green
          'healthcare': const Color(0xFF2E7D32), // Dark green
          'entertainment': const Color(0xFFA5D6A7), // Very light green
          'savings': const Color(0xFF1B5E20),    // Very dark green
          'other': Colors.grey.shade500,
        };
      case IncomeTier.lowerMiddle:
        return {
          'housing': const Color(0xFF00ACC1),    // Deep cyan
          'food': const Color(0xFF26C6DA),       // Medium cyan
          'transportation': const Color(0xFF4DD0E1), // Light cyan
          'utilities': const Color(0xFF00BCD4),  // Cyan
          'healthcare': const Color(0xFF006064), // Dark cyan
          'entertainment': const Color(0xFFB2EBF2), // Very light cyan
          'savings': const Color(0xFF00838F),    // Very dark cyan
          'other': Colors.grey.shade500,
        };
      case IncomeTier.middle:
        return {
          'housing': const Color(0xFF1976D2),    // Deep blue
          'food': const Color(0xFF42A5F5),       // Medium blue  
          'transportation': const Color(0xFF64B5F6), // Light blue
          'utilities': const Color(0xFF2196F3),  // Blue
          'healthcare': const Color(0xFF0D47A1), // Dark blue
          'entertainment': const Color(0xFFBBDEFB), // Very light blue
          'savings': const Color(0xFF0277BD),    // Very dark blue
          'other': Colors.grey.shade500,
        };
      case IncomeTier.upperMiddle:
        return {
          'housing': const Color(0xFF5E35B1),    // Deep purple
          'food': const Color(0xFF7986CB),       // Medium purple
          'transportation': const Color(0xFF9575CD), // Light purple
          'utilities': const Color(0xFF673AB7),  // Deep purple
          'healthcare': const Color(0xFF311B92), // Dark purple
          'entertainment': const Color(0xFFD1C4E9), // Very light purple
          'savings': const Color(0xFF4527A0),    // Very dark purple
          'other': Colors.grey.shade500,
        };
      case IncomeTier.high:
        return {
          'housing': const Color(0xFF7B1FA2),    // Deep purple
          'food': const Color(0xFF9C27B0),       // Medium purple
          'transportation': const Color(0xFFBA68C8), // Light purple
          'utilities': const Color(0xFF8E24AA),  // Purple
          'healthcare': const Color(0xFF4A148C), // Dark purple
          'entertainment': const Color(0xFFE1BEE7), // Very light purple
          'savings': const Color(0xFF6A1B9A),    // Very dark purple
          'other': Colors.grey.shade500,
        };
    }
  }

  /// Get tier-specific gradients
  static LinearGradient getTierGradient(IncomeTier tier) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    final secondary = _incomeService.getIncomeTierSecondaryColor(tier);
    
    return LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        secondary,
        secondary.withValues(alpha: 0.7),
        secondary.withValues(alpha: 0.5),
      ],
    );
  }

  /// Get tier-specific shadow colors
  static List<BoxShadow> getTierShadows(IncomeTier tier) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    
    return [
      BoxShadow(
        color: primary.withValues(alpha: 0.1),
        offset: const Offset(0, 4),
        blurRadius: 12,
        spreadRadius: 0,
      ),
      BoxShadow(
        color: primary.withValues(alpha: 0.05),
        offset: const Offset(0, 2),
        blurRadius: 6,
        spreadRadius: 0,
      ),
    ];
  }

  /// Create tier-specific decorated container
  static Widget createTierContainer({
    required IncomeTier tier,
    required Widget child,
    EdgeInsetsGeometry? padding,
    EdgeInsetsGeometry? margin,
    double borderRadius = 16,
  }) {
    final gradient = getTierGradient(tier);
    final shadows = getTierShadows(tier);
    
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: shadows,
      ),
      child: Padding(
        padding: padding ?? const EdgeInsets.all(16),
        child: child,
      ),
    );
  }

  /// Get tier-appropriate success/warning/error indicators
  static Map<String, Color> getTierStatusColors(IncomeTier tier) {
    return {
      'success': Colors.green.shade600,
      'warning': Colors.orange.shade600,
      'error': Colors.red.shade600,
      'info': _incomeService.getIncomeTierPrimaryColor(tier),
    };
  }

  /// Create tier-themed floating action button
  static FloatingActionButton createTierFAB({
    required IncomeTier tier,
    required VoidCallback onPressed,
    required Widget child,
  }) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    
    return FloatingActionButton(
      onPressed: onPressed,
      backgroundColor: primary,
      foregroundColor: Colors.white,
      elevation: 6,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: child,
    );
  }

  /// Create tier-themed app bar
  static AppBar createTierAppBar({
    required IncomeTier tier,
    required String title,
    List<Widget>? actions,
    Widget? leading,
    bool centerTitle = true,
  }) {
    final primary = _incomeService.getIncomeTierPrimaryColor(tier);
    
    return AppBar(
      title: Text(
        title,
        style: const TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
        ),
      ),
      backgroundColor: Colors.white,
      foregroundColor: primary,
      elevation: 0,
      centerTitle: centerTitle,
      actions: actions,
      leading: leading,
      iconTheme: IconThemeData(color: primary),
    );
  }
}
import 'package:flutter/material.dart';

/// MITA Material Design 3 Theme System
/// Provides consistent theming across all screens with proper Material 3 implementation
class MitaTheme {
  // MITA Brand Colors
  static const Color _mitaPrimary = Color(0xFF193C57);  // Deep navy blue
  static const Color _mitaSecondary = Color(0xFFFFD25F); // Warm yellow
  static const Color _mitaBackground = Color(0xFFFFF9F0); // Warm cream
  static const Color _mitaSurface = Color(0xFFFFFFFF);   // Pure white
  
  /// Material 3 Light Color Scheme
  static const ColorScheme _lightColorScheme = ColorScheme.light(
    // Primary colors
    primary: _mitaPrimary,
    onPrimary: Colors.white,
    primaryContainer: Color(0xFFE1F4FD),
    onPrimaryContainer: Color(0xFF0A1A25),
    
    // Secondary colors
    secondary: _mitaSecondary,
    onSecondary: _mitaPrimary,
    secondaryContainer: Color(0xFFFFF8E1),
    onSecondaryContainer: Color(0xFF3D2F00),
    
    // Tertiary colors
    tertiary: Color(0xFF4CAF50),
    onTertiary: Colors.white,
    tertiaryContainer: Color(0xFFE8F5E8),
    onTertiaryContainer: Color(0xFF1B5E20),
    
    // Surface colors
    surface: _mitaSurface,
    onSurface: Color(0xFF1A1B1E),
    onSurfaceVariant: Color(0xFF49454F),
    surfaceContainerHighest: Color(0xFFF7F2FA),
    surfaceContainerHigh: Color(0xFFF2EEFA),
    surfaceContainer: Color(0xFFECE6F0),
    surfaceContainerLow: Color(0xFFF7F2FA),
    surfaceContainerLowest: Colors.white,
    
    // Error colors
    error: Color(0xFFBA1A1A),
    onError: Colors.white,
    errorContainer: Color(0xFFFFDAD6),
    onErrorContainer: Color(0xFF410002),
    
    // Outline colors
    outline: Color(0xFF79747E),
    outlineVariant: Color(0xFFCAC4D0),
    scrim: Color(0xFF000000),
    shadow: Color(0xFF000000),
  );
  
  /// Material 3 Dark Color Scheme
  static const ColorScheme _darkColorScheme = ColorScheme.dark(
    // Primary colors
    primary: Color(0xFF9CCEFF),
    onPrimary: Color(0xFF003258),
    primaryContainer: Color(0xFF004A77),
    onPrimaryContainer: Color(0xFFD1E4FF),
    
    // Secondary colors
    secondary: Color(0xFFE6C200),
    onSecondary: Color(0xFF3D2F00),
    secondaryContainer: Color(0xFF5A4300),
    onSecondaryContainer: Color(0xFFFFDF9C),
    
    // Tertiary colors
    tertiary: Color(0xFF81C784),
    onTertiary: Color(0xFF003910),
    tertiaryContainer: Color(0xFF1B5E20),
    onTertiaryContainer: Color(0xFFA5D6A7),
    
    // Surface colors
    surface: Color(0xFF101214),
    onSurface: Color(0xFFE2E2E9),
    onSurfaceVariant: Color(0xFFCAC4D0),
    surfaceContainerHighest: Color(0xFF36343B),
    surfaceContainerHigh: Color(0xFF2B2930),
    surfaceContainer: Color(0xFF211F26),
    surfaceContainerLow: Color(0xFF1A1B1E),
    surfaceContainerLowest: Color(0xFF0F0D13),
    
    // Error colors
    error: Color(0xFFFFB4AB),
    onError: Color(0xFF690005),
    errorContainer: Color(0xFF93000A),
    onErrorContainer: Color(0xFFFFDAD6),
    
    // Outline colors
    outline: Color(0xFF938F99),
    outlineVariant: Color(0xFF49454F),
    scrim: Color(0xFF000000),
    shadow: Color(0xFF000000),
  );

  /// Main Material 3 Light Theme
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: _lightColorScheme,
      fontFamily: 'Manrope',
      
      // App Bar Theme
      appBarTheme: AppBarTheme(
        backgroundColor: _lightColorScheme.surface,
        foregroundColor: _lightColorScheme.onSurface,
        elevation: 0,
        centerTitle: true,
        scrolledUnderElevation: 1,
        titleTextStyle: const TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w700,
          fontSize: 22,
          color: _mitaPrimary,
        ),
        iconTheme: const IconThemeData(
          color: _mitaPrimary,
          size: 24,
        ),
      ),
      
      // Card Theme with proper Material 3 elevation
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(
            color: _lightColorScheme.outlineVariant,
            width: 1,
          ),
        ),
        color: _lightColorScheme.surface,
        surfaceTintColor: _lightColorScheme.surfaceTint,
      ),
      
      // Elevated Button Theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: _lightColorScheme.primary,
          foregroundColor: _lightColorScheme.onPrimary,
          elevation: 1,
          shadowColor: _lightColorScheme.shadow,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          minimumSize: const Size(64, 48),
        ),
      ),
      
      // Filled Button Theme (for primary actions)
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: _lightColorScheme.primary,
          foregroundColor: _lightColorScheme.onPrimary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          minimumSize: const Size(64, 48),
        ),
      ),
      
      // Text Button Theme
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: _lightColorScheme.primary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
          ),
          textStyle: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
      ),
      
      // Input Decoration Theme with Material 3 styling
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: _lightColorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: _lightColorScheme.outline,
            width: 1,
          ),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: _lightColorScheme.outline,
            width: 1,
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: _lightColorScheme.primary,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: _lightColorScheme.error,
            width: 1,
          ),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(
            color: _lightColorScheme.error,
            width: 2,
          ),
        ),
        labelStyle: TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w500,
          color: _lightColorScheme.onSurface,
        ),
        hintStyle: TextStyle(
          fontFamily: 'Manrope',
          color: _lightColorScheme.onSurface.withValues(alpha: 0.6),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
      
      // Checkbox Theme
      checkboxTheme: CheckboxThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
        checkColor: WidgetStateProperty.all(_lightColorScheme.onPrimary),
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return _lightColorScheme.primary;
          }
          return _lightColorScheme.outline;
        }),
      ),
      
      // Chip Theme
      chipTheme: ChipThemeData(
        backgroundColor: _lightColorScheme.surfaceContainerHighest,
        selectedColor: _lightColorScheme.secondaryContainer,
        disabledColor: _lightColorScheme.surfaceContainerHighest.withValues(alpha: 0.12),
        labelStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w500,
        ),
        secondaryLabelStyle: TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w500,
          color: _lightColorScheme.onSecondaryContainer,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        side: BorderSide(
          color: _lightColorScheme.outline,
          width: 1,
        ),
      ),
      
      // FloatingActionButton Theme
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: _lightColorScheme.primary,
        foregroundColor: _lightColorScheme.onPrimary,
        elevation: 6,
        focusElevation: 8,
        hoverElevation: 8,
        highlightElevation: 12,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      
      // Search Bar Theme
      searchBarTheme: SearchBarThemeData(
        backgroundColor: WidgetStateProperty.all(_lightColorScheme.surfaceContainer),
        surfaceTintColor: WidgetStateProperty.all(_lightColorScheme.surfaceTint),
        overlayColor: WidgetStateProperty.all(_lightColorScheme.surfaceContainerHighest.withValues(alpha: 0.8)),
        shape: WidgetStateProperty.all(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(28),
          ),
        ),
        textStyle: WidgetStateProperty.all(
          const TextStyle(
            fontFamily: 'Manrope',
            fontWeight: FontWeight.w400,
            fontSize: 16,
          ),
        ),
        hintStyle: WidgetStateProperty.all(
          TextStyle(
            fontFamily: 'Manrope',
            color: _lightColorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
      ),
      
      // SnackBar Theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: _lightColorScheme.inverseSurface,
        contentTextStyle: TextStyle(
          fontFamily: 'Manrope',
          color: _lightColorScheme.onInverseSurface,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        behavior: SnackBarBehavior.floating,
      ),
      
      // Progress Indicator Theme
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: _lightColorScheme.primary,
        linearTrackColor: _lightColorScheme.surfaceContainerHighest,
        circularTrackColor: _lightColorScheme.surfaceContainerHighest,
      ),
    );
  }

  /// Main Material 3 Dark Theme
  static ThemeData get darkTheme {
    return lightTheme.copyWith(
      colorScheme: _darkColorScheme,
      scaffoldBackgroundColor: _darkColorScheme.surface,
    );
  }

  /// MITA-specific status colors for financial indicators
  static const Map<String, Color> statusColors = {
    'success': Color(0xFF4CAF50),    // Green for under budget
    'warning': Color(0xFFFF9800),    // Orange for approaching limit
    'danger': Color(0xFFF44336),     // Red for over budget
    'info': _mitaPrimary,            // Primary for neutral info
    'excellent': Color(0xFF2E7D32),  // Dark green for excellent spending
  };

  /// Get spending status color based on budget percentage
  static Color getSpendingStatusColor(double percentage) {
    if (percentage <= 0.7) return statusColors['success']!;
    if (percentage <= 0.9) return statusColors['warning']!;
    return statusColors['danger']!;
  }

  /// Create elevated card with proper Material 3 styling
  static Widget createElevatedCard({
    required Widget child,
    EdgeInsetsGeometry? padding,
    EdgeInsetsGeometry? margin,
    double elevation = 1,
    Color? backgroundColor,
    VoidCallback? onTap,
  }) {
    return Container(
      margin: margin,
      child: Card(
        elevation: elevation,
        color: backgroundColor,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: padding ?? const EdgeInsets.all(16),
            child: child,
          ),
        ),
      ),
    );
  }

  /// Create Material 3 status indicator chip
  static Widget createStatusChip({
    required String label,
    required String status,
    IconData? icon,
  }) {
    final color = statusColors[status] ?? statusColors['info']!;
    
    return Chip(
      avatar: icon != null 
        ? Icon(icon, size: 16, color: color)
        : null,
      label: Text(
        label,
        style: TextStyle(
          fontFamily: 'Sora',
          fontWeight: FontWeight.w600,
          fontSize: 12,
          color: color,
        ),
      ),
      backgroundColor: color.withValues(alpha: 0.1),
      side: BorderSide(color: color, width: 1),
    );
  }

  /// Create loading indicator with MITA styling
  static Widget createLoadingIndicator({String? message}) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(
          color: _lightColorScheme.primary,
          strokeWidth: 3,
        ),
        if (message != null) ...[
          const SizedBox(height: 16),
          Text(
            message,
            style: const TextStyle(
              fontFamily: 'Manrope',
              fontSize: 14,
              color: _mitaPrimary,
            ),
          ),
        ],
      ],
    );
  }
}
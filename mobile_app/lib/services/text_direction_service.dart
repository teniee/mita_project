import 'package:flutter/material.dart';
import 'localization_service.dart';

/// Service to handle text direction and RTL layout support in MITA
/// Provides utilities for proper RTL/LTR layout and text handling
class TextDirectionService {
  static TextDirectionService? _instance;

  TextDirectionService._internal();

  static TextDirectionService get instance {
    _instance ??= TextDirectionService._internal();
    return _instance!;
  }

  /// Get text direction based on current locale
  TextDirection get textDirection => LocalizationService.instance.textDirection;

  /// Check if current locale uses RTL text direction
  bool get isRTL => textDirection == TextDirection.rtl;

  /// Get appropriate alignment for text in current locale
  TextAlign getTextAlign({TextAlign? fallback}) {
    if (isRTL) {
      return fallback == TextAlign.left
          ? TextAlign.right
          : fallback == TextAlign.right
              ? TextAlign.left
              : fallback ?? TextAlign.right;
    } else {
      return fallback ?? TextAlign.left;
    }
  }

  /// Get appropriate alignment for UI elements
  Alignment getAlignment({Alignment? ltrAlignment, Alignment? rtlAlignment}) {
    if (isRTL) {
      return rtlAlignment ??
          _mirrorAlignment(ltrAlignment ?? Alignment.centerLeft);
    } else {
      return ltrAlignment ?? Alignment.centerLeft;
    }
  }

  /// Get appropriate MainAxisAlignment for flex layouts
  MainAxisAlignment getMainAxisAlignment(
      {MainAxisAlignment? ltrAlignment, MainAxisAlignment? rtlAlignment}) {
    if (isRTL) {
      return rtlAlignment ??
          _mirrorMainAxisAlignment(ltrAlignment ?? MainAxisAlignment.start);
    } else {
      return ltrAlignment ?? MainAxisAlignment.start;
    }
  }

  /// Get appropriate CrossAxisAlignment for flex layouts
  CrossAxisAlignment getCrossAxisAlignment(
      {CrossAxisAlignment? ltrAlignment, CrossAxisAlignment? rtlAlignment}) {
    if (isRTL) {
      return rtlAlignment ??
          _mirrorCrossAxisAlignment(ltrAlignment ?? CrossAxisAlignment.start);
    } else {
      return ltrAlignment ?? CrossAxisAlignment.start;
    }
  }

  /// Get appropriate EdgeInsets for padding/margin with RTL support
  EdgeInsetsGeometry getEdgeInsets({
    double? left,
    double? right,
    double? top,
    double? bottom,
    double? start,
    double? end,
    double all = 0.0,
  }) {
    if (start != null || end != null) {
      // Use directional values
      return EdgeInsetsDirectional.only(
        start: start ?? 0.0,
        end: end ?? 0.0,
        top: top ?? all,
        bottom: bottom ?? all,
      );
    } else {
      // Use absolute values
      return EdgeInsets.only(
        left: left ?? all,
        right: right ?? all,
        top: top ?? all,
        bottom: bottom ?? all,
      );
    }
  }

  /// Create directional EdgeInsets that adapt to text direction
  EdgeInsetsDirectional getDirectionalPadding({
    double start = 0.0,
    double end = 0.0,
    double top = 0.0,
    double bottom = 0.0,
  }) {
    return EdgeInsetsDirectional.only(
      start: start,
      end: end,
      top: top,
      bottom: bottom,
    );
  }

  /// Get appropriate icon for directional navigation
  IconData getDirectionalIcon({
    required IconData ltrIcon,
    required IconData rtlIcon,
  }) {
    return isRTL ? rtlIcon : ltrIcon;
  }

  /// Get back navigation icon appropriate for current direction
  IconData get backIcon {
    return getDirectionalIcon(
      ltrIcon: Icons.arrow_back,
      rtlIcon: Icons.arrow_forward,
    );
  }

  /// Get forward navigation icon appropriate for current direction
  IconData get forwardIcon {
    return getDirectionalIcon(
      ltrIcon: Icons.arrow_forward,
      rtlIcon: Icons.arrow_back,
    );
  }

  /// Get chevron left icon appropriate for current direction
  IconData get chevronLeftIcon {
    return getDirectionalIcon(
      ltrIcon: Icons.chevron_left,
      rtlIcon: Icons.chevron_right,
    );
  }

  /// Get chevron right icon appropriate for current direction
  IconData get chevronRightIcon {
    return getDirectionalIcon(
      ltrIcon: Icons.chevron_right,
      rtlIcon: Icons.chevron_left,
    );
  }

  /// Wrap widget with proper directionality
  Widget wrapWithDirectionality(Widget child, {TextDirection? textDirection}) {
    return Directionality(
      textDirection: textDirection ?? this.textDirection,
      child: child,
    );
  }

  /// Create a Row widget that respects text direction
  Widget createDirectionalRow({
    required List<Widget> children,
    MainAxisAlignment mainAxisAlignment = MainAxisAlignment.start,
    CrossAxisAlignment crossAxisAlignment = CrossAxisAlignment.center,
    MainAxisSize mainAxisSize = MainAxisSize.max,
  }) {
    return Row(
      textDirection: textDirection,
      mainAxisAlignment: getMainAxisAlignment(ltrAlignment: mainAxisAlignment),
      crossAxisAlignment:
          getCrossAxisAlignment(ltrAlignment: crossAxisAlignment),
      mainAxisSize: mainAxisSize,
      children: children,
    );
  }

  /// Create appropriate positioned widget for floating elements
  Widget createDirectionalPositioned({
    required Widget child,
    double? start,
    double? end,
    double? top,
    double? bottom,
  }) {
    if (isRTL) {
      return Positioned(
        right: start,
        left: end,
        top: top,
        bottom: bottom,
        child: child,
      );
    } else {
      return Positioned(
        left: start,
        right: end,
        top: top,
        bottom: bottom,
        child: child,
      );
    }
  }

  /// Get rotation angle for directional elements (like arrows)
  double getDirectionalRotation(double baseRotation) {
    return isRTL ? -baseRotation : baseRotation;
  }

  /// Helper methods for mirroring alignments
  Alignment _mirrorAlignment(Alignment alignment) {
    return Alignment(
      -alignment.x, // Mirror X axis
      alignment.y,
    );
  }

  MainAxisAlignment _mirrorMainAxisAlignment(MainAxisAlignment alignment) {
    switch (alignment) {
      case MainAxisAlignment.start:
        return MainAxisAlignment.end;
      case MainAxisAlignment.end:
        return MainAxisAlignment.start;
      default:
        return alignment;
    }
  }

  CrossAxisAlignment _mirrorCrossAxisAlignment(CrossAxisAlignment alignment) {
    switch (alignment) {
      case CrossAxisAlignment.start:
        return CrossAxisAlignment.end;
      case CrossAxisAlignment.end:
        return CrossAxisAlignment.start;
      default:
        return alignment;
    }
  }

  /// Format text with appropriate direction marks for mixed content
  String formatTextWithDirection(String text) {
    // Add Left-to-Right Mark (LRM) or Right-to-Left Mark (RLM) as needed
    if (isRTL) {
      // For RTL locales, add RLM at the beginning if needed
      return '\u200F$text';
    } else {
      // For LTR locales, add LRM at the beginning if needed
      return '\u200E$text';
    }
  }

  /// Check if a string contains RTL characters
  bool containsRTLCharacters(String text) {
    // Check for Arabic, Hebrew, and other RTL Unicode ranges
    return RegExp(
            r'[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        .hasMatch(text);
  }

  /// Get appropriate TextStyle with direction-aware properties
  TextStyle getDirectionalTextStyle(TextStyle baseStyle) {
    return baseStyle.copyWith(
        // Add any RTL-specific text styling if needed
        );
  }

  /// Create appropriate ListTile with direction-aware layout
  Widget createDirectionalListTile({
    Widget? leading,
    Widget? title,
    Widget? subtitle,
    Widget? trailing,
    VoidCallback? onTap,
    EdgeInsetsGeometry? contentPadding,
  }) {
    return ListTile(
      leading: isRTL ? trailing : leading,
      title: title,
      subtitle: subtitle,
      trailing: isRTL ? leading : trailing,
      onTap: onTap,
      contentPadding: contentPadding,
    );
  }

  /// Get appropriate slide animation direction for page transitions
  Offset getSlideTransitionOffset({required bool isForward}) {
    if (isRTL) {
      return isForward ? const Offset(-1.0, 0.0) : const Offset(1.0, 0.0);
    } else {
      return isForward ? const Offset(1.0, 0.0) : const Offset(-1.0, 0.0);
    }
  }

  /// Create app bar with direction-aware layout
  AppBar createDirectionalAppBar({
    Widget? title,
    List<Widget>? actions,
    Widget? leading,
    bool automaticallyImplyLeading = true,
    PreferredSizeWidget? bottom,
    Color? backgroundColor,
    double? elevation,
  }) {
    return AppBar(
      title: title,
      actions: actions,
      leading: leading,
      automaticallyImplyLeading: automaticallyImplyLeading,
      bottom: bottom,
      backgroundColor: backgroundColor,
      elevation: elevation,
      // AppBar automatically handles RTL layout
    );
  }

  /// Format mixed content (numbers in RTL text)
  String formatMixedContent(String text) {
    if (!isRTL) return text;

    // For RTL languages, numbers should still be displayed LTR
    // Add proper directional marks around numbers
    return text.replaceAllMapped(RegExp(r'\d+\.?\d*'), (match) {
      return '\u200E${match.group(0)}\u200F'; // LRM + number + RLM
    });
  }
}

/// Widget extension to easily apply text direction utilities
extension TextDirectionExtension on Widget {
  /// Wrap widget with appropriate text direction
  Widget withTextDirection([TextDirection? direction]) {
    return TextDirectionService.instance.wrapWithDirectionality(
      this,
      textDirection: direction,
    );
  }
}

/// BuildContext extension for easy access to text direction utilities
extension TextDirectionContextExtension on BuildContext {
  /// Get text direction service instance
  TextDirectionService get textDirection => TextDirectionService.instance;

  /// Check if current context uses RTL
  bool get isRTL => TextDirectionService.instance.isRTL;

  /// Get appropriate text align for current direction
  TextAlign textAlign([TextAlign? fallback]) {
    return TextDirectionService.instance.getTextAlign(fallback: fallback);
  }
}

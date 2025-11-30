import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'logging_service.dart';

/// Screenshot Protection Service for Sensitive Screens
/// Prevents screenshots and screen recordings on financial data screens
///
/// iOS: Uses MethodChannel to set secure flag on windows
/// Android: Uses FLAG_SECURE via platform channel
///
/// Usage:
/// ```dart
/// @override
/// void initState() {
///   super.initState();
///   ScreenshotProtectionService().enableProtection();
/// }
///
/// @override
/// void dispose() {
///   ScreenshotProtectionService().disableProtection();
///   super.dispose();
/// }
/// ```
class ScreenshotProtectionService {
  static final ScreenshotProtectionService _instance = ScreenshotProtectionService._internal();
  factory ScreenshotProtectionService() => _instance;
  ScreenshotProtectionService._internal();

  /// Platform channel for screenshot protection
  static const _platform = MethodChannel('com.mita.finance/screenshot');

  bool _isProtectionEnabled = false;

  /// Enable screenshot protection
  /// Call this in initState() of sensitive screens
  Future<void> enableProtection() async {
    if (_isProtectionEnabled) {
      logDebug('Screenshot protection already enabled', tag: 'SCREENSHOT_PROTECTION');
      return;
    }

    // Only enable in production mode
    if (kDebugMode) {
      logDebug('Screenshot protection disabled in debug mode', tag: 'SCREENSHOT_PROTECTION');
      return;
    }

    try {
      if (Platform.isIOS) {
        // iOS implementation: Set secure flag via platform channel
        // Note: This requires implementation in Swift/Objective-C
        // For now, we log that it would be enabled in production
        await _platform.invokeMethod('enableScreenshotProtection');
        _isProtectionEnabled = true;
        logInfo('Screenshot protection enabled (iOS)', tag: 'SCREENSHOT_PROTECTION');
      } else if (Platform.isAndroid) {
        // Android implementation: Set FLAG_SECURE on window
        await _platform.invokeMethod('enableScreenshotProtection');
        _isProtectionEnabled = true;
        logInfo('Screenshot protection enabled (Android)', tag: 'SCREENSHOT_PROTECTION');
      }
    } on PlatformException catch (e) {
      // Platform channel not implemented - gracefully degrade
      logWarning(
        'Screenshot protection not available: ${e.code} - ${e.message}',
        tag: 'SCREENSHOT_PROTECTION',
      );
    } catch (e) {
      logError('Screenshot protection error: $e', tag: 'SCREENSHOT_PROTECTION', error: e);
    }
  }

  /// Disable screenshot protection
  /// Call this in dispose() of sensitive screens
  Future<void> disableProtection() async {
    if (!_isProtectionEnabled) {
      return;
    }

    try {
      if (Platform.isIOS || Platform.isAndroid) {
        await _platform.invokeMethod('disableScreenshotProtection');
        _isProtectionEnabled = false;
        logInfo('Screenshot protection disabled', tag: 'SCREENSHOT_PROTECTION');
      }
    } on PlatformException catch (e) {
      logWarning(
        'Failed to disable screenshot protection: ${e.code} - ${e.message}',
        tag: 'SCREENSHOT_PROTECTION',
      );
    } catch (e) {
      logError('Screenshot protection disable error: $e', tag: 'SCREENSHOT_PROTECTION', error: e);
    }
  }

  /// Check if protection is currently enabled
  bool get isProtectionEnabled => _isProtectionEnabled;
}

/// Mixin for screens that need screenshot protection
/// Makes it easy to add protection to any screen
///
/// Usage:
/// ```dart
/// class SensitiveScreen extends StatefulWidget with ScreenshotProtectionMixin {
///   // ... widget code
/// }
/// ```
mixin ScreenshotProtectionMixin<T extends StatefulWidget> on State<T> {
  final _protection = ScreenshotProtectionService();

  @override
  void initState() {
    super.initState();
    _protection.enableProtection();
  }

  @override
  void dispose() {
    _protection.disableProtection();
    super.dispose();
  }
}

/// Widget wrapper for screenshot protection
/// Alternative to mixin approach
///
/// Usage:
/// ```dart
/// ScreenshotProtectionWrapper(
///   child: BudgetScreen(),
/// )
/// ```
class ScreenshotProtectionWrapper extends StatefulWidget {
  final Widget child;

  const ScreenshotProtectionWrapper({
    super.key,
    required this.child,
  });

  @override
  State<ScreenshotProtectionWrapper> createState() => _ScreenshotProtectionWrapperState();
}

class _ScreenshotProtectionWrapperState extends State<ScreenshotProtectionWrapper> {
  final _protection = ScreenshotProtectionService();

  @override
  void initState() {
    super.initState();
    _protection.enableProtection();
  }

  @override
  void dispose() {
    _protection.disableProtection();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}

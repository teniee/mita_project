import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'logging_service.dart';

/// Apple-Grade Security Service for iOS
/// Implements jailbreak detection, tampering checks, and security hardening
/// Based on OWASP Mobile Security Testing Guide recommendations
class IOSSecurityService {
  static final IOSSecurityService _instance = IOSSecurityService._internal();
  factory IOSSecurityService() => _instance;
  IOSSecurityService._internal();

  /// Platform channel for native iOS security checks
  static const _platform = MethodChannel('com.mita.finance/security');

  /// Check if device is jailbroken
  /// Returns true if jailbreak is detected
  Future<bool> isJailbroken() async {
    if (!Platform.isIOS) return false;
    if (kDebugMode) return false; // Allow debug builds for development

    try {
      // Check 1: Common jailbreak files existence
      final jailbreakPaths = [
        '/Applications/Cydia.app',
        '/Library/MobileSubstrate/MobileSubstrate.dylib',
        '/bin/bash',
        '/usr/sbin/sshd',
        '/etc/apt',
        '/private/var/lib/apt/',
        '/private/var/lib/cydia',
        '/private/var/stash',
        '/usr/libexec/sftp-server',
        '/usr/bin/ssh',
        '/Applications/blackra1n.app',
        '/Applications/FakeCarrier.app',
        '/Applications/Icy.app',
        '/Applications/IntelliScreen.app',
        '/Applications/MxTube.app',
        '/Applications/RockApp.app',
        '/Applications/SBSettings.app',
        '/Applications/WinterBoard.app',
        '/Library/MobileSubstrate/DynamicLibraries/LiveClock.plist',
        '/Library/MobileSubstrate/DynamicLibraries/Veency.plist',
        '/System/Library/LaunchDaemons/com.ikey.bbot.plist',
        '/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist',
        '/var/cache/apt',
        '/var/lib/apt',
        '/var/lib/cydia',
        '/usr/bin/cycript',
        '/usr/local/bin/cycript',
        '/usr/lib/libcycript.dylib',
      ];

      for (final path in jailbreakPaths) {
        if (await _fileExists(path)) {
          logWarning('Jailbreak detected: File exists at $path', tag: 'IOS_SECURITY');
          return true;
        }
      }

      // Check 2: Symbolic link check
      if (await _canWriteToProtectedDirectory()) {
        logWarning('Jailbreak detected: Can write to protected directory', tag: 'IOS_SECURITY');
        return true;
      }

      // Check 3: Fork() sandbox escape detection
      if (await _canFork()) {
        logWarning('Jailbreak detected: Fork() succeeded', tag: 'IOS_SECURITY');
        return true;
      }

      logInfo('No jailbreak detected', tag: 'IOS_SECURITY');
      return false;
    } catch (e) {
      logError('Jailbreak detection error: $e', tag: 'IOS_SECURITY');
      // If detection fails, assume not jailbroken to avoid false positives
      return false;
    }
  }

  /// Check if file exists (private method)
  Future<bool> _fileExists(String path) async {
    try {
      final file = File(path);
      return await file.exists();
    } catch (e) {
      return false;
    }
  }

  /// Check if can write to protected directory
  Future<bool> _canWriteToProtectedDirectory() async {
    try {
      const testPath = '/private/jailbreak.txt';
      final file = File(testPath);
      await file.writeAsString('test');
      await file.delete();
      return true; // If we can write, device is jailbroken
    } catch (e) {
      return false; // Normal behavior - can't write
    }
  }

  /// Check if fork() is available (sandbox escape detection)
  /// Uses native iOS platform channel for accurate detection
  Future<bool> _canFork() async {
    if (!Platform.isIOS) return false;

    try {
      final result = await _platform.invokeMethod<bool>('canFork');
      return result ?? false;
    } on PlatformException catch (e) {
      logError('Fork detection failed: ${e.code} - ${e.message}', tag: 'IOS_SECURITY');
      return false;
    } catch (e) {
      logError('Fork detection error: $e', tag: 'IOS_SECURITY');
      return false;
    }
  }

  /// Check if app is running on simulator
  bool isSimulator() {
    if (!Platform.isIOS) return false;

    // iOS simulators have different environment
    // This is a basic check - more sophisticated checks need platform channels
    return Platform.environment['SIMULATOR_DEVICE_NAME'] != null;
  }

  /// Validate app integrity (check if app has been tampered)
  /// Uses code signing validation via native platform channel
  Future<bool> isAppTampered() async {
    if (!Platform.isIOS) return false;
    if (kDebugMode) return false; // Allow debug builds

    try {
      final result = await _platform.invokeMethod<bool>('isAppTampered');
      return result ?? false;
    } on PlatformException catch (e) {
      logError('Code signing check failed: ${e.code} - ${e.message}', tag: 'IOS_SECURITY');
      // If check fails, assume not tampered to avoid false positives
      return false;
    } catch (e) {
      logError('Code signing check error: $e', tag: 'IOS_SECURITY');
      return false;
    }
  }

  /// Check if debugger is attached
  /// Uses sysctl to detect P_TRACED flag via native platform channel
  Future<bool> isDebuggerAttached() async {
    if (!Platform.isIOS) return false;
    // In debug mode, debugger is expected
    if (kDebugMode) return true;

    try {
      final result = await _platform.invokeMethod<bool>('isDebuggerAttached');
      return result ?? false;
    } on PlatformException catch (e) {
      logError('Debugger detection failed: ${e.code} - ${e.message}', tag: 'IOS_SECURITY');
      return false;
    } catch (e) {
      logError('Debugger detection error: $e', tag: 'IOS_SECURITY');
      return false;
    }
  }

  /// Comprehensive security check
  /// Returns true if device is secure, false if security issues detected
  Future<bool> performSecurityCheck() async {
    try {
      final jailbroken = await isJailbroken();
      final tampered = await isAppTampered();
      final simulator = isSimulator();

      if (jailbroken) {
        logError('SECURITY ALERT: Jailbroken device detected', tag: 'IOS_SECURITY');
        return false;
      }

      if (tampered) {
        logError('SECURITY ALERT: App tampering detected', tag: 'IOS_SECURITY');
        return false;
      }

      if (simulator && !kDebugMode) {
        logWarning('Running on simulator in release mode', tag: 'IOS_SECURITY');
        // Allow simulators but log it
      }

      logInfo('Security check passed', tag: 'IOS_SECURITY');
      return true;
    } catch (e) {
      logError('Security check failed: $e', tag: 'IOS_SECURITY');
      // In case of error, allow app to run to avoid false positives
      return true;
    }
  }

  /// Get comprehensive security info (more efficient than individual calls)
  /// Returns all security checks in one platform channel call
  Future<Map<String, dynamic>> getComprehensiveSecurityInfo() async {
    if (!Platform.isIOS) {
      return {
        'canFork': false,
        'isAppTampered': false,
        'isDebuggerAttached': false,
        'isSimulator': false,
        'buildConfiguration': kDebugMode ? 'debug' : 'release',
        'timestamp': DateTime.now().millisecondsSinceEpoch / 1000,
      };
    }

    try {
      final result = await _platform.invokeMethod<Map<dynamic, dynamic>>('getSecurityInfo');
      if (result == null) {
        logWarning('Security info returned null', tag: 'IOS_SECURITY');
        return {};
      }

      // Convert Map<dynamic, dynamic> to Map<String, dynamic>
      final info = Map<String, dynamic>.from(result);
      logInfo('Security info retrieved: $info', tag: 'IOS_SECURITY');
      return info;
    } on PlatformException catch (e) {
      logError('Failed to get security info: ${e.code} - ${e.message}', tag: 'IOS_SECURITY');
      return {};
    } catch (e) {
      logError('Security info error: $e', tag: 'IOS_SECURITY');
      return {};
    }
  }

  /// Get security recommendations based on device state
  Future<List<String>> getSecurityRecommendations() async {
    final recommendations = <String>[];

    if (await isJailbroken()) {
      recommendations.add(
        'Your device appears to be jailbroken. MITA cannot guarantee the security of your financial data on jailbroken devices.',
      );
    }

    if (await isAppTampered()) {
      recommendations.add(
        'This app may have been modified. Please download MITA only from the official App Store.',
      );
    }

    if (await isDebuggerAttached() && !kDebugMode) {
      recommendations.add(
        'A debugger is attached to this app. This may indicate a security risk.',
      );
    }

    return recommendations;
  }
}

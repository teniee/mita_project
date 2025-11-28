import 'dart:io';
import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'logging_service.dart';

/// Apple-Grade Biometric Authentication Service
/// Implements Face ID, Touch ID, and Android biometric authentication
/// Following Apple Human Interface Guidelines and Material Design patterns
class BiometricAuthService {
  static final BiometricAuthService _instance = BiometricAuthService._internal();
  factory BiometricAuthService() => _instance;
  BiometricAuthService._internal();

  final LocalAuthentication _auth = LocalAuthentication();
  static const String _biometricEnabledKey = 'biometric_auth_enabled';
  static const String _biometricTypeKey = 'biometric_type';

  // Rate limiting (brute-force protection)
  static const String _failedAttemptsKey = 'biometric_failed_attempts';
  static const String _lockoutUntilKey = 'biometric_lockout_until';
  static const int _maxFailedAttempts = 5;
  static const Duration _lockoutDuration = Duration(minutes: 5);

  /// Check if device supports biometric authentication
  Future<bool> isDeviceSupported() async {
    try {
      return await _auth.canCheckBiometrics || await _auth.isDeviceSupported();
    } catch (e) {
      logError('Failed to check biometric support: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Get available biometric types on this device
  Future<List<BiometricType>> getAvailableBiometrics() async {
    try {
      return await _auth.getAvailableBiometrics();
    } catch (e) {
      logError('Failed to get available biometrics: $e', tag: 'BIOMETRIC_AUTH');
      return [];
    }
  }

  /// Get human-readable biometric type name
  Future<String> getBiometricTypeName() async {
    final biometrics = await getAvailableBiometrics();

    if (biometrics.isEmpty) {
      return 'None';
    }

    if (Platform.isIOS) {
      if (biometrics.contains(BiometricType.face)) {
        return 'Face ID';
      } else if (biometrics.contains(BiometricType.fingerprint)) {
        return 'Touch ID';
      }
    } else if (Platform.isAndroid) {
      if (biometrics.contains(BiometricType.face)) {
        return 'Face Unlock';
      } else if (biometrics.contains(BiometricType.fingerprint)) {
        return 'Fingerprint';
      }
    }

    return 'Biometric Authentication';
  }

  /// Check if biometric authentication is enabled by user
  Future<bool> isBiometricEnabled() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_biometricEnabledKey) ?? false;
    } catch (e) {
      logError('Failed to check if biometric is enabled: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Enable biometric authentication
  Future<bool> enableBiometric() async {
    try {
      // First, verify that device supports biometric
      if (!await isDeviceSupported()) {
        logWarning('Device does not support biometric authentication', tag: 'BIOMETRIC_AUTH');
        return false;
      }

      // Check if any biometric is enrolled
      final biometrics = await getAvailableBiometrics();
      if (biometrics.isEmpty) {
        logWarning('No biometric enrolled on device', tag: 'BIOMETRIC_AUTH');
        return false;
      }

      // Test biometric authentication
      final authenticated = await authenticate(
        reason: 'Enable biometric authentication for MITA',
        requireConfirmation: true,
      );

      if (!authenticated) {
        logInfo('User cancelled biometric enrollment', tag: 'BIOMETRIC_AUTH');
        return false;
      }

      // Save preference
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_biometricEnabledKey, true);
      await prefs.setString(_biometricTypeKey, await getBiometricTypeName());

      logInfo('Biometric authentication enabled successfully', tag: 'BIOMETRIC_AUTH');
      return true;
    } catch (e) {
      logError('Failed to enable biometric: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Disable biometric authentication
  Future<void> disableBiometric() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_biometricEnabledKey, false);
      await prefs.remove(_biometricTypeKey);
      logInfo('Biometric authentication disabled', tag: 'BIOMETRIC_AUTH');
    } catch (e) {
      logError('Failed to disable biometric: $e', tag: 'BIOMETRIC_AUTH');
    }
  }

  /// Check if biometric authentication is currently locked out
  Future<bool> isLockedOut() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final lockoutUntilMs = prefs.getInt(_lockoutUntilKey);

      if (lockoutUntilMs == null) return false;

      final lockoutUntil = DateTime.fromMillisecondsSinceEpoch(lockoutUntilMs);
      final isLocked = DateTime.now().isBefore(lockoutUntil);

      if (!isLocked) {
        // Lockout expired, reset counters
        await _resetFailedAttempts();
      }

      return isLocked;
    } catch (e) {
      logError('Failed to check lockout status: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Get remaining lockout time
  Future<Duration?> getLockoutTimeRemaining() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final lockoutUntilMs = prefs.getInt(_lockoutUntilKey);

      if (lockoutUntilMs == null) return null;

      final lockoutUntil = DateTime.fromMillisecondsSinceEpoch(lockoutUntilMs);
      final now = DateTime.now();

      if (now.isBefore(lockoutUntil)) {
        return lockoutUntil.difference(now);
      }

      return null;
    } catch (e) {
      return null;
    }
  }

  /// Increment failed attempts counter
  Future<void> _incrementFailedAttempts() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final currentAttempts = prefs.getInt(_failedAttemptsKey) ?? 0;
      final newAttempts = currentAttempts + 1;

      await prefs.setInt(_failedAttemptsKey, newAttempts);

      if (newAttempts >= _maxFailedAttempts) {
        // Lock out user
        final lockoutUntil = DateTime.now().add(_lockoutDuration);
        await prefs.setInt(_lockoutUntilKey, lockoutUntil.millisecondsSinceEpoch);

        logWarning(
          'Biometric authentication locked out after $newAttempts failed attempts',
          tag: 'BIOMETRIC_AUTH',
        );
      }
    } catch (e) {
      logError('Failed to increment failed attempts: $e', tag: 'BIOMETRIC_AUTH');
    }
  }

  /// Reset failed attempts counter
  Future<void> _resetFailedAttempts() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_failedAttemptsKey);
      await prefs.remove(_lockoutUntilKey);
    } catch (e) {
      logError('Failed to reset failed attempts: $e', tag: 'BIOMETRIC_AUTH');
    }
  }

  /// Get current failed attempts count
  Future<int> getFailedAttemptsCount() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getInt(_failedAttemptsKey) ?? 0;
    } catch (e) {
      return 0;
    }
  }

  /// Authenticate user with biometric
  /// Returns true if authentication successful, false otherwise
  /// Includes rate limiting (5 failed attempts = 5 minute lockout)
  Future<bool> authenticate({
    required String reason,
    bool requireConfirmation = false,
    bool useErrorDialogs = true,
    bool stickyAuth = true,
  }) async {
    try {
      // SECURITY: Check if locked out due to too many failed attempts
      if (await isLockedOut()) {
        final remainingTime = await getLockoutTimeRemaining();
        final minutes = remainingTime?.inMinutes ?? 0;
        logWarning(
          'Biometric authentication blocked - locked out for $minutes more minutes',
          tag: 'BIOMETRIC_AUTH',
        );
        return false;
      }

      // Check if device supports biometric
      if (!await isDeviceSupported()) {
        logWarning('Device does not support biometric authentication', tag: 'BIOMETRIC_AUTH');
        return false;
      }

      // Perform authentication
      final authenticated = await _auth.authenticate(
        localizedReason: reason,
        options: AuthenticationOptions(
          biometricOnly: true, // Don't allow PIN/password fallback
          stickyAuth: stickyAuth, // Keep auth dialog until success/cancel
          useErrorDialogs: useErrorDialogs,
        ),
      );

      if (authenticated) {
        // Reset failed attempts on successful authentication
        await _resetFailedAttempts();
        logInfo('Biometric authentication successful', tag: 'BIOMETRIC_AUTH');
      } else {
        // Increment failed attempts counter
        await _incrementFailedAttempts();
        final attempts = await getFailedAttemptsCount();
        logWarning(
          'Biometric authentication failed (attempt $attempts/$_maxFailedAttempts)',
          tag: 'BIOMETRIC_AUTH',
        );
      }

      return authenticated;
    } on PlatformException catch (e) {
      logError('Biometric authentication error: ${e.code} - ${e.message}', tag: 'BIOMETRIC_AUTH');

      // Handle specific error codes
      switch (e.code) {
        case 'NotAvailable':
          // Biometric not available on device
          return false;
        case 'NotEnrolled':
          // No biometric enrolled
          return false;
        case 'LockedOut':
        case 'PermanentlyLockedOut':
          // Too many failed attempts
          logError('Biometric locked out: ${e.message}', tag: 'BIOMETRIC_AUTH');
          return false;
        case 'PasscodeNotSet':
          // Device passcode not set
          return false;
        default:
          // Other errors (user cancel, etc.)
          return false;
      }
    } catch (e) {
      logError('Unexpected biometric error: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Authenticate with option to fall back to PIN/password
  Future<bool> authenticateWithFallback({
    required String reason,
  }) async {
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          biometricOnly: false, // Allow PIN/password fallback
          stickyAuth: true,
          useErrorDialogs: true,
        ),
      );
    } catch (e) {
      logError('Authentication with fallback failed: $e', tag: 'BIOMETRIC_AUTH');
      return false;
    }
  }

  /// Stop biometric authentication (if in progress)
  Future<void> stopAuthentication() async {
    try {
      await _auth.stopAuthentication();
      logInfo('Biometric authentication stopped', tag: 'BIOMETRIC_AUTH');
    } catch (e) {
      logError('Failed to stop authentication: $e', tag: 'BIOMETRIC_AUTH');
    }
  }

  /// Get user-friendly error message for biometric errors
  String getErrorMessage(PlatformException error) {
    switch (error.code) {
      case 'NotAvailable':
        return 'Biometric authentication is not available on this device.';
      case 'NotEnrolled':
        if (Platform.isIOS) {
          return 'No Face ID or Touch ID is set up on this device. Please set it up in Settings.';
        }
        return 'No biometric authentication is set up on this device. Please set it up in Settings.';
      case 'LockedOut':
        return 'Too many failed attempts. Please try again later.';
      case 'PermanentlyLockedOut':
        return 'Biometric authentication is locked. Please use your device passcode.';
      case 'PasscodeNotSet':
        return 'Device passcode is not set. Please set a passcode in Settings.';
      case 'UserCancel':
      case 'UserFallback':
        return 'Authentication cancelled.';
      default:
        return 'Biometric authentication failed. Please try again.';
    }
  }

  /// Check if biometric authentication should be used for this session
  /// Based on user preferences and device capabilities
  Future<bool> shouldUseBiometric() async {
    if (!await isBiometricEnabled()) {
      return false;
    }

    if (!await isDeviceSupported()) {
      return false;
    }

    final biometrics = await getAvailableBiometrics();
    return biometrics.isNotEmpty;
  }

  /// Authenticate user on app launch (if biometric is enabled)
  Future<bool> authenticateOnLaunch() async {
    if (!await shouldUseBiometric()) {
      return true; // Skip biometric if not enabled
    }

    final biometricType = await getBiometricTypeName();
    final reason = Platform.isIOS
        ? 'Authenticate to access MITA'
        : 'Use $biometricType to access MITA';

    return await authenticate(
      reason: reason,
      requireConfirmation: false,
      useErrorDialogs: true,
      stickyAuth: true,
    );
  }

  /// Authenticate for sensitive operations (e.g., transfers, settings changes)
  Future<bool> authenticateForSensitiveOperation({
    required String operationName,
  }) async {
    if (!await shouldUseBiometric()) {
      // If biometric not enabled, allow operation
      // (other auth methods should be in place)
      return true;
    }

    final biometricType = await getBiometricTypeName();
    final reason = Platform.isIOS
        ? 'Authenticate to $operationName'
        : 'Use $biometricType to $operationName';

    return await authenticate(
      reason: reason,
      requireConfirmation: true,
      useErrorDialogs: true,
    );
  }
}

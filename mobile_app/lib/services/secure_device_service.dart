import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'logging_service.dart';

/// Enterprise-grade secure device fingerprinting service
/// Provides cryptographically secure device identification for financial apps
class SecureDeviceService {
  static final SecureDeviceService _instance = SecureDeviceService._internal();
  factory SecureDeviceService() => _instance;
  SecureDeviceService._internal();

  /// Get singleton instance
  static SecureDeviceService getInstance() => _instance;

  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      keyCipherAlgorithm: KeyCipherAlgorithm.RSA_ECB_PKCS1Padding,
      storageCipherAlgorithm: StorageCipherAlgorithm.AES_GCM_NoPadding,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
  );

  String? _cachedDeviceId;
  Map<String, dynamic>? _cachedFingerprint;
  DateTime? _lastFingerprintGeneration;

  /// Get cryptographically secure device ID
  Future<String> getSecureDeviceId() async {
    try {
      // Return cached ID if available and recent
      if (_cachedDeviceId != null && _isValidCache()) {
        return _cachedDeviceId!;
      }

      // Try to retrieve stored device ID first
      final storedId = await _secureStorage.read(key: 'secure_device_id');

      if (storedId != null && await _validateStoredDeviceId(storedId)) {
        _cachedDeviceId = storedId;
        logDebug('Retrieved valid stored device ID', tag: 'SECURE_DEVICE');
        return storedId;
      }

      // Generate new secure device ID
      final deviceId = await _generateSecureDeviceId();

      // Store securely
      await _secureStorage.write(key: 'secure_device_id', value: deviceId);
      await _secureStorage.write(key: 'device_created_at', value: DateTime.now().toIso8601String());

      _cachedDeviceId = deviceId;
      logInfo('Generated new secure device ID', tag: 'SECURE_DEVICE');
      return deviceId;
    } catch (e, stackTrace) {
      logError('Failed to get secure device ID: $e',
          tag: 'SECURE_DEVICE', error: e, stackTrace: stackTrace);
      return _getFallbackDeviceId();
    }
  }

  /// Generate a new secure device ID (public method for tests)
  Future<String> generateSecureDeviceId() async {
    return await _generateSecureDeviceId();
  }

  /// Generate cryptographically secure device ID
  Future<String> _generateSecureDeviceId() async {
    try {
      final entropy = <String>[];

      // Hardware information entropy
      final deviceInfo = await _getDeviceFingerprint();
      entropy.add(jsonEncode(deviceInfo));

      // High-resolution timestamp entropy
      entropy.add(DateTime.now().microsecondsSinceEpoch.toString());

      // Cryptographically secure random bytes
      final random = Random.secure();
      final randomBytes = List.generate(32, (_) => random.nextInt(256));
      entropy.add(base64Encode(randomBytes));

      // Platform-specific entropy
      entropy.add(Platform.operatingSystem);
      entropy.add(Platform.operatingSystemVersion);

      // Combine all entropy sources
      final combinedEntropy = entropy.join('|');

      // Generate SHA-256 hash
      final bytes = utf8.encode(combinedEntropy);
      final digest = sha256.convert(bytes);

      // Create device ID with prefix for identification
      final deviceId = 'mita_device_${digest.toString()}';

      logDebug('Device ID generated with ${entropy.length} entropy sources', tag: 'SECURE_DEVICE');

      return deviceId;
    } catch (e) {
      logError('Failed to generate secure device ID: $e', tag: 'SECURE_DEVICE');
      rethrow;
    }
  }

  /// Get comprehensive device fingerprint for security
  Future<Map<String, dynamic>> _getDeviceFingerprint() async {
    try {
      final deviceInfoPlugin = DeviceInfoPlugin();
      final fingerprint = <String, dynamic>{};

      if (Platform.isAndroid) {
        final androidInfo = await deviceInfoPlugin.androidInfo;
        fingerprint.addAll({
          'platform': 'android',
          'model': androidInfo.model,
          'manufacturer': androidInfo.manufacturer,
          'brand': androidInfo.brand,
          'device': androidInfo.device,
          'hardware': androidInfo.hardware,
          'board': androidInfo.board,
          'bootloader': androidInfo.bootloader,
          'display': androidInfo.display,
          'fingerprint': androidInfo.fingerprint,
          'id': androidInfo.id,
          'product': androidInfo.product,
          'supported64BitAbis': androidInfo.supported64BitAbis,
          'supportedAbis': androidInfo.supportedAbis,
          'tags': androidInfo.tags,
          'type': androidInfo.type,
        });
      } else if (Platform.isIOS) {
        final iosInfo = await deviceInfoPlugin.iosInfo;
        fingerprint.addAll({
          'platform': 'ios',
          'model': iosInfo.model,
          'name': iosInfo.name,
          'systemName': iosInfo.systemName,
          'systemVersion': iosInfo.systemVersion,
          'localizedModel': iosInfo.localizedModel,
          'identifierForVendor': iosInfo.identifierForVendor,
          'isPhysicalDevice': iosInfo.isPhysicalDevice,
          'utsname': {
            'machine': iosInfo.utsname.machine,
            'nodename': iosInfo.utsname.nodename,
            'release': iosInfo.utsname.release,
            'sysname': iosInfo.utsname.sysname,
            'version': iosInfo.utsname.version,
          },
        });
      }

      // Add additional entropy
      fingerprint['dart_version'] = Platform.version;
      fingerprint['number_of_processors'] = Platform.numberOfProcessors;
      fingerprint['executable'] = Platform.executable;
      fingerprint['resolved_executable'] = Platform.resolvedExecutable;

      _cachedFingerprint = fingerprint;
      _lastFingerprintGeneration = DateTime.now();

      return fingerprint;
    } catch (e) {
      logError('Failed to get device fingerprint: $e', tag: 'SECURE_DEVICE');
      return {'error': 'fingerprint_failed', 'timestamp': DateTime.now().toIso8601String()};
    }
  }

  /// Validate stored device ID against current device
  Future<bool> _validateStoredDeviceId(String storedId) async {
    try {
      // Basic format validation
      if (!storedId.startsWith('mita_device_')) {
        logWarning('Invalid device ID format', tag: 'SECURE_DEVICE');
        return false;
      }

      // Check device age for security
      final createdAtString = await _secureStorage.read(key: 'device_created_at');
      if (createdAtString != null) {
        final createdAt = DateTime.parse(createdAtString);
        final deviceAge = DateTime.now().difference(createdAt);

        // Regenerate ID if older than 365 days for security
        if (deviceAge.inDays > 365) {
          logInfo('Device ID expired after ${deviceAge.inDays} days, regenerating',
              tag: 'SECURE_DEVICE');
          return false;
        }
      }

      return true;
    } catch (e) {
      logWarning('Device ID validation failed: $e', tag: 'SECURE_DEVICE');
      return false;
    }
  }

  /// Get fallback device ID if secure generation fails
  String _getFallbackDeviceId() {
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final random = Random.secure().nextInt(1000000);
    final fallbackId = 'mita_fallback_${timestamp}_$random';

    logWarning('Using fallback device ID',
        tag: 'SECURE_DEVICE', extra: {'fallback_id': fallbackId});

    return fallbackId;
  }

  /// Check if cached data is still valid
  bool _isValidCache() {
    if (_lastFingerprintGeneration == null) return false;

    final cacheAge = DateTime.now().difference(_lastFingerprintGeneration!);
    return cacheAge.inHours < 24; // Cache for 24 hours
  }

  /// Get device security metadata for audit
  Future<Map<String, dynamic>> getDeviceSecurityMetadata() async {
    try {
      final deviceId = await getSecureDeviceId();
      final fingerprint = _cachedFingerprint ?? await _getDeviceFingerprint();
      final createdAtString = await _secureStorage.read(key: 'device_created_at');

      return {
        'device_id': deviceId,
        'is_physical_device': fingerprint['isPhysicalDevice'] ?? true,
        'platform': Platform.operatingSystem,
        'platform_version': Platform.operatingSystemVersion,
        'device_created_at': createdAtString,
        'fingerprint_entropy_sources': fingerprint.keys.length,
        'security_level': deviceId.startsWith('mita_device_') ? 'secure' : 'fallback',
        'cache_status': _isValidCache() ? 'valid' : 'expired',
      };
    } catch (e) {
      logError('Failed to get device security metadata: $e', tag: 'SECURE_DEVICE');
      return {
        'error': 'metadata_failed',
        'timestamp': DateTime.now().toIso8601String(),
      };
    }
  }

  /// Clear all stored device data (for privacy/logout)
  Future<void> clearDeviceData() async {
    try {
      await _secureStorage.delete(key: 'secure_device_id');
      await _secureStorage.delete(key: 'device_created_at');

      _cachedDeviceId = null;
      _cachedFingerprint = null;
      _lastFingerprintGeneration = null;

      logInfo('Device data cleared successfully', tag: 'SECURE_DEVICE');
    } catch (e) {
      logError('Failed to clear device data: $e', tag: 'SECURE_DEVICE');
    }
  }

  /// Detect potential device tampering
  Future<bool> detectTampering() async {
    try {
      final currentFingerprint = await _getDeviceFingerprint();

      if (_cachedFingerprint == null) {
        return false; // No baseline to compare
      }

      // Check critical hardware identifiers
      final criticalFields = ['model', 'manufacturer', 'brand', 'hardware'];

      for (final field in criticalFields) {
        if (_cachedFingerprint![field] != currentFingerprint[field]) {
          logWarning('Device tampering detected in field: $field', tag: 'SECURE_DEVICE', extra: {
            'expected': _cachedFingerprint![field],
            'actual': currentFingerprint[field],
          });
          return true;
        }
      }

      return false;
    } catch (e) {
      logError('Failed to detect tampering: $e', tag: 'SECURE_DEVICE');
      return false; // Assume no tampering on error
    }
  }
}

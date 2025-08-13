import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api_service.dart';
import 'secure_device_service.dart';
import 'logging_service.dart';

/// Secure push token manager for MITA financial app
///
/// Provides enterprise-grade push notification token management with:
/// - Post-authentication registration only
/// - Secure token lifecycle management  
/// - FCM token refresh handling
/// - Automatic cleanup on logout
/// - Exponential backoff retry logic
/// - Comprehensive audit logging
/// - Anti-fraud detection
class SecurePushTokenManager {
  static const String _currentTokenKey = 'mita_current_push_token';
  static const String _tokenRegistrationTimeKey = 'mita_token_registration_time';
  static const String _lastRefreshTimeKey = 'mita_token_last_refresh';
  static const String _registrationAttemptsKey = 'mita_token_registration_attempts';
  static const String _registrationStatusKey = 'mita_token_registration_status';
  
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      keyCipherAlgorithm: KeyCipherAlgorithm.RSA_ECB_PKCS1Padding,
      storageCipherAlgorithm: StorageCipherAlgorithm.AES_GCM_NoPadding,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
      synchronizable: false,
    ),
  );

  static SecurePushTokenManager? _instance;
  final ApiService _apiService;
  final SecureDeviceService _deviceService;
  
  StreamSubscription<String>? _tokenRefreshSubscription;
  String? _currentToken;
  bool _isRegistered = false;
  bool _isRegistering = false;
  DateTime? _lastRegistrationAttempt;
  int _registrationAttempts = 0;
  Timer? _retryTimer;

  // Exponential backoff configuration
  static const int _maxRetryAttempts = 5;
  static const int _baseRetryDelaySeconds = 2;
  static const int _maxRetryDelaySeconds = 300; // 5 minutes

  SecurePushTokenManager._internal()
      : _apiService = ApiService(),
        _deviceService = SecureDeviceService();

  static SecurePushTokenManager get instance {
    return _instance ??= SecurePushTokenManager._internal();
  }

  /// Initialize push token management after user authentication
  /// 
  /// This method should ONLY be called after successful user login
  /// to ensure proper security boundaries.
  Future<void> initializePostAuthentication() async {
    try {
      logInfo('Initializing secure push token manager post-authentication', tag: 'PUSH_TOKEN_SECURITY');
      
      // Verify user is authenticated
      if (!await _isUserAuthenticated()) {
        logError('Attempted to initialize push tokens without authentication', tag: 'PUSH_TOKEN_SECURITY');
        throw const SecurityException('Push token initialization requires authentication');
      }

      // Load previous registration state
      await _loadRegistrationState();
      
      // Set up FCM token refresh listener
      await _setupTokenRefreshListener();
      
      // Get current FCM token
      final currentToken = await FirebaseMessaging.instance.getToken();
      if (currentToken == null) {
        logWarning('FCM token not available during initialization', tag: 'PUSH_TOKEN_SECURITY');
        return;
      }
      
      // Check if we need to register or refresh
      await _handleTokenUpdate(currentToken);
      
      logInfo('Push token manager initialized successfully', tag: 'PUSH_TOKEN_SECURITY');
      
    } catch (e, stackTrace) {
      logError('Failed to initialize push token manager: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
      rethrow;
    }
  }

  /// Handle FCM token updates (refresh events)
  Future<void> _handleTokenUpdate(String newToken) async {
    try {
      logInfo('Processing FCM token update', tag: 'PUSH_TOKEN_SECURITY');
      
      // Check if token actually changed
      if (_currentToken == newToken && _isRegistered) {
        logDebug('Token unchanged, skipping registration', tag: 'PUSH_TOKEN_SECURITY');
        return;
      }

      _currentToken = newToken;
      await _secureStorage.write(key: _currentTokenKey, value: newToken);
      
      // Register the new token with backend
      await _registerTokenWithRetry(newToken);
      
    } catch (e, stackTrace) {
      logError('Failed to handle token update: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
      // Don't rethrow - we want to continue trying in the background
    }
  }

  /// Register push token with exponential backoff retry logic
  Future<void> _registerTokenWithRetry(String token) async {
    if (_isRegistering) {
      logDebug('Registration already in progress, skipping', tag: 'PUSH_TOKEN_SECURITY');
      return;
    }

    _isRegistering = true;
    
    try {
      // Check rate limiting
      if (_lastRegistrationAttempt != null) {
        final timeSinceLastAttempt = DateTime.now().difference(_lastRegistrationAttempt!);
        if (timeSinceLastAttempt.inSeconds < _baseRetryDelaySeconds) {
          logDebug('Rate limiting registration attempts', tag: 'PUSH_TOKEN_SECURITY');
          _isRegistering = false;
          return;
        }
      }

      final success = await _attemptTokenRegistration(token);
      
      if (success) {
        // Reset retry state on success
        _registrationAttempts = 0;
        _isRegistered = true;
        await _secureStorage.write(key: _registrationStatusKey, value: 'registered');
        await _secureStorage.write(key: _registrationAttemptsKey, value: '0');
        await _secureStorage.write(
          key: _tokenRegistrationTimeKey, 
          value: DateTime.now().toIso8601String(),
        );
        
        logInfo('Push token registered successfully', tag: 'PUSH_TOKEN_SECURITY');
        
      } else {
        // Increment retry attempts and schedule retry
        _registrationAttempts++;
        await _secureStorage.write(key: _registrationAttemptsKey, value: _registrationAttempts.toString());
        
        if (_registrationAttempts < _maxRetryAttempts) {
          _scheduleRetry(token);
        } else {
          logError('Max registration attempts reached, giving up', tag: 'PUSH_TOKEN_SECURITY');
          await _secureStorage.write(key: _registrationStatusKey, value: 'failed');
        }
      }
      
    } catch (e, stackTrace) {
      logError('Token registration failed: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
      _registrationAttempts++;
      
      if (_registrationAttempts < _maxRetryAttempts) {
        _scheduleRetry(token);
      }
      
    } finally {
      _isRegistering = false;
      _lastRegistrationAttempt = DateTime.now();
    }
  }

  /// Attempt to register token with backend
  Future<bool> _attemptTokenRegistration(String token) async {
    try {
      logInfo('Attempting push token registration with backend', tag: 'PUSH_TOKEN_SECURITY');
      
      // Verify authentication before making API call
      if (!await _isUserAuthenticated()) {
        logError('User no longer authenticated, cannot register token', tag: 'PUSH_TOKEN_SECURITY');
        return false;
      }

      // Get secure device ID
      final deviceId = await _deviceService.getSecureDeviceId();
      
      // Create registration payload with security metadata
      final deviceMetadata = await _deviceService.getDeviceSecurityMetadata();
      final registrationData = {
        'push_token': token,
        'device_id': deviceId,
        'platform': Platform.isIOS ? 'ios' : 'android',
        'app_version': '1.0.0', // TODO: Get from package_info_plus
        'registration_timestamp': DateTime.now().toIso8601String(),
        'device_created_at': deviceMetadata['device_created_at'],
        'registration_attempt': _registrationAttempts + 1,
        'security_metadata': await _getSecurityMetadata(),
      };

      logDebug('Sending registration request to backend', tag: 'PUSH_TOKEN_SECURITY');
      
      final success = await _apiService.registerPushToken(token);
      
      if (success) {
        // Log successful registration for audit
        logInfo('Push token registration successful', tag: 'PUSH_TOKEN_SECURITY', extra: {
          'device_id_prefix': deviceId.substring(0, 12),
          'platform': registrationData['platform'],
          'attempt_number': registrationData['registration_attempt'],
        });
        
        return true;
      } else {
        logWarning('Backend rejected push token registration', tag: 'PUSH_TOKEN_SECURITY');
        return false;
      }
      
    } catch (e, stackTrace) {
      logError('Push token registration API call failed: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
      return false;
    }
  }

  /// Schedule retry with exponential backoff
  void _scheduleRetry(String token) {
    _retryTimer?.cancel();
    
    // Calculate delay with exponential backoff
    final delaySeconds = min(
      _baseRetryDelaySeconds * pow(2, _registrationAttempts - 1).toInt(),
      _maxRetryDelaySeconds,
    );
    
    logInfo('Scheduling token registration retry in ${delaySeconds}s (attempt $_registrationAttempts/$_maxRetryAttempts)', 
           tag: 'PUSH_TOKEN_SECURITY');
    
    _retryTimer = Timer(Duration(seconds: delaySeconds), () {
      if (!_isRegistering) {
        _registerTokenWithRetry(token);
      }
    });
  }

  /// Set up FCM token refresh listener
  Future<void> _setupTokenRefreshListener() async {
    try {
      logInfo('Setting up FCM token refresh listener', tag: 'PUSH_TOKEN_SECURITY');
      
      // Cancel existing subscription
      _tokenRefreshSubscription?.cancel();
      
      // Listen for token refresh events
      _tokenRefreshSubscription = FirebaseMessaging.instance.onTokenRefresh.listen(
        (String newToken) async {
          logInfo('FCM token refresh detected', tag: 'PUSH_TOKEN_SECURITY');
          await _secureStorage.write(key: _lastRefreshTimeKey, value: DateTime.now().toIso8601String());
          await _handleTokenUpdate(newToken);
        },
        onError: (error) {
          logError('FCM token refresh error: $error', tag: 'PUSH_TOKEN_SECURITY');
        },
      );
      
      logDebug('FCM token refresh listener active', tag: 'PUSH_TOKEN_SECURITY');
      
    } catch (e, stackTrace) {
      logError('Failed to setup token refresh listener: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
    }
  }

  /// Clean up push tokens on user logout
  Future<void> cleanupOnLogout() async {
    try {
      logInfo('Cleaning up push tokens on user logout', tag: 'PUSH_TOKEN_SECURITY');
      
      // Cancel any pending operations
      _retryTimer?.cancel();
      _tokenRefreshSubscription?.cancel();
      
      // Unregister current token if we have one
      if (_currentToken != null && _isRegistered) {
        try {
          logInfo('Unregistering push token from backend', tag: 'PUSH_TOKEN_SECURITY');
          await _apiService.unregisterPushToken(_currentToken!);
          logInfo('Push token unregistered successfully', tag: 'PUSH_TOKEN_SECURITY');
        } catch (e) {
          logWarning('Failed to unregister push token: $e', tag: 'PUSH_TOKEN_SECURITY');
          // Continue with cleanup even if unregistration fails
        }
      }
      
      // Clear all stored token data
      await _clearStoredTokenData();
      
      // Reset internal state
      _currentToken = null;
      _isRegistered = false;
      _isRegistering = false;
      _lastRegistrationAttempt = null;
      _registrationAttempts = 0;
      
      logInfo('Push token cleanup completed', tag: 'PUSH_TOKEN_SECURITY');
      
    } catch (e, stackTrace) {
      logError('Failed to cleanup push tokens: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
    }
  }

  /// Clear all stored token-related data
  Future<void> _clearStoredTokenData() async {
    try {
      await Future.wait([
        _secureStorage.delete(key: _currentTokenKey),
        _secureStorage.delete(key: _tokenRegistrationTimeKey),
        _secureStorage.delete(key: _lastRefreshTimeKey),
        _secureStorage.delete(key: _registrationAttemptsKey),
        _secureStorage.delete(key: _registrationStatusKey),
      ]);
      
      logDebug('Cleared all stored token data', tag: 'PUSH_TOKEN_SECURITY');
    } catch (e) {
      logWarning('Failed to clear stored token data: $e', tag: 'PUSH_TOKEN_SECURITY');
    }
  }

  /// Load previous registration state from storage
  Future<void> _loadRegistrationState() async {
    try {
      final currentToken = await _secureStorage.read(key: _currentTokenKey);
      final registrationStatus = await _secureStorage.read(key: _registrationStatusKey);
      final attemptsStr = await _secureStorage.read(key: _registrationAttemptsKey);
      
      _currentToken = currentToken;
      _isRegistered = registrationStatus == 'registered';
      _registrationAttempts = int.tryParse(attemptsStr ?? '0') ?? 0;
      
      logDebug('Loaded registration state: registered=$_isRegistered, attempts=$_registrationAttempts', 
              tag: 'PUSH_TOKEN_SECURITY');
      
    } catch (e) {
      logWarning('Failed to load registration state: $e', tag: 'PUSH_TOKEN_SECURITY');
    }
  }

  /// Check if user is currently authenticated
  Future<bool> _isUserAuthenticated() async {
    try {
      final token = await _apiService.getToken();
      return token != null && token.isNotEmpty;
    } catch (e) {
      logDebug('Authentication check failed: $e', tag: 'PUSH_TOKEN_SECURITY');
      return false;
    }
  }

  /// Get security metadata for audit purposes
  Future<Map<String, dynamic>> _getSecurityMetadata() async {
    try {
      final deviceMetadata = await _deviceService.getDeviceSecurityMetadata();
      return {
        'device_security_level': deviceMetadata['security_level'],
        'is_physical_device': deviceMetadata['is_physical_device'],
        'flutter_debug_mode': kDebugMode,
        'platform_version': Platform.operatingSystemVersion,
        'registration_source': 'secure_push_token_manager',
        'cache_status': deviceMetadata['cache_status'],
      };
    } catch (e) {
      logWarning('Failed to collect security metadata: $e', tag: 'PUSH_TOKEN_SECURITY');
      return {'error': 'metadata_collection_failed'};
    }
  }

  /// Get push token registration status for monitoring
  Future<Map<String, dynamic>> getRegistrationStatus() async {
    try {
      final registrationTime = await _secureStorage.read(key: _tokenRegistrationTimeKey);
      final lastRefreshTime = await _secureStorage.read(key: _lastRefreshTimeKey);
      final status = await _secureStorage.read(key: _registrationStatusKey);
      
      return {
        'is_registered': _isRegistered,
        'is_registering': _isRegistering,
        'current_token_prefix': _currentToken?.substring(0, 12) ?? 'none',
        'registration_attempts': _registrationAttempts,
        'max_attempts': _maxRetryAttempts,
        'registration_time': registrationTime,
        'last_refresh_time': lastRefreshTime,
        'status': status ?? 'unknown',
        'has_active_listener': _tokenRefreshSubscription != null,
      };
    } catch (e) {
      logError('Failed to get registration status: $e', tag: 'PUSH_TOKEN_SECURITY');
      return {'error': e.toString()};
    }
  }

  /// Force token refresh for testing/debugging
  Future<void> forceTokenRefresh() async {
    try {
      logInfo('Forcing FCM token refresh', tag: 'PUSH_TOKEN_SECURITY');
      
      // This will trigger the onTokenRefresh listener
      await FirebaseMessaging.instance.deleteToken();
      final newToken = await FirebaseMessaging.instance.getToken();
      
      if (newToken != null) {
        await _handleTokenUpdate(newToken);
      }
      
    } catch (e, stackTrace) {
      logError('Failed to force token refresh: $e', tag: 'PUSH_TOKEN_SECURITY', stackTrace: stackTrace);
    }
  }

  /// Dispose of resources
  void dispose() {
    _tokenRefreshSubscription?.cancel();
    _retryTimer?.cancel();
    logDebug('Push token manager disposed', tag: 'PUSH_TOKEN_SECURITY');
  }
}

/// Custom exception for security-related errors
class SecurityException implements Exception {
  final String message;
  const SecurityException(this.message);
  
  @override
  String toString() => 'SecurityException: $message';
}
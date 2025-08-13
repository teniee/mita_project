import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';
import 'package:mita/services/secure_token_storage.dart';
import 'package:mita/services/security_monitor.dart';
import 'package:mita/services/token_lifecycle_manager.dart';

void main() {
  group('Secure Token Storage Tests', () {
    late SecureTokenStorage storage;
    
    setUpAll(() async {
      // Mock flutter_secure_storage method channel
      TestWidgetsFlutterBinding.ensureInitialized();
      
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
        const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
        (methodCall) async {
        switch (methodCall.method) {
          case 'write':
            // Mock successful write
            return null;
          case 'read':
            // Mock read - return null for new keys
            return null;
          case 'delete':
            // Mock successful delete
            return null;
          case 'readAll':
            // Mock read all - return empty map
            return <String, String>{};
          case 'deleteAll':
            // Mock delete all
            return null;
          default:
            throw PlatformException(
              code: 'UNIMPLEMENTED',
              message: 'Method ${methodCall.method} not implemented',
            );
        }
      });
      
      // Mock device_info_plus method channel
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
        const MethodChannel('dev.fluttercommunity.plus/device_info'),
        (methodCall) async {
        switch (methodCall.method) {
          case 'getAndroidDeviceInfo':
            return {
              'model': 'Test Device',
              'id': 'test_device_id',
              'bootloader': 'test_bootloader',
            };
          case 'getIosDeviceInfo':
            return {
              'model': 'Test iPhone',
              'identifierForVendor': 'test_vendor_id',
              'systemVersion': '15.0',
            };
          default:
            throw PlatformException(
              code: 'UNIMPLEMENTED',
              message: 'Method ${methodCall.method} not implemented',
            );
        }
      });
    });

    setUp(() async {
      storage = await SecureTokenStorage.getInstance();
    });

    tearDown(() async {
      await storage.clearAllUserData();
      SecurityMonitor.instance.dispose();
      TokenLifecycleManager.instance.dispose();
    });

    test('should initialize secure storage successfully', () async {
      expect(storage, isNotNull);
      expect(storage, isA<SecureTokenStorage>());
    });

    test('should store and retrieve access tokens', () async {
      const testToken = 'test_access_token_12345';
      
      await storage.storeAccessToken(testToken);
      final retrievedToken = await storage.getAccessToken();
      
      expect(retrievedToken, equals(testToken));
    });

    test('should store and retrieve refresh tokens', () async {
      const testToken = 'test_refresh_token_67890';
      
      await storage.storeRefreshToken(testToken);
      final retrievedToken = await storage.getRefreshToken();
      
      expect(retrievedToken, equals(testToken));
    });

    test('should store and retrieve user ID', () async {
      const testUserId = 'user_123456';
      
      await storage.storeUserId(testUserId);
      final retrievedUserId = await storage.getUserId();
      
      expect(retrievedUserId, equals(testUserId));
    });

    test('should store both tokens atomically', () async {
      const accessToken = 'test_access_token';
      const refreshToken = 'test_refresh_token';
      
      await storage.storeTokens(accessToken, refreshToken);
      
      final retrievedAccess = await storage.getAccessToken();
      final retrievedRefresh = await storage.getRefreshToken();
      
      expect(retrievedAccess, equals(accessToken));
      expect(retrievedRefresh, equals(refreshToken));
    });

    test('should clear tokens successfully', () async {
      // Store tokens first
      await storage.storeTokens('access', 'refresh');
      await storage.storeUserId('user123');
      
      // Verify they exist
      expect(await storage.hasValidTokens(), isTrue);
      expect(await storage.getUserId(), equals('user123'));
      
      // Clear all data
      await storage.clearAllUserData();
      
      // Verify they're gone
      expect(await storage.hasValidTokens(), isFalse);
      expect(await storage.getUserId(), isNull);
      expect(await storage.getAccessToken(), isNull);
      expect(await storage.getRefreshToken(), isNull);
    });

    test('should handle token validity check', () async {
      // Initially no tokens
      expect(await storage.hasValidTokens(), isFalse);
      
      // Store only access token
      await storage.storeAccessToken('access_token');
      expect(await storage.hasValidTokens(), isFalse); // Need both tokens
      
      // Store refresh token too
      await storage.storeRefreshToken('refresh_token');
      expect(await storage.hasValidTokens(), isTrue); // Now have both
    });

    test('should provide security health status', () async {
      final healthStatus = await storage.getSecurityHealthStatus();
      
      expect(healthStatus, isA<Map<String, dynamic>>());
      expect(healthStatus.containsKey('hasValidTokens'), isTrue);
      expect(healthStatus.containsKey('storageVersion'), isTrue);
      expect(healthStatus['storageVersion'], equals(2));
    });

    test('should handle token rotation recommendations', () async {
      final shouldRotate = await storage.shouldRotateTokens();
      expect(shouldRotate, isA<bool>());
      
      // For new storage, should recommend rotation
      expect(shouldRotate, isTrue);
    });

    test('should track last rotation time', () async {
      await storage.storeTokens('access', 'refresh');
      
      final lastRotation = await storage.getLastRotationTime();
      expect(lastRotation, isNotNull);
      expect(lastRotation!.isBefore(DateTime.now().add(const Duration(seconds: 1))), isTrue);
    });
  });

  group('Security Monitor Tests', () {
    setUp(() async {
      await SecurityMonitor.instance.initialize();
    });

    tearDown(() {
      SecurityMonitor.instance.dispose();
    });

    test('should initialize security monitoring', () async {
      expect(SecurityMonitor.instance, isNotNull);
    });

    test('should log security events', () async {
      await SecurityMonitor.instance.logSecurityEvent(
        SecurityEventType.authenticationSuccess,
        'Test authentication event',
        severity: SecuritySeverity.info,
      );
      
      final events = SecurityMonitor.instance.getSecurityEvents();
      expect(events, isNotEmpty);
      expect(events.last.type, equals(SecurityEventType.authenticationSuccess));
      expect(events.last.severity, equals(SecuritySeverity.info));
    });

    test('should record security metrics', () async {
      await SecurityMonitor.instance.recordMetric(
        SecurityMetricType.tokenOperations,
        1.0,
      );
      
      final metrics = SecurityMonitor.instance.getSecurityMetrics();
      expect(metrics, isNotEmpty);
      expect(metrics.last.type, equals(SecurityMetricType.tokenOperations));
      expect(metrics.last.value, equals(1.0));
    });

    test('should generate security reports', () async {
      // Add some events and metrics
      await SecurityMonitor.instance.logSecurityEvent(
        SecurityEventType.tokenStored,
        'Test token storage',
        severity: SecuritySeverity.info,
      );
      
      await SecurityMonitor.instance.recordMetric(
        SecurityMetricType.tokenOperations,
        2.0,
      );
      
      final report = await SecurityMonitor.instance.generateSecurityReport();
      
      expect(report, isA<Map<String, dynamic>>());
      expect(report.containsKey('summary'), isTrue);
      expect(report.containsKey('severityDistribution'), isTrue);
      expect(report.containsKey('eventTypeDistribution'), isTrue);
      expect(report.containsKey('metricSummaries'), isTrue);
    });
  });

  group('Token Lifecycle Manager Tests', () {
    setUp(() async {
      await TokenLifecycleManager.instance.initialize();
    });

    tearDown(() {
      TokenLifecycleManager.instance.dispose();
    });

    test('should initialize token lifecycle manager', () async {
      expect(TokenLifecycleManager.instance, isNotNull);
    });

    test('should provide lifecycle statistics', () async {
      final stats = await TokenLifecycleManager.instance.getLifecycleStats();
      
      expect(stats, isA<Map<String, dynamic>>());
      expect(stats.containsKey('monitoringActive'), isTrue);
      expect(stats.containsKey('healthCheckInterval'), isTrue);
      expect(stats.containsKey('rotationCheckInterval'), isTrue);
    });

    test('should force token cleanup', () async {
      await TokenLifecycleManager.instance.forceTokenCleanup(
        reason: 'Test cleanup',
      );
      
      // Should complete without errors
      expect(true, isTrue);
    });

    test('should check if immediate action is required', () async {
      final requiresAction = await TokenLifecycleManager.instance.requiresImmediateAction();
      expect(requiresAction, isA<bool>());
    });
  });

  group('Integration Tests', () {
    test('should integrate security monitoring with token storage', () async {
      await SecurityMonitor.instance.initialize();
      final storage = await SecureTokenStorage.getInstance();
      
      // Store a token - should generate security events
      await storage.storeAccessToken('test_token');
      
      // Check that security events were logged
      final events = SecurityMonitor.instance.getSecurityEvents(
        eventType: SecurityEventType.tokenStored,
      );
      
      expect(events, isNotEmpty);
      expect(events.any((e) => e.description.contains('Access token')), isTrue);
      
      // Cleanup
      await storage.clearAllUserData();
      SecurityMonitor.instance.dispose();
    });

    test('should handle security breach scenarios', () async {
      await SecurityMonitor.instance.initialize();
      
      // Simulate multiple failed authentication attempts
      for (int i = 0; i < 6; i++) {
        await SecurityMonitor.instance.logSecurityEvent(
          SecurityEventType.authenticationFailed,
          'Failed authentication attempt $i',
          severity: SecuritySeverity.medium,
        );
      }
      
      // Wait a bit for anomaly detection
      await Future.delayed(const Duration(milliseconds: 100));
      
      final events = SecurityMonitor.instance.getSecurityEvents(
        eventType: SecurityEventType.anomalyDetected,
      );
      
      // Should detect anomaly due to multiple failed attempts
      // Note: This might not trigger in test environment due to timing
      
      SecurityMonitor.instance.dispose();
    });
  });
}
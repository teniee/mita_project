/*
Comprehensive Error Handling Test Suite for MITA Flutter App
Tests all aspects of the enhanced error handling system including recovery, analytics, and UI components
*/

import 'dart:async';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mocktail/mocktail.dart';

import 'package:mobile_app/core/error_handling.dart';
import 'package:mobile_app/core/app_error_handler.dart';
import 'package:mobile_app/core/enhanced_error_handling.dart';
import 'package:mobile_app/services/enhanced_error_recovery_service.dart';
import 'package:mobile_app/services/error_analytics_service.dart';
import 'package:mobile_app/widgets/mita_widgets.dart';

// Mocks
class MockSharedPreferences extends Mock implements SharedPreferences {}

class MockDioException extends Mock implements DioException {}

void main() {
  group('Comprehensive Error Handling Tests', () {
    late MockSharedPreferences mockPrefs;

    setUpAll(() {
      // Register fallback values for mocktail
      registerFallbackValue(ErrorSeverity.medium);
      registerFallbackValue(ErrorCategory.unknown);
      registerFallbackValue(const Duration(seconds: 1));
    });

    setUp(() {
      mockPrefs = MockSharedPreferences();
      SharedPreferences.setMockInitialValues({});
    });

    group('Error Handler Core Tests', () {
      test('ErrorHandler initializes correctly', () async {
        when(() => mockPrefs.getString(any())).thenReturn(null);
        when(() => mockPrefs.getStringList(any())).thenReturn(null);
        when(() => mockPrefs.setStringList(any(), any()))
            .thenAnswer((_) async => true);

        final errorHandler = ErrorHandler.instance;
        await errorHandler.initialize();

        expect(errorHandler, isNotNull);
      });

      test('Error reporting works correctly', () {
        const testError = 'Test error message';
        const testSeverity = ErrorSeverity.high;
        const testCategory = ErrorCategory.network;

        expect(() {
          ErrorHandler.reportError(
            testError,
            severity: testSeverity,
            category: testCategory,
          );
        }, returnsNormally);
      });

      test('Network error reporting includes proper context', () {
        const testError = 'Network timeout';
        const endpoint = '/api/budget';
        const statusCode = 500;

        expect(() {
          ErrorHandler.reportNetworkError(
            testError,
            endpoint: endpoint,
            statusCode: statusCode,
          );
        }, returnsNormally);
      });

      test('Authentication error reporting works', () {
        const testError = 'Token expired';
        const action = 'login';

        expect(() {
          ErrorHandler.reportAuthError(
            testError,
            action: action,
          );
        }, returnsNormally);
      });
    });

    group('Enhanced Error Handling Tests', () {
      test('Enhanced error handling executes with retry', () async {
        int attemptCount = 0;

        final result = await EnhancedErrorHandling.executeWithRetry<String>(
          () async {
            attemptCount++;
            if (attemptCount < 3) {
              throw const SocketException('Connection failed');
            }
            return 'Success';
          },
          operationName: 'Test Operation',
          maxRetries: 3,
          retryDelay: const Duration(milliseconds: 100),
        );

        expect(result, equals('Success'));
        expect(attemptCount, equals(3));
      });

      test('Enhanced error handling respects retry limits', () async {
        int attemptCount = 0;

        final result = await EnhancedErrorHandling.executeWithRetry<String>(
          () async {
            attemptCount++;
            throw const SocketException('Connection failed');
          },
          operationName: 'Failing Operation',
          maxRetries: 2,
          fallbackValue: 'Fallback',
          retryDelay: const Duration(milliseconds: 50),
        );

        expect(result, equals('Fallback'));
        expect(attemptCount, equals(2));
      });

      test('Circuit breaker pattern works with timeout', () async {
        final result =
            await EnhancedErrorHandling.executeWithCircuitBreaker<String>(
          () async {
            await Future.delayed(const Duration(seconds: 2));
            return 'Should timeout';
          },
          timeout: const Duration(milliseconds: 100),
          operationName: 'Timeout Test',
          fallbackValue: 'Timed out',
        );

        expect(result, equals('Timed out'));
      });

      test('Safe widget builder handles widget errors', () {
        final widget = EnhancedErrorHandling.safeBuilder(
          () => throw Exception('Widget build error'),
          widgetName: 'Test Widget',
          fallbackWidget: const Text('Error fallback'),
        );

        expect(widget, isA<Text>());
      });

      test('Network error handler provides appropriate messages', () {
        // Test connection timeout
        final mockDioException = MockDioException();
        when(() => mockDioException.type)
            .thenReturn(DioExceptionType.connectionTimeout);

        final message =
            EnhancedErrorHandling.handleNetworkError(mockDioException);
        expect(message, contains('Connection timeout'));

        // Test 401 error
        when(() => mockDioException.type)
            .thenReturn(DioExceptionType.badResponse);
        when(() => mockDioException.response).thenReturn(Response(
          requestOptions: RequestOptions(path: '/api/test'),
          statusCode: 401,
        ));

        final authMessage =
            EnhancedErrorHandling.handleNetworkError(mockDioException);
        expect(authMessage, contains('Authentication required'));
      });
    });

    group('Error Recovery Service Tests', () {
      late EnhancedErrorRecoveryService recoveryService;

      setUp(() {
        recoveryService = EnhancedErrorRecoveryService.instance;
        recoveryService.initialize();
      });

      test('Recovery service initializes with default strategies', () {
        final stats = recoveryService.getRecoveryStats();
        expect(stats['registeredStrategies'], greaterThan(0));
      });

      test('Network recovery strategy provides appropriate delays', () async {
        final mockDioException = MockDioException();
        when(() => mockDioException.type)
            .thenReturn(DioExceptionType.connectionTimeout);

        final strategy = NetworkRecoveryStrategy();
        final context = RecoveryContext(
          operationId: 'test',
          operationName: 'Test Operation',
          maxRetries: 3,
          initialDelay: const Duration(seconds: 1),
          exponentialBackoff: true,
          retryableExceptions: [DioException],
          fallbackValue: null,
        );

        final result =
            await strategy.attemptRecovery(mockDioException, context);
        expect(result.shouldProceed, isTrue);
        expect(result.suggestedDelay, isNotNull);
      });

      test('Recovery service executes operation with recovery', () async {
        int attemptCount = 0;

        final result = await recoveryService.executeWithRecovery<String>(
          operation: () async {
            attemptCount++;
            if (attemptCount < 3) {
              throw const SocketException('Connection failed');
            }
            return 'Recovered';
          },
          operationId: 'recovery_test',
          operationName: 'Recovery Test',
          maxRetries: 3,
          fallbackValue: 'Failed',
        );

        expect(result, equals('Recovered'));
        expect(attemptCount, equals(3));
      });

      test('Custom recovery strategy can be registered', () {
        final customStrategy = TestRecoveryStrategy();
        recoveryService.registerRecoveryStrategy(TestException, customStrategy);

        final stats = recoveryService.getRecoveryStats();
        expect(
            stats['registeredStrategies'], greaterThan(4)); // Default + custom
      });
    });

    group('Error Analytics Service Tests', () {
      late ErrorAnalyticsService analyticsService;

      setUp(() async {
        analyticsService = ErrorAnalyticsService.instance;
        SharedPreferences.setMockInitialValues({});
        await analyticsService.initialize();
      });

      test('Analytics service records errors correctly', () {
        analyticsService.recordError(
          error: Exception('Test error'),
          severity: ErrorSeverity.medium,
          category: ErrorCategory.network,
          operationName: 'test_operation',
          screenName: 'TestScreen',
        );

        final summary = analyticsService.getAnalyticsSummary();
        expect(summary.totalErrors, equals(1));
        expect(summary.uniqueErrors, equals(1));
      });

      test('Error trends are calculated correctly', () {
        // Record errors at different times
        final baseTime = DateTime.now().subtract(const Duration(hours: 2));

        for (int i = 0; i < 5; i++) {
          analyticsService.recordError(
            error: Exception('Trend test error $i'),
            severity: ErrorSeverity.medium,
            category: ErrorCategory.network,
          );
        }

        final trends = analyticsService.getErrorTrends(
          period: const Duration(hours: 3),
          interval: const Duration(hours: 1),
        );

        expect(trends, isNotEmpty);
        expect(trends.last.errorCount, greaterThan(0));
      });

      test('Error patterns are detected', () {
        final now = DateTime.now();

        // Record errors that should form a pattern
        for (int i = 0; i < 3; i++) {
          analyticsService.recordError(
            error: Exception('Pattern error A'),
            severity: ErrorSeverity.medium,
            category: ErrorCategory.network,
          );

          analyticsService.recordError(
            error: Exception('Pattern error B'),
            severity: ErrorSeverity.medium,
            category: ErrorCategory.ui,
          );
        }

        final patterns = analyticsService.getErrorPatterns();
        expect(patterns, isNotEmpty);
      });

      test('Error impact assessment works correctly', () {
        const errorKey = 'test_error_key';

        // Record multiple occurrences
        for (int i = 0; i < 5; i++) {
          analyticsService.recordError(
            error: Exception('High impact error'),
            severity: ErrorSeverity.high,
            category: ErrorCategory.authentication,
            operationName: 'critical_operation',
          );
        }

        final summary = analyticsService.getAnalyticsSummary();
        final errorMetrics = summary.topErrors.first;
        final assessment =
            analyticsService.assessErrorImpact(errorMetrics.errorKey);

        expect(assessment.impactLevel, isNot(equals(ImpactLevel.minimal)));
        expect(assessment.frequency, equals(5));
      });
    });

    group('Error UI Widget Tests', () {
      testWidgets('Enhanced error screen renders correctly',
          (WidgetTester tester) async {
        bool retryPressed = false;
        bool homePressed = false;

        await tester.pumpWidget(
          MaterialApp(
            home: MitaWidgets.buildErrorScreen(
              title: 'Test Error',
              message: 'This is a test error message',
              onRetry: () => retryPressed = true,
              onGoHome: () => homePressed = true,
            ),
          ),
        );

        // Verify error content
        expect(find.text('Test Error'), findsOneWidget);
        expect(find.text('This is a test error message'), findsOneWidget);
        expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);

        // Test retry button
        await tester.tap(find.text('Try Again'));
        await tester.pump();
        expect(retryPressed, isTrue);

        // Test home button
        await tester.tap(find.text('Go to Home'));
        await tester.pump();
        expect(homePressed, isTrue);
      });

      testWidgets('Error banner renders with different severities',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Column(
                children: [
                  MitaWidgets.buildErrorBanner(
                    message: 'Low severity error',
                    severity: ErrorSeverity.low,
                  ),
                  MitaWidgets.buildErrorBanner(
                    message: 'High severity error',
                    severity: ErrorSeverity.high,
                  ),
                ],
              ),
            ),
          ),
        );

        expect(find.text('Low severity error'), findsOneWidget);
        expect(find.text('High severity error'), findsOneWidget);
        expect(find.byIcon(Icons.info_outline_rounded), findsOneWidget);
        expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      });

      testWidgets('Inline error message displays correctly',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: MitaWidgets.buildInlineError(
                message: 'Field validation error',
              ),
            ),
          ),
        );

        expect(find.text('Field validation error'), findsOneWidget);
        expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      });

      testWidgets('Loading with error state handles transitions',
          (WidgetTester tester) async {
        bool isLoading = true;
        String? error;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: StatefulBuilder(
                builder: (context, setState) {
                  return Column(
                    children: [
                      MitaWidgets.buildLoadingWithError(
                        isLoading: isLoading,
                        error: error,
                        loadingMessage: 'Loading data...',
                        onRetry: () {
                          setState(() {
                            isLoading = true;
                            error = null;
                          });
                        },
                        child: const Text('Content loaded'),
                      ),
                      ElevatedButton(
                        onPressed: () {
                          setState(() {
                            isLoading = false;
                            error = 'Test error';
                          });
                        },
                        child: const Text('Simulate Error'),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        );

        // Initially loading
        expect(find.text('Loading data...'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Simulate error
        await tester.tap(find.text('Simulate Error'));
        await tester.pump();

        expect(find.text('Test error'), findsOneWidget);
        expect(find.text('Try Again'), findsOneWidget);
      });

      testWidgets('Network status indicator shows correct states',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Column(
                children: [
                  MitaWidgets.buildNetworkStatusIndicator(
                    isConnected: true,
                    showWhenConnected: true,
                  ),
                  MitaWidgets.buildNetworkStatusIndicator(
                    isConnected: false,
                  ),
                ],
              ),
            ),
          ),
        );

        expect(find.text('Connected'), findsOneWidget);
        expect(find.text('No internet connection'), findsOneWidget);
        expect(find.byIcon(Icons.wifi_rounded), findsOneWidget);
        expect(find.byIcon(Icons.wifi_off_rounded), findsOneWidget);
      });
    });

    group('Error Handling Mixin Tests', () {
      testWidgets('RobustErrorHandlingMixin provides error state management',
          (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: TestWidget(),
          ),
        );

        final testWidgetState =
            tester.state<TestWidgetState>(find.byType(TestWidget));

        // Test loading state
        expect(testWidgetState.isLoading, isFalse);

        // Test error execution
        await testWidgetState.executeRobustly(() async {
          await Future.delayed(const Duration(milliseconds: 100));
          throw Exception('Test execution error');
        }, operationName: 'Test Operation');

        await tester.pump();
        expect(testWidgetState.errorMessage, isNotNull);
      });
    });

    group('Integration Tests', () {
      test('Full error flow from occurrence to recovery', () async {
        final recoveryService = EnhancedErrorRecoveryService.instance;
        final analyticsService = ErrorAnalyticsService.instance;

        await analyticsService.initialize();
        recoveryService.initialize();

        int operationAttempts = 0;

        // Simulate an operation that fails then succeeds
        final result = await recoveryService.executeWithRecovery<String>(
          operation: () async {
            operationAttempts++;
            if (operationAttempts < 3) {
              final error = DioException(
                requestOptions: RequestOptions(path: '/api/test'),
                type: DioExceptionType.connectionTimeout,
              );

              // Record in analytics
              analyticsService.recordError(
                error: error,
                severity: ErrorSeverity.medium,
                category: ErrorCategory.network,
                operationName: 'test_integration',
              );

              throw error;
            }
            return 'Integration Success';
          },
          operationId: 'integration_test',
          maxRetries: 3,
        );

        expect(result, equals('Integration Success'));
        expect(operationAttempts, equals(3));

        // Verify analytics recorded the errors
        final summary = analyticsService.getAnalyticsSummary();
        expect(summary.totalErrors, equals(2)); // 2 failed attempts
      });
    });
  });
}

// Helper classes for testing
class TestException implements Exception {
  final String message;
  TestException(this.message);

  @override
  String toString() => 'TestException: $message';
}

class TestRecoveryStrategy extends RecoveryStrategy {
  @override
  Future<RecoveryResult> attemptRecovery(
      dynamic error, RecoveryContext context) async {
    return RecoveryResult.proceed(
      delay: const Duration(milliseconds: 100),
      context: {'recovery_type': 'test_recovery'},
    );
  }
}

class TestWidget extends StatefulWidget {
  @override
  TestWidgetState createState() => TestWidgetState();
}

class TestWidgetState extends State<TestWidget> with RobustErrorHandlingMixin {
  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return buildLoadingState(message: 'Testing...');
    }

    if (errorMessage != null) {
      return buildErrorState(
        message: errorMessage,
        onRetry: () => clearError(),
      );
    }

    return const Scaffold(
      body: Center(
        child: Text('Test Widget Content'),
      ),
    );
  }
}

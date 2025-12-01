/*
Comprehensive Error Message Testing Framework for MITA
Tests error message quality, accessibility, and user experience
*/

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:mockito/mockito.dart';
import '../lib/core/financial_error_messages.dart' as ErrorMessages;
import '../lib/services/financial_error_service.dart';
import '../lib/widgets/financial_error_widgets.dart';

class MockBuildContext extends Mock implements BuildContext {}

void main() {
  group('Financial Error Messages', () {
    late FinancialErrorService errorService;

    setUp(() {
      errorService = FinancialErrorService.instance;
    });

    group('Error Categorization', () {
      test('should categorize session expired errors correctly', () {
        final error = DioException(
          requestOptions: RequestOptions(path: '/api/test'),
          response: Response(
            requestOptions: RequestOptions(path: '/api/test'),
            statusCode: 401,
          ),
        );

        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        expect(errorInfo.title, contains('Session'));
        expect(errorInfo.category, equals('Authentication'));
        expect(errorInfo.severity,
            equals(ErrorMessages.FinancialErrorSeverity.medium));
        expect(errorInfo.financialContext, isNotNull);
        expect(errorInfo.actions.isNotEmpty, isTrue);
      });

      test('should categorize budget exceeded errors correctly', () {
        final error = Exception('Budget exceeded by \$25.50');
        final context = {'operation': 'transaction', 'amount': '\$25.50'};

        final errorInfo = ErrorMessages.FinancialErrorMessages.getErrorInfo(
          error,
          additionalContext: context,
        );

        expect(errorInfo.title, contains('Budget'));
        expect(errorInfo.message, contains('exceed'));
        expect(errorInfo.category, equals('Budget Management'));
        expect(errorInfo.tips, isNotNull);
        expect(errorInfo.tips!.isNotEmpty, isTrue);
      });

      test('should categorize network errors correctly', () {
        final error = DioException(
          requestOptions: RequestOptions(path: '/api/test'),
          type: DioExceptionType.connectionTimeout,
        );

        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        expect(errorInfo.category, contains('Connectivity'));
        expect(
            errorInfo.actions.any((a) =>
                a.action == ErrorMessages.FinancialErrorActionType.retry),
            isTrue);
        expect(errorInfo.financialContext, contains('secure'));
      });

      test('should categorize validation errors correctly', () {
        final error = Exception('Invalid email format');

        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        expect(errorInfo.severity,
            equals(ErrorMessages.FinancialErrorSeverity.low));
        expect(
            errorInfo.actions.any(
                (a) => a.action == ErrorMessages.FinancialErrorActionType.edit),
            isTrue);
      });
    });

    group('Error Message Quality', () {
      test('should provide user-friendly language', () {
        final error =
            Exception('TransactionException: Database connection failed');

        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        // Should not contain technical terms
        expect(errorInfo.title, isNot(contains('Exception')));
        expect(errorInfo.message, isNot(contains('Database')));
        expect(errorInfo.message, isNot(contains('connection failed')));

        // Should contain user-friendly language
        expect(errorInfo.message, contains(RegExp(r'(try again|safe|secure)')));
      });

      test('should provide actionable guidance', () {
        final error = DioException(
          requestOptions: RequestOptions(path: '/api/transactions'),
          type: DioExceptionType.connectionTimeout,
        );

        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        // Should have at least one actionable step
        expect(errorInfo.actions.isNotEmpty, isTrue);

        // Actions should be specific and helpful
        final actionLabels =
            errorInfo.actions.map((a) => a.label.toLowerCase()).toList();
        expect(
            actionLabels.any((label) =>
                label.contains('try') ||
                label.contains('check') ||
                label.contains('retry')),
            isTrue);
      });

      test('should include financial context for money-related errors', () {
        final errors = [
          Exception('Budget exceeded'),
          Exception('Transaction failed'),
          Exception('Invalid amount'),
          DioException(
            requestOptions: RequestOptions(path: '/api/auth'),
            response: Response(
              requestOptions: RequestOptions(path: '/api/auth'),
              statusCode: 401,
            ),
          ),
        ];

        for (final error in errors) {
          final errorInfo =
              ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

          // Financial errors should have context about data security/accuracy
          if (errorInfo.category.contains('Authentication') ||
              errorInfo.category.contains('Transaction') ||
              errorInfo.category.contains('Budget')) {
            expect(errorInfo.financialContext, isNotNull);
            expect(
                errorInfo.financialContext!.toLowerCase(),
                anyOf(contains('secure'), contains('safe'),
                    contains('accurate')));
          }
        }
      });

      test('should provide helpful tips for complex errors', () {
        final error = Exception('Budget exceeded by \$50.00');

        final errorInfo = ErrorMessages.FinancialErrorMessages.getErrorInfo(
          error,
          additionalContext: {'operation': 'transaction'},
        );

        expect(errorInfo.tips, isNotNull);
        expect(errorInfo.tips!.length, greaterThan(1));

        // Tips should be actionable and specific
        for (final tip in errorInfo.tips!) {
          expect(tip.length, greaterThan(10)); // Not just one word
          expect(tip, matches(RegExp(r'^[A-Z]'))); // Starts with capital
          expect(tip,
              isNot(endsWith('.'))); // Doesn't end with period (list format)
        }
      });
    });

    group('Error Message Structure', () {
      test('should have consistent structure', () {
        final errors = [
          Exception('Network error'),
          Exception('Validation failed'),
          Exception('Budget exceeded'),
          Exception('Session expired'),
        ];

        for (final error in errors) {
          final errorInfo =
              ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

          // Required fields
          expect(errorInfo.title, isNotEmpty);
          expect(errorInfo.message, isNotEmpty);
          expect(errorInfo.actions, isNotEmpty);
          expect(errorInfo.icon, isNotNull);
          expect(errorInfo.severity, isNotNull);
          expect(errorInfo.category, isNotEmpty);

          // Title should be concise
          expect(errorInfo.title.length, lessThan(50));

          // Message should be detailed but not overwhelming
          expect(errorInfo.message.length, greaterThan(20));
          expect(errorInfo.message.length, lessThan(200));

          // At least one primary action
          expect(errorInfo.actions.where((a) => a.isPrimary).length,
              greaterThanOrEqualTo(1));
        }
      });

      test('should use appropriate severity levels', () {
        final testCases = {
          Exception('Session expired'):
              ErrorMessages.FinancialErrorSeverity.medium,
          Exception('Invalid email'): ErrorMessages.FinancialErrorSeverity.low,
          Exception('Data corruption detected'):
              ErrorMessages.FinancialErrorSeverity.high,
          Exception('Security breach'):
              ErrorMessages.FinancialErrorSeverity.critical,
        };

        testCases.forEach((error, expectedSeverity) {
          final errorInfo =
              ErrorMessages.FinancialErrorMessages.getErrorInfo(error);
          expect(errorInfo.severity, equals(expectedSeverity));
        });
      });
    });

    group('Action Button Quality', () {
      test('should have clear, actionable button labels', () {
        final error = Exception('Transaction failed');
        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        for (final action in errorInfo.actions) {
          // Labels should be clear and specific
          expect(action.label, isNotEmpty);
          expect(action.label.length, lessThan(20)); // Not too long
          expect(action.label,
              matches(RegExp(r'^[A-Z]'))); // Proper capitalization

          // Avoid generic labels
          expect(action.label, isNot(equals('OK')));
          expect(action.label, isNot(equals('Submit')));
          expect(action.label, isNot(equals('Continue')));
        }
      });

      test('should prioritize primary actions correctly', () {
        final errors = [
          Exception('Session expired'),
          Exception('Budget exceeded'),
          Exception('Transaction failed'),
        ];

        for (final error in errors) {
          final errorInfo =
              ErrorMessages.FinancialErrorMessages.getErrorInfo(error);
          final primaryActions = errorInfo.actions.where((a) => a.isPrimary);

          // Should have exactly one primary action (or very few)
          expect(primaryActions.length, lessThanOrEqualTo(2));
          expect(primaryActions.length, greaterThanOrEqualTo(1));

          // Primary action should be the most helpful
          final primaryAction = primaryActions.first;
          expect(
              primaryAction.action,
              anyOf(
                ErrorMessages.FinancialErrorActionType.retry,
                ErrorMessages.FinancialErrorActionType.reauth,
                ErrorMessages.FinancialErrorActionType.edit,
                ErrorMessages.FinancialErrorActionType.override,
              ));
        }
      });
    });

    group('Accessibility', () {
      test('should provide screen reader appropriate content', () {
        final error = Exception('Budget exceeded by \$25.50');
        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        // Content should be readable by screen readers
        final screenReaderContent =
            '${errorInfo.category} Error: ${errorInfo.title}. ${errorInfo.message}';

        // Should not contain visual-only information
        expect(screenReaderContent,
            isNot(contains(RegExp(r'click|tap|see|look'))));

        // Should provide complete context
        expect(screenReaderContent.length, greaterThan(50));
        expect(screenReaderContent, contains(errorInfo.category));
        expect(screenReaderContent, contains(errorInfo.title));
        expect(screenReaderContent, contains(errorInfo.message));
      });

      test('should have appropriate semantic structure', () {
        final error = Exception('Transaction failed');
        final errorInfo =
            ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

        // Icons should have semantic meaning
        expect(errorInfo.icon, isNotNull);

        // Categories should be descriptive
        expect(errorInfo.category, isNot(equals('Error')));
        expect(errorInfo.category, matches(RegExp(r'^[A-Z][a-zA-Z\s]+$')));

        // Severity should map to importance levels
        final importanceMapping = {
          ErrorMessages.FinancialErrorSeverity.low: false,
          ErrorMessages.FinancialErrorSeverity.medium: false,
          ErrorMessages.FinancialErrorSeverity.high: true,
          ErrorMessages.FinancialErrorSeverity.critical: true,
        };

        expect(importanceMapping.containsKey(errorInfo.severity), isTrue);
      });
    });

    group('Financial Validation', () {
      test('should validate financial amounts correctly', () {
        final testCases = {
          '25.50': null, // Valid
          '0.99': null, // Valid
          '1000.00': null, // Valid
          '': 'Please enter an amount', // Required field
          'abc': 'Please enter a valid amount (numbers only)', // Invalid format
          '-10.00': 'Amount must be greater than zero', // Negative
          '25.555': 'Maximum 2 decimal places for cents', // Too many decimals
        };

        testCases.forEach((input, expectedError) {
          final result = errorService.validateFinancialAmount(input);
          expect(result, equals(expectedError));
        });
      });

      test('should validate email with financial context', () {
        final testCases = {
          'user@example.com': null, // Valid
          'test@domain.co.uk': null, // Valid
          '': 'Email is required for secure account access', // Required
          'invalid-email':
              'Please enter a valid email for account security', // Invalid format
          '@domain.com':
              'Please enter a valid email for account security', // Missing local part
        };

        testCases.forEach((input, expectedError) {
          final result = errorService.validateFinancialEmail(input);
          expect(result, equals(expectedError));
        });
      });
    });
  });

  group('Error Widget Tests', () {
    testWidgets('FinancialErrorDialog should display correctly',
        (WidgetTester tester) async {
      final errorInfo = ErrorMessages.FinancialErrorInfo(
        title: 'Test Error',
        message: 'This is a test error message',
        actions: [
          ErrorMessages.FinancialErrorAction(
            label: 'Retry',
            action: ErrorMessages.FinancialErrorActionType.retry,
            isPrimary: true,
          ),
        ],
        icon: Icons.error_outline,
        severity: ErrorMessages.FinancialErrorSeverity.medium,
        category: 'Test',
      );

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: FinancialErrorDialog(errorInfo: errorInfo),
        ),
      ));

      // Check that title is displayed
      expect(find.text('Test Error'), findsOneWidget);

      // Check that message is displayed
      expect(find.text('This is a test error message'), findsOneWidget);

      // Check that retry button is displayed
      expect(find.text('Retry'), findsOneWidget);

      // Check that icon is displayed
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('FinancialErrorSnackBar should display correctly',
        (WidgetTester tester) async {
      final errorInfo = ErrorMessages.FinancialErrorInfo(
        title: 'Network Error',
        message: 'Please check your connection',
        actions: [
          ErrorMessages.FinancialErrorAction(
            label: 'Retry',
            action: ErrorMessages.FinancialErrorActionType.retry,
            isPrimary: true,
          ),
        ],
        icon: Icons.wifi_off,
        severity: ErrorMessages.FinancialErrorSeverity.low,
        category: 'Network',
      );

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  FinancialErrorSnackBar.create(
                    errorInfo: errorInfo,
                    context: context,
                  ),
                );
              },
              child: const Text('Show Error'),
            ),
          ),
        ),
      ));

      // Tap button to show snackbar
      await tester.tap(find.text('Show Error'));
      await tester.pumpAndSettle();

      // Check that snackbar content is displayed
      expect(find.text('Network Error'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
    });
  });

  group('Localization Tests', () {
    test('should handle missing localization gracefully', () {
      final error = Exception('Test error');

      // Test without context (no localization)
      final errorInfo =
          ErrorMessages.FinancialErrorMessages.getErrorInfo(error);

      expect(errorInfo.title, isNotEmpty);
      expect(errorInfo.message, isNotEmpty);
      expect(errorInfo.actions, isNotEmpty);
    });
  });

  group('Integration Tests', () {
    test('should maintain consistency across error types', () {
      final errorTypes = [
        Exception('Network error'),
        Exception('Validation failed'),
        Exception('Budget exceeded'),
        Exception('Session expired'),
        DioException(requestOptions: RequestOptions(path: '/test')),
      ];

      final errorInfos = errorTypes
          .map((e) => ErrorMessages.FinancialErrorMessages.getErrorInfo(e))
          .toList();

      // All should have consistent structure
      for (final info in errorInfos) {
        expect(info.title, matches(RegExp(r'^[A-Z][^.!?]*$'))); // Title format
        expect(
            info.message, matches(RegExp(r'^[A-Z].*[.!]$'))); // Message format
        expect(info.category,
            matches(RegExp(r'^[A-Z][a-zA-Z\s]*$'))); // Category format
      }

      // Financial context should be present for financial operations
      final financialErrorInfos = errorInfos
          .where((info) =>
              info.category.contains('Budget') ||
              info.category.contains('Transaction') ||
              info.category.contains('Authentication'))
          .toList();

      for (final info in financialErrorInfos) {
        expect(info.financialContext, isNotNull);
      }
    });
  });
}

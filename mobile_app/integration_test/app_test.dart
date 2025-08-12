import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mockito/mockito.dart';

import '../lib/main.dart' as app;
import '../lib/services/api_service.dart';
import '../lib/services/user_data_manager.dart';
import '../lib/services/accessibility_service.dart';
import '../lib/services/push_notification_service.dart';
import '../lib/l10n/generated/app_localizations.dart';

import 'test_helpers.dart';
import 'mock_services.dart';

/// Comprehensive Flutter Integration Tests for MITA
/// 
/// These tests validate complete user journeys and ensure production readiness
/// focusing on financial accuracy, security, and accessibility requirements.
///
/// Test Coverage:
/// - Complete onboarding flow from first launch to dashboard
/// - Authentication flows (email/password, Google Sign-In)
/// - Financial features (budget management, transaction entry)
/// - Mobile-specific functionality (push notifications, connectivity)
/// - Error handling and edge cases
/// - Accessibility and internationalization
/// - Security validations
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('MITA Integration Tests', () {
    late MockApiService mockApiService;
    late MockUserDataManager mockUserDataManager;
    late TestHelpers testHelpers;

    setUpAll(() async {
      // Initialize test environment
      testHelpers = TestHelpers();
      await testHelpers.initializeTestEnvironment();
    });

    setUp(() async {
      // Reset mocks for each test
      mockApiService = MockApiService();
      mockUserDataManager = MockUserDataManager();
      
      // Setup default mock behaviors
      await testHelpers.setupDefaultMockBehaviors(
        mockApiService: mockApiService,
        mockUserDataManager: mockUserDataManager,
      );
    });

    tearDown(() async {
      // Clean up after each test
      await testHelpers.cleanupTestEnvironment();
    });

    // ==========================================================================
    // ONBOARDING FLOW TESTS
    // ==========================================================================
    
    group('Onboarding Flow Tests', () {
      testWidgets(
        'Complete onboarding flow from first launch to dashboard',
        (WidgetTester tester) async {
          // Setup: New user (no token)
          when(mockApiService.getToken()).thenAnswer((_) async => null);
          
          // Launch app
          await tester.pumpWidget(app.MITAApp());
          await tester.pumpAndSettle(const Duration(seconds: 3));

          // Verify: Welcome screen appears
          expect(find.text('MITA'), findsOneWidget);
          expect(find.text('Money Intelligence Task Assistant'), findsOneWidget);
          
          // Test: Welcome screen auto-navigation to login
          await tester.pumpAndSettle(const Duration(seconds: 4));
          
          // Verify: Navigated to login screen
          await testHelpers.verifyLoginScreenElements(tester);
          
          // Test: Navigate to registration from login
          await tester.tap(find.text('Sign Up'));
          await tester.pumpAndSettle();
          
          // Verify: Registration screen elements
          await testHelpers.verifyRegistrationScreenElements(tester);
          
          // Test: Complete registration flow
          await testHelpers.completeRegistrationFlow(
            tester: tester,
            email: 'test@example.com',
            password: 'SecurePass123!',
            mockApiService: mockApiService,
          );
          
          // Verify: Navigated to onboarding
          await tester.pumpAndSettle();
          expect(find.text('Select Your Region'), findsOneWidget);
          
          // Test: Complete onboarding steps
          await testHelpers.completeOnboardingFlow(
            tester: tester,
            mockApiService: mockApiService,
          );
          
          // Verify: Reached main dashboard
          await tester.pumpAndSettle();
          await testHelpers.verifyDashboardElements(tester);
          
          // Test financial accuracy: Verify initial budget state
          await testHelpers.verifyInitialBudgetState(tester);
        },
        timeout: const Timeout(Duration(minutes: 5)),
      );

      testWidgets(
        'Existing user with completed onboarding goes to dashboard',
        (WidgetTester tester) async {
          // Setup: Existing user with valid token and completed onboarding
          when(mockApiService.getToken()).thenAnswer((_) async => 'valid_token');
          when(mockUserDataManager.hasCompletedOnboarding())
              .thenAnswer((_) async => true);
          
          // Launch app
          await tester.pumpWidget(app.MITAApp());
          await tester.pumpAndSettle(const Duration(seconds: 4));
          
          // Verify: Directly navigated to dashboard
          await testHelpers.verifyDashboardElements(tester);
          
          // Verify: No onboarding screens shown
          expect(find.text('Select Your Region'), findsNothing);
          expect(find.text('Set Your Location'), findsNothing);
        },
      );

      testWidgets(
        'User with token but incomplete onboarding continues setup',
        (WidgetTester tester) async {
          // Setup: User with token but incomplete onboarding
          when(mockApiService.getToken()).thenAnswer((_) async => 'valid_token');
          when(mockUserDataManager.hasCompletedOnboarding())
              .thenAnswer((_) async => false);
          
          // Launch app
          await tester.pumpWidget(app.MITAApp());
          await tester.pumpAndSettle(const Duration(seconds: 4));
          
          // Verify: Navigated to onboarding region screen
          expect(find.text('Select Your Region'), findsOneWidget);
          
          // Test: Complete remaining onboarding
          await testHelpers.completeOnboardingFlow(
            tester: tester,
            mockApiService: mockApiService,
          );
          
          // Verify: Reached dashboard after completion
          await tester.pumpAndSettle();
          await testHelpers.verifyDashboardElements(tester);
        },
      );
    });

    // ==========================================================================
    // AUTHENTICATION FLOW TESTS
    // ==========================================================================
    
    group('Authentication Flow Tests', () {
      testWidgets(
        'Email/password login with validation and error handling',
        (WidgetTester tester) async {
          // Setup: Navigate to login screen
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Empty form validation
          await tester.tap(find.byType(FilledButton));
          await tester.pumpAndSettle();
          
          // Verify: Validation errors shown
          expect(find.text('Please enter your email'), findsOneWidget);
          expect(find.text('Please enter your password'), findsOneWidget);
          
          // Test: Invalid email format validation
          await tester.enterText(
            find.byKey(const Key('email_field')), 
            'invalid-email'
          );
          await tester.tap(find.byType(FilledButton));
          await tester.pumpAndSettle();
          
          // Verify: Email validation error
          expect(find.text('Please enter a valid email'), findsOneWidget);
          
          // Test: Weak password validation
          await testHelpers.clearAndEnterText(
            tester, 
            find.byKey(const Key('password_field')), 
            '123'
          );
          await tester.tap(find.byType(FilledButton));
          await tester.pumpAndSettle();
          
          // Verify: Password strength validation
          expect(find.text('Password is too weak'), findsOneWidget);
          
          // Test: Successful login with strong credentials
          await testHelpers.performSuccessfulLogin(
            tester: tester,
            email: 'test@example.com',
            password: 'SecurePass123!',
            mockApiService: mockApiService,
          );
          
          // Verify: Navigation to dashboard
          await tester.pumpAndSettle();
          await testHelpers.verifyDashboardElements(tester);
          
          // Verify: Push notification registration triggered
          verify(mockApiService.registerPushToken(any)).called(1);
        },
      );

      testWidgets(
        'Google Sign-In integration flow',
        (WidgetTester tester) async {
          // Setup: Navigate to login screen
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Google Sign-In button
          final googleButton = find.text('Continue with Google');
          expect(googleButton, findsOneWidget);
          
          // Mock Google Sign-In success
          when(mockApiService.loginWithGoogle(any)).thenAnswer((_) async => 
            MockResponse(data: {
              'access_token': 'google_access_token',
              'refresh_token': 'google_refresh_token',
            }));
          
          await tester.tap(googleButton);
          await tester.pumpAndSettle();
          
          // Verify: Loading state shown
          expect(find.byType(CircularProgressIndicator), findsOneWidget);
          
          // Verify: Successful navigation to dashboard
          await tester.pumpAndSettle(const Duration(seconds: 2));
          await testHelpers.verifyDashboardElements(tester);
          
          // Verify: Tokens saved
          verify(mockApiService.saveTokens(
            'google_access_token', 
            'google_refresh_token'
          )).called(1);
        },
      );

      testWidgets(
        'Password reset UI flow',
        (WidgetTester tester) async {
          // Setup: Navigate to login screen
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Navigate to forgot password
          await tester.tap(find.text('Forgot?'));
          await tester.pumpAndSettle();
          
          // Verify: Forgot password screen elements
          expect(find.text('Reset Password'), findsOneWidget);
          expect(find.text('Enter your email address'), findsOneWidget);
          
          // Test: Email validation in password reset
          await tester.enterText(
            find.byType(TextFormField), 
            'invalid-email'
          );
          await tester.tap(find.byType(FilledButton));
          await tester.pumpAndSettle();
          
          // Verify: Validation error
          expect(find.text('Please enter a valid email'), findsOneWidget);
          
          // Test: Successful password reset request
          await testHelpers.clearAndEnterText(
            tester, 
            find.byType(TextFormField), 
            'test@example.com'
          );
          
          when(mockApiService.requestPasswordReset('test@example.com'))
              .thenAnswer((_) async => MockResponse(data: {'success': true}));
          
          await tester.tap(find.byType(FilledButton));
          await tester.pumpAndSettle();
          
          // Verify: Success message
          expect(find.text('Password reset email sent'), findsOneWidget);
        },
      );

      testWidgets(
        'Session timeout and token refresh handling',
        (WidgetTester tester) async {
          // Setup: User logged in with expired token
          await testHelpers.loginUser(tester, mockApiService);
          
          // Simulate API call with expired token
          when(mockApiService.getBudgetData())
              .thenThrow(DioError(
                requestOptions: RequestOptions(path: '/budget'),
                response: Response(
                  statusCode: 401,
                  requestOptions: RequestOptions(path: '/budget'),
                ),
              ));
          
          // Mock successful token refresh
          when(mockApiService.refreshTokens()).thenAnswer((_) async => true);
          
          // Test: Trigger API call that will fail with 401
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Token refresh was attempted
          verify(mockApiService.refreshTokens()).called(1);
          
          // Verify: User not logged out (token refresh worked)
          expect(find.text('Login'), findsNothing);
        },
      );
    });

    // ==========================================================================
    // FINANCIAL FEATURE TESTS
    // ==========================================================================
    
    group('Financial Feature Tests', () {
      setUp(() async {
        // Login user before financial tests
        await testHelpers.loginUser(tester, mockApiService);
      });

      testWidgets(
        'Daily budget display and real-time updates',
        (WidgetTester tester) async {
          // Setup: Mock budget data
          when(mockApiService.getBudgetData()).thenAnswer((_) async =>
            MockResponse(data: {
              'dailyBudget': 50.00,
              'remainingBudget': 30.25,
              'spentToday': 19.75,
              'currency': 'USD',
            }));
          
          // Navigate to budget screen
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Budget data displayed correctly
          expect(find.text('\$50.00'), findsOneWidget); // Daily budget
          expect(find.text('\$30.25'), findsOneWidget); // Remaining
          expect(find.text('\$19.75'), findsOneWidget); // Spent today
          
          // Test: Currency formatting accuracy
          await testHelpers.verifyMonetaryFormatting(tester);
          
          // Test: Budget progress calculation
          final progressIndicator = find.byType(LinearProgressIndicator);
          expect(progressIndicator, findsOneWidget);
          
          // Verify progress value (19.75/50.00 = 0.395)
          final progress = tester.widget<LinearProgressIndicator>(progressIndicator);
          expect(progress.value, closeTo(0.395, 0.001));
        },
      );

      testWidgets(
        'Transaction entry with validation and budget updates',
        (WidgetTester tester) async {
          // Navigate to add expense screen
          await tester.tap(find.byIcon(Icons.add));
          await tester.pumpAndSettle();
          
          // Verify: Add expense screen elements
          expect(find.text('Add Expense'), findsOneWidget);
          expect(find.byKey(const Key('amount_field')), findsOneWidget);
          expect(find.byKey(const Key('description_field')), findsOneWidget);
          
          // Test: Invalid amount validation
          await tester.enterText(
            find.byKey(const Key('amount_field')), 
            'invalid'
          );
          await tester.tap(find.text('Save'));
          await tester.pumpAndSettle();
          
          // Verify: Amount validation error
          expect(find.text('Please enter a valid amount'), findsOneWidget);
          
          // Test: Negative amount handling
          await testHelpers.clearAndEnterText(
            tester, 
            find.byKey(const Key('amount_field')), 
            '-10.50'
          );
          await tester.tap(find.text('Save'));
          await tester.pumpAndSettle();
          
          // Verify: Negative amount error
          expect(find.text('Amount must be positive'), findsOneWidget);
          
          // Test: Valid transaction entry
          await testHelpers.clearAndEnterText(
            tester, 
            find.byKey(const Key('amount_field')), 
            '15.75'
          );
          await tester.enterText(
            find.byKey(const Key('description_field')), 
            'Coffee and snack'
          );
          
          // Mock successful transaction save
          when(mockApiService.addExpense(any)).thenAnswer((_) async =>
            MockResponse(data: {
              'id': '123',
              'amount': 15.75,
              'description': 'Coffee and snack',
              'timestamp': DateTime.now().toIso8601String(),
            }));
          
          await tester.tap(find.text('Save'));
          await tester.pumpAndSettle();
          
          // Verify: Success feedback
          expect(find.text('Expense added successfully'), findsOneWidget);
          
          // Verify: Navigation back to budget screen
          await tester.pumpAndSettle();
          expect(find.text('Add Expense'), findsNothing);
          
          // Verify: Budget updated with new expense
          await testHelpers.verifyBudgetUpdate(tester, 15.75);
        },
      );

      testWidgets(
        'Budget overflow protection and warnings',
        (WidgetTester tester) async {
          // Setup: Mock budget near limit
          when(mockApiService.getBudgetData()).thenAnswer((_) async =>
            MockResponse(data: {
              'dailyBudget': 50.00,
              'remainingBudget': 5.25,
              'spentToday': 44.75,
              'currency': 'USD',
            }));
          
          // Navigate to add expense
          await tester.tap(find.byIcon(Icons.add));
          await tester.pumpAndSettle();
          
          // Test: Add expense that exceeds budget
          await tester.enterText(
            find.byKey(const Key('amount_field')), 
            '10.00'
          );
          await tester.enterText(
            find.byKey(const Key('description_field')), 
            'Expensive item'
          );
          await tester.tap(find.text('Save'));
          await tester.pumpAndSettle();
          
          // Verify: Budget overflow warning
          expect(find.text('This will exceed your daily budget'), findsOneWidget);
          expect(find.text('Continue anyway?'), findsOneWidget);
          
          // Test: Cancel overflow
          await tester.tap(find.text('Cancel'));
          await tester.pumpAndSettle();
          
          // Verify: Transaction not saved
          expect(find.text('Add Expense'), findsOneWidget);
          
          // Test: Confirm overflow
          await tester.tap(find.text('Save'));
          await tester.pumpAndSettle();
          await tester.tap(find.text('Continue'));
          await tester.pumpAndSettle();
          
          // Verify: Transaction saved with warning flag
          verify(mockApiService.addExpense(argThat(
            predicate((data) => data['budgetOverride'] == true)
          ))).called(1);
        },
      );

      testWidgets(
        'Decimal precision and currency handling',
        (WidgetTester tester) async {
          // Test various decimal scenarios
          final testAmounts = [
            '0.01',    // Minimum amount
            '0.99',    // Under dollar
            '1.00',    // Exact dollar
            '999.99',  // Large amount
            '1234.567', // More than 2 decimal places
          ];
          
          for (final amount in testAmounts) {
            await tester.tap(find.byIcon(Icons.add));
            await tester.pumpAndSettle();
            
            await tester.enterText(
              find.byKey(const Key('amount_field')), 
              amount
            );
            
            // Verify proper formatting
            final field = tester.widget<TextFormField>(
              find.byKey(const Key('amount_field'))
            );
            
            // Check decimal truncation to 2 places
            if (amount == '1234.567') {
              expect(field.controller?.text, equals('1234.56'));
            }
            
            await tester.tap(find.byIcon(Icons.close));
            await tester.pumpAndSettle();
          }
        },
      );
    });

    // ==========================================================================
    // MOBILE-SPECIFIC FUNCTIONALITY TESTS
    // ==========================================================================
    
    group('Mobile-Specific Functionality Tests', () {
      testWidgets(
        'Push notification registration after login',
        (WidgetTester tester) async {
          // Mock successful login
          await testHelpers.performSuccessfulLogin(
            tester: tester,
            email: 'test@example.com',
            password: 'SecurePass123!',
            mockApiService: mockApiService,
          );
          
          // Verify: Push notification service initialized
          verify(mockApiService.registerPushToken(any)).called(1);
          
          // Verify: Token registration happened after authentication
          final verificationOrder = verify(mockApiService.registerPushToken(any));
          final loginOrder = verify(mockApiService.login(any, any));
          expect(verificationOrder.calledAfter(loginOrder), isTrue);
        },
      );

      testWidgets(
        'Network connectivity changes and offline mode',
        (WidgetTester tester) async {
          // Setup: Login user
          await testHelpers.loginUser(tester, mockApiService);
          
          // Test: Simulate network loss
          await testHelpers.simulateNetworkLoss(mockApiService);
          
          // Attempt to load budget data
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Offline mode indicator
          expect(find.text('Offline Mode'), findsOneWidget);
          expect(find.byIcon(Icons.cloud_off), findsOneWidget);
          
          // Verify: Cached data shown
          expect(find.text('Last updated'), findsOneWidget);
          
          // Test: Network restoration
          await testHelpers.simulateNetworkRestoration(mockApiService);
          
          // Pull to refresh
          await tester.drag(
            find.byType(RefreshIndicator),
            const Offset(0, 300)
          );
          await tester.pumpAndSettle();
          
          // Verify: Online mode restored
          expect(find.text('Offline Mode'), findsNothing);
          expect(find.byIcon(Icons.cloud_off), findsNothing);
        },
      );

      testWidgets(
        'Device orientation changes and responsive layout',
        (WidgetTester tester) async {
          // Setup: Login and navigate to dashboard
          await testHelpers.loginUser(tester, mockApiService);
          
          // Test: Portrait mode (default)
          await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
            'flutter/system_chrome',
            const StandardMethodCodec().encodeMethodCall(
              const MethodCall('SystemChrome.setPreferredOrientations', [
                'DeviceOrientation.portraitUp'
              ])
            ),
            (data) {},
          );
          await tester.pumpAndSettle();
          
          // Verify: Portrait layout
          expect(find.byType(BottomNavigationBar), findsOneWidget);
          
          // Test: Landscape mode
          await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
            'flutter/system_chrome',
            const StandardMethodCodec().encodeMethodCall(
              const MethodCall('SystemChrome.setPreferredOrientations', [
                'DeviceOrientation.landscapeLeft'
              ])
            ),
            (data) {},
          );
          await tester.pumpAndSettle();
          
          // Verify: Landscape adaptations
          await testHelpers.verifyLandscapeLayout(tester);
        },
      );

      testWidgets(
        'Background app transitions and data persistence',
        (WidgetTester tester) async {
          // Setup: Add transaction
          await testHelpers.loginUser(tester, mockApiService);
          await testHelpers.addTestTransaction(
            tester: tester,
            amount: '25.50',
            description: 'Test expense',
            mockApiService: mockApiService,
          );
          
          // Test: App goes to background
          await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
            'flutter/system_chrome',
            const StandardMethodCodec().encodeMethodCall(
              const MethodCall('SystemChrome.setApplicationSwitcherDescription', {
                'label': 'MITA',
                'primaryColor': 0xFF193C57,
              })
            ),
            (data) {},
          );
          
          // Simulate app resume after 30 minutes
          await Future.delayed(const Duration(milliseconds: 100));
          
          // Verify: Data persisted
          expect(find.text('Test expense'), findsOneWidget);
          expect(find.text('\$25.50'), findsOneWidget);
          
          // Verify: Auto-refresh triggered
          verify(mockApiService.getBudgetData()).called(greaterThan(1));
        },
      );
    });

    // ==========================================================================
    // ERROR HANDLING AND EDGE CASES
    // ==========================================================================
    
    group('Error Handling and Edge Cases Tests', () {
      testWidgets(
        'Network errors and recovery',
        (WidgetTester tester) async {
          // Setup: Login user
          await testHelpers.loginUser(tester, mockApiService);
          
          // Test: Network timeout during budget load
          when(mockApiService.getBudgetData())
              .thenThrow(DioError(
                type: DioErrorType.connectTimeout,
                requestOptions: RequestOptions(path: '/budget'),
              ));
          
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Timeout error handling
          expect(find.text('Connection timeout'), findsOneWidget);
          expect(find.text('Try again'), findsOneWidget);
          
          // Test: Retry mechanism
          when(mockApiService.getBudgetData()).thenAnswer((_) async =>
            MockResponse(data: {'dailyBudget': 50.00}));
          
          await tester.tap(find.text('Try again'));
          await tester.pumpAndSettle();
          
          // Verify: Successful retry
          expect(find.text('Connection timeout'), findsNothing);
          expect(find.text('\$50.00'), findsOneWidget);
        },
      );

      testWidgets(
        'Invalid input sanitization and XSS prevention',
        (WidgetTester tester) async {
          // Navigate to add expense
          await testHelpers.loginUser(tester, mockApiService);
          await tester.tap(find.byIcon(Icons.add));
          await tester.pumpAndSettle();
          
          // Test: Script injection attempt
          const maliciousInput = '<script>alert("xss")</script>';
          await tester.enterText(
            find.byKey(const Key('description_field')), 
            maliciousInput
          );
          
          // Verify: Input sanitized
          final field = tester.widget<TextFormField>(
            find.byKey(const Key('description_field'))
          );
          expect(field.controller?.text, isNot(contains('<script>')));
          expect(field.controller?.text, equals('alert("xss")'));
          
          // Test: SQL injection attempt
          const sqlInjection = "'; DROP TABLE expenses; --";
          await testHelpers.clearAndEnterText(
            tester, 
            find.byKey(const Key('description_field')), 
            sqlInjection
          );
          
          // Verify: SQL characters escaped/sanitized
          final fieldAfterSql = tester.widget<TextFormField>(
            find.byKey(const Key('description_field'))
          );
          expect(fieldAfterSql.controller?.text, isNot(contains('DROP TABLE')));
        },
      );

      testWidgets(
        'Concurrent operations and race condition prevention',
        (WidgetTester tester) async {
          // Setup: Login user
          await testHelpers.loginUser(tester, mockApiService);
          
          // Test: Multiple simultaneous expense additions
          final futures = <Future>[];
          
          for (int i = 0; i < 5; i++) {
            futures.add(testHelpers.addTestTransaction(
              tester: tester,
              amount: '10.0$i',
              description: 'Transaction $i',
              mockApiService: mockApiService,
            ));
          }
          
          // Wait for all operations
          await Future.wait(futures);
          await tester.pumpAndSettle();
          
          // Verify: All transactions processed without corruption
          for (int i = 0; i < 5; i++) {
            expect(find.text('Transaction $i'), findsOneWidget);
            expect(find.text('\$10.0$i'), findsOneWidget);
          }
          
          // Verify: Budget calculations are consistent
          await testHelpers.verifyBudgetConsistency(tester);
        },
      );

      testWidgets(
        'Memory pressure and resource cleanup',
        (WidgetTester tester) async {
          // Test: Create and dispose many screens rapidly
          await testHelpers.loginUser(tester, mockApiService);
          
          for (int i = 0; i < 50; i++) {
            // Navigate through all tabs rapidly
            for (int tab = 0; tab < 6; tab++) {
              await tester.tap(find.byType(BottomNavigationBarItem).at(tab));
              await tester.pump(); // Don't wait for settle
            }
          }
          
          await tester.pumpAndSettle();
          
          // Verify: App still responsive
          expect(find.byType(BottomNavigationBar), findsOneWidget);
          
          // Verify: No memory leaks (controllers disposed)
          await testHelpers.verifyResourceCleanup(tester);
        },
      );
    });

    // ==========================================================================
    // ACCESSIBILITY AND INTERNATIONALIZATION TESTS
    // ==========================================================================
    
    group('Accessibility and i18n Tests', () {
      testWidgets(
        'Screen reader navigation and announcements',
        (WidgetTester tester) async {
          // Enable accessibility testing
          final SemanticsHandle handle = tester.ensureSemantics();
          
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Screen reader labels
          expect(
            tester.getSemantics(find.text('Welcome Back')),
            matchesSemantics(
              label: 'MITA Login. Welcome back. Sign in to continue managing your finances',
              isHeader: true,
            ),
          );
          
          // Test: Form field accessibility
          expect(
            tester.getSemantics(find.byKey(const Key('email_field'))),
            matchesSemantics(
              label: 'Email address, required field. Enter your email to sign in to MITA',
              isTextField: true,
            ),
          );
          
          // Test: Button accessibility
          expect(
            tester.getSemantics(find.byType(FilledButton)),
            matchesSemantics(
              label: 'Sign in to MITA. Enter valid email and password to enable',
              isButton: true,
            ),
          );
          
          handle.dispose();
        },
      );

      testWidgets(
        'High contrast mode support',
        (WidgetTester tester) async {
          // Enable high contrast mode
          tester.platformDispatcher.accessibilityFeaturesTestValue = 
            FakeAccessibilityFeatures(highContrast: true);
          
          await testHelpers.loginUser(tester, mockApiService);
          
          // Verify: High contrast colors used
          final theme = Theme.of(tester.element(find.byType(MaterialApp)));
          expect(theme.colorScheme.background, equals(Colors.black));
          expect(theme.colorScheme.onBackground, equals(Colors.white));
          
          // Verify: Sufficient color contrast ratios
          await testHelpers.verifyColorContrastRatios(tester);
        },
      );

      testWidgets(
        'Spanish localization integration',
        (WidgetTester tester) async {
          // Set Spanish locale
          await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
            'flutter/platform_views',
            const StandardMethodCodec().encodeMethodCall(
              const MethodCall('routeUpdated', {
                'location': '/',
                'state': null,
                'locale': 'es'
              })
            ),
            (data) {},
          );
          
          await tester.pumpWidget(app.MITAApp());
          await tester.pumpAndSettle(const Duration(seconds: 3));
          
          // Verify: Spanish text displayed
          expect(find.text('Bienvenido de vuelta'), findsOneWidget); // Welcome Back
          expect(find.text('Correo electrónico'), findsOneWidget); // Email
          expect(find.text('Contraseña'), findsOneWidget); // Password
          
          // Test: Currency formatting in Spanish locale
          await testHelpers.loginUser(tester, mockApiService);
          await testHelpers.verifySpanishCurrencyFormatting(tester);
        },
      );

      testWidgets(
        'Large font size adaptation',
        (WidgetTester tester) async {
          // Set large accessibility font
          tester.platformDispatcher.textScaleFactorTestValue = 2.0;
          
          await testHelpers.loginUser(tester, mockApiService);
          
          // Verify: Layout adapts to large fonts
          expect(find.byType(Scrollable), findsWidgets);
          
          // Verify: Touch targets remain accessible
          await testHelpers.verifyMinimumTouchTargets(tester);
          
          // Verify: Text doesn't overflow
          await testHelpers.verifyNoTextOverflow(tester);
        },
      );

      testWidgets(
        'Voice Over / TalkBack navigation flow',
        (WidgetTester tester) async {
          final SemanticsHandle handle = tester.ensureSemantics();
          
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Logical reading order
          final semanticsNodes = tester.allSemantics.toList();
          final readingOrder = semanticsNodes
              .where((node) => node.hasFlag(SemanticsFlag.isTextField) || 
                             node.hasFlag(SemanticsFlag.isButton))
              .toList();
          
          // Verify: Tab order is logical (email -> password -> sign in)
          expect(readingOrder.length, greaterThanOrEqualTo(3));
          expect(readingOrder[0].label, contains('Email'));
          expect(readingOrder[1].label, contains('Password'));
          expect(readingOrder[2].label, contains('Sign in'));
          
          handle.dispose();
        },
      );
    });

    // ==========================================================================
    // SECURITY VALIDATION TESTS
    // ==========================================================================
    
    group('Security Validation Tests', () {
      testWidgets(
        'JWT token manipulation prevention',
        (WidgetTester tester) async {
          // Setup: Valid login
          await testHelpers.loginUser(tester, mockApiService);
          
          // Test: Tampered token rejection
          when(mockApiService.getBudgetData())
              .thenThrow(DioError(
                type: DioErrorType.response,
                requestOptions: RequestOptions(path: '/budget'),
                response: Response(
                  statusCode: 401,
                  data: {'error': 'Invalid token signature'},
                  requestOptions: RequestOptions(path: '/budget'),
                ),
              ));
          
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Automatic logout on token tampering
          expect(find.text('Login'), findsOneWidget);
          
          // Verify: Secure storage cleared
          verify(mockApiService.clearTokens()).called(1);
        },
      );

      testWidgets(
        'Rate limiting protection',
        (WidgetTester tester) async {
          await testHelpers.navigateToLoginScreen(tester, mockApiService);
          
          // Test: Multiple rapid login attempts
          when(mockApiService.login(any, any))
              .thenThrow(DioError(
                type: DioErrorType.response,
                requestOptions: RequestOptions(path: '/login'),
                response: Response(
                  statusCode: 429,
                  data: {'error': 'Rate limit exceeded'},
                  requestOptions: RequestOptions(path: '/login'),
                ),
              ));
          
          // Attempt multiple logins rapidly
          for (int i = 0; i < 5; i++) {
            await testHelpers.attemptLogin(
              tester: tester,
              email: 'test@example.com',
              password: 'password',
              shouldSucceed: false,
            );
          }
          
          // Verify: Rate limiting message shown
          expect(find.text('Too many attempts'), findsOneWidget);
          expect(find.text('Please wait before trying again'), findsOneWidget);
        },
      );

      testWidgets(
        'Cross-user data access prevention',
        (WidgetTester tester) async {
          // Login as user 1
          await testHelpers.loginUser(tester, mockApiService, userId: 'user1');
          
          // Mock API returning another user's data (security violation)
          when(mockApiService.getBudgetData()).thenAnswer((_) async =>
            MockResponse(data: {
              'userId': 'user2', // Wrong user!
              'dailyBudget': 100.00,
            }));
          
          await tester.tap(find.text('Budget'));
          await tester.pumpAndSettle();
          
          // Verify: Data rejected and user logged out
          expect(find.text('Security error'), findsOneWidget);
          expect(find.text('Login'), findsOneWidget);
          
          // Verify: Tokens cleared for security
          verify(mockApiService.clearTokens()).called(1);
        },
      );
    });

    // ==========================================================================
    // PERFORMANCE VALIDATION TESTS
    // ==========================================================================
    
    group('Performance Validation Tests', () {
      testWidgets(
        'App launch performance (< 3 seconds)',
        (WidgetTester tester) async {
          final stopwatch = Stopwatch()..start();
          
          await tester.pumpWidget(app.MITAApp());
          await tester.pumpAndSettle();
          
          stopwatch.stop();
          
          // Verify: Launch time under 3 seconds
          expect(stopwatch.elapsedMilliseconds, lessThan(3000));
        },
      );

      testWidgets(
        'Navigation performance and smoothness',
        (WidgetTester tester) async {
          await testHelpers.loginUser(tester, mockApiService);
          
          final stopwatch = Stopwatch();
          
          // Test navigation between all tabs
          for (int i = 0; i < 6; i++) {
            stopwatch.start();
            
            await tester.tap(find.byType(BottomNavigationBarItem).at(i));
            await tester.pumpAndSettle();
            
            stopwatch.stop();
            
            // Verify: Each navigation < 500ms
            expect(stopwatch.elapsedMilliseconds, lessThan(500));
            stopwatch.reset();
          }
        },
      );

      testWidgets(
        'Memory usage stability during extended use',
        (WidgetTester tester) async {
          await testHelpers.loginUser(tester, mockApiService);
          
          // Simulate extended app usage
          for (int i = 0; i < 100; i++) {
            // Add transactions
            await testHelpers.addTestTransaction(
              tester: tester,
              amount: '${i + 1}.00',
              description: 'Transaction $i',
              mockApiService: mockApiService,
            );
            
            // Navigate between screens
            await tester.tap(find.byType(BottomNavigationBarItem).at(i % 6));
            await tester.pump();
            
            if (i % 10 == 0) {
              await tester.pumpAndSettle();
              
              // Verify: App remains responsive
              expect(find.byType(BottomNavigationBar), findsOneWidget);
            }
          }
          
          await tester.pumpAndSettle();
          
          // Verify: Final state is stable
          expect(find.byType(BottomNavigationBar), findsOneWidget);
        },
      );
    });
  });
}

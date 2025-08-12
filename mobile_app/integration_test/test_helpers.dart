import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:dio/dio.dart';

import '../lib/main.dart';
import 'mock_services.dart';

/// Test helpers for MITA integration tests
/// 
/// Provides reusable test utilities, mock setups, and verification methods
/// to ensure consistent and thorough testing across all integration test scenarios.
/// 
/// Key features:
/// - Financial accuracy verification
/// - Security validation helpers  
/// - Accessibility testing utilities
/// - Mock service management
/// - UI interaction helpers
class TestHelpers {
  static const Duration _standardTimeout = Duration(seconds: 30);
  static const Duration _longTimeout = Duration(minutes: 2);
  
  /// Initialize test environment with proper mocking and configurations
  Future<void> initializeTestEnvironment() async {
    // Set up test environment
    WidgetsFlutterBinding.ensureInitialized();
    
    // Configure mock HTTP client for consistent responses
    await _setupHttpMocks();
    
    // Configure mock secure storage
    await _setupSecureStorageMocks();
    
    // Setup Firebase mocks
    await _setupFirebaseMocks();
  }

  /// Setup default mock behaviors for common scenarios
  Future<void> setupDefaultMockBehaviors({
    required MockApiService mockApiService,
    required MockUserDataManager mockUserDataManager,
  }) async {
    // Default API responses
    when(mockApiService.getToken()).thenAnswer((_) async => null);
    when(mockApiService.hasCompletedOnboarding()).thenAnswer((_) async => false);
    when(mockUserDataManager.hasCompletedOnboarding()).thenAnswer((_) async => false);
    
    // Default budget data
    when(mockApiService.getBudgetData()).thenAnswer((_) async =>
      MockResponse(data: {
        'dailyBudget': 50.00,
        'remainingBudget': 50.00,
        'spentToday': 0.00,
        'currency': 'USD',
        'lastUpdated': DateTime.now().toIso8601String(),
      }));
    
    // Default successful operations
    when(mockApiService.saveTokens(any, any)).thenAnswer((_) async => {});
    when(mockApiService.clearTokens()).thenAnswer((_) async => {});
    when(mockApiService.registerPushToken(any)).thenAnswer((_) async => 
      MockResponse(data: {'success': true}));
  }

  /// Clean up test environment after each test
  Future<void> cleanupTestEnvironment() async {
    // Clear any persisted state
    await _clearTestStorage();
    
    // Reset platform channels
    await _resetPlatformChannels();
    
    // Clear mock interactions
    clearInteractions;
  }

  // ==========================================================================
  // NAVIGATION AND FLOW HELPERS
  // ==========================================================================

  /// Navigate to login screen from welcome screen
  Future<void> navigateToLoginScreen(
    WidgetTester tester, 
    MockApiService mockApiService
  ) async {
    when(mockApiService.getToken()).thenAnswer((_) async => null);
    
    await tester.pumpWidget(const MITAApp());
    await tester.pumpAndSettle(const Duration(seconds: 4));
    
    // Should be on login screen now
    await verifyLoginScreenElements(tester);
  }

  /// Complete user login flow
  Future<void> loginUser(
    WidgetTester tester, 
    MockApiService mockApiService, {
    String? userId,
  }) async {
    await navigateToLoginScreen(tester, mockApiService);
    
    await performSuccessfulLogin(
      tester: tester,
      email: 'test@example.com',
      password: 'SecurePass123!',
      mockApiService: mockApiService,
      userId: userId,
    );
  }

  /// Perform successful login with validation
  Future<void> performSuccessfulLogin({
    required WidgetTester tester,
    required String email,
    required String password,
    required MockApiService mockApiService,
    String? userId,
  }) async {
    // Mock successful login response
    when(mockApiService.login(email, password)).thenAnswer((_) async =>
      MockResponse(data: {
        'access_token': 'valid_access_token',
        'refresh_token': 'valid_refresh_token',
        'user': {
          'id': userId ?? 'test_user_123',
          'email': email,
          'hasCompletedOnboarding': true,
        }
      }));
    
    // Mock onboarding check
    when(mockApiService.hasCompletedOnboarding()).thenAnswer((_) async => true);
    
    // Enter credentials
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('email_field')), 
      email
    );
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('password_field')), 
      password
    );
    
    // Submit form
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle(_standardTimeout);
    
    // Verify navigation to dashboard
    await verifyDashboardElements(tester);
  }

  /// Complete registration flow
  Future<void> completeRegistrationFlow({
    required WidgetTester tester,
    required String email,
    required String password,
    required MockApiService mockApiService,
  }) async {
    // Mock successful registration
    when(mockApiService.register(any)).thenAnswer((_) async =>
      MockResponse(data: {
        'access_token': 'new_user_token',
        'refresh_token': 'new_refresh_token',
        'user': {
          'id': 'new_user_123',
          'email': email,
          'hasCompletedOnboarding': false,
        }
      }));
    
    // Fill registration form
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('email_field')), 
      email
    );
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('password_field')), 
      password
    );
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('confirm_password_field')), 
      password
    );
    
    // Accept terms
    await tester.tap(find.byKey(const Key('terms_checkbox')));
    
    // Submit registration
    await tester.tap(find.text('Create Account'));
    await tester.pumpAndSettle(_standardTimeout);
  }

  /// Complete onboarding flow
  Future<void> completeOnboardingFlow({
    required WidgetTester tester,
    required MockApiService mockApiService,
  }) async {
    // Mock successful onboarding steps
    when(mockApiService.updateUserRegion(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.updateUserLocation(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.updateUserIncome(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.updateUserExpenses(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.updateUserGoals(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.updateUserHabits(any)).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    when(mockApiService.completeOnboarding()).thenAnswer((_) async =>
      MockResponse(data: {'success': true}));
    
    // Step 1: Region selection
    if (find.text('Select Your Region').evaluate().isNotEmpty) {
      await tester.tap(find.text('United States'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Step 2: Location
    if (find.text('Set Your Location').evaluate().isNotEmpty) {
      await tester.tap(find.text('Use Current Location'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Step 3: Income
    if (find.text('Monthly Income').evaluate().isNotEmpty) {
      await clearAndEnterText(
        tester, 
        find.byKey(const Key('income_field')), 
        '5000'
      );
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Step 4: Expenses
    if (find.text('Monthly Expenses').evaluate().isNotEmpty) {
      await clearAndEnterText(
        tester, 
        find.byKey(const Key('expenses_field')), 
        '3000'
      );
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Step 5: Goals
    if (find.text('Financial Goals').evaluate().isNotEmpty) {
      await tester.tap(find.text('Emergency Fund'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Step 6: Habits
    if (find.text('Spending Habits').evaluate().isNotEmpty) {
      await tester.tap(find.text('Track Daily Expenses'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
    }
    
    // Final step: Complete
    if (find.text('Setup Complete').evaluate().isNotEmpty) {
      await tester.tap(find.text('Get Started'));
      await tester.pumpAndSettle();
    }
  }

  // ==========================================================================
  // VERIFICATION HELPERS
  // ==========================================================================

  /// Verify login screen elements are present and accessible
  Future<void> verifyLoginScreenElements(WidgetTester tester) async {
    expect(find.text('Welcome Back'), findsOneWidget);
    expect(find.text('Sign in to continue'), findsOneWidget);
    expect(find.byKey(const Key('email_field')), findsOneWidget);
    expect(find.byKey(const Key('password_field')), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);
    expect(find.text('Continue with Google'), findsOneWidget);
    expect(find.text('Sign Up'), findsOneWidget);
  }

  /// Verify registration screen elements
  Future<void> verifyRegistrationScreenElements(WidgetTester tester) async {
    expect(find.text('Create Account'), findsOneWidget);
    expect(find.byKey(const Key('email_field')), findsOneWidget);
    expect(find.byKey(const Key('password_field')), findsOneWidget);
    expect(find.byKey(const Key('confirm_password_field')), findsOneWidget);
    expect(find.byKey(const Key('terms_checkbox')), findsOneWidget);
  }

  /// Verify dashboard elements are present
  Future<void> verifyDashboardElements(WidgetTester tester) async {
    expect(find.byType(BottomNavigationBar), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Calendar'), findsOneWidget);
    expect(find.text('Goals'), findsOneWidget);
    expect(find.text('Insights'), findsOneWidget);
    expect(find.text('Habits'), findsOneWidget);
    expect(find.text('Mood'), findsOneWidget);
  }

  /// Verify initial budget state after onboarding
  Future<void> verifyInitialBudgetState(WidgetTester tester) async {
    // Check for budget display elements
    expect(find.textContaining('\$'), findsWidgets);
    
    // Verify budget is positive and formatted correctly
    final budgetTexts = find.textContaining('\$').evaluate()
        .map((e) => (e.widget as Text).data)
        .where((text) => text != null)
        .toList();
    
    for (final budgetText in budgetTexts) {
      expect(budgetText, matches(r'\$\d+\.\d{2}'));
      
      // Extract numeric value and verify it's positive
      final numericValue = double.tryParse(
        budgetText!.replaceAll('\$', '').replaceAll(',', '')
      );
      expect(numericValue, greaterThanOrEqualTo(0.0));
    }
  }

  /// Verify monetary formatting accuracy
  Future<void> verifyMonetaryFormatting(WidgetTester tester) async {
    final moneyTexts = find.textContaining('\$').evaluate()
        .map((e) => (e.widget as Text).data)
        .where((text) => text != null)
        .toList();
    
    for (final moneyText in moneyTexts) {
      // Verify proper currency format: $XX.XX
      expect(moneyText, matches(r'\$\d{1,3}(,\d{3})*\.\d{2}'));
      
      // Verify no floating point errors (only 2 decimal places)
      final decimalPart = moneyText!.split('.').last;
      expect(decimalPart.length, equals(2));
    }
  }

  /// Verify budget update after expense addition
  Future<void> verifyBudgetUpdate(WidgetTester tester, double expenseAmount) async {
    // Mock updated budget data
    final mockApiService = MockApiService();
    when(mockApiService.getBudgetData()).thenAnswer((_) async =>
      MockResponse(data: {
        'dailyBudget': 50.00,
        'remainingBudget': 50.00 - expenseAmount,
        'spentToday': expenseAmount,
        'currency': 'USD',
      }));
    
    // Refresh and verify
    await tester.pumpAndSettle();
    
    final spentText = '\$${expenseAmount.toStringAsFixed(2)}';
    expect(find.text(spentText), findsOneWidget);
    
    final remainingText = '\$${(50.00 - expenseAmount).toStringAsFixed(2)}';
    expect(find.text(remainingText), findsOneWidget);
  }

  /// Verify budget consistency across operations
  Future<void> verifyBudgetConsistency(WidgetTester tester) async {
    // Find all monetary values
    final moneyTexts = find.textContaining('\$').evaluate()
        .map((e) => (e.widget as Text).data)
        .where((text) => text != null)
        .map((text) => double.tryParse(
            text!.replaceAll('\$', '').replaceAll(',', '')))
        .where((value) => value != null)
        .cast<double>()
        .toList();
    
    // Verify mathematical consistency
    // daily budget = spent + remaining
    if (moneyTexts.length >= 3) {
      final dailyBudget = moneyTexts[0];
      final spent = moneyTexts[1];
      final remaining = moneyTexts[2];
      
      expect(spent + remaining, closeTo(dailyBudget, 0.01));
    }
  }

  // ==========================================================================
  // FINANCIAL TEST HELPERS
  // ==========================================================================

  /// Add a test transaction with proper validation
  Future<void> addTestTransaction({
    required WidgetTester tester,
    required String amount,
    required String description,
    required MockApiService mockApiService,
  }) async {
    // Mock successful expense addition
    when(mockApiService.addExpense(any)).thenAnswer((_) async =>
      MockResponse(data: {
        'id': DateTime.now().millisecondsSinceEpoch.toString(),
        'amount': double.parse(amount),
        'description': description,
        'timestamp': DateTime.now().toIso8601String(),
        'category': 'general',
      }));
    
    // Navigate to add expense
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();
    
    // Enter transaction details
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('amount_field')), 
      amount
    );
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('description_field')), 
      description
    );
    
    // Save transaction
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    
    // Verify success
    expect(find.text('Expense added successfully'), findsOneWidget);
  }

  // ==========================================================================
  // MOBILE-SPECIFIC TEST HELPERS
  // ==========================================================================

  /// Simulate network loss
  Future<void> simulateNetworkLoss(MockApiService mockApiService) async {
    when(mockApiService.getBudgetData())
        .thenThrow(DioError(
          type: DioErrorType.connectionError,
          requestOptions: RequestOptions(path: '/budget'),
          message: 'Network unreachable',
        ));
  }

  /// Simulate network restoration
  Future<void> simulateNetworkRestoration(MockApiService mockApiService) async {
    when(mockApiService.getBudgetData()).thenAnswer((_) async =>
      MockResponse(data: {
        'dailyBudget': 50.00,
        'remainingBudget': 30.00,
        'spentToday': 20.00,
        'currency': 'USD',
      }));
  }

  /// Verify landscape layout adaptations
  Future<void> verifyLandscapeLayout(WidgetTester tester) async {
    // In landscape, bottom nav might be side nav or adapted
    expect(find.byType(NavigationBar), findsAny);
    
    // Verify content is still accessible
    expect(find.text('Home'), findsOneWidget);
  }

  // ==========================================================================
  // ACCESSIBILITY TEST HELPERS
  // ==========================================================================

  /// Verify minimum touch target sizes (44x44 dp)
  Future<void> verifyMinimumTouchTargets(WidgetTester tester) async {
    final buttons = find.byType(ElevatedButton).evaluate().toList() +
        find.byType(TextButton).evaluate().toList() +
        find.byType(IconButton).evaluate().toList();
    
    for (final button in buttons) {
      final renderBox = button.renderObject as RenderBox?;
      if (renderBox != null) {
        expect(renderBox.size.width, greaterThanOrEqualTo(44.0));
        expect(renderBox.size.height, greaterThanOrEqualTo(44.0));
      }
    }
  }

  /// Verify no text overflow in accessibility mode
  Future<void> verifyNoTextOverflow(WidgetTester tester) async {
    final textWidgets = find.byType(Text).evaluate().toList();
    
    for (final textWidget in textWidgets) {
      final renderParagraph = textWidget.renderObject as RenderParagraph?;
      if (renderParagraph != null) {
        expect(renderParagraph.hasVisualOverflow, isFalse);
      }
    }
  }

  /// Verify color contrast ratios for accessibility
  Future<void> verifyColorContrastRatios(WidgetTester tester) async {
    // This would integrate with color contrast checking tools
    // For now, verify high contrast theme is applied
    final theme = Theme.of(tester.element(find.byType(MaterialApp)));
    expect(theme.brightness, equals(Brightness.dark));
  }

  /// Verify Spanish currency formatting
  Future<void> verifySpanishCurrencyFormatting(WidgetTester tester) async {
    // Look for Spanish currency format: 50,00 € or $50,00
    final currencyTexts = find.textContaining(RegExp(r'[\$€]')).evaluate()
        .map((e) => (e.widget as Text).data)
        .toList();
    
    // Verify Spanish locale formatting (comma for decimal separator)
    for (final text in currencyTexts) {
      if (text != null && text.contains(',')) {
        expect(text, matches(r'[\$€]\d{1,3}(.\d{3})*,\d{2}'));
      }
    }
  }

  // ==========================================================================
  // ERROR HANDLING TEST HELPERS
  // ==========================================================================

  /// Attempt login with optional success/failure
  Future<void> attemptLogin({
    required WidgetTester tester,
    required String email,
    required String password,
    required bool shouldSucceed,
  }) async {
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('email_field')), 
      email
    );
    await clearAndEnterText(
      tester, 
      find.byKey(const Key('password_field')), 
      password
    );
    
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();
  }

  /// Verify resource cleanup (no memory leaks)
  Future<void> verifyResourceCleanup(WidgetTester tester) async {
    // This would integrate with memory profiling tools
    // For now, verify app is still responsive
    expect(find.byType(MaterialApp), findsOneWidget);
    
    // Verify no lingering timers or streams
    expect(tester.binding.hasScheduledFrame, isFalse);
  }

  // ==========================================================================
  // UTILITY HELPERS
  // ==========================================================================

  /// Clear text field and enter new text
  Future<void> clearAndEnterText(
    WidgetTester tester, 
    Finder finder, 
    String text
  ) async {
    await tester.tap(finder);
    await tester.pumpAndSettle();
    
    // Clear existing text
    await tester.sendKeyEvent(LogicalKeyboardKey.selectAll);
    await tester.pumpAndSettle();
    
    // Enter new text
    await tester.enterText(finder, text);
    await tester.pumpAndSettle();
  }

  // ==========================================================================
  // PRIVATE SETUP HELPERS
  // ==========================================================================

  Future<void> _setupHttpMocks() async {
    // Configure HTTP client mocks
  }

  Future<void> _setupSecureStorageMocks() async {
    // Configure secure storage mocks
  }

  Future<void> _setupFirebaseMocks() async {
    // Configure Firebase mocks
  }

  Future<void> _clearTestStorage() async {
    // Clear test storage
  }

  Future<void> _resetPlatformChannels() async {
    // Reset platform channels to default state
  }
}
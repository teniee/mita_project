import 'package:mockito/mockito.dart';
import 'package:dio/dio.dart';
import '../lib/services/api_service.dart';
import '../lib/services/user_data_manager.dart';
import '../lib/services/accessibility_service.dart';
import '../lib/services/push_notification_service.dart';

/// Mock services for MITA integration testing
/// 
/// These mocks provide consistent, controlled responses for testing
/// critical financial operations, security features, and user flows.
/// 
/// All mocks are designed with financial safety in mind:
/// - Monetary values are always precise decimals
/// - Security validations are enforced
/// - Error scenarios are realistic
/// - Performance characteristics are maintained

// ==========================================================================
// MOCK RESPONSE CLASS
// ==========================================================================

/// Mock HTTP response for API calls
class MockResponse {
  final dynamic data;
  final int statusCode;
  final Map<String, dynamic> headers;

  MockResponse({
    required this.data,
    this.statusCode = 200,
    this.headers = const {},
  });

  T getData<T>() => data as T;
}

// ==========================================================================
// MOCK API SERVICE
// ==========================================================================

/// Mock API service for integration testing
class MockApiService extends Mock implements ApiService {
  
  // Authentication methods
  @override
  Future<String?> getToken() => (super.noSuchMethod(
    Invocation.method(#getToken, []),
    returnValue: Future<String?>.value(null),
  ) as Future<String?>);

  @override
  Future<void> saveTokens(String accessToken, String refreshToken) => 
    (super.noSuchMethod(
      Invocation.method(#saveTokens, [accessToken, refreshToken]),
      returnValue: Future<void>.value(),
    ) as Future<void>);

  @override
  Future<void> clearTokens() => (super.noSuchMethod(
    Invocation.method(#clearTokens, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);

  @override
  Future<bool> refreshTokens() => (super.noSuchMethod(
    Invocation.method(#refreshTokens, []),
    returnValue: Future<bool>.value(false),
  ) as Future<bool>);

  @override
  Future<MockResponse> login(String email, String password) => 
    (super.noSuchMethod(
      Invocation.method(#login, [email, password]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {
          'access_token': 'mock_access_token',
          'refresh_token': 'mock_refresh_token',
          'user': {
            'id': 'mock_user_123',
            'email': email,
            'hasCompletedOnboarding': true,
          }
        })
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> loginWithGoogle(String idToken) => 
    (super.noSuchMethod(
      Invocation.method(#loginWithGoogle, [idToken]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {
          'access_token': 'google_access_token',
          'refresh_token': 'google_refresh_token',
          'user': {
            'id': 'google_user_123',
            'email': 'user@gmail.com',
            'hasCompletedOnboarding': true,
          }
        })
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> register(Map<String, dynamic> userData) => 
    (super.noSuchMethod(
      Invocation.method(#register, [userData]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {
          'access_token': 'new_user_token',
          'refresh_token': 'new_refresh_token',
          'user': {
            'id': 'new_user_123',
            'email': userData['email'],
            'hasCompletedOnboarding': false,
          }
        })
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> requestPasswordReset(String email) => 
    (super.noSuchMethod(
      Invocation.method(#requestPasswordReset, [email]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true, 'message': 'Password reset email sent'})
      ),
    ) as Future<MockResponse>);

  // Onboarding methods
  @override
  Future<bool> hasCompletedOnboarding() => (super.noSuchMethod(
    Invocation.method(#hasCompletedOnboarding, []),
    returnValue: Future<bool>.value(false),
  ) as Future<bool>);

  @override
  Future<MockResponse> updateUserRegion(String region) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserRegion, [region]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateUserLocation(Map<String, dynamic> location) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserLocation, [location]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateUserIncome(double monthlyIncome) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserIncome, [monthlyIncome]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateUserExpenses(double monthlyExpenses) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserExpenses, [monthlyExpenses]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateUserGoals(List<String> goals) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserGoals, [goals]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateUserHabits(List<String> habits) => 
    (super.noSuchMethod(
      Invocation.method(#updateUserHabits, [habits]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> completeOnboarding() => 
    (super.noSuchMethod(
      Invocation.method(#completeOnboarding, []),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  // Financial data methods
  @override
  Future<MockResponse> getBudgetData() => (super.noSuchMethod(
    Invocation.method(#getBudgetData, []),
    returnValue: Future<MockResponse>.value(
      MockResponse(data: {
        'dailyBudget': 50.00,
        'remainingBudget': 50.00,
        'spentToday': 0.00,
        'currency': 'USD',
        'lastUpdated': DateTime.now().toIso8601String(),
        'weeklyLimit': 350.00,
        'monthlyLimit': 1500.00,
      })
    ),
  ) as Future<MockResponse>);

  @override
  Future<MockResponse> addExpense(Map<String, dynamic> expenseData) => 
    (super.noSuchMethod(
      Invocation.method(#addExpense, [expenseData]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {
          'id': DateTime.now().millisecondsSinceEpoch.toString(),
          'amount': expenseData['amount'],
          'description': expenseData['description'],
          'category': expenseData['category'] ?? 'general',
          'timestamp': DateTime.now().toIso8601String(),
          'budgetOverride': expenseData['budgetOverride'] ?? false,
        })
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updateExpense(String id, Map<String, dynamic> expenseData) => 
    (super.noSuchMethod(
      Invocation.method(#updateExpense, [id, expenseData]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {
          'id': id,
          'amount': expenseData['amount'],
          'description': expenseData['description'],
          'category': expenseData['category'] ?? 'general',
          'timestamp': DateTime.now().toIso8601String(),
        })
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> deleteExpense(String id) => 
    (super.noSuchMethod(
      Invocation.method(#deleteExpense, [id]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> getTransactionHistory({
    DateTime? startDate,
    DateTime? endDate,
    String? category,
    int? limit,
  }) => (super.noSuchMethod(
    Invocation.method(#getTransactionHistory, [], {
      #startDate: startDate,
      #endDate: endDate,
      #category: category,
      #limit: limit,
    }),
    returnValue: Future<MockResponse>.value(
      MockResponse(data: {
        'transactions': [
          {
            'id': '1',
            'amount': 15.50,
            'description': 'Coffee',
            'category': 'food',
            'timestamp': DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
          },
          {
            'id': '2',
            'amount': 25.00,
            'description': 'Lunch',
            'category': 'food',
            'timestamp': DateTime.now().subtract(const Duration(hours: 4)).toIso8601String(),
          },
        ],
        'total': 40.50,
        'count': 2,
      })
    ),
  ) as Future<MockResponse>);

  // Push notification methods
  @override
  Future<MockResponse> registerPushToken(String token) => 
    (super.noSuchMethod(
      Invocation.method(#registerPushToken, [token]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  @override
  Future<MockResponse> updatePushPreferences(Map<String, bool> preferences) => 
    (super.noSuchMethod(
      Invocation.method(#updatePushPreferences, [preferences]),
      returnValue: Future<MockResponse>.value(
        MockResponse(data: {'success': true})
      ),
    ) as Future<MockResponse>);

  // Analytics methods
  @override
  Future<MockResponse> getInsightsData() => (super.noSuchMethod(
    Invocation.method(#getInsightsData, []),
    returnValue: Future<MockResponse>.value(
      MockResponse(data: {
        'spendingByCategory': {
          'food': 150.75,
          'transportation': 45.20,
          'entertainment': 80.00,
          'shopping': 120.50,
        },
        'weeklyTrend': [
          {'week': '2024-01-01', 'amount': 89.50},
          {'week': '2024-01-08', 'amount': 95.20},
          {'week': '2024-01-15', 'amount': 102.75},
          {'week': '2024-01-22', 'amount': 87.30},
        ],
        'budgetEfficiency': 0.85,
        'savingsGoalProgress': 0.65,
      })
    ),
  ) as Future<MockResponse>);

  // Security validation methods  
  @override
  Future<bool> validateUserAccess(String userId) => (super.noSuchMethod(
    Invocation.method(#validateUserAccess, [userId]),
    returnValue: Future<bool>.value(true),
  ) as Future<bool>);

  @override
  Future<MockResponse> changePassword({
    required String currentPassword,
    required String newPassword,
  }) => (super.noSuchMethod(
    Invocation.method(#changePassword, [], {
      #currentPassword: currentPassword,
      #newPassword: newPassword,
    }),
    returnValue: Future<MockResponse>.value(
      MockResponse(data: {'success': true})
    ),
  ) as Future<MockResponse>);

  // Error simulation methods
  Future<void> simulateNetworkError() async {
    throw DioError(
      type: DioErrorType.connectionError,
      requestOptions: RequestOptions(path: '/test'),
      message: 'Network unreachable',
    );
  }

  Future<void> simulateServerError() async {
    throw DioError(
      type: DioErrorType.response,
      requestOptions: RequestOptions(path: '/test'),
      response: Response(
        statusCode: 500,
        data: {'error': 'Internal server error'},
        requestOptions: RequestOptions(path: '/test'),
      ),
    );
  }

  Future<void> simulateTimeoutError() async {
    throw DioError(
      type: DioErrorType.receiveTimeout,
      requestOptions: RequestOptions(path: '/test'),
      message: 'Request timeout',
    );
  }

  Future<void> simulateAuthError() async {
    throw DioError(
      type: DioErrorType.response,
      requestOptions: RequestOptions(path: '/test'),
      response: Response(
        statusCode: 401,
        data: {'error': 'Invalid or expired token'},
        requestOptions: RequestOptions(path: '/test'),
      ),
    );
  }
}

// ==========================================================================
// MOCK USER DATA MANAGER
// ==========================================================================

/// Mock user data manager for local data operations
class MockUserDataManager extends Mock implements UserDataManager {

  @override
  Future<void> initialize() => (super.noSuchMethod(
    Invocation.method(#initialize, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);

  @override
  Future<bool> hasCompletedOnboarding() => (super.noSuchMethod(
    Invocation.method(#hasCompletedOnboarding, []),
    returnValue: Future<bool>.value(false),
  ) as Future<bool>);

  @override
  Future<void> setOnboardingComplete() => (super.noSuchMethod(
    Invocation.method(#setOnboardingComplete, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);

  @override
  Future<Map<String, dynamic>?> getUserData() => (super.noSuchMethod(
    Invocation.method(#getUserData, []),
    returnValue: Future<Map<String, dynamic>?>.value({
      'id': 'mock_user_123',
      'email': 'test@example.com',
      'region': 'US',
      'monthlyIncome': 5000.00,
      'monthlyExpenses': 3000.00,
      'currency': 'USD',
    }),
  ) as Future<Map<String, dynamic>?>);

  @override
  Future<void> saveUserData(Map<String, dynamic> userData) => 
    (super.noSuchMethod(
      Invocation.method(#saveUserData, [userData]),
      returnValue: Future<void>.value(),
    ) as Future<void>);

  @override
  Future<void> clearUserData() => (super.noSuchMethod(
    Invocation.method(#clearUserData, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);

  @override
  Future<List<Map<String, dynamic>>> getCachedTransactions() => 
    (super.noSuchMethod(
      Invocation.method(#getCachedTransactions, []),
      returnValue: Future<List<Map<String, dynamic>>>.value([
        {
          'id': 'cached_1',
          'amount': 12.50,
          'description': 'Cached expense',
          'timestamp': DateTime.now().subtract(const Duration(hours: 1)).toIso8601String(),
        }
      ]),
    ) as Future<List<Map<String, dynamic>>>);

  @override
  Future<void> cacheTransaction(Map<String, dynamic> transaction) => 
    (super.noSuchMethod(
      Invocation.method(#cacheTransaction, [transaction]),
      returnValue: Future<void>.value(),
    ) as Future<void>);

  @override
  Future<void> clearCache() => (super.noSuchMethod(
    Invocation.method(#clearCache, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);
}

// ==========================================================================
// MOCK ACCESSIBILITY SERVICE
// ==========================================================================

/// Mock accessibility service for testing accessibility features
class MockAccessibilityService extends Mock implements AccessibilityService {

  @override
  Future<void> initialize() => (super.noSuchMethod(
    Invocation.method(#initialize, []),
    returnValue: Future<void>.value(),
  ) as Future<void>);

  @override
  void announceToScreenReader(
    String message, {
    String? financialContext,
    bool isImportant = false,
  }) => super.noSuchMethod(
    Invocation.method(#announceToScreenReader, [message], {
      #financialContext: financialContext,
      #isImportant: isImportant,
    }),
  );

  @override
  void announceNavigation(
    String screenName, {
    String? description,
  }) => super.noSuchMethod(
    Invocation.method(#announceNavigation, [screenName], {
      #description: description,
    }),
  );

  @override
  void announceFormErrors(List<String> errors) => super.noSuchMethod(
    Invocation.method(#announceFormErrors, [errors]),
  );

  @override
  String createButtonSemanticLabel({
    required String action,
    String? context,
    bool isDisabled = false,
  }) => (super.noSuchMethod(
    Invocation.method(#createButtonSemanticLabel, [], {
      #action: action,
      #context: context,
      #isDisabled: isDisabled,
    }),
    returnValue: isDisabled 
      ? '$action (disabled)${context != null ? '. $context' : ''}'
      : '$action${context != null ? '. $context' : ''}',
  ) as String);

  @override
  String createTextFieldSemanticLabel({
    required String label,
    bool isRequired = false,
    String? helperText,
  }) => (super.noSuchMethod(
    Invocation.method(#createTextFieldSemanticLabel, [], {
      #label: label,
      #isRequired: isRequired,
      #helperText: helperText,
    }),
    returnValue: '$label${isRequired ? ', required field' : ''}${helperText != null ? '. $helperText' : ''}',
  ) as String);

  @override
  Duration getAnimationDuration(Duration originalDuration) => 
    (super.noSuchMethod(
      Invocation.method(#getAnimationDuration, [originalDuration]),
      returnValue: originalDuration,
    ) as Duration);

  @override
  bool get isHighContrastEnabled => (super.noSuchMethod(
    Invocation.getter(#isHighContrastEnabled),
    returnValue: false,
  ) as bool);

  @override
  bool get isScreenReaderEnabled => (super.noSuchMethod(
    Invocation.getter(#isScreenReaderEnabled),
    returnValue: false,
  ) as bool);

  @override
  double get textScaleFactor => (super.noSuchMethod(
    Invocation.getter(#textScaleFactor),
    returnValue: 1.0,
  ) as double);
}

// ==========================================================================
// MOCK EXTENSIONS
// ==========================================================================

/// Extension to add minimum touch target wrapper
extension MockWidgetTesting on Widget {
  Widget withMinimumTouchTarget() {
    return Container(
      constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
      child: this,
    );
  }
}
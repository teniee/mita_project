import 'package:flutter/foundation.dart';
import '../services/user_data_manager.dart';
import '../services/logging_service.dart';
import '../services/token_lifecycle_manager.dart';
import '../services/iap_service.dart';
import '../services/api_service.dart';

/// User state enum for tracking authentication and data loading states
enum UserState {
  initial,
  loading,
  authenticated,
  unauthenticated,
  error,
}

/// Centralized user state management provider
/// Manages user authentication state, profile data, and financial context
class UserProvider extends ChangeNotifier {
  final UserDataManager _userDataManager = UserDataManager.instance;
  final IapService _iapService = IapService();
  final ApiService _apiService = ApiService();

  // State
  UserState _state = UserState.initial;
  Map<String, dynamic> _userProfile = {};
  Map<String, dynamic> _financialContext = {};
  String? _errorMessage;
  bool _isLoading = false;
  bool _hasCompletedOnboarding = false;
  String? _referralCode;
  bool _isLoadingReferral = false;

  // Getters
  UserState get state => _state;
  Map<String, dynamic> get userProfile => _userProfile;
  Map<String, dynamic> get financialContext => _financialContext;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get hasCompletedOnboarding => _hasCompletedOnboarding;
  bool get isAuthenticated => _state == UserState.authenticated;
  String? get referralCode => _referralCode;
  bool get isLoadingReferral => _isLoadingReferral;

  // User profile convenience getters
  String get userName => _userProfile['name'] as String? ?? 'User';
  String get userEmail => _userProfile['email'] as String? ?? '';
  double get userIncome {
    final incomeData = _userProfile['income'];
    return (incomeData == null)
        ? 0.0
        : (incomeData is num)
            ? incomeData.toDouble()
            : (incomeData is String ? double.tryParse(incomeData) ?? 0.0 : 0.0);
  }
  String get userCurrency => _userProfile['currency'] as String? ?? 'USD';
  String get userRegion => _userProfile['region'] as String? ?? '';
  String get userCountryCode => _userProfile['countryCode'] as String? ?? '';
  List<dynamic> get userExpenses {
    final expenses = _userProfile['expenses'];
    if (expenses is List) return expenses;
    return [];
  }
  List<dynamic> get userGoals {
    final goals = _userProfile['goals'];
    if (goals is List) return goals;
    return [];
  }
  List<dynamic> get userHabits {
    final habits = _userProfile['habits'];
    if (habits is List) return habits;
    return [];
  }

  /// Initialize the provider and load user data
  Future<void> initialize() async {
    if (_state != UserState.initial) return;

    _setLoading(true);
    _state = UserState.loading;
    notifyListeners();

    try {
      logInfo('Initializing UserProvider', tag: 'USER_PROVIDER');

      // CRITICAL FIX: Check if user has a valid token before making API calls
      final token = await _apiService.getToken();
      if (token == null || token.isEmpty) {
        logWarning('No authentication token found - user must login first',
            tag: 'USER_PROVIDER');
        _state = UserState.unauthenticated;
        _errorMessage = 'Not authenticated';
        return;
      }

      // Initialize the underlying user data manager
      await _userDataManager.initialize();

      // Load user profile
      await loadUserProfile();

      // Check onboarding status
      _hasCompletedOnboarding = await _userDataManager.hasCompletedOnboarding();

      // Load financial context
      await loadFinancialContext();

      _state = UserState.authenticated;
      logInfo('UserProvider initialized successfully', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to initialize UserProvider: $e', tag: 'USER_PROVIDER');
      _errorMessage = e.toString();
      _state = UserState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load user profile from cache or API
  Future<void> loadUserProfile() async {
    try {
      _setLoading(true);

      final profile = await _userDataManager.getUserProfile();
      _userProfile = profile;

      logInfo('User profile loaded: ${profile['name']}', tag: 'USER_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Failed to load user profile: $e', tag: 'USER_PROVIDER');
      _errorMessage = 'Failed to load user profile';
    } finally {
      _setLoading(false);
    }
  }

  /// Load financial context for budget calculations
  Future<void> loadFinancialContext() async {
    try {
      final context = await _userDataManager.getFinancialContext();
      _financialContext = context;

      // Check if onboarding is needed
      if (context['needs_onboarding'] == true) {
        _hasCompletedOnboarding = false;
      }

      logInfo('Financial context loaded', tag: 'USER_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Failed to load financial context: $e', tag: 'USER_PROVIDER');
    }
  }

  /// Update user profile
  Future<bool> updateUserProfile(Map<String, dynamic> profileData) async {
    try {
      _setLoading(true);

      final success = await _userDataManager.updateUserProfile(profileData);

      if (success) {
        // Merge updates into local state
        _userProfile = {..._userProfile, ...profileData};
        logInfo('User profile updated successfully', tag: 'USER_PROVIDER');
        notifyListeners();
      }

      return success;
    } catch (e) {
      logError('Failed to update user profile: $e', tag: 'USER_PROVIDER');
      _errorMessage = 'Failed to update profile';
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Cache onboarding data after completion
  Future<void> cacheOnboardingData(Map<String, dynamic> onboardingData) async {
    try {
      await _userDataManager.cacheOnboardingData(onboardingData);
      _hasCompletedOnboarding = true;

      // Refresh profile and financial context
      await loadUserProfile();
      await loadFinancialContext();

      logInfo('Onboarding data cached and user state updated',
          tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to cache onboarding data: $e', tag: 'USER_PROVIDER');
      rethrow;
    }
  }

  /// Refresh all user data from API
  Future<void> refreshUserData() async {
    try {
      _setLoading(true);

      await _userDataManager.refreshUserData();
      await loadUserProfile();
      await loadFinancialContext();

      logInfo('User data refreshed successfully', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to refresh user data: $e', tag: 'USER_PROVIDER');
      _errorMessage = 'Failed to refresh user data';
    } finally {
      _setLoading(false);
    }
  }

  /// Load referral code from API
  Future<void> loadReferralCode() async {
    if (_isLoadingReferral) return;

    try {
      _isLoadingReferral = true;
      notifyListeners();

      final code = await _apiService.getReferralCode();
      _referralCode = code;

      logInfo('Referral code loaded successfully', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to load referral code: $e', tag: 'USER_PROVIDER');
      _errorMessage = 'Failed to load referral code';
    } finally {
      _isLoadingReferral = false;
      notifyListeners();
    }
  }

  /// Clear user data (logout)
  Future<void> logout() async {
    try {
      _setLoading(true);

      await _userDataManager.clearUserData();

      // Reset state
      _userProfile = {};
      _financialContext = {};
      _hasCompletedOnboarding = false;
      _referralCode = null;
      _state = UserState.unauthenticated;

      logInfo('User logged out successfully', tag: 'USER_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Failed to logout: $e', tag: 'USER_PROVIDER');
      _errorMessage = 'Failed to logout';
    } finally {
      _setLoading(false);
    }
  }

  /// Set authentication state after login and start token lifecycle management
  Future<void> setAuthenticated() async {
    _state = UserState.authenticated;
    notifyListeners();

    // Initialize token lifecycle manager for automatic token refresh
    try {
      await TokenLifecycleManager.instance.initialize();
      logInfo('Token lifecycle manager started', tag: 'USER_PROVIDER');
    } catch (e) {
      logWarning('Failed to start token lifecycle manager: $e',
          tag: 'USER_PROVIDER');
      // Non-critical error - user can still use the app
    }
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  // IAP Methods

  /// Initialize IAP service
  Future<void> initializeIap() async {
    try {
      await _iapService.initialize();
      logInfo('IAP service initialized', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to initialize IAP service: $e', tag: 'USER_PROVIDER');
      rethrow;
    }
  }

  /// Purchase premium subscription
  Future<void> buyPremium({String productId = 'premium'}) async {
    try {
      logInfo('Starting premium purchase', tag: 'USER_PROVIDER');
      await _iapService.buyPremium(productId: productId);
      logInfo('Premium purchase completed', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Premium purchase failed: $e', tag: 'USER_PROVIDER');
      rethrow;
    }
  }

  /// Restore previous purchases
  Future<void> restorePurchases() async {
    try {
      logInfo('Restoring purchases', tag: 'USER_PROVIDER');
      await _iapService.restorePurchases();
      logInfo('Purchases restored', tag: 'USER_PROVIDER');
    } catch (e) {
      logError('Failed to restore purchases: $e', tag: 'USER_PROVIDER');
      rethrow;
    }
  }

  /// Check if user has premium subscription
  Future<bool> isPremiumUser() async {
    try {
      return await _iapService.isPremiumUser();
    } catch (e) {
      logError('Failed to check premium status: $e', tag: 'USER_PROVIDER');
      return false;
    }
  }

  /// Get subscription information
  Future<SubscriptionInfo?> getSubscriptionInfo() async {
    try {
      return await _iapService.getSubscriptionInfo();
    } catch (e) {
      logError('Failed to get subscription info: $e', tag: 'USER_PROVIDER');
      return null;
    }
  }

  /// Get premium status stream for reactive updates
  /// TEMPORARILY DISABLED: Stream exposure causes MultiProvider render tree violation
  /// TODO: Migrate to StreamProvider if stream functionality is needed
  /// Original: Stream<bool> get premiumStatusStream => _iapService.premiumStatusStream;
  // Stream<bool> get premiumStatusStream => _iapService.premiumStatusStream;
}

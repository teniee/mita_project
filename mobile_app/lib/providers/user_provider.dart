import 'package:flutter/foundation.dart';
import '../services/user_data_manager.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

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
  final ApiService _apiService = ApiService();

  // State
  UserState _state = UserState.initial;
  Map<String, dynamic> _userProfile = {};
  Map<String, dynamic> _financialContext = {};
  String? _errorMessage;
  bool _isLoading = false;
  bool _hasCompletedOnboarding = false;

  // Getters
  UserState get state => _state;
  Map<String, dynamic> get userProfile => _userProfile;
  Map<String, dynamic> get financialContext => _financialContext;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get hasCompletedOnboarding => _hasCompletedOnboarding;
  bool get isAuthenticated => _state == UserState.authenticated;

  // User profile convenience getters
  String get userName => _userProfile['name'] as String? ?? 'User';
  String get userEmail => _userProfile['email'] as String? ?? '';
  double get userIncome => (_userProfile['income'] as num?)?.toDouble() ?? 0.0;
  String get userCurrency => _userProfile['currency'] as String? ?? 'USD';
  String get userRegion => _userProfile['region'] as String? ?? '';
  String get userCountryCode => _userProfile['countryCode'] as String? ?? '';
  List<dynamic> get userExpenses => _userProfile['expenses'] as List<dynamic>? ?? [];
  List<dynamic> get userGoals => _userProfile['goals'] as List<dynamic>? ?? [];
  List<dynamic> get userHabits => _userProfile['habits'] as List<dynamic>? ?? [];

  /// Initialize the provider and load user data
  Future<void> initialize() async {
    if (_state != UserState.initial) return;

    _setLoading(true);
    _state = UserState.loading;
    notifyListeners();

    try {
      logInfo('Initializing UserProvider', tag: 'USER_PROVIDER');

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

      logInfo('Onboarding data cached and user state updated', tag: 'USER_PROVIDER');
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

  /// Clear user data (logout)
  Future<void> logout() async {
    try {
      _setLoading(true);

      await _userDataManager.clearUserData();

      // Reset state
      _userProfile = {};
      _financialContext = {};
      _hasCompletedOnboarding = false;
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

  /// Set authentication state after login
  void setAuthenticated() {
    _state = UserState.authenticated;
    notifyListeners();
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
}

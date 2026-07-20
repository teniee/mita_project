import 'dart:convert';
import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../utils/json_utils.dart';
import 'logging_service.dart';
import 'api_service.dart';

/// Production-level user data state management system
/// Handles user data flow from onboarding through entire app lifecycle
class UserDataManager {
  static UserDataManager? _instance;
  static UserDataManager get instance =>
      _instance ??= UserDataManager._internal();

  UserDataManager._internal();

  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();
  final ApiService _apiService = ApiService();

  // In-memory cache for fast access
  Map<String, dynamic>? _cachedUserProfile;
  Map<String, dynamic>? _cachedOnboardingData;
  DateTime? _lastRefresh;

  // Cache expiry duration
  static const Duration _cacheExpiry = Duration(hours: 2);

  /// Initialize user data manager with fresh data load
  Future<void> initialize() async {
    try {
      logInfo('Initializing UserDataManager', tag: 'USER_DATA_MANAGER');

      // Try to load cached data first for immediate UI response
      await _loadCachedData();

      // CRITICAL FIX: AWAIT the refresh to ensure data is loaded before proceeding
      // This prevents race conditions and redundant API calls in UserProvider
      try {
        await refreshUserData();
      } catch (e) {
        logWarning('API refresh failed (will use cached data if available): $e',
            tag: 'USER_DATA_MANAGER');
        // Non-fatal for new users - they'll complete onboarding next
      }
    } catch (e) {
      logError('Failed to initialize UserDataManager: $e',
          tag: 'USER_DATA_MANAGER');
    }
  }

  /// Get user profile with intelligent fallback strategy
  Future<Map<String, dynamic>> getUserProfile() async {
    try {
      // Return cached data if available and fresh
      if (_cachedUserProfile != null && _isCacheFresh()) {
        return _cachedUserProfile!;
      }

      // Try to refresh from API with gentle error handling
      final profile = await _apiService.getUserProfile().timeout(
        const Duration(seconds: 8), // Увеличиваем timeout для stability
        onTimeout: () {
          logWarning('getUserProfile timeout - using cached data',
              tag: 'USER_DATA_MANAGER');
          return <String, dynamic>{};
        },
      ).catchError((Object error) {
        logWarning('getUserProfile error - using cached data: $error',
            tag: 'USER_DATA_MANAGER');
        return <String, dynamic>{};
      });

      if (profile.isNotEmpty && profile.containsKey('data')) {
        final userData = profile['data'] as Map<String, dynamic>;
        _cachedUserProfile = userData;
        _lastRefresh = DateTime.now();
        await _saveCachedData();
        return userData;
      }

      // Fall back to cached data if available
      if (_cachedUserProfile != null) {
        logWarning('Using cached user profile due to API failure',
            tag: 'USER_DATA_MANAGER');
        return _cachedUserProfile!;
      }

      // Fall back to default user profile
      logWarning('Using default user profile', tag: 'USER_DATA_MANAGER');
      return _getDefaultUserProfile();
    } catch (e) {
      logError('Failed to get user profile: $e', tag: 'USER_DATA_MANAGER');
      return _cachedUserProfile ?? _getDefaultUserProfile();
    }
  }

  /// Update user profile both locally and on backend
  Future<bool> updateUserProfile(Map<String, dynamic> profileData) async {
    try {
      logInfo('Updating user profile', tag: 'USER_DATA_MANAGER');

      // Optimistic update - update local cache immediately
      _cachedUserProfile = profileData;
      _lastRefresh = DateTime.now();
      await _saveCachedData();

      // Try to sync with backend
      await _apiService.updateUserProfile(profileData).timeout(
            const Duration(seconds: 10),
            onTimeout: () => throw Exception('Profile update timeout'),
          );

      logInfo('Profile update successful', tag: 'USER_DATA_MANAGER');
      return true;
    } catch (e) {
      logError('Failed to update profile on backend: $e',
          tag: 'USER_DATA_MANAGER');

      // The optimistic write above is NOT confirmed server truth. Invalidate
      // freshness (memory + persisted timestamp) so it can't masquerade as a
      // fresh profile: the next getUserProfile() must re-fetch and replace it
      // with server truth rather than short-circuit on the 2h TTL. Keeping the
      // local edit for display is fine; treating it as authoritative is not.
      _lastRefresh = null;
      try {
        await _secureStorage.delete(key: 'cache_timestamp');
      } catch (_) {}
      logWarning(
          'Profile updated locally only - marked stale for server re-sync',
          tag: 'USER_DATA_MANAGER');
      return false;
    }
  }

  /// Save onboarding data for immediate use after completion
  Future<void> cacheOnboardingData(Map<String, dynamic> onboardingData) async {
    try {
      logInfo(
          'CRITICAL DEBUG: Starting to cache onboarding data: $onboardingData',
          tag: 'USER_DATA_MANAGER');

      _cachedOnboardingData = onboardingData;
      logInfo('CRITICAL DEBUG: Set _cachedOnboardingData in memory',
          tag: 'USER_DATA_MANAGER');

      // Transform onboarding data to user profile format
      _cachedUserProfile = _transformOnboardingToProfile(onboardingData);
      _lastRefresh = DateTime.now();
      logInfo('CRITICAL DEBUG: Transformed data and set timestamp',
          tag: 'USER_DATA_MANAGER');

      await _saveCachedData();
      logInfo('CRITICAL DEBUG: Called _saveCachedData()',
          tag: 'USER_DATA_MANAGER');

      // VERIFY IT ACTUALLY WORKED
      final verifyCache = hasCachedOnboardingData();
      logInfo('CRITICAL DEBUG: Verification after save: $verifyCache',
          tag: 'USER_DATA_MANAGER');

      logInfo('CRITICAL DEBUG: Onboarding data cached successfully',
          tag: 'USER_DATA_MANAGER');
    } catch (e) {
      logError('CRITICAL DEBUG: Failed to cache onboarding data: $e',
          tag: 'USER_DATA_MANAGER');
      rethrow;
    }
  }

  /// Check if we have cached onboarding data (non-recursive)
  bool hasCachedOnboardingData() {
    final result = _cachedOnboardingData != null;
    logInfo(
        'CRITICAL DEBUG: hasCachedOnboardingData() called, result: $result, data: $_cachedOnboardingData',
        tag: 'USER_DATA_MANAGER');
    return result;
  }

  /// Get raw cached onboarding data for calendar generation
  /// Returns null if no cached data available
  Map<String, dynamic>? getCachedOnboardingData() {
    return _cachedOnboardingData;
  }

  /// Check if user has completed onboarding
  Future<bool> hasCompletedOnboarding() async {
    try {
      // Check if we have cached onboarding data
      if (_cachedOnboardingData != null) {
        return true;
      }

      // Check via API
      return await _apiService.hasCompletedOnboarding();
    } catch (e) {
      logError('Failed to check onboarding status: $e',
          tag: 'USER_DATA_MANAGER');
      return false;
    }
  }

  /// Force refresh user data from API
  Future<void> refreshUserData() async {
    try {
      logInfo('Force refreshing user data', tag: 'USER_DATA_MANAGER');

      // forceRefresh bypasses ApiService's own /users/me TTL cache —
      // without it a "force refresh" could serve the same stale profile
      // this call is trying to replace.
      final profile = await _apiService.getUserProfile(forceRefresh: true);

      if (profile.isNotEmpty && profile.containsKey('data')) {
        _cachedUserProfile = profile['data'] as Map<String, dynamic>;
        _lastRefresh = DateTime.now();
        await _saveCachedData();

        logInfo('User data refreshed successfully', tag: 'USER_DATA_MANAGER');
      }
    } catch (e) {
      logError('Failed to refresh user data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  /// Clear all cached user data (for logout)
  Future<void> clearUserData() async {
    try {
      logInfo('Clearing user data', tag: 'USER_DATA_MANAGER');

      _cachedUserProfile = null;
      _cachedOnboardingData = null;
      _lastRefresh = null;

      await _secureStorage.delete(key: 'cached_user_profile');
      await _secureStorage.delete(key: 'cached_onboarding_data');
      await _secureStorage.delete(key: 'cache_timestamp');

      logInfo('User data cleared successfully', tag: 'USER_DATA_MANAGER');
    } catch (e) {
      logError('Failed to clear user data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  /// Get user's financial context for budget calculations
  Future<Map<String, dynamic>> getFinancialContext() async {
    try {
      // Server truth first. The transformed onboarding payload is only a
      // stopgap for the window between submit and the profile reflecting
      // it — the old order returned it FOREVER (it persists in secure
      // storage), so the app never picked up the real profile again until
      // logout.
      final profile = await getUserProfile();
      logInfo('Retrieved user profile for financial context: $profile',
          tag: 'USER_DATA_MANAGER');

      // Check if profile has required financial data
      final income = (profile['income'] as num?)?.toDouble();

      if ((income == null || income <= 0) && _cachedOnboardingData != null) {
        logInfo(
            'Profile has no income yet - using cached onboarding data for financial context',
            tag: 'USER_DATA_MANAGER');
        return _transformOnboardingToFinancialContext(_cachedOnboardingData!);
      }

      if (income == null || income <= 0) {
        // Check onboarding status to determine if user needs to complete onboarding
        final hasCompleted = await hasCompletedOnboarding();

        if (!hasCompleted) {
          logInfo(
              'User has not completed onboarding - returning incomplete context',
              tag: 'USER_DATA_MANAGER');
          return {
            'incomplete_onboarding': true,
            'needs_onboarding': true,
            'income': 0.0,
            'expenses': <dynamic>[],
            'goals': <String>[],
            'habits': <String>[],
            'region': '',
            'countryCode': '',
            'stateCode': '',
            'currency': 'USD',
          };
        } else {
          // User completed onboarding but data is missing from profile - API issue
          logWarning(
              'User completed onboarding but profile missing income data',
              tag: 'USER_DATA_MANAGER');
          return {
            'api_error': true,
            'incomplete_onboarding': false,
            'needs_onboarding': false,
            'income': 0.0,
            'expenses': <dynamic>[],
            'goals': <String>[],
            'habits': <String>[],
            'region': '',
            'countryCode': '',
            'stateCode': '',
            'currency': 'USD',
          };
        }
      }

      // Profile has valid income data - return complete financial context
      // Defensive type checking to handle both Map and List formats
      final expenses = profile['expenses'];
      final goals = profile['goals'];
      final habits = profile['habits'];

      return {
        'income': income,
        'expenses': expenses is List ? expenses : <dynamic>[],
        'goals':
            goals is List ? goals : (goals is Map ? <dynamic>[goals] : <dynamic>['budgeting']),
        'habits': habits is List ? habits : <dynamic>[],
        'region': profile['region'] as String? ?? '',
        'countryCode': profile['countryCode'] as String? ?? '',
        'stateCode': profile['stateCode'] as String? ?? '',
        'incomeTier': profile['incomeTier'] as String? ?? 'middle',
        'currency': profile['currency'] as String? ?? 'USD',
        'budgetMethod': profile['budgetMethod'] as String? ?? '50/30/20 Rule',
        'incomplete_onboarding': false,
        'needs_onboarding': false,
      };
    } catch (e) {
      logError('Error getting financial context: $e', tag: 'USER_DATA_MANAGER');

      // Return error context to indicate API failure
      return {
        'api_error': true,
        'error_message': e.toString(),
        'incomplete_onboarding': false,
        'needs_onboarding': false,
        'income': 0.0,
        'expenses': <dynamic>[],
        'goals': <dynamic>[],
        'habits': <dynamic>[],
        'region': '',
        'countryCode': '',
        'stateCode': '',
        'currency': 'USD',
      };
    }
  }

  // Private helper methods

  bool _isCacheFresh() {
    if (_lastRefresh == null) return false;
    return DateTime.now().difference(_lastRefresh!) < _cacheExpiry;
  }

  /// A cached profile is only usable if it isn't the synthetic placeholder
  /// produced by [_getDefaultUserProfile] (or empty). Persisting/serving that
  /// placeholder poisoned the dashboard with a fake "MITA User" / income 0
  /// state that survived restarts.
  @visibleForTesting
  static bool isUsableCachedProfile(Map<String, dynamic> profile) {
    if (profile.isEmpty) return false;
    if (profile['email'] == 'user@mita.finance') return false;
    return true;
  }

  Future<void> _loadCachedData() async {
    try {
      final profileData = await _secureStorage.read(key: 'cached_user_profile');
      final onboardingData =
          await _secureStorage.read(key: 'cached_onboarding_data');
      final timestampData = await _secureStorage.read(key: 'cache_timestamp');

      if (profileData != null) {
        final decoded = jsonDecode(profileData) as Map<String, dynamic>;
        if (isUsableCachedProfile(decoded)) {
          _cachedUserProfile = decoded;
        } else {
          // A synthetic/placeholder profile must never survive a restart as if
          // it were real — clear it so the app re-fetches server truth.
          logWarning(
              'Discarding invalid cached profile on load (placeholder/empty)',
              tag: 'USER_DATA_MANAGER');
          await _secureStorage.delete(key: 'cached_user_profile');
          await _secureStorage.delete(key: 'cache_timestamp');
        }
      }

      if (onboardingData != null) {
        _cachedOnboardingData =
            jsonDecode(onboardingData) as Map<String, dynamic>;
      }

      if (timestampData != null) {
        _lastRefresh =
            DateTime.fromMillisecondsSinceEpoch(int.parse(timestampData));
      }

      logInfo('Cached data loaded successfully', tag: 'USER_DATA_MANAGER');
    } catch (e) {
      logError('Failed to load cached data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  Future<void> _saveCachedData() async {
    try {
      if (_cachedUserProfile != null) {
        await _secureStorage.write(
          key: 'cached_user_profile',
          value: jsonEncode(_cachedUserProfile!),
        );
      }

      if (_cachedOnboardingData != null) {
        await _secureStorage.write(
          key: 'cached_onboarding_data',
          value: jsonEncode(_cachedOnboardingData!),
        );
      }

      if (_lastRefresh != null) {
        await _secureStorage.write(
          key: 'cache_timestamp',
          value: _lastRefresh!.millisecondsSinceEpoch.toString(),
        );
      }
    } catch (e) {
      logError('Failed to save cached data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  /// Numeric monthly income from either the onboarding payload shape
  /// ({'monthly_income': 6000, 'additional_income': 0}) or a flat number.
  ///
  /// The onboarding submit body nests income in a map; storing that map as
  /// `income` made every consumer's safe numeric cast produce 0.0, so a
  /// freshly onboarded user saw "Complete your profile" and an empty
  /// dashboard until logout.
  @visibleForTesting
  static double monthlyIncomeFrom(dynamic income) {
    if (income is Map) {
      return asDouble(asStringKeyedMap(income)['monthly_income']);
    }
    return asDouble(income);
  }

  Map<String, dynamic> _transformOnboardingToProfile(
      Map<String, dynamic> onboardingData) {
    final income = onboardingData['income'];
    if (income == null) {
      throw ArgumentError('Income is required in onboarding data');
    }

    return {
      'income': monthlyIncomeFrom(income),
      'expenses': onboardingData['expenses'] ?? <dynamic>[],
      'goals': onboardingData['goals'] ?? ['budgeting'],
      'habits': onboardingData['habits'] ?? <dynamic>[],
      'region': onboardingData['region'] ?? 'United States',
      'countryCode': onboardingData['countryCode'] ?? 'US',
      'stateCode': onboardingData['stateCode'] ?? 'CA',
      'incomeTier': onboardingData['incomeTier'] ?? 'middle',
      'currency': 'USD',
      'budgetMethod': '50/30/20 Rule',
      'name': 'MITA User',
      'email': 'user@mita.finance',
      'member_since': DateTime.now().toIso8601String(),
      'profile_completion': 100,
      'verified_email': true,
      'dark_mode': false,
      'notifications': true,
    };
  }

  /// Transform onboarding data directly to financial context format
  Map<String, dynamic> _transformOnboardingToFinancialContext(
      Map<String, dynamic> onboardingData) {
    final income = onboardingData['income'];
    if (income == null) {
      throw ArgumentError('Income is required in onboarding data');
    }

    return {
      'income': monthlyIncomeFrom(income),
      'expenses': onboardingData['expenses'] ?? <dynamic>[],
      'goals': onboardingData['goals'] ?? ['budgeting'],
      'habits': onboardingData['habits'] ?? <dynamic>[],
      'region': onboardingData['region'] ?? '',
      'countryCode': onboardingData['countryCode'] ?? '',
      'stateCode': onboardingData['stateCode'] ?? '',
      'incomeTier': onboardingData['incomeTier'] ?? 'middle',
      'currency': 'USD',
      'budgetMethod': '50/30/20 Rule',
      'incomplete_onboarding': false,
      'needs_onboarding': false,
    };
  }

  Map<String, dynamic> _getDefaultUserProfile() {
    logWarning(
        'CRITICAL DEBUG: Using default user profile - this means onboarding data is not available',
        tag: 'USER_DATA_MANAGER');

    // Return a safe default profile instead of throwing
    // This prevents crashes but indicates incomplete onboarding
    return {
      'name': 'MITA User',
      'email': 'user@mita.finance',
      'income': 0.0, // This will trigger onboarding flow in financial context
      'expenses': <dynamic>[],
      'goals': ['budgeting'],
      'habits': <dynamic>[],
      'currency': 'USD',
      'region': 'United States',
      'countryCode': 'US',
      'stateCode': 'CA',
      'incomeTier': 'middle',
      'budgetMethod': '50/30/20 Rule',
      'member_since': DateTime.now().toIso8601String(),
      'profile_completion': 0, // Indicates incomplete profile
    };
  }

}

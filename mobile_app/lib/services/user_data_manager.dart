import 'dart:convert';
import 'package:crypto/crypto.dart';
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

  UserDataManager._internal()
      : _secureStorage = const FlutterSecureStorage(),
        _apiService = ApiService();

  @visibleForTesting
  UserDataManager.forTesting({
    required FlutterSecureStorage secureStorage,
    required ApiService apiService,
  })  : _secureStorage = secureStorage,
        _apiService = apiService;

  final FlutterSecureStorage _secureStorage;
  final ApiService _apiService;

  // In-memory cache for fast access
  Map<String, dynamic>? _cachedUserProfile;
  Map<String, dynamic>? _cachedOnboardingData;
  DateTime? _lastRefresh;
  String? _cacheOwner;
  int _sessionGeneration = 0;
  Future<void> _cacheMutationTail = Future<void>.value();

  // Cache expiry duration
  static const Duration _cacheExpiry = Duration(hours: 2);

  /// Synchronously fences all prior asynchronous cache work and clears memory.
  /// Persisted data is owner-namespaced; [clearUserData] additionally removes
  /// the namespace belonging to the identity that is logging out.
  int beginSessionBoundary() {
    _sessionGeneration += 1;
    _cachedUserProfile = null;
    _cachedOnboardingData = null;
    _lastRefresh = null;
    _cacheOwner = null;
    return _sessionGeneration;
  }

  bool _isCurrentGeneration(int generation) => generation == _sessionGeneration;

  /// Initialize user data manager with fresh data load
  Future<void> initialize() async {
    final generation = _sessionGeneration;
    try {
      logInfo('Initializing UserDataManager', tag: 'USER_DATA_MANAGER');

      final owner = await _apiService.getUserId();
      if (!_isCurrentGeneration(generation)) return;
      _cacheOwner = owner;

      // Try to load only this account's cache for immediate UI response.
      if (owner != null && owner.isNotEmpty) {
        await _loadCachedData(generation, owner);
      }
      if (!_isCurrentGeneration(generation)) return;

      // CRITICAL FIX: AWAIT the refresh to ensure data is loaded before proceeding
      // This prevents race conditions and redundant API calls in UserProvider
      try {
        await refreshUserData(sessionGeneration: generation);
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
    final generation = _sessionGeneration;
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

      if (!_isCurrentGeneration(generation)) {
        return _getDefaultUserProfile();
      }

      if (profile.isNotEmpty && profile.containsKey('data')) {
        final userData = asStringKeyedMap(profile['data']);
        _cachedUserProfile = userData;
        _lastRefresh = DateTime.now();
        await _saveCachedData(generation);
        if (!_isCurrentGeneration(generation)) {
          return _getDefaultUserProfile();
        }
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
      return _isCurrentGeneration(generation)
          ? (_cachedUserProfile ?? _getDefaultUserProfile())
          : _getDefaultUserProfile();
    }
  }

  /// Update user profile both locally and on backend
  Future<bool> updateUserProfile(Map<String, dynamic> profileData) async {
    final generation = _sessionGeneration;
    try {
      logInfo('Updating user profile', tag: 'USER_DATA_MANAGER');

      // Optimistic update - update local cache immediately
      _cachedUserProfile = profileData;
      _lastRefresh = DateTime.now();
      await _saveCachedData(generation);
      if (!_isCurrentGeneration(generation)) return false;

      // Try to sync with backend
      await _apiService.updateUserProfile(profileData).timeout(
            const Duration(seconds: 10),
            onTimeout: () => throw Exception('Profile update timeout'),
          );
      if (!_isCurrentGeneration(generation)) return false;

      logInfo('Profile update successful', tag: 'USER_DATA_MANAGER');
      return true;
    } catch (e) {
      if (!_isCurrentGeneration(generation)) return false;
      logError('Failed to update profile on backend: $e',
          tag: 'USER_DATA_MANAGER');

      // The optimistic write above is NOT confirmed server truth. Invalidate
      // freshness (memory + persisted timestamp) so it can't masquerade as a
      // fresh profile: the next getUserProfile() must re-fetch and replace it
      // with server truth rather than short-circuit on the 2h TTL. Keeping the
      // local edit for display is fine; treating it as authoritative is not.
      _lastRefresh = null;
      try {
        final owner = _cacheOwner;
        if (owner != null) {
          await _secureStorage.delete(key: _cacheKey(owner, 'timestamp'));
        }
      } catch (_) {}
      logWarning(
          'Profile updated locally only - marked stale for server re-sync',
          tag: 'USER_DATA_MANAGER');
      return false;
    }
  }

  /// Save onboarding data for immediate use after completion
  Future<void> cacheOnboardingData(Map<String, dynamic> onboardingData) async {
    final generation = _sessionGeneration;
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

      await _saveCachedData(generation);
      if (!_isCurrentGeneration(generation)) return;
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
    final generation = _sessionGeneration;
    try {
      // Check if we have cached onboarding data
      if (_cachedOnboardingData != null) {
        return true;
      }

      // Check via API
      final completed = await _apiService.hasCompletedOnboarding();
      return _isCurrentGeneration(generation) ? completed : false;
    } catch (e) {
      logError('Failed to check onboarding status: $e',
          tag: 'USER_DATA_MANAGER');
      return false;
    }
  }

  /// Force refresh user data from API
  Future<void> refreshUserData({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    try {
      logInfo('Force refreshing user data', tag: 'USER_DATA_MANAGER');

      // forceRefresh bypasses ApiService's own /users/me TTL cache —
      // without it a "force refresh" could serve the same stale profile
      // this call is trying to replace.
      final profile = await _apiService.getUserProfile(forceRefresh: true);
      if (!_isCurrentGeneration(generation)) return;

      if (profile.isNotEmpty && profile.containsKey('data')) {
        _cachedUserProfile = asStringKeyedMap(profile['data']);
        _lastRefresh = DateTime.now();
        await _saveCachedData(generation);
        if (!_isCurrentGeneration(generation)) return;

        logInfo('User data refreshed successfully', tag: 'USER_DATA_MANAGER');
      }
    } catch (e) {
      logError('Failed to refresh user data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  /// Clear all cached user data (for logout)
  Future<void> clearUserData() async {
    final owner = _cacheOwner;
    final generation = beginSessionBoundary();
    try {
      logInfo('Clearing user data', tag: 'USER_DATA_MANAGER');

      await _deleteCachedData(generation, owner);

      logInfo('User data cleared successfully', tag: 'USER_DATA_MANAGER');
    } catch (e) {
      logError('Failed to clear user data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  /// Get user's financial context for budget calculations
  Future<Map<String, dynamic>> getFinancialContext() async {
    final generation = _sessionGeneration;
    try {
      // Server truth first. The transformed onboarding payload is only a
      // stopgap for the window between submit and the profile reflecting
      // it — the old order returned it FOREVER (it persists in secure
      // storage), so the app never picked up the real profile again until
      // logout.
      final profile = await getUserProfile();
      if (!_isCurrentGeneration(generation)) {
        return _unavailableFinancialContext();
      }
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
        if (!_isCurrentGeneration(generation)) {
          return _unavailableFinancialContext();
        }

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
        'goals': goals is List
            ? goals
            : (goals is Map ? <dynamic>[goals] : <dynamic>['budgeting']),
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
      return _unavailableFinancialContext(errorMessage: e.toString());
    }
  }

  Map<String, dynamic> _unavailableFinancialContext({String? errorMessage}) {
    return {
      'api_error': true,
      if (errorMessage != null) 'error_message': errorMessage,
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

  // Private helper methods

  bool _isCacheFresh() {
    if (_lastRefresh == null) return false;
    return DateTime.now().difference(_lastRefresh!) < _cacheExpiry;
  }

  /// A profile is only usable if it isn't the synthetic placeholder produced
  /// by [_getDefaultUserProfile] (or empty). Persisting/serving that
  /// placeholder poisoned the dashboard with a fake "MITA User" / income 0
  /// state that survived restarts.
  ///
  /// Public, not test-only: the splash screen needs the same test to tell an
  /// unresolved session apart from a genuinely new user, because
  /// getUserProfile answers a 401 with the placeholder rather than an error.
  static bool isUsableCachedProfile(Map<String, dynamic> profile) {
    if (profile.isEmpty) return false;
    if (profile['email'] == 'user@mita.finance') return false;
    return true;
  }

  @visibleForTesting
  static String cacheNamespaceForOwner(String owner) =>
      sha256.convert(utf8.encode(owner)).toString();

  String _cacheKey(String owner, String field) =>
      'user_cache_${cacheNamespaceForOwner(owner)}_$field';

  Future<T> _serializeCacheMutation<T>(Future<T> Function() mutation) {
    final operation = _cacheMutationTail.then<T>((_) => mutation());
    _cacheMutationTail =
        operation.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return operation;
  }

  Future<void> _loadCachedData(int generation, String owner) async {
    try {
      final ownerMarker =
          await _secureStorage.read(key: _cacheKey(owner, 'owner'));
      if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

      // A namespace is not trusted without an exact owner marker. This also
      // prevents old, unnamespaced account-A cache from being loaded for B.
      if (ownerMarker != owner) {
        logInfo('No owner-matched cached user data available',
            tag: 'USER_DATA_MANAGER');
        return;
      }

      final profileData =
          await _secureStorage.read(key: _cacheKey(owner, 'profile'));
      final onboardingData =
          await _secureStorage.read(key: _cacheKey(owner, 'onboarding'));
      final timestampData =
          await _secureStorage.read(key: _cacheKey(owner, 'timestamp'));
      if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

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
          await _serializeCacheMutation<void>(() async {
            if (!_isCurrentGeneration(generation) || _cacheOwner != owner) {
              return;
            }
            await _secureStorage.delete(key: _cacheKey(owner, 'profile'));
            await _secureStorage.delete(key: _cacheKey(owner, 'timestamp'));
          });
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

  Future<void> _saveCachedData(int generation) async {
    if (!_isCurrentGeneration(generation)) return;
    final owner = _cacheOwner;
    if (owner == null || owner.isEmpty) {
      // Account ownership is required for persistent cache writes. In-memory
      // data remains available for the current screen.
      return;
    }

    final profile = _cachedUserProfile == null
        ? null
        : Map<String, dynamic>.from(_cachedUserProfile!);
    final onboarding = _cachedOnboardingData == null
        ? null
        : Map<String, dynamic>.from(_cachedOnboardingData!);
    final refreshedAt = _lastRefresh;

    try {
      await _serializeCacheMutation<void>(() async {
        if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

        if (profile != null) {
          await _secureStorage.write(
            key: _cacheKey(owner, 'profile'),
            value: jsonEncode(profile),
          );
        }
        if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

        if (onboarding != null) {
          await _secureStorage.write(
            key: _cacheKey(owner, 'onboarding'),
            value: jsonEncode(onboarding),
          );
        }
        if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

        if (refreshedAt != null) {
          await _secureStorage.write(
            key: _cacheKey(owner, 'timestamp'),
            value: refreshedAt.millisecondsSinceEpoch.toString(),
          );
        }
        if (!_isCurrentGeneration(generation) || _cacheOwner != owner) return;

        // Commit marker last: partial writes are never considered loadable.
        await _secureStorage.write(
          key: _cacheKey(owner, 'owner'),
          value: owner,
        );
      });
    } catch (e) {
      logError('Failed to save cached data: $e', tag: 'USER_DATA_MANAGER');
    }
  }

  Future<void> _deleteCachedData(int generation, String? owner) {
    return _serializeCacheMutation<void>(() async {
      // This delete belongs to the logout generation. If a newer identity has
      // already started, only the captured account namespace is touched.
      if (!_isCurrentGeneration(generation) && owner == null) return;

      if (owner != null && owner.isNotEmpty) {
        for (final field in const [
          'profile',
          'onboarding',
          'timestamp',
          'owner',
        ]) {
          await _secureStorage.delete(key: _cacheKey(owner, field));
        }
      }

      // Remove legacy unnamespaced entries. They are never loaded by the new
      // code, but deleting them prevents residual private data from lingering.
      for (final key in const [
        'cached_user_profile',
        'cached_onboarding_data',
        'cache_timestamp',
        'cached_data_owner',
      ]) {
        await _secureStorage.delete(key: key);
      }
    });
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

import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'logging_service.dart';
import 'api_service.dart';

/// Production-level user data state management system
/// Handles user data flow from onboarding through entire app lifecycle
class UserDataManager {
  static UserDataManager? _instance;
  static UserDataManager get instance => _instance ??= UserDataManager._internal();
  
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
      
      // Then refresh from API in background
      _refreshFromApiBackground();
      
    } catch (e) {
      logError('Failed to initialize UserDataManager: $e', tag: 'USER_DATA_MANAGER');
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
          logWarning('getUserProfile timeout - using cached data', tag: 'USER_DATA_MANAGER');
          return <String, dynamic>{};
        },
      ).catchError((error) {
        logWarning('getUserProfile error - using cached data: $error', tag: 'USER_DATA_MANAGER');
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
        logWarning('Using cached user profile due to API failure', tag: 'USER_DATA_MANAGER');
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
      final success = await _apiService.updateUserProfile(profileData).timeout(
        const Duration(seconds: 10),
        onTimeout: () => throw Exception('Profile update timeout'),
      );
      
      logInfo('Profile update successful', tag: 'USER_DATA_MANAGER');
      return true;
      
    } catch (e) {
      logError('Failed to update profile on backend: $e', tag: 'USER_DATA_MANAGER');
      
      // Keep local changes even if backend fails
      logWarning('Profile updated locally only - will sync later', tag: 'USER_DATA_MANAGER');
      return false;
    }
  }
  
  /// Save onboarding data for immediate use after completion
  Future<void> cacheOnboardingData(Map<String, dynamic> onboardingData) async {
    try {
      logInfo('Caching onboarding data', tag: 'USER_DATA_MANAGER');
      
      _cachedOnboardingData = onboardingData;
      
      // Transform onboarding data to user profile format
      _cachedUserProfile = _transformOnboardingToProfile(onboardingData);
      _lastRefresh = DateTime.now();
      
      await _saveCachedData();
      
      logInfo('Onboarding data cached successfully', tag: 'USER_DATA_MANAGER');
      
    } catch (e) {
      logError('Failed to cache onboarding data: $e', tag: 'USER_DATA_MANAGER');
    }
  }
  
  /// Check if we have cached onboarding data (non-recursive)
  bool hasCachedOnboardingData() {
    return _cachedOnboardingData != null;
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
      logError('Failed to check onboarding status: $e', tag: 'USER_DATA_MANAGER');
      return false;
    }
  }
  
  /// Force refresh user data from API
  Future<void> refreshUserData() async {
    try {
      logInfo('Force refreshing user data', tag: 'USER_DATA_MANAGER');
      
      final profile = await _apiService.getUserProfile();
      
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
    final profile = await getUserProfile();
    
    final income = (profile['income'] as num?)?.toDouble();
    if (income == null || income <= 0) {
      throw Exception('Income data required. Please complete onboarding.');
    }
    
    return {
      'income': income,
      'expenses': profile['expenses'] as List<dynamic>? ?? [],
      'goals': profile['goals'] as List<dynamic>? ?? ['budgeting'],
      'habits': profile['habits'] as List<dynamic>? ?? [],
      'region': profile['region'] as String? ?? 'United States',
      'stateCode': profile['stateCode'] as String? ?? 'CA',
      'incomeTier': profile['incomeTier'] as String? ?? 'middle',
      'currency': profile['currency'] as String? ?? 'USD',
      'budgetMethod': profile['budgetMethod'] as String? ?? '50/30/20 Rule',
    };
  }
  
  // Private helper methods
  
  bool _isCacheFresh() {
    if (_lastRefresh == null) return false;
    return DateTime.now().difference(_lastRefresh!) < _cacheExpiry;
  }
  
  Future<void> _loadCachedData() async {
    try {
      final profileData = await _secureStorage.read(key: 'cached_user_profile');
      final onboardingData = await _secureStorage.read(key: 'cached_onboarding_data');
      final timestampData = await _secureStorage.read(key: 'cache_timestamp');
      
      if (profileData != null) {
        _cachedUserProfile = jsonDecode(profileData) as Map<String, dynamic>;
      }
      
      if (onboardingData != null) {
        _cachedOnboardingData = jsonDecode(onboardingData) as Map<String, dynamic>;
      }
      
      if (timestampData != null) {
        _lastRefresh = DateTime.fromMillisecondsSinceEpoch(int.parse(timestampData));
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
  
  void _refreshFromApiBackground() {
    Future.delayed(Duration.zero, () async {
      try {
        await refreshUserData();
      } catch (e) {
        logError('Background refresh failed: $e', tag: 'USER_DATA_MANAGER');
      }
    });
  }
  
  Map<String, dynamic> _transformOnboardingToProfile(Map<String, dynamic> onboardingData) {
    final income = onboardingData['income'];
    if (income == null) {
      throw ArgumentError('Income is required in onboarding data');
    }
    
    return {
      'income': income,
      'expenses': onboardingData['expenses'] ?? [],
      'goals': onboardingData['goals'] ?? ['budgeting'],
      'habits': onboardingData['habits'] ?? [],
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
  
  Map<String, dynamic> _getDefaultUserProfile() {
    throw Exception('Default user profile should not be used. Please complete onboarding to set up your profile.');
  }

  Map<String, dynamic> _getEmptyUserProfile() {
    return {
      'name': 'MITA User',
      'email': 'user@mita.finance',
      'expenses': [],
      'goals': ['budgeting'],
      'habits': [],
      'currency': 'USD',
      'region': 'United States',
      'countryCode': 'US',
      'stateCode': 'CA',
      'incomeTier': 'middle',
      'budgetMethod': '50/30/20 Rule',
      'member_since': DateTime.now().subtract(const Duration(days: 30)).toIso8601String(),
      'profile_completion': 85,
      'verified_email': true,
      'dark_mode': false,
      'notifications': true,
    };
  }
}
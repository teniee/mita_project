import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'advanced_offline_service.dart';
import 'logging_service.dart';
import 'timeout_manager_service.dart';

/// Offline-first data provider that ensures instant app loading
/// with immediate fallback data and background sync
class OfflineFirstProvider {
  static final OfflineFirstProvider _instance = OfflineFirstProvider._internal();
  factory OfflineFirstProvider() => _instance;
  OfflineFirstProvider._internal();

  final ApiService _apiService = ApiService();
  final AdvancedOfflineService _offlineService = AdvancedOfflineService();
  final TimeoutManagerService _timeoutManager = TimeoutManagerService();
  
  // Data caches for instant access
  Map<String, dynamic>? _cachedDashboard;
  List<dynamic>? _cachedCalendar;
  Map<String, dynamic>? _cachedUserProfile;
  
  // Loading state management
  final ValueNotifier<bool> _isInitialized = ValueNotifier<bool>(false);
  final ValueNotifier<bool> _isBackgroundSyncing = ValueNotifier<bool>(false);
  
  Timer? _backgroundSyncTimer;
  bool _hasInitialized = false;

  ValueNotifier<bool> get isInitialized => _isInitialized;
  ValueNotifier<bool> get isBackgroundSyncing => _isBackgroundSyncing;

  /// Initialize the offline-first provider
  Future<void> initialize() async {
    if (_hasInitialized) return;

    try {
      logDebug('Initializing offline-first provider', tag: 'OFFLINE_FIRST');
      
      // Initialize offline service
      await _offlineService.initialize();
      
      // Load cached data immediately for instant UI
      await _loadCachedData();
      
      // Mark as initialized immediately so UI can render
      _isInitialized.value = true;
      _hasInitialized = true;
      
      // Start background sync (don't wait for it)
      _startBackgroundSync();
      
      logDebug('Offline-first provider initialized successfully', tag: 'OFFLINE_FIRST');
    } catch (e) {
      logError('Failed to initialize offline-first provider', tag: 'OFFLINE_FIRST', error: e);
      
      // Still mark as initialized with fallback data
      await _generateFallbackData();
      _isInitialized.value = true;
      _hasInitialized = true;
    }
  }

  /// Load cached data from local storage
  Future<void> _loadCachedData() async {
    try {
      // Try to load cached dashboard
      final dashboardCache = await _offlineService.getCachedResponse('dashboard_data');
      if (dashboardCache != null && !dashboardCache.isExpired) {
        _cachedDashboard = jsonDecode(dashboardCache.data) as Map<String, dynamic>;
        logDebug('Loaded cached dashboard data', tag: 'OFFLINE_FIRST');
      }
      
      // Try to load cached calendar
      final calendarCache = await _offlineService.getCachedResponse('calendar_data');
      if (calendarCache != null && !calendarCache.isExpired) {
        _cachedCalendar = jsonDecode(calendarCache.data) as List<dynamic>;
        logDebug('Loaded cached calendar data', tag: 'OFFLINE_FIRST');
      }
      
      // Try to load cached user profile
      final profileCache = await _offlineService.getCachedResponse('user_profile');
      if (profileCache != null && !profileCache.isExpired) {
        _cachedUserProfile = jsonDecode(profileCache.data) as Map<String, dynamic>;
        logDebug('Loaded cached user profile', tag: 'OFFLINE_FIRST');
      }
      
      // If no cached data exists, generate fallback data
      if (_cachedDashboard == null || _cachedCalendar == null) {
        await _generateFallbackData();
      }
    } catch (e) {
      logWarning('Error loading cached data, using fallback', tag: 'OFFLINE_FIRST');
      await _generateFallbackData();
    }
  }

  /// Generate fallback data when no cache is available
  Future<void> _generateFallbackData() async {
    try {
      logInfo('Generating safe fallback data for offline-first provider', tag: 'OFFLINE_FIRST');

      // Generate safe default dashboard data
      _cachedDashboard = _generateDefaultDashboard();

      // Generate safe default calendar data
      _cachedCalendar = _generateDefaultCalendar();

      // Generate safe default user profile (minimal data)
      _cachedUserProfile = _generateDefaultUserProfile();

      logInfo('Safe fallback data generated successfully', tag: 'OFFLINE_FIRST');
    } catch (e) {
      logError('Failed to generate fallback data: $e', tag: 'OFFLINE_FIRST');

      // Ensure we at least have empty structures to prevent crashes
      _cachedDashboard ??= <String, dynamic>{};
      _cachedCalendar ??= <dynamic>[];
      _cachedUserProfile ??= <String, dynamic>{'data': {'income': 0.0}};
    }
  }

  /// Generate basic calendar fallback
  List<dynamic> _generateBasicCalendar(double income) {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;
    final dailyBudget = (income * 0.55) / 30;

    return List.generate(daysInMonth, (index) {
      final day = index + 1;
      final currentDate = DateTime(today.year, today.month, day);
      final isToday = day == today.day;
      final isPastDay = currentDate.isBefore(today);

      return {
        'day': day,
        'limit': dailyBudget.round(),
        'spent': isPastDay ? (dailyBudget * 0.7).round() : (isToday ? (dailyBudget * 0.5).round() : 0),
        'status': 'good',
        'is_today': isToday,
        'is_weekend': currentDate.weekday >= 6,
      };
    });
  }

  /// Generate safe default dashboard data
  Map<String, dynamic> _generateDefaultDashboard() {
    final now = DateTime.now();

    return {
      'balance': 0.0,
      'spent': 0.0,
      'daily_targets': <Map<String, dynamic>>[],
      'week': _generateDefaultWeekData(),
      'transactions': <Map<String, dynamic>>[],
      'currency': 'USD',
      'last_updated': now.toIso8601String(),
      'default_data': true, // Flag to indicate this is fallback data
    };
  }

  /// Generate safe default calendar data
  List<dynamic> _generateDefaultCalendar() {
    final today = DateTime.now();
    final daysInMonth = DateTime(today.year, today.month + 1, 0).day;

    return List.generate(daysInMonth, (index) {
      final day = index + 1;
      final currentDate = DateTime(today.year, today.month, day);
      final isToday = day == today.day;

      return <String, dynamic>{
        'day': day,
        'limit': 0,
        'spent': 0,
        'status': 'neutral',
        'is_today': isToday,
        'is_weekend': currentDate.weekday >= 6,
      };
    });
  }

  /// Generate safe default user profile
  Map<String, dynamic> _generateDefaultUserProfile() {
    return {
      'data': {
        'name': 'MITA User',
        'email': 'user@mita.finance',
        'income': 0.0, // This will trigger proper onboarding flow
        'expenses': <dynamic>[],
        'goals': <String>['budgeting'],
        'habits': <dynamic>[],
        'currency': 'USD',
        'region': 'United States',
        'countryCode': 'US',
        'stateCode': 'CA',
        'incomeTier': 'middle',
        'budgetMethod': '50/30/20 Rule',
        'member_since': DateTime.now().toIso8601String(),
        'profile_completion': 0, // Indicates incomplete profile
        'fallback_profile': true, // Flag to indicate this is fallback data
      }
    };
  }

  /// Generate default week data for dashboard
  List<Map<String, dynamic>> _generateDefaultWeekData() {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return List.generate(7, (index) => <String, dynamic>{
      'day': days[index],
      'status': 'neutral',
    });
  }

  /// Get dashboard data (instant from cache)
  Map<String, dynamic> getDashboardData() {
    return _cachedDashboard ?? {};
  }

  /// Get calendar data (instant from cache)
  List<dynamic> getCalendarData() {
    return _cachedCalendar ?? [];
  }

  /// Get user profile (instant from cache)
  Map<String, dynamic> getUserProfile() {
    if (_cachedUserProfile == null) {
      logWarning('User profile not cached, generating default profile', tag: 'OFFLINE_FIRST');
      _cachedUserProfile = _generateDefaultUserProfile();
    }
    return _cachedUserProfile!;
  }

  /// Start background sync to update cached data
  void _startBackgroundSync() {
    // Start immediate background sync
    _performBackgroundSync();
    
    // Set up periodic background sync (every 5 minutes)
    _backgroundSyncTimer = Timer.periodic(const Duration(minutes: 5), (_) {
      _performBackgroundSync();
    });
  }

  /// Perform background sync without affecting UI
  Future<void> _performBackgroundSync() async {
    if (_isBackgroundSyncing.value) return; // Avoid overlapping syncs
    
    _isBackgroundSyncing.value = true;
    
    try {
      logDebug('Starting background sync', tag: 'OFFLINE_FIRST');
      
      // Sync dashboard data in background
      _timeoutManager.executeBackground<void>(
        operation: () async {
          try {
            final dashboardData = await _apiService.getDashboard();
            _cachedDashboard = dashboardData;
            
            // Cache for next time
            await _offlineService.cacheResponse(
              key: 'dashboard_data',
              data: jsonEncode(dashboardData),
              expiry: const Duration(hours: 2),
            );
            
            logDebug('Dashboard data synced in background', tag: 'OFFLINE_FIRST');
          } catch (e) {
            logDebug('Background dashboard sync failed (expected)', tag: 'OFFLINE_FIRST');
          }
        },
        timeout: const Duration(seconds: 8),
        operationName: 'Background Dashboard Sync',
      );
      
      // Sync calendar data in background
      _timeoutManager.executeBackground<void>(
        operation: () async {
          try {
            final calendarData = await _apiService.getCalendar();
            _cachedCalendar = calendarData;
            
            // Cache for next time
            await _offlineService.cacheResponse(
              key: 'calendar_data',
              data: jsonEncode(calendarData),
              expiry: const Duration(hours: 2),
            );
            
            logDebug('Calendar data synced in background', tag: 'OFFLINE_FIRST');
          } catch (e) {
            logDebug('Background calendar sync failed (expected)', tag: 'OFFLINE_FIRST');
          }
        },
        timeout: const Duration(seconds: 8),
        operationName: 'Background Calendar Sync',
      );
      
      // Sync user profile in background
      _timeoutManager.executeBackground<void>(
        operation: () async {
          try {
            final profileData = await _apiService.getUserProfile();
            _cachedUserProfile = profileData;
            
            // Cache for next time
            await _offlineService.cacheResponse(
              key: 'user_profile',
              data: jsonEncode(profileData),
              expiry: const Duration(hours: 4),
            );
            
            logDebug('User profile synced in background', tag: 'OFFLINE_FIRST');
          } catch (e) {
            logDebug('Background profile sync failed (expected)', tag: 'OFFLINE_FIRST');
          }
        },
        timeout: const Duration(seconds: 5),
        operationName: 'Background Profile Sync',
      );
      
    } finally {
      _isBackgroundSyncing.value = false;
    }
  }

  /// Force refresh data (user-initiated)
  Future<void> refreshData() async {
    try {
      logDebug('User-initiated data refresh', tag: 'OFFLINE_FIRST');
      
      // Try to get fresh data with timeout
      final dashboardFuture = _timeoutManager.executeWithFallback<Map<String, dynamic>>(
        operation: () => _apiService.getDashboard(),
        fallbackValue: _cachedDashboard ?? {},
        timeout: const Duration(seconds: 8),
        operationName: 'Refresh Dashboard',
      );
      
      final calendarFuture = _timeoutManager.executeWithFallback<List<dynamic>>(
        operation: () => _apiService.getCalendar(),
        fallbackValue: _cachedCalendar ?? [],
        timeout: const Duration(seconds: 8),
        operationName: 'Refresh Calendar',
      );
      
      // Wait for both with reasonable timeout
      final results = await Future.wait([
        dashboardFuture,
        calendarFuture,
      ]);
      
      _cachedDashboard = results[0] as Map<String, dynamic>;
      _cachedCalendar = results[1] as List<dynamic>;
      
      // Cache the refreshed data
      await _offlineService.cacheResponse(
        key: 'dashboard_data',
        data: jsonEncode(_cachedDashboard),
        expiry: const Duration(hours: 2),
      );
      
      await _offlineService.cacheResponse(
        key: 'calendar_data',
        data: jsonEncode(_cachedCalendar),
        expiry: const Duration(hours: 2),
      );
      
      logDebug('Data refresh completed successfully', tag: 'OFFLINE_FIRST');
    } catch (e) {
      logWarning('Data refresh partially failed, keeping cached data', tag: 'OFFLINE_FIRST');
    }
  }

  /// Get sync status
  OfflineFirstStatus getStatus() {
    return OfflineFirstStatus(
      isInitialized: _isInitialized.value,
      isBackgroundSyncing: _isBackgroundSyncing.value,
      hasCachedDashboard: _cachedDashboard != null,
      hasCachedCalendar: _cachedCalendar != null,
      hasCachedProfile: _cachedUserProfile != null,
    );
  }

  /// Clear all cached data
  Future<void> clearCache() async {
    try {
      await _offlineService.clearOfflineData();
      _cachedDashboard = null;
      _cachedCalendar = null;
      _cachedUserProfile = null;
      
      // Regenerate fallback data
      await _generateFallbackData();
      
      logDebug('Offline cache cleared and regenerated', tag: 'OFFLINE_FIRST');
    } catch (e) {
      logError('Failed to clear offline cache', tag: 'OFFLINE_FIRST', error: e);
    }
  }

  /// Dispose resources
  void dispose() {
    _backgroundSyncTimer?.cancel();
    _isInitialized.dispose();
    _isBackgroundSyncing.dispose();
  }
}

/// Status information for offline-first provider
class OfflineFirstStatus {
  final bool isInitialized;
  final bool isBackgroundSyncing;
  final bool hasCachedDashboard;
  final bool hasCachedCalendar;
  final bool hasCachedProfile;

  OfflineFirstStatus({
    required this.isInitialized,
    required this.isBackgroundSyncing,
    required this.hasCachedDashboard,
    required this.hasCachedCalendar,
    required this.hasCachedProfile,
  });

  bool get hasAllCachedData => hasCachedDashboard && hasCachedCalendar && hasCachedProfile;

  @override
  String toString() {
    return 'OfflineFirstStatus(initialized: $isInitialized, syncing: $isBackgroundSyncing, '
           'cached: dashboard=$hasCachedDashboard, calendar=$hasCachedCalendar, profile=$hasCachedProfile)';
  }
}
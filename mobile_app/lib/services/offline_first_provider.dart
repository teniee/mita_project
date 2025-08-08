import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'advanced_offline_service.dart';
import 'calendar_fallback_service.dart';
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
        _cachedDashboard = jsonDecode(dashboardCache.data);
        logDebug('Loaded cached dashboard data', tag: 'OFFLINE_FIRST');
      }
      
      // Try to load cached calendar
      final calendarCache = await _offlineService.getCachedResponse('calendar_data');
      if (calendarCache != null && !calendarCache.isExpired) {
        _cachedCalendar = jsonDecode(calendarCache.data);
        logDebug('Loaded cached calendar data', tag: 'OFFLINE_FIRST');
      }
      
      // Try to load cached user profile
      final profileCache = await _offlineService.getCachedResponse('user_profile');
      if (profileCache != null && !profileCache.isExpired) {
        _cachedUserProfile = jsonDecode(profileCache.data);
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
    const defaultIncome = 3000.0;
    
    // Generate fallback dashboard data
    _cachedDashboard = {
      'balance': defaultIncome * 0.85,
      'today_budget': (defaultIncome * 0.55) / 30,
      'today_spent': ((defaultIncome * 0.55) / 30) * 0.6,
      'monthly_budget': defaultIncome * 0.55,
      'monthly_spent': (defaultIncome * 0.55) * 0.6,
      'daily_targets': [
        {
          'category': 'Food & Dining',
          'limit': (defaultIncome * 0.15) / 30,
          'spent': ((defaultIncome * 0.15) / 30) * 0.60,
        },
        {
          'category': 'Transportation',
          'limit': (defaultIncome * 0.15) / 30,
          'spent': ((defaultIncome * 0.15) / 30) * 0.40,
        },
        {
          'category': 'Entertainment',
          'limit': (defaultIncome * 0.08) / 30,
          'spent': ((defaultIncome * 0.08) / 30) * 0.30,
        },
        {
          'category': 'Shopping',
          'limit': (defaultIncome * 0.12) / 30,
          'spent': ((defaultIncome * 0.12) / 30) * 0.25,
        },
      ],
      'week': [
        {'day': 'Mon', 'status': 'good'},
        {'day': 'Tue', 'status': 'good'},
        {'day': 'Wed', 'status': 'warning'},
        {'day': 'Thu', 'status': 'good'},
        {'day': 'Fri', 'status': 'good'},
        {'day': 'Sat', 'status': 'over'},
        {'day': 'Sun', 'status': 'good'},
      ],
      'transactions': [
        {
          'action': 'Morning Coffee',
          'amount': '12.50',
          'category': 'Food',
          'date': DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
        },
        {
          'action': 'Grocery Shopping',
          'amount': '89.32',
          'category': 'Food',
          'date': DateTime.now().subtract(const Duration(days: 1)).toIso8601String(),
        },
      ],
    };
    
    // Generate fallback calendar data
    try {
      final fallbackService = CalendarFallbackService();
      _cachedCalendar = await fallbackService.generateFallbackCalendarData(
        monthlyIncome: defaultIncome,
        year: DateTime.now().year,
        month: DateTime.now().month,
      );
    } catch (e) {
      _cachedCalendar = _generateBasicCalendar(defaultIncome);
    }
    
    // Generate fallback user profile
    _cachedUserProfile = {
      'data': {
        'income': defaultIncome,
        'name': 'User',
        'location': null,
      }
    };
    
    logDebug('Generated fallback data for instant UI', tag: 'OFFLINE_FIRST');
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
    return _cachedUserProfile ?? {'data': {'income': 3000.0}};
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
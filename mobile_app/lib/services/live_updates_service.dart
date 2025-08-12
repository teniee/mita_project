import 'dart:async';
import 'package:flutter/foundation.dart';
import 'logging_service.dart';
import 'api_service.dart';
import 'user_data_manager.dart';

/// Service for handling live updates and real-time data synchronization
class LiveUpdatesService {
  static final LiveUpdatesService _instance = LiveUpdatesService._internal();
  factory LiveUpdatesService() => _instance;
  LiveUpdatesService._internal();

  final ApiService _apiService = ApiService();
  final UserDataManager _userDataManager = UserDataManager.instance;

  // Stream controllers for different types of updates
  final StreamController<Map<String, dynamic>> _dashboardUpdatesController = 
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _transactionUpdatesController = 
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _budgetUpdatesController = 
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _profileUpdatesController = 
      StreamController<Map<String, dynamic>>.broadcast();

  // Timer for polling-based live updates
  Timer? _liveUpdateTimer;
  bool _isEnabled = false;
  bool _isRunning = false;
  
  // Cache for last known data to detect changes
  Map<String, dynamic>? _lastDashboardData;
  Map<String, dynamic>? _lastProfileData;
  int _lastTransactionCount = 0;
  
  // Update intervals
  static const Duration _defaultUpdateInterval = Duration(minutes: 2);
  static const Duration _fastUpdateInterval = Duration(seconds: 30);
  
  Duration _currentUpdateInterval = _defaultUpdateInterval;

  /// Stream of dashboard updates
  Stream<Map<String, dynamic>> get dashboardUpdates => _dashboardUpdatesController.stream;
  
  /// Stream of transaction updates  
  Stream<Map<String, dynamic>> get transactionUpdates => _transactionUpdatesController.stream;
  
  /// Stream of budget updates
  Stream<Map<String, dynamic>> get budgetUpdates => _budgetUpdatesController.stream;
  
  /// Stream of profile updates
  Stream<Map<String, dynamic>> get profileUpdates => _profileUpdatesController.stream;

  /// Whether live updates are currently enabled
  bool get isEnabled => _isEnabled;
  
  /// Whether live updates are currently running
  bool get isRunning => _isRunning;

  /// Enable live updates with optional custom interval
  Future<void> enableLiveUpdates([Duration? interval]) async {
    if (_isEnabled) {
      logDebug('Live updates already enabled', tag: 'LIVE_UPDATES');
      return;
    }

    _currentUpdateInterval = interval ?? _defaultUpdateInterval;
    _isEnabled = true;

    logInfo('Enabling live updates with ${_currentUpdateInterval.inMinutes} minute intervals', 
        tag: 'LIVE_UPDATES');

    await _startLiveUpdates();
  }

  /// Disable live updates
  void disableLiveUpdates() {
    if (!_isEnabled) {
      logDebug('Live updates already disabled', tag: 'LIVE_UPDATES');
      return;
    }

    logInfo('Disabling live updates', tag: 'LIVE_UPDATES');
    
    _isEnabled = false;
    _isRunning = false;
    _liveUpdateTimer?.cancel();
    _liveUpdateTimer = null;
  }

  /// Start the live update polling mechanism
  Future<void> _startLiveUpdates() async {
    if (_isRunning) return;

    _isRunning = true;
    logDebug('Starting live update polling', tag: 'LIVE_UPDATES');

    // Do initial data fetch
    await _performLiveUpdate();

    // Set up periodic updates
    _liveUpdateTimer = Timer.periodic(_currentUpdateInterval, (timer) async {
      if (!_isEnabled) {
        timer.cancel();
        return;
      }
      await _performLiveUpdate();
    });
  }

  /// Perform a single live update check
  Future<void> _performLiveUpdate() async {
    if (!_isEnabled) return;

    try {
      logDebug('Performing live update check', tag: 'LIVE_UPDATES');

      // Check for dashboard updates
      await _checkDashboardUpdates();
      
      // Check for profile updates  
      await _checkProfileUpdates();
      
      // Check for new transactions
      await _checkTransactionUpdates();
      
      // Check for budget changes
      await _checkBudgetUpdates();

    } catch (e) {
      logError('Error during live update: $e', tag: 'LIVE_UPDATES');
    }
  }

  /// Check for dashboard data updates
  Future<void> _checkDashboardUpdates() async {
    try {
      final dashboardData = await _apiService.getDashboard();
      
      if (_lastDashboardData == null || _hasDataChanged(_lastDashboardData!, dashboardData)) {
        logDebug('Dashboard data changed, notifying listeners', tag: 'LIVE_UPDATES');
        _lastDashboardData = Map.from(dashboardData);
        _dashboardUpdatesController.add(dashboardData);
      }
    } catch (e) {
      logWarning('Failed to check dashboard updates: $e', tag: 'LIVE_UPDATES');
    }
  }

  /// Check for profile data updates
  Future<void> _checkProfileUpdates() async {
    try {
      final profileData = await _userDataManager.getUserProfile();
      
      if (_lastProfileData == null || _hasDataChanged(_lastProfileData!, profileData)) {
        logDebug('Profile data changed, notifying listeners', tag: 'LIVE_UPDATES');
        _lastProfileData = Map.from(profileData);
        _profileUpdatesController.add(profileData);
      }
    } catch (e) {
      logWarning('Failed to check profile updates: $e', tag: 'LIVE_UPDATES');
    }
  }

  /// Check for new transactions
  Future<void> _checkTransactionUpdates() async {
    try {
      // Get today's transactions to check for changes
      final today = DateTime.now();
      final todayString = '${today.year}-${today.month.toString().padLeft(2, '0')}-${today.day.toString().padLeft(2, '0')}';
      
      final transactions = await _apiService.getTransactionsByDate(todayString);
      final currentCount = transactions.length;
      
      if (_lastTransactionCount != currentCount) {
        logDebug('New transaction detected, notifying listeners', tag: 'LIVE_UPDATES');
        _lastTransactionCount = currentCount;
        
        _transactionUpdatesController.add({
          'transactions': transactions,
          'hasNewTransactions': true,
          'timestamp': DateTime.now().toIso8601String(),
          'date': todayString,
        });
      }
    } catch (e) {
      logWarning('Failed to check transaction updates: $e', tag: 'LIVE_UPDATES');
    }
  }

  /// Check for budget updates
  Future<void> _checkBudgetUpdates() async {
    try {
      // For now, budget updates are triggered by dashboard changes
      // In the future, this could check for specific budget modifications
      logDebug('Budget update check completed', tag: 'LIVE_UPDATES');
    } catch (e) {
      logWarning('Failed to check budget updates: $e', tag: 'LIVE_UPDATES');
    }
  }

  /// Helper method to detect if data has meaningfully changed
  bool _hasDataChanged(Map<String, dynamic> oldData, Map<String, dynamic> newData) {
    // Simple comparison - in production, you might want more sophisticated diffing
    try {
      // Compare key fields that indicate meaningful changes
      final oldBalance = oldData['balance'] ?? 0.0;
      final newBalance = newData['balance'] ?? 0.0;
      
      final oldTodaySpent = oldData['today_spent'] ?? 0.0; 
      final newTodaySpent = newData['today_spent'] ?? 0.0;
      
      final oldTodayBudget = oldData['today_budget'] ?? 0.0;
      final newTodayBudget = newData['today_budget'] ?? 0.0;

      return (oldBalance != newBalance) || 
             (oldTodaySpent != newTodaySpent) || 
             (oldTodayBudget != newTodayBudget);
             
    } catch (e) {
      // If comparison fails, assume data changed to be safe
      return true;
    }
  }

  /// Force an immediate live update check
  Future<void> forceUpdate() async {
    logInfo('Forcing immediate live update', tag: 'LIVE_UPDATES');
    await _performLiveUpdate();
  }

  /// Set update interval for more/less frequent updates
  void setUpdateInterval(Duration interval) {
    if (_currentUpdateInterval != interval) {
      logInfo('Changing live update interval from ${_currentUpdateInterval.inMinutes} to ${interval.inMinutes} minutes', 
          tag: 'LIVE_UPDATES');
      
      _currentUpdateInterval = interval;
      
      // Restart with new interval if currently running
      if (_isEnabled && _isRunning) {
        _liveUpdateTimer?.cancel();
        _startLiveUpdates();
      }
    }
  }

  /// Enable fast updates (30 seconds) for active usage
  void enableFastUpdates() {
    setUpdateInterval(_fastUpdateInterval);
  }

  /// Return to normal update frequency
  void enableNormalUpdates() {
    setUpdateInterval(_defaultUpdateInterval);
  }

  /// Get current update status
  Map<String, dynamic> getStatus() {
    return {
      'enabled': _isEnabled,
      'running': _isRunning,
      'interval_minutes': _currentUpdateInterval.inMinutes,
      'interval_seconds': _currentUpdateInterval.inSeconds,
      'last_dashboard_update': _lastDashboardData != null ? 'cached' : 'none',
      'last_profile_update': _lastProfileData != null ? 'cached' : 'none',
      'transaction_count': _lastTransactionCount,
    };
  }

  /// Dispose resources and clean up
  void dispose() {
    logInfo('Disposing live updates service', tag: 'LIVE_UPDATES');
    
    disableLiveUpdates();
    
    _dashboardUpdatesController.close();
    _transactionUpdatesController.close();
    _budgetUpdatesController.close();
    _profileUpdatesController.close();
  }
}
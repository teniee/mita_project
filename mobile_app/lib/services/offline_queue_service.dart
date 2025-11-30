import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_service.dart';
import 'logging_service.dart';

class OfflineQueueService {
  OfflineQueueService._() {
    _init();
  }

  static final OfflineQueueService instance = OfflineQueueService._();

  final Connectivity _connectivity = Connectivity();
  bool _isOnline = true;

  void _init() {
    _connectivity.onConnectivityChanged.listen((results) {
      final result = results.isNotEmpty ? results.first : ConnectivityResult.none;
      final online = result != ConnectivityResult.none;
      if (online && !_isOnline) {
        _flushQueue();
      }
      _isOnline = online;
    });
  }

  Future<void> queueExpense(Map<String, dynamic> data) async {
    if (_isOnline) {
      await ApiService().createExpense(data);
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_expenses') ?? [];
    list.add(jsonEncode(data));
    await prefs.setStringList('queued_expenses', list);
  }

  /// Queue a registration attempt for when connection is restored
  Future<void> queueRegistration(String email, String password) async {
    logInfo('Queueing registration for when connection is restored', tag: 'OFFLINE_QUEUE');

    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_registrations') ?? [];

    final registrationData = {
      'email': email,
      'password': password,
      'timestamp': DateTime.now().toIso8601String(),
      'type': 'registration',
    };

    list.add(jsonEncode(registrationData));
    await prefs.setStringList('queued_registrations', list);

    logInfo('Registration queued for ${email.substring(0, 3)}***', tag: 'OFFLINE_QUEUE');
  }

  /// Check if there are queued registrations
  Future<bool> hasQueuedRegistrations() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_registrations') ?? [];
    return list.isNotEmpty;
  }

  /// Get the first queued registration without removing it
  Future<Map<String, dynamic>?> peekQueuedRegistration() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_registrations') ?? [];

    if (list.isEmpty) return null;

    try {
      return jsonDecode(list.first) as Map<String, dynamic>;
    } catch (e) {
      logError('Failed to parse queued registration: $e', tag: 'OFFLINE_QUEUE');
      return null;
    }
  }

  /// Clear all queued registrations (called after successful registration)
  Future<void> clearQueuedRegistrations() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('queued_registrations');
    logInfo('Cleared all queued registrations', tag: 'OFFLINE_QUEUE');
  }

  /// Remove the first queued registration from the queue
  Future<void> removeFirstQueuedRegistration() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_registrations') ?? [];

    if (list.isNotEmpty) {
      list.removeAt(0);
      await prefs.setStringList('queued_registrations', list);
      logInfo('Removed first queued registration', tag: 'OFFLINE_QUEUE');
    }
  }

  Future<void> _flushQueue() async {
    await _flushExpenseQueue();
    await _flushRegistrationQueue();
    await _refreshBudget();
  }

  Future<void> _flushExpenseQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_expenses') ?? [];
    final remaining = <String>[];
    for (final item in list) {
      final data = jsonDecode(item) as Map<String, dynamic>;
      try {
        await ApiService().createExpense(data);
      } catch (_) {
        remaining.add(item);
      }
    }
    await prefs.setStringList('queued_expenses', remaining);
  }

  Future<void> _flushRegistrationQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList('queued_registrations') ?? [];
    final remaining = <String>[];

    logInfo('Processing ${list.length} queued registrations', tag: 'OFFLINE_QUEUE');

    for (final item in list) {
      try {
        final data = jsonDecode(item) as Map<String, dynamic>;
        final email = data['email'] as String;
        final password = data['password'] as String;

        logInfo('Attempting queued registration for ${email.substring(0, 3)}***',
            tag: 'OFFLINE_QUEUE');

        // Use standard FastAPI registration (emergency methods removed)
        await ApiService().register(email, password);
        logInfo('Queued FastAPI registration successful for ${email.substring(0, 3)}***',
            tag: 'OFFLINE_QUEUE');
      } catch (e) {
        logWarning('Queued registration failed, keeping in queue: $e', tag: 'OFFLINE_QUEUE');
        remaining.add(item);
      }
    }

    await prefs.setStringList('queued_registrations', remaining);

    if (remaining.length < list.length) {
      logInfo('Successfully processed ${list.length - remaining.length} queued registrations',
          tag: 'OFFLINE_QUEUE');
    }
  }

  Future<void> _refreshBudget() async {
    try {
      await ApiService().getDashboard();
    } catch (e) {
      logWarning('Failed to refresh budget after sync: $e', tag: 'OFFLINE_QUEUE');
      // Non-critical - dashboard will refresh on next navigation
    }
  }
}

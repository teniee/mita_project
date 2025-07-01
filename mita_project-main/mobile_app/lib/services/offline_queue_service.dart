import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_service.dart';

class OfflineQueueService {
  OfflineQueueService._() {
    _init();
  }

  static final OfflineQueueService instance = OfflineQueueService._();

  final Connectivity _connectivity = Connectivity();
  bool _isOnline = true;

  void _init() {
    _connectivity.onConnectivityChanged.listen((result) {
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

  Future<void> _flushQueue() async {
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
    await _refreshBudget();
  }

  Future<void> _refreshBudget() async {
    try {
      await ApiService().getDashboard();
    } catch (_) {}
  }
}

import 'dart:async';
import 'package:flutter/material.dart';
import 'logging_service.dart';

/// A service that manages the global state of expenses and provides real-time updates
/// to the calendar and other screens when expenses are added, modified, or deleted.
class ExpenseStateService extends ChangeNotifier {
  // Singleton pattern
  static final ExpenseStateService _instance = ExpenseStateService._internal();
  factory ExpenseStateService() => _instance;
  ExpenseStateService._internal();

  // Current calendar data cache
  List<dynamic> _calendarData = [];
  bool _isLoading = false;
  String? _error;
  DateTime _lastUpdated = DateTime.now();

  // Stream controllers for real-time updates
  final StreamController<List<dynamic>> _calendarUpdateController =
      StreamController<List<dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _expenseAddedController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _expenseUpdatedController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<int> _expenseDeletedController =
      StreamController<int>.broadcast();

  // Getters
  List<dynamic> get calendarData => _calendarData;
  bool get isLoading => _isLoading;
  String? get error => _error;
  DateTime get lastUpdated => _lastUpdated;

  // Stream getters
  Stream<List<dynamic>> get calendarUpdates => _calendarUpdateController.stream;
  Stream<Map<String, dynamic>> get expenseAdded =>
      _expenseAddedController.stream;
  Stream<Map<String, dynamic>> get expenseUpdated =>
      _expenseUpdatedController.stream;
  Stream<int> get expenseDeleted => _expenseDeletedController.stream;

  /// Updates the calendar data cache and notifies listeners
  void updateCalendarData(List<dynamic> newData) {
    _calendarData = newData;
    _lastUpdated = DateTime.now();
    _error = null;

    logDebug('Calendar data updated with ${newData.length} items',
        tag: 'EXPENSE_STATE');

    // Notify listeners
    notifyListeners();
    _calendarUpdateController.add(newData);
  }

  /// Sets the loading state
  void setLoading(bool loading) {
    if (_isLoading != loading) {
      _isLoading = loading;
      notifyListeners();
    }
  }

  /// Sets an error state
  void setError(String? error) {
    _error = error;
    notifyListeners();
  }

  /// Optimistically adds an expense to the calendar data
  void addExpenseOptimistically(Map<String, dynamic> expenseData) {
    try {
      logDebug('Adding expense optimistically',
          tag: 'EXPENSE_STATE', extra: expenseData);

      final amount = (expenseData['amount'] as num?)?.toDouble() ?? 0.0;
      final dateString = expenseData['date'] as String?;
      final category = expenseData['action'] as String? ??
          expenseData['category'] as String?;

      if (dateString == null) {
        logWarning('Cannot add expense optimistically: missing date',
            tag: 'EXPENSE_STATE');
        return;
      }

      final expenseDate = DateTime.tryParse(dateString);
      if (expenseDate == null) {
        logWarning('Cannot parse expense date: $dateString',
            tag: 'EXPENSE_STATE');
        return;
      }

      // Find the corresponding day in calendar data and update it
      final updatedCalendarData = List<dynamic>.from(_calendarData);
      final dayNumber = expenseDate.day;

      for (int i = 0; i < updatedCalendarData.length; i++) {
        final dayData = updatedCalendarData[i];
        if (dayData is Map<String, dynamic> && dayData['day'] == dayNumber) {
          // Create a copy and update spent amount
          final updatedDay = Map<String, dynamic>.from(dayData);
          final currentSpent = (updatedDay['spent'] as num?)?.toDouble() ?? 0.0;
          updatedDay['spent'] = (currentSpent + amount).round();

          // Update status based on new spending
          final limit = (updatedDay['limit'] as num?)?.toDouble() ?? 0.0;
          final newSpent = updatedDay['spent'] as num;
          final spentRatio = limit > 0 ? newSpent / limit : 0.0;

          if (spentRatio > 1.1) {
            updatedDay['status'] = 'over';
          } else if (spentRatio > 0.85) {
            updatedDay['status'] = 'warning';
          } else {
            updatedDay['status'] = 'good';
          }

          // Update categories if available
          if (category != null &&
              updatedDay['categories'] is Map<String, dynamic>) {
            final categories = Map<String, dynamic>.from(
                updatedDay['categories'] as Map<String, dynamic>);
            final categoryKey = _mapCategoryToKey(category);
            final currentCategorySpent =
                (categories[categoryKey] as num?)?.toDouble() ?? 0.0;
            categories[categoryKey] = (currentCategorySpent + amount).round();
            updatedDay['categories'] = categories;
          }

          updatedCalendarData[i] = updatedDay;
          break;
        }
      }

      // Update the calendar data
      updateCalendarData(updatedCalendarData);

      // Emit expense added event
      _expenseAddedController.add({
        ...expenseData,
        'optimistic': true,
        'added_at': DateTime.now().toIso8601String(),
      });

      logInfo('Expense added optimistically to day $dayNumber',
          tag: 'EXPENSE_STATE',
          extra: {
            'amount': amount,
            'category': category,
            'day': dayNumber,
          });
    } catch (e, stackTrace) {
      logError('Failed to add expense optimistically',
          tag: 'EXPENSE_STATE',
          error: e,
          extra: {
            'stackTrace': stackTrace.toString(),
            'expenseData': expenseData,
          });
    }
  }

  /// Updates an existing expense in the calendar data
  void updateExpenseOptimistically(
      int expenseId, Map<String, dynamic> updatedData) {
    try {
      logDebug('Updating expense optimistically', tag: 'EXPENSE_STATE', extra: {
        'expenseId': expenseId,
        'updatedData': updatedData,
      });

      // For now, we'll treat this as removing the old expense and adding the new one
      // In a real implementation, you'd track individual expenses by ID

      // Emit expense updated event
      _expenseUpdatedController.add({
        'id': expenseId,
        ...updatedData,
        'optimistic': true,
        'updated_at': DateTime.now().toIso8601String(),
      });
    } catch (e, stackTrace) {
      logError('Failed to update expense optimistically',
          tag: 'EXPENSE_STATE',
          error: e,
          extra: {
            'stackTrace': stackTrace.toString(),
            'expenseId': expenseId,
            'updatedData': updatedData,
          });
    }
  }

  /// Removes an expense from the calendar data optimistically
  void deleteExpenseOptimistically(
      int expenseId, Map<String, dynamic> expenseData) {
    try {
      logDebug('Deleting expense optimistically', tag: 'EXPENSE_STATE', extra: {
        'expenseId': expenseId,
        'expenseData': expenseData,
      });

      final amount = (expenseData['amount'] as num?)?.toDouble() ?? 0.0;
      final dateString = expenseData['date'] as String?;

      if (dateString == null) return;

      final expenseDate = DateTime.tryParse(dateString);
      if (expenseDate == null) return;

      // Find the corresponding day in calendar data and update it
      final updatedCalendarData = List<dynamic>.from(_calendarData);
      final dayNumber = expenseDate.day;

      for (int i = 0; i < updatedCalendarData.length; i++) {
        final dayData = updatedCalendarData[i];
        if (dayData is Map<String, dynamic> && dayData['day'] == dayNumber) {
          // Create a copy and update spent amount
          final updatedDay = Map<String, dynamic>.from(dayData);
          final currentSpent = (updatedDay['spent'] as num?)?.toDouble() ?? 0.0;
          updatedDay['spent'] =
              (currentSpent - amount).round().clamp(0, double.infinity).round();

          // Update status based on new spending
          final limit = (updatedDay['limit'] as num?)?.toDouble() ?? 0.0;
          final newSpent = updatedDay['spent'] as num;
          final spentRatio = limit > 0 ? newSpent / limit : 0.0;

          if (spentRatio > 1.1) {
            updatedDay['status'] = 'over';
          } else if (spentRatio > 0.85) {
            updatedDay['status'] = 'warning';
          } else {
            updatedDay['status'] = 'good';
          }

          updatedCalendarData[i] = updatedDay;
          break;
        }
      }

      // Update the calendar data
      updateCalendarData(updatedCalendarData);

      // Emit expense deleted event
      _expenseDeletedController.add(expenseId);

      logInfo('Expense deleted optimistically from day $dayNumber',
          tag: 'EXPENSE_STATE',
          extra: {
            'expenseId': expenseId,
            'amount': amount,
            'day': dayNumber,
          });
    } catch (e, stackTrace) {
      logError('Failed to delete expense optimistically',
          tag: 'EXPENSE_STATE',
          error: e,
          extra: {
            'stackTrace': stackTrace.toString(),
            'expenseId': expenseId,
            'expenseData': expenseData,
          });
    }
  }

  /// Rollback optimistic changes in case of API failure
  void rollbackOptimisticChanges(List<dynamic> previousCalendarData) {
    logWarning('Rolling back optimistic changes', tag: 'EXPENSE_STATE');
    updateCalendarData(previousCalendarData);
  }

  /// Map category names to calendar category keys
  String _mapCategoryToKey(String category) {
    switch (category.toLowerCase()) {
      case 'food':
      case 'food & dining':
        return 'food';
      case 'transport':
      case 'transportation':
        return 'transportation';
      case 'entertainment':
      case 'fun':
        return 'entertainment';
      case 'shopping':
      case 'retail':
        return 'shopping';
      case 'health':
      case 'healthcare':
        return 'healthcare';
      case 'utilities':
        return 'utilities';
      case 'education':
        return 'education';
      default:
        return 'other';
    }
  }

  /// Refresh calendar data from API (called after successful API operations)
  void refreshCalendarData() {
    logDebug('Triggering calendar data refresh', tag: 'EXPENSE_STATE');
    // This will be called by the calendar screen to refresh its data
    notifyListeners();
  }

  /// Clear all data (useful for logout)
  void clear() {
    _calendarData.clear();
    _isLoading = false;
    _error = null;
    _lastUpdated = DateTime.now();
    notifyListeners();

    logDebug('Expense state cleared', tag: 'EXPENSE_STATE');
  }

  /// Get spending status for a specific day
  Map<String, dynamic>? getDayStatus(int dayNumber) {
    try {
      for (final dayData in _calendarData) {
        if (dayData is Map<String, dynamic> && dayData['day'] == dayNumber) {
          return Map<String, dynamic>.from(dayData);
        }
      }
    } catch (e) {
      logError('Failed to get day status for day $dayNumber',
          tag: 'EXPENSE_STATE', error: e);
    }
    return null;
  }

  /// Get total spending for current month
  double getTotalMonthSpending() {
    try {
      double total = 0.0;
      for (final dayData in _calendarData) {
        if (dayData is Map<String, dynamic>) {
          final spent = (dayData['spent'] as num?)?.toDouble() ?? 0.0;
          total += spent;
        }
      }
      return total;
    } catch (e) {
      logError('Failed to calculate total month spending',
          tag: 'EXPENSE_STATE', error: e);
      return 0.0;
    }
  }

  /// Get total budget for current month
  double getTotalMonthBudget() {
    try {
      double total = 0.0;
      for (final dayData in _calendarData) {
        if (dayData is Map<String, dynamic>) {
          final limit = (dayData['limit'] as num?)?.toDouble() ?? 0.0;
          total += limit;
        }
      }
      return total;
    } catch (e) {
      logError('Failed to calculate total month budget',
          tag: 'EXPENSE_STATE', error: e);
      return 0.0;
    }
  }

  @override
  void dispose() {
    _calendarUpdateController.close();
    _expenseAddedController.close();
    _expenseUpdatedController.close();
    _expenseDeletedController.close();
    super.dispose();
  }
}

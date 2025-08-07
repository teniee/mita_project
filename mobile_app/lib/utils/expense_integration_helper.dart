import 'package:flutter/material.dart';
import 'dart:async';
import '../services/expense_state_service.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// Helper class that provides utilities for integrating expense-related functionality
/// across different screens and maintaining real-time synchronization
class ExpenseIntegrationHelper {
  static final ExpenseStateService _expenseStateService = ExpenseStateService();
  static final ApiService _apiService = ApiService();

  /// Navigate to add expense screen with proper result handling and real-time updates
  static Future<Map<String, dynamic>?> navigateToAddExpense(BuildContext context) async {
    logDebug('Navigating to add expense screen', tag: 'EXPENSE_INTEGRATION');

    try {
      final result = await Navigator.pushNamed(context, '/add_expense');
      
      if (result != null && result is Map<String, dynamic>) {
        logInfo('Add expense navigation completed', tag: 'EXPENSE_INTEGRATION', extra: {
          'success': result['success'],
          'amount': result['amount'],
          'category': result['category'],
        });

        // Show success feedback if not already shown
        if (result['success'] == true && context.mounted) {
          _showGlobalSuccessFeedback(context, result);
        }

        return result;
      }
    } catch (e, stackTrace) {
      logError('Failed to navigate to add expense', tag: 'EXPENSE_INTEGRATION', error: e, extra: {
        'stackTrace': stackTrace.toString(),
      });

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error, color: Colors.white),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Failed to open expense form. Please try again.',
                    style: TextStyle(fontFamily: 'Manrope'),
                  ),
                ),
              ],
            ),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }

    return null;
  }

  /// Refresh calendar data from API and update state service
  static Future<void> refreshCalendarData({bool showLoading = false}) async {
    logDebug('Refreshing calendar data', tag: 'EXPENSE_INTEGRATION', extra: {
      'showLoading': showLoading,
    });

    if (showLoading) {
      _expenseStateService.setLoading(true);
    }

    try {
      final data = await _apiService.getCalendar();
      _expenseStateService.updateCalendarData(data);
      
      logInfo('Calendar data refreshed successfully', tag: 'EXPENSE_INTEGRATION', extra: {
        'dataCount': data.length,
      });
    } catch (e) {
      logError('Failed to refresh calendar data', tag: 'EXPENSE_INTEGRATION', error: e);
      _expenseStateService.setError('Failed to refresh calendar data');
    } finally {
      if (showLoading) {
        _expenseStateService.setLoading(false);
      }
    }
  }

  /// Get current spending status for today
  static Map<String, dynamic>? getTodaySpendingStatus() {
    final today = DateTime.now().day;
    final dayStatus = _expenseStateService.getDayStatus(today);
    
    if (dayStatus != null) {
      logDebug('Retrieved today\'s spending status', tag: 'EXPENSE_INTEGRATION', extra: {
        'day': today,
        'status': dayStatus['status'],
        'spent': dayStatus['spent'],
        'limit': dayStatus['limit'],
      });
    }

    return dayStatus;
  }

  /// Check if user is over budget for today
  static bool isOverBudgetToday() {
    final todayStatus = getTodaySpendingStatus();
    return todayStatus?['status'] == 'over';
  }

  /// Get spending percentage for today
  static double getTodaySpendingPercentage() {
    final todayStatus = getTodaySpendingStatus();
    if (todayStatus == null) return 0.0;

    final spent = (todayStatus['spent'] as num?)?.toDouble() ?? 0.0;
    final limit = (todayStatus['limit'] as num?)?.toDouble() ?? 0.0;
    
    return limit > 0 ? (spent / limit) * 100 : 0.0;
  }

  /// Get remaining budget for today
  static double getTodayRemainingBudget() {
    final todayStatus = getTodaySpendingStatus();
    if (todayStatus == null) return 0.0;

    final spent = (todayStatus['spent'] as num?)?.toDouble() ?? 0.0;
    final limit = (todayStatus['limit'] as num?)?.toDouble() ?? 0.0;
    
    return (limit - spent).clamp(0.0, double.infinity);
  }

  /// Show a consolidated success feedback across the app
  static void _showGlobalSuccessFeedback(BuildContext context, Map<String, dynamic> result) {
    final amount = result['amount'] as double?;
    final category = result['category'] as String?;

    if (amount == null || category == null) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Container(
          padding: const EdgeInsets.all(4),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.trending_up,
                  color: Colors.white,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Budget Updated!',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                    Text(
                      '\$${amount.toStringAsFixed(2)} added to $category',
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 12,
                        color: Colors.white70,
                      ),
                    ),
                  ],
                ),
              ),
              TextButton(
                onPressed: () {
                  ScaffoldMessenger.of(context).hideCurrentSnackBar();
                },
                child: const Text(
                  'VIEW',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ),
        backgroundColor: Colors.green.shade600,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 4),
        margin: const EdgeInsets.all(16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }

  /// Listen to expense state changes and provide callbacks
  static StreamSubscription<List<dynamic>> listenToCalendarUpdates(
    Function(List<dynamic>) onUpdate,
  ) {
    return _expenseStateService.calendarUpdates.listen(onUpdate);
  }

  /// Listen to expense additions and provide callbacks  
  static StreamSubscription<Map<String, dynamic>> listenToExpenseAdditions(
    Function(Map<String, dynamic>) onExpenseAdded,
  ) {
    return _expenseStateService.expenseAdded.listen(onExpenseAdded);
  }

  /// Get the expense state service instance (for advanced usage)
  static ExpenseStateService get expenseStateService => _expenseStateService;

  /// Check if calendar data is stale and needs refresh
  static bool isCalendarDataStale({Duration threshold = const Duration(minutes: 5)}) {
    final timeSinceUpdate = DateTime.now().difference(_expenseStateService.lastUpdated);
    return timeSinceUpdate > threshold;
  }

  /// Get a summary of current month spending
  static Map<String, dynamic> getMonthSummary() {
    final totalSpent = _expenseStateService.getTotalMonthSpending();
    final totalBudget = _expenseStateService.getTotalMonthBudget();
    final spentPercentage = totalBudget > 0 ? (totalSpent / totalBudget) * 100 : 0.0;

    return {
      'total_spent': totalSpent,
      'total_budget': totalBudget,
      'spent_percentage': spentPercentage,
      'remaining_budget': totalBudget - totalSpent,
      'is_over_budget': spentPercentage > 100,
      'status': spentPercentage > 100 
          ? 'over' 
          : spentPercentage > 85 
              ? 'warning' 
              : 'good',
    };
  }

  /// Show budget warning if user is approaching or over limit
  static void showBudgetWarningIfNeeded(BuildContext context) {
    final summary = getMonthSummary();
    final spentPercentage = summary['spent_percentage'] as double;
    
    if (spentPercentage > 90 && context.mounted) {
      final isOver = spentPercentage > 100;
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(
                isOver ? Icons.warning : Icons.info,
                color: Colors.white,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      isOver ? 'Over Budget!' : 'Budget Warning',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      isOver 
                          ? 'You\'ve exceeded your monthly budget'
                          : 'You\'ve used ${spentPercentage.toStringAsFixed(0)}% of your budget',
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          backgroundColor: isOver ? Colors.red.shade600 : Colors.orange.shade600,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 5),
        ),
      );
    }
  }
}
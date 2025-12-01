import 'package:flutter/foundation.dart';
import '../models/transaction_model.dart';
import '../services/transaction_service.dart';
import '../services/logging_service.dart';

/// Transaction state enum for tracking loading states
enum TransactionState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized transaction state management provider
/// Manages transaction list, filtering, and CRUD operations
class TransactionProvider extends ChangeNotifier {
  final TransactionService _transactionService = TransactionService();

  // State
  TransactionState _state = TransactionState.initial;
  bool _isLoading = false;
  String? _errorMessage;

  // Transaction data
  List<TransactionModel> _transactions = [];
  Map<String, double> _spendingByCategory = {};
  double _totalSpending = 0.0;

  // Filter state
  String? _selectedCategory;
  DateTime? _startDate;
  DateTime? _endDate;

  // Getters
  TransactionState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  List<TransactionModel> get transactions => _transactions;
  Map<String, double> get spendingByCategory => _spendingByCategory;
  double get totalSpending => _totalSpending;
  String? get selectedCategory => _selectedCategory;
  DateTime? get startDate => _startDate;
  DateTime? get endDate => _endDate;

  // Transaction count
  int get transactionCount => _transactions.length;

  /// Initialize the provider and load transactions
  Future<void> initialize() async {
    if (_state != TransactionState.initial) return;

    logInfo('Initializing TransactionProvider', tag: 'TRANSACTION_PROVIDER');
    await loadTransactions();
  }

  /// Load transactions with current filters
  Future<void> loadTransactions() async {
    _setLoading(true);
    _state = TransactionState.loading;
    notifyListeners();

    try {
      final transactions = await _transactionService.getTransactions(
        category: _selectedCategory,
        startDate: _startDate,
        endDate: _endDate,
        limit: 100,
      );

      _transactions = transactions;
      _calculateTotalSpending();
      _state = TransactionState.loaded;

      logInfo('Transactions loaded: ${_transactions.length} items',
          tag: 'TRANSACTION_PROVIDER');
    } catch (e) {
      logError('Error loading transactions: $e', tag: 'TRANSACTION_PROVIDER');
      _transactions = [];
      _errorMessage = e.toString();
      _state = TransactionState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load transactions for a specific date range
  Future<void> loadTransactionsByDateRange({
    required DateTime startDate,
    required DateTime endDate,
    String? category,
  }) async {
    _startDate = startDate;
    _endDate = endDate;
    _selectedCategory = category;
    await loadTransactions();
  }

  /// Load transactions for a specific month
  Future<void> loadMonthlyTransactions({
    required int year,
    required int month,
    String? category,
  }) async {
    _startDate = DateTime(year, month, 1);
    _endDate = DateTime(year, month + 1, 0, 23, 59, 59);
    _selectedCategory = category;
    await loadTransactions();
  }

  /// Load recent transactions
  Future<void> loadRecentTransactions({int days = 7, int limit = 50}) async {
    _endDate = DateTime.now();
    _startDate = _endDate!.subtract(Duration(days: days));
    _selectedCategory = null;

    try {
      _setLoading(true);
      final transactions = await _transactionService.getRecentTransactions(
        days: days,
        limit: limit,
      );
      _transactions = transactions;
      _calculateTotalSpending();
      _state = TransactionState.loaded;
      logInfo('Recent transactions loaded: ${_transactions.length} items',
          tag: 'TRANSACTION_PROVIDER');
    } catch (e) {
      logError('Error loading recent transactions: $e',
          tag: 'TRANSACTION_PROVIDER');
      _errorMessage = e.toString();
    } finally {
      _setLoading(false);
    }
  }

  /// Create a new transaction
  Future<TransactionModel?> createTransaction(TransactionInput input) async {
    try {
      _setLoading(true);

      final transaction = await _transactionService.createTransaction(input);

      // Add to local list
      _transactions.insert(0, transaction);
      _calculateTotalSpending();

      logInfo('Transaction created: ${transaction.id}',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();

      return transaction;
    } catch (e) {
      logError('Error creating transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to create transaction';
      return null;
    } finally {
      _setLoading(false);
    }
  }

  /// Update an existing transaction
  Future<TransactionModel?> updateTransaction(
    String transactionId,
    TransactionInput input,
  ) async {
    try {
      _setLoading(true);

      final updatedTransaction = await _transactionService.updateTransaction(
        transactionId,
        input,
      );

      // Update in local list
      final index = _transactions.indexWhere((t) => t.id == transactionId);
      if (index != -1) {
        _transactions[index] = updatedTransaction;
        _calculateTotalSpending();
      }

      logInfo('Transaction updated: $transactionId',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();

      return updatedTransaction;
    } catch (e) {
      logError('Error updating transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to update transaction';
      return null;
    } finally {
      _setLoading(false);
    }
  }

  /// Delete a transaction
  Future<bool> deleteTransaction(String transactionId) async {
    try {
      _setLoading(true);

      await _transactionService.deleteTransaction(transactionId);

      // Remove from local list
      _transactions.removeWhere((t) => t.id == transactionId);
      _calculateTotalSpending();

      logInfo('Transaction deleted: $transactionId',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();

      return true;
    } catch (e) {
      logError('Error deleting transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to delete transaction';
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Get spending by category
  Future<void> loadSpendingByCategory({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final categoryTotals = await _transactionService.getSpendingByCategory(
        startDate: startDate,
        endDate: endDate,
      );
      _spendingByCategory = categoryTotals;

      logInfo(
          'Spending by category loaded: ${_spendingByCategory.length} categories',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();
    } catch (e) {
      logError('Error loading spending by category: $e',
          tag: 'TRANSACTION_PROVIDER');
    }
  }

  /// Set category filter
  void setCategory(String? category) {
    if (_selectedCategory != category) {
      _selectedCategory = category;
      loadTransactions();
    }
  }

  /// Set date range filter
  void setDateRange(DateTime? start, DateTime? end) {
    _startDate = start;
    _endDate = end;
    loadTransactions();
  }

  /// Clear all filters
  void clearFilters() {
    _selectedCategory = null;
    _startDate = null;
    _endDate = null;
    loadTransactions();
  }

  /// Get transactions for today
  List<TransactionModel> getTodayTransactions() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return _transactions.where((t) {
      final transactionDate =
          DateTime(t.spentAt.year, t.spentAt.month, t.spentAt.day);
      return transactionDate == today;
    }).toList();
  }

  /// Get transactions for this week
  List<TransactionModel> getThisWeekTransactions() {
    final now = DateTime.now();
    final weekStart = now.subtract(Duration(days: now.weekday - 1));
    final startOfWeek =
        DateTime(weekStart.year, weekStart.month, weekStart.day);
    return _transactions.where((t) => t.spentAt.isAfter(startOfWeek)).toList();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  /// Refresh transactions
  Future<void> refresh() async {
    await loadTransactions();
  }

  // Private helper to calculate total spending
  void _calculateTotalSpending() {
    _totalSpending = _transactions.fold<double>(
      0.0,
      (sum, transaction) => sum + transaction.amount,
    );

    // Also calculate by category
    _spendingByCategory = {};
    for (final transaction in _transactions) {
      _spendingByCategory[transaction.category] =
          (_spendingByCategory[transaction.category] ?? 0.0) +
              transaction.amount;
    }
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
}

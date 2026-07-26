import 'package:flutter/foundation.dart';
import '../models/transaction_model.dart';
import '../services/transaction_service.dart';
import '../services/api_service.dart';
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
  final TransactionService _transactionService;
  final ApiService _apiService;

  TransactionProvider({
    TransactionService? transactionService,
    ApiService? apiService,
  })  : _transactionService = transactionService ?? TransactionService(),
        _apiService = apiService ?? ApiService();

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
  int _sessionGeneration = 0;
  int _loadRequestId = 0;
  Future<void>? _initializeInFlight;
  int? _initializeGeneration;

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
  Future<void> initialize() {
    if (_state != TransactionState.initial) return Future.value();

    final generation = _sessionGeneration;
    final inFlight = _initializeInFlight;
    if (inFlight != null && _initializeGeneration == generation) {
      return inFlight;
    }

    final future = _doInitialize(generation);
    _initializeInFlight = future;
    _initializeGeneration = generation;
    future.whenComplete(() {
      if (identical(_initializeInFlight, future) &&
          _initializeGeneration == generation) {
        _initializeInFlight = null;
        _initializeGeneration = null;
      }
    });
    return future;
  }

  Future<void> _doInitialize(int generation) async {
    logInfo('Initializing TransactionProvider', tag: 'TRANSACTION_PROVIDER');

    // CRITICAL FIX: Check if user has a valid token before making API calls
    final token = await _apiService.getToken();
    if (generation != _sessionGeneration) return;
    if (token == null || token.isEmpty) {
      logWarning(
          'No authentication token found - skipping transactions initialization',
          tag: 'TRANSACTION_PROVIDER');
      _state = TransactionState.error;
      _errorMessage = 'Not authenticated';
      notifyListeners();
      return;
    }

    await loadTransactions(sessionGeneration: generation);
  }

  /// Load transactions with current filters
  Future<void> loadTransactions({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    final requestId = ++_loadRequestId;
    final selectedCategory = _selectedCategory;
    final startDate = _startDate;
    final endDate = _endDate;
    _setLoading(true);
    _state = TransactionState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      final transactions = await _transactionService.getTransactions(
        category: selectedCategory,
        startDate: startDate,
        endDate: endDate,
        limit: 100,
      );
      if (!_isCurrent(generation) || requestId != _loadRequestId) return;

      _transactions = transactions;
      _calculateTotalSpending();
      _state = TransactionState.loaded;

      logInfo('Transactions loaded: ${_transactions.length} items',
          tag: 'TRANSACTION_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation) || requestId != _loadRequestId) return;
      logError('Error loading transactions: $e', tag: 'TRANSACTION_PROVIDER');
      _transactions = [];
      _calculateTotalSpending();
      _errorMessage = e.toString();
      _state = TransactionState.error;
    } finally {
      if (_isCurrent(generation) && requestId == _loadRequestId) {
        _setLoading(false);
      }
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
    final generation = _sessionGeneration;
    final requestId = ++_loadRequestId;
    _endDate = DateTime.now();
    _startDate = _endDate!.subtract(Duration(days: days));
    _selectedCategory = null;

    try {
      _setLoading(true);
      final transactions = await _transactionService.getRecentTransactions(
        days: days,
        limit: limit,
      );
      if (!_isCurrent(generation) || requestId != _loadRequestId) return;
      _transactions = transactions;
      _calculateTotalSpending();
      _state = TransactionState.loaded;
      _errorMessage = null;
      logInfo('Recent transactions loaded: ${_transactions.length} items',
          tag: 'TRANSACTION_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation) || requestId != _loadRequestId) return;
      logError('Error loading recent transactions: $e',
          tag: 'TRANSACTION_PROVIDER');
      _errorMessage = e.toString();
      _state = TransactionState.error;
    } finally {
      if (_isCurrent(generation) && requestId == _loadRequestId) {
        _setLoading(false);
      }
    }
  }

  /// Create a new transaction
  Future<TransactionModel?> createTransaction(TransactionInput input) async {
    final generation = _sessionGeneration;
    // A list request started before this mutation represents pre-write state
    // and must not overwrite the newly created transaction when it completes.
    _loadRequestId += 1;
    try {
      _setLoading(true);

      final transaction = await _transactionService.createTransaction(input);
      if (!_isCurrent(generation)) return null;

      // Add to local list
      _transactions.insert(0, transaction);
      _calculateTotalSpending();

      logInfo('Transaction created: ${transaction.id}',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();

      return transaction;
    } catch (e) {
      if (!_isCurrent(generation)) return null;
      logError('Error creating transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to create transaction';
      return null;
    } finally {
      if (_isCurrent(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Update an existing transaction
  Future<TransactionModel?> updateTransaction(
    String transactionId,
    TransactionInput input,
  ) async {
    final generation = _sessionGeneration;
    _loadRequestId += 1;
    try {
      _setLoading(true);

      final updatedTransaction = await _transactionService.updateTransaction(
        transactionId,
        input,
      );
      if (!_isCurrent(generation)) return null;

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
      if (!_isCurrent(generation)) return null;
      logError('Error updating transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to update transaction';
      return null;
    } finally {
      if (_isCurrent(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Delete a transaction
  Future<bool> deleteTransaction(String transactionId) async {
    final generation = _sessionGeneration;
    _loadRequestId += 1;
    try {
      _setLoading(true);

      await _transactionService.deleteTransaction(transactionId);
      if (!_isCurrent(generation)) return false;

      // Remove from local list
      _transactions.removeWhere((t) => t.id == transactionId);
      _calculateTotalSpending();

      logInfo('Transaction deleted: $transactionId',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();

      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Error deleting transaction: $e', tag: 'TRANSACTION_PROVIDER');
      _errorMessage = 'Failed to delete transaction';
      return false;
    } finally {
      if (_isCurrent(generation)) {
        _setLoading(false);
      }
    }
  }

  /// Get spending by category
  Future<void> loadSpendingByCategory({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final generation = _sessionGeneration;
    try {
      final categoryTotals = await _transactionService.getSpendingByCategory(
        startDate: startDate,
        endDate: endDate,
      );
      if (!_isCurrent(generation)) return;
      _spendingByCategory = categoryTotals;

      logInfo(
          'Spending by category loaded: ${_spendingByCategory.length} categories',
          tag: 'TRANSACTION_PROVIDER');
      notifyListeners();
    } catch (e) {
      if (!_isCurrent(generation)) return;
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

  /// Clear all account-scoped state immediately at an authentication boundary.
  ///
  /// Incrementing the generation first makes every response already in flight
  /// obsolete, so a slow request from user A cannot repopulate user B's UI.
  void resetSession() {
    _sessionGeneration += 1;
    _loadRequestId += 1;
    _initializeInFlight = null;
    _initializeGeneration = null;
    _transactions = [];
    _spendingByCategory = {};
    _totalSpending = 0.0;
    _selectedCategory = null;
    _startDate = null;
    _endDate = null;
    _errorMessage = null;
    _isLoading = false;
    _state = TransactionState.initial;
    notifyListeners();
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

  bool _isCurrent(int generation) => generation == _sessionGeneration;
}

import 'package:dio/dio.dart';
import '../models/transaction_model.dart';
import 'api_service.dart';
import 'logging_service.dart';
import '../utils/json_utils.dart';

/// Transaction Service
/// Handles all transaction-related API calls.
///
/// Every request goes through ApiService.authedDio, the interceptor-equipped
/// Dio instance: it attaches the current access token on each request and, on
/// a 401, transparently refreshes the token and replays the request once.
/// This service previously used the raw `http` package with a manually
/// fetched token, which bypassed that interceptor entirely — an expired
/// access token then failed every create/edit/delete with "Unauthorized"
/// and no refresh attempt (device-reproduced during the core journey).
class TransactionService {
  final ApiService _apiService = ApiService();

  Dio get _dio => _apiService.authedDio;

  Never _mapError(DioException e, String action) {
    final code = e.response?.statusCode;
    if (code == 404) {
      throw Exception('Transaction not found');
    }
    if (code == 401) {
      // Reached only when refresh itself failed (rotation exhausted / refresh
      // token expired) — a genuine re-login case, not a transient token expiry.
      throw Exception('Unauthorized - please log in again');
    }
    if (code == 400) {
      final error = asStringKeyedMap(e.response?.data);
      throw Exception(
          asString(error['detail'], fallback: 'Invalid transaction data'));
    }
    throw Exception('Failed to $action: ${code ?? e.message}');
  }

  /// Get all transactions with optional filters
  Future<List<TransactionModel>> getTransactions({
    int skip = 0,
    int limit = 100,
    DateTime? startDate,
    DateTime? endDate,
    String? category,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'skip': skip,
        'limit': limit,
      };
      if (startDate != null) {
        queryParams['start_date'] = startDate.toUtc().toIso8601String();
      }
      if (endDate != null) {
        queryParams['end_date'] = endDate.toUtc().toIso8601String();
      }
      if (category != null && category.isNotEmpty) {
        queryParams['category'] = category;
      }

      // Collection route is '/transactions/' — the slashless form triggers a
      // 307 redirect and some HTTP clients drop the Authorization header
      // across redirects (DEF-008).
      final response = await _dio.get<dynamic>(
        '/transactions/',
        queryParameters: queryParams,
      );

      final data = response.data;
      List<dynamic> transactionList;
      if (data is Map && data.containsKey('data')) {
        if (data['data'] is List) {
          transactionList = data['data'] as List<dynamic>;
        } else if (data['data'] is Map &&
            asStringKeyedMap(data['data'])['transactions'] != null) {
          transactionList =
              asList(asStringKeyedMap(data['data'])['transactions']);
        } else {
          transactionList = [];
        }
      } else if (data is List) {
        transactionList = data;
      } else {
        transactionList = [];
      }

      return transactionList
          .map((json) => TransactionModel.fromJson(
              Map<String, dynamic>.from(json as Map)))
          .toList();
    } on DioException catch (e) {
      logError('Error loading transactions: ${e.message}');
      _mapError(e, 'load transactions');
    } catch (e) {
      logError('Error loading transactions: $e');
      rethrow;
    }
  }

  /// Get a single transaction by ID
  Future<TransactionModel> getTransaction(String transactionId) async {
    try {
      final response =
          await _dio.get<dynamic>('/transactions/$transactionId');
      final data = response.data;
      final transactionData =
          data is Map && data.containsKey('data') ? data['data'] : data;
      return TransactionModel.fromJson(
          Map<String, dynamic>.from(transactionData as Map));
    } on DioException catch (e) {
      logError('Error loading transaction: ${e.message}');
      _mapError(e, 'load transaction');
    } catch (e) {
      logError('Error loading transaction: $e');
      rethrow;
    }
  }

  /// Create a new transaction
  Future<TransactionModel> createTransaction(TransactionInput input) async {
    try {
      final response = await _dio.post<dynamic>(
        // Trailing slash required — see DEF-008 note in getTransactions.
        '/transactions/',
        data: input.toJson(),
      );
      final data = response.data;
      final transactionData =
          data is Map && data.containsKey('data') ? data['data'] : data;
      return TransactionModel.fromJson(
          Map<String, dynamic>.from(transactionData as Map));
    } on DioException catch (e) {
      logError('Error creating transaction: ${e.message}');
      _mapError(e, 'create transaction');
    } catch (e) {
      logError('Error creating transaction: $e');
      rethrow;
    }
  }

  /// Update an existing transaction
  Future<TransactionModel> updateTransaction(
    String transactionId,
    TransactionInput input,
  ) async {
    try {
      final response = await _dio.put<dynamic>(
        '/transactions/$transactionId',
        data: input.toJson(),
      );
      final data = response.data;
      final transactionData =
          data is Map && data.containsKey('data') ? data['data'] : data;
      return TransactionModel.fromJson(
          Map<String, dynamic>.from(transactionData as Map));
    } on DioException catch (e) {
      logError('Error updating transaction: ${e.message}');
      _mapError(e, 'update transaction');
    } catch (e) {
      logError('Error updating transaction: $e');
      rethrow;
    }
  }

  /// Delete a transaction
  Future<bool> deleteTransaction(String transactionId) async {
    try {
      await _dio.delete<dynamic>('/transactions/$transactionId');
      return true;
    } on DioException catch (e) {
      logError('Error deleting transaction: ${e.message}');
      _mapError(e, 'delete transaction');
    } catch (e) {
      logError('Error deleting transaction: $e');
      rethrow;
    }
  }

  /// Get transactions by date range
  Future<List<TransactionModel>> getTransactionsByDateRange({
    required DateTime startDate,
    required DateTime endDate,
    String? category,
  }) async {
    return getTransactions(
      startDate: startDate,
      endDate: endDate,
      category: category,
      limit: 1000,
    );
  }

  /// Get transactions for a specific month
  Future<List<TransactionModel>> getMonthlyTransactions({
    required int year,
    required int month,
    String? category,
  }) async {
    final startDate = DateTime(year, month, 1);
    final endDate = DateTime(year, month + 1, 0, 23, 59, 59);

    return getTransactionsByDateRange(
      startDate: startDate,
      endDate: endDate,
      category: category,
    );
  }

  /// Get recent transactions (last [days] days)
  Future<List<TransactionModel>> getRecentTransactions({
    int days = 7,
    int limit = 50,
  }) async {
    final endDate = DateTime.now();
    final startDate = endDate.subtract(Duration(days: days));

    return getTransactions(
      startDate: startDate,
      endDate: endDate,
      limit: limit,
    );
  }

  /// Get transactions by category
  Future<List<TransactionModel>> getTransactionsByCategory(
    String category, {
    int limit = 100,
  }) async {
    return getTransactions(category: category, limit: limit);
  }

  /// Calculate total spending for a date range
  Future<double> calculateTotalSpending({
    DateTime? startDate,
    DateTime? endDate,
    String? category,
  }) async {
    final transactions = await getTransactions(
      startDate: startDate,
      endDate: endDate,
      category: category,
      limit: 10000,
    );

    return transactions.fold<double>(
      0.0,
      (sum, transaction) => sum + transaction.amount,
    );
  }

  /// Get spending totals grouped by category
  Future<Map<String, double>> getSpendingByCategory({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final transactions = await getTransactions(
      startDate: startDate,
      endDate: endDate,
      limit: 10000,
    );

    final categoryTotals = <String, double>{};
    for (final transaction in transactions) {
      categoryTotals[transaction.category] =
          (categoryTotals[transaction.category] ?? 0.0) + transaction.amount;
    }
    return categoryTotals;
  }
}

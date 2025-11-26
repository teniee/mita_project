import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config_clean.dart';
import '../models/transaction_model.dart';
import 'api_service.dart';
import 'logging_service.dart';

/// Transaction Service
/// Handles all transaction-related API calls
class TransactionService {
  final ApiService _apiService = ApiService();

  /// Get all transactions with optional filters
  Future<List<TransactionModel>> getTransactions({
    int skip = 0,
    int limit = 100,
    DateTime? startDate,
    DateTime? endDate,
    String? category,
  }) async {
    try {
      final token = await _apiService.getToken();
      if (token == null) {
        throw Exception('Not authenticated');
      }

      // Build query parameters
      final queryParams = <String, String>{
        'skip': skip.toString(),
        'limit': limit.toString(),
      };

      if (startDate != null) {
        queryParams['start_date'] = startDate.toIso8601String();
      }
      if (endDate != null) {
        queryParams['end_date'] = endDate.toIso8601String();
      }
      if (category != null && category.isNotEmpty) {
        queryParams['category'] = category;
      }

      final uri = Uri.parse('${AppConfig.fullApiUrl}/transactions')
          .replace(queryParameters: queryParams);

      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);

        // Handle different response formats
        List<dynamic> transactionList;
        if (data is Map && data.containsKey('data')) {
          if (data['data'] is List) {
            transactionList = data['data'] as List<dynamic>;
          } else if (data['data'] is Map && data['data']['transactions'] != null) {
            transactionList = data['data']['transactions'] as List<dynamic>;
          } else {
            transactionList = [];
          }
        } else if (data is List) {
          transactionList = data as List<dynamic>;
        } else {
          transactionList = [];
        }

        return transactionList
            .map((json) => TransactionModel.fromJson(json as Map<String, dynamic>))
            .toList();
      } else if (response.statusCode == 401) {
        throw Exception('Unauthorized - please log in again');
      } else {
        throw Exception('Failed to load transactions: ${response.statusCode}');
      }
    } catch (e) {
      logError('Error loading transactions: $e');
      rethrow;
    }
  }

  /// Get a single transaction by ID
  Future<TransactionModel> getTransaction(String transactionId) async {
    try {
      final token = await _apiService.getToken();
      if (token == null) {
        throw Exception('Not authenticated');
      }

      final response = await http.get(
        Uri.parse('${AppConfig.fullApiUrl}/transactions/$transactionId'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);

        // Handle wrapped response
        final transactionData = data is Map && data.containsKey('data')
            ? data['data']
            : data;

        return TransactionModel.fromJson(transactionData as Map<String, dynamic>);
      } else if (response.statusCode == 404) {
        throw Exception('Transaction not found');
      } else if (response.statusCode == 401) {
        throw Exception('Unauthorized - please log in again');
      } else {
        throw Exception('Failed to load transaction: ${response.statusCode}');
      }
    } catch (e) {
      logError('Error loading transaction: $e');
      rethrow;
    }
  }

  /// Create a new transaction
  Future<TransactionModel> createTransaction(TransactionInput input) async {
    try {
      final token = await _apiService.getToken();
      if (token == null) {
        throw Exception('Not authenticated');
      }

      final response = await http.post(
        Uri.parse('${AppConfig.fullApiUrl}/transactions'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode(input.toJson()),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = json.decode(response.body);

        // Handle wrapped response
        final transactionData = data is Map && data.containsKey('data')
            ? data['data']
            : data;

        return TransactionModel.fromJson(transactionData as Map<String, dynamic>);
      } else if (response.statusCode == 401) {
        throw Exception('Unauthorized - please log in again');
      } else if (response.statusCode == 400) {
        final error = json.decode(response.body);
        throw Exception(error['detail'] ?? 'Invalid transaction data');
      } else {
        throw Exception('Failed to create transaction: ${response.statusCode}');
      }
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
      final token = await _apiService.getToken();
      if (token == null) {
        throw Exception('Not authenticated');
      }

      final response = await http.put(
        Uri.parse('${AppConfig.fullApiUrl}/transactions/$transactionId'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode(input.toJson()),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);

        // Handle wrapped response
        final transactionData = data is Map && data.containsKey('data')
            ? data['data']
            : data;

        return TransactionModel.fromJson(transactionData as Map<String, dynamic>);
      } else if (response.statusCode == 404) {
        throw Exception('Transaction not found');
      } else if (response.statusCode == 401) {
        throw Exception('Unauthorized - please log in again');
      } else if (response.statusCode == 400) {
        final error = json.decode(response.body);
        throw Exception(error['detail'] ?? 'Invalid transaction data');
      } else {
        throw Exception('Failed to update transaction: ${response.statusCode}');
      }
    } catch (e) {
      logError('Error updating transaction: $e');
      rethrow;
    }
  }

  /// Delete a transaction
  Future<bool> deleteTransaction(String transactionId) async {
    try {
      final token = await _apiService.getToken();
      if (token == null) {
        throw Exception('Not authenticated');
      }

      final response = await http.delete(
        Uri.parse('${AppConfig.fullApiUrl}/transactions/$transactionId'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        return true;
      } else if (response.statusCode == 404) {
        throw Exception('Transaction not found');
      } else if (response.statusCode == 401) {
        throw Exception('Unauthorized - please log in again');
      } else {
        throw Exception('Failed to delete transaction: ${response.statusCode}');
      }
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

  /// Get recent transactions (last N days)
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
    return getTransactions(
      category: category,
      limit: limit,
    );
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

  /// Get spending by category
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

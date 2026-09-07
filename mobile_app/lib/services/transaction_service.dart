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

      // One unparseable row must not blank the whole history.
      //
      // TransactionModel.fromJson hard-casts id/category/amount and
      // DateTime.parses spent_at/created_at, so a single row missing any of
      // them threw out of this .map() and the catch below rethrew — the user
      // lost every transaction, not one. The transactions table permits NULL
      // spent_at/created_at (0001_initial declares them with neither
      // nullable=False nor a server_default; only the ORM-side `default=`
      // fills them), so the payload that triggers this is reachable from a
      // row written outside the ORM.
      //
      // The diagnostic must never carry the row's data. Dart's FormatException
      // embeds its input in toString(): double.parse('1234.56USD') throws
      // "Invalid double\n1234.56USD" and DateTime.parse does the same with the
      // offending date string. logError forwards to Crashlytics in release
      // builds and LoggingService._maskPII only masks emails, cards, phones,
      // IBANs and tokens — an amount, a merchant or a note passes through
      // untouched. So the exception is classified against the schema and
      // discarded; only field names and runtime type names are reported.
      final transactions = <TransactionModel>[];
      final failures = <String>[];
      StackTrace? firstFailureStack;
      for (var i = 0; i < transactionList.length; i++) {
        try {
          transactions.add(TransactionModel.fromJson(
              Map<String, dynamic>.from(transactionList[i] as Map)));
        } catch (e, stackTrace) {
          firstFailureStack ??= stackTrace;
          failures.add('#$i ${_describeParseFailure(transactionList[i], e)}');
        }
      }
      if (failures.isNotEmpty) {
        // One report per load, not one per row: a payload where every row is
        // malformed would otherwise emit up to `limit` Crashlytics non-fatals.
        // Reported at error level so a malformed server payload is visible to
        // an operator, with the stack of the first failure and a value-free
        // stand-in exception — the real one is never attached.
        logError(
            'Dropped ${failures.length} of ${transactionList.length} '
            'transactions that failed to parse: ${failures.join('; ')}',
            tag: 'TRANSACTION_SERVICE',
            error: TransactionParseException(
                failures.length, transactionList.length),
            stackTrace: firstFailureStack);
      }
      return transactions;
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
      final response = await _dio.get<dynamic>('/transactions/$transactionId');
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

/// Raised in place of the real parse exception when a transaction row cannot
/// be decoded.
///
/// Exists purely so the failure report carries a type and a stack trace
/// without carrying the row. The real exception is discarded at the catch
/// site: see the note in [TransactionService.getTransactions].
class TransactionParseException implements Exception {
  const TransactionParseException(this.dropped, this.total);

  /// How many rows in the response failed to parse.
  final int dropped;

  /// How many rows the response contained.
  final int total;

  @override
  String toString() =>
      'TransactionParseException: dropped $dropped of $total transaction rows';
}

// Field groups mirroring what TransactionModel.fromJson requires, used to
// classify a parse failure without reading any value.
const _requiredStrings = ['id', 'category'];
const _optionalStrings = [
  'currency',
  'description',
  'merchant',
  'location',
  'receipt_url',
  'notes',
];
const _requiredDates = ['spent_at', 'created_at'];
const _optionalDates = ['updated_at'];
const _optionalBools = [
  'is_recurring',
  'rebalanced',
  'rebalance_fully_covered'
];
const _optionalNums = ['confidence_score', 'rebalance_covered'];

/// Describe why a row failed to parse using only schema information.
///
/// Reports field names and Dart runtime type names — never a field value, and
/// never the caught exception's message, which for FormatException embeds the
/// input that failed. When nothing in the row explains the failure, it falls
/// back to the exception's runtime type, which is likewise a type name
/// (`FormatException`, `_TypeError`) and carries no data.
String _describeParseFailure(Object? row, Object error) {
  if (row is! Map) {
    return 'row is ${row.runtimeType}, expected Map';
  }

  final problems = <String>[];

  void checkString(String key, {required bool required}) {
    final value = row[key];
    if (value == null) {
      if (required) problems.add('$key missing');
      return;
    }
    if (value is! String) {
      problems.add('$key is ${value.runtimeType}, expected String');
    }
  }

  void checkDate(String key, {required bool required}) {
    final value = row[key];
    if (value == null) {
      if (required) problems.add('$key missing');
      return;
    }
    if (value is! String) {
      problems.add('$key is ${value.runtimeType}, expected String');
      return;
    }
    if (DateTime.tryParse(value) == null) {
      problems.add('$key is not an ISO-8601 date');
    }
  }

  void checkTyped(String key, bool Function(Object) ok, String expected) {
    // Typed as Object? rather than left dynamic so the null check below
    // promotes it for `ok`, which takes a non-nullable Object.
    final Object? value = row[key];
    if (value == null) return;
    if (!ok(value)) {
      problems.add('$key is ${value.runtimeType}, expected $expected');
    }
  }

  for (final key in _requiredStrings) {
    checkString(key, required: true);
  }
  for (final key in _optionalStrings) {
    checkString(key, required: false);
  }
  for (final key in _requiredDates) {
    checkDate(key, required: true);
  }
  for (final key in _optionalDates) {
    checkDate(key, required: false);
  }
  for (final key in _optionalBools) {
    checkTyped(key, (v) => v is bool, 'bool');
  }
  for (final key in _optionalNums) {
    checkTyped(key, (v) => v is num, 'num');
  }

  final amount = row['amount'];
  if (amount == null) {
    problems.add('amount missing');
  } else if (amount is String) {
    if (double.tryParse(amount) == null) {
      problems.add('amount is a String that is not a number');
    }
  } else if (amount is! num) {
    problems.add('amount is ${amount.runtimeType}, expected num or String');
  }

  final tags = row['tags'];
  if (tags != null) {
    if (tags is! List) {
      problems.add('tags is ${tags.runtimeType}, expected List');
    } else if (tags.any((t) => t is! String)) {
      problems.add('tags contains a non-String element');
    }
  }

  if (problems.isEmpty) {
    return 'unclassified ${error.runtimeType}';
  }
  return problems.join(', ');
}

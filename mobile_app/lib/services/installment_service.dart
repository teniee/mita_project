import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models/installment_models.dart';
import 'api_service.dart';
import 'logging_service.dart';

/// Installment Service
/// Handles all installment-related API calls with offline support and error handling
class InstallmentService {
  // Singleton pattern
  static final InstallmentService _instance = InstallmentService._internal();
  factory InstallmentService() => _instance;
  InstallmentService._internal();

  final ApiService _apiService = ApiService();

  // API configuration
  static const Duration _defaultTimeout = Duration(seconds: 30);
  static const int _maxRetries = 3;
  static const Duration _retryDelay = Duration(seconds: 2);

  /// Helper method to get authorization headers
  Future<Map<String, String>> _getHeaders() async {
    final token = await _apiService.getToken();
    if (token == null) {
      throw InstallmentServiceException('Not authenticated', 401);
    }
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  /// Helper method to handle HTTP errors with RFC7807 compliance
  void _handleHttpError(http.Response response, String operation) {
    final statusCode = response.statusCode;
    String errorMessage;

    try {
      final errorData = json.decode(response.body);
      if (errorData is Map) {
        // RFC7807 Problem Details
        errorMessage = (errorData['detail'] ??
            errorData['message'] ??
            errorData['title'] ??
            'Unknown error') as String;

        // Log structured error
        logError(
          'Installment API Error: $operation',
          tag: 'INSTALLMENT_SERVICE',
          extra: {
            'operation': operation,
            'statusCode': statusCode,
            'detail': errorMessage,
            'type': errorData['type'],
            'instance': errorData['instance'],
          },
        );
      } else {
        errorMessage = 'Server error: $statusCode';
      }
    } catch (e) {
      errorMessage = 'Server error: $statusCode';
      logError('Failed to parse error response for $operation',
          tag: 'INSTALLMENT_SERVICE', error: e);
    }

    throw InstallmentServiceException(errorMessage, statusCode);
  }

  /// Helper method to execute request with retry logic
  Future<http.Response> _executeWithRetry(
    Future<http.Response> Function() request,
    String operation,
  ) async {
    int attempts = 0;
    Exception? lastException;

    while (attempts < _maxRetries) {
      attempts++;
      try {
        final response = await request();

        // Log successful requests
        logDebug(
          'Installment API Success: $operation',
          tag: 'INSTALLMENT_SERVICE',
          extra: {
            'operation': operation,
            'statusCode': response.statusCode,
            'attempt': attempts,
          },
        );

        return response;
      } on http.ClientException catch (e) {
        lastException = e;
        logWarning(
          'Network error on attempt $attempts/$_maxRetries for $operation',
          tag: 'INSTALLMENT_SERVICE',
          extra: {'error': e.toString()},
        );

        if (attempts < _maxRetries) {
          await Future<void>.delayed(_retryDelay * attempts);
        }
      } catch (e) {
        // For other errors, don't retry
        logError('Non-retryable error for $operation',
            tag: 'INSTALLMENT_SERVICE', error: e);
        rethrow;
      }
    }

    throw InstallmentServiceException(
      'Network error after $_maxRetries attempts: ${lastException?.toString() ?? "Unknown error"}',
      0,
    );
  }

  // ==========================================================================
  // PUBLIC API METHODS
  // ==========================================================================

  /// Calculate installment risk and get recommendations
  /// POST /api/installments/calculator
  Future<InstallmentCalculatorOutput> calculateInstallmentRisk(
    InstallmentCalculatorInput input,
  ) async {
    try {
      logInfo(
        'Calculating installment risk',
        tag: 'INSTALLMENT_SERVICE',
        extra: {
          'purchaseAmount': input.purchaseAmount,
          'category': input.category.name,
          'numPayments': input.numPayments,
        },
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .post(
              Uri.parse('$defaultApiBaseUrl/installments/calculator'),
              headers: headers,
              body: json.encode(input.toJson()),
            )
            .timeout(_defaultTimeout);
      }, 'calculateInstallmentRisk');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return InstallmentCalculatorOutput.fromJson(data);
      } else {
        _handleHttpError(response, 'calculateInstallmentRisk');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error calculating installment risk',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException(
          'Failed to calculate installment risk: $e', 0);
    }
  }

  /// Create a new financial profile
  /// POST /api/installments/profile
  Future<UserFinancialProfile> createFinancialProfile(
    UserFinancialProfile profile,
  ) async {
    try {
      logInfo('Creating financial profile', tag: 'INSTALLMENT_SERVICE');

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .post(
              Uri.parse('$defaultApiBaseUrl/installments/profile'),
              headers: headers,
              body: json.encode(profile.toJson()),
            )
            .timeout(_defaultTimeout);
      }, 'createFinancialProfile');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return UserFinancialProfile.fromJson(data);
      } else {
        _handleHttpError(response, 'createFinancialProfile');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error creating financial profile',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException(
          'Failed to create financial profile: $e', 0);
    }
  }

  /// Get user's financial profile
  /// GET /api/installments/profile
  Future<UserFinancialProfile?> getFinancialProfile() async {
    try {
      logDebug('Fetching financial profile', tag: 'INSTALLMENT_SERVICE');

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .get(
              Uri.parse('$defaultApiBaseUrl/installments/profile'),
              headers: headers,
            )
            .timeout(_defaultTimeout);
      }, 'getFinancialProfile');

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return UserFinancialProfile.fromJson(data);
      } else if (response.statusCode == 404) {
        // Profile doesn't exist yet, return null
        logDebug('Financial profile not found', tag: 'INSTALLMENT_SERVICE');
        return null;
      } else {
        _handleHttpError(response, 'getFinancialProfile');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error fetching financial profile',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException(
          'Failed to fetch financial profile: $e', 0);
    }
  }

  /// Create a new installment plan
  /// POST /api/installments
  Future<Installment> createInstallment(Installment installment) async {
    try {
      logInfo(
        'Creating installment plan',
        tag: 'INSTALLMENT_SERVICE',
        extra: {
          'itemName': installment.itemName,
          'totalAmount': installment.totalAmount,
        },
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .post(
              Uri.parse('$defaultApiBaseUrl/installments'),
              headers: headers,
              body: json.encode(installment.toJson()),
            )
            .timeout(_defaultTimeout);
      }, 'createInstallment');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return Installment.fromJson(data);
      } else {
        _handleHttpError(response, 'createInstallment');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error creating installment',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to create installment: $e', 0);
    }
  }

  /// Get all installments with optional status filter
  /// GET /api/installments?status=active
  Future<InstallmentsSummary> getInstallments(
      {InstallmentStatus? status}) async {
    try {
      logDebug(
        'Fetching installments',
        tag: 'INSTALLMENT_SERVICE',
        extra: {'status': status?.name},
      );

      final queryParams = <String, String>{};
      if (status != null) {
        queryParams['status'] = status.toJson();
      }

      final uri = Uri.parse('$defaultApiBaseUrl/installments').replace(
          queryParameters: queryParams.isNotEmpty ? queryParams : null);

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http.get(uri, headers: headers).timeout(_defaultTimeout);
      }, 'getInstallments');

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return InstallmentsSummary.fromJson(data);
      } else {
        _handleHttpError(response, 'getInstallments');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error fetching installments',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to fetch installments: $e', 0);
    }
  }

  /// Get a single installment by ID
  /// GET /api/installments/{installment_id}
  Future<Installment> getInstallment(String installmentId) async {
    try {
      logDebug(
        'Fetching installment',
        tag: 'INSTALLMENT_SERVICE',
        extra: {'installmentId': installmentId},
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .get(
              Uri.parse('$defaultApiBaseUrl/installments/$installmentId'),
              headers: headers,
            )
            .timeout(_defaultTimeout);
      }, 'getInstallment');

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return Installment.fromJson(data);
      } else if (response.statusCode == 404) {
        throw InstallmentServiceException('Installment not found', 404);
      } else {
        _handleHttpError(response, 'getInstallment');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error fetching installment',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to fetch installment: $e', 0);
    }
  }

  /// Update an existing installment
  /// PATCH /api/installments/{installment_id}
  Future<Installment> updateInstallment(
    String installmentId,
    Map<String, dynamic> updates,
  ) async {
    try {
      logInfo(
        'Updating installment',
        tag: 'INSTALLMENT_SERVICE',
        extra: {
          'installmentId': installmentId,
          'updates': updates.keys.toList(),
        },
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .patch(
              Uri.parse('$defaultApiBaseUrl/installments/$installmentId'),
              headers: headers,
              body: json.encode(updates),
            )
            .timeout(_defaultTimeout);
      }, 'updateInstallment');

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return Installment.fromJson(data);
      } else if (response.statusCode == 404) {
        throw InstallmentServiceException('Installment not found', 404);
      } else {
        _handleHttpError(response, 'updateInstallment');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error updating installment',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to update installment: $e', 0);
    }
  }

  /// Delete an installment
  /// DELETE /api/installments/{installment_id}
  Future<void> deleteInstallment(String installmentId) async {
    try {
      logInfo(
        'Deleting installment',
        tag: 'INSTALLMENT_SERVICE',
        extra: {'installmentId': installmentId},
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .delete(
              Uri.parse('$defaultApiBaseUrl/installments/$installmentId'),
              headers: headers,
            )
            .timeout(_defaultTimeout);
      }, 'deleteInstallment');

      if (response.statusCode == 200 || response.statusCode == 204) {
        logInfo(
          'Installment deleted successfully',
          tag: 'INSTALLMENT_SERVICE',
          extra: {'installmentId': installmentId},
        );
      } else if (response.statusCode == 404) {
        throw InstallmentServiceException('Installment not found', 404);
      } else {
        _handleHttpError(response, 'deleteInstallment');
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error deleting installment',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to delete installment: $e', 0);
    }
  }

  /// Get monthly calendar of installment payments
  /// GET /api/installments/calendar/{year}/{month}
  Future<Map<String, dynamic>> getMonthlyCalendar(int year, int month) async {
    try {
      logDebug(
        'Fetching monthly calendar',
        tag: 'INSTALLMENT_SERVICE',
        extra: {'year': year, 'month': month},
      );

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .get(
              Uri.parse(
                  '$defaultApiBaseUrl/installments/calendar/$year/$month'),
              headers: headers,
            )
            .timeout(_defaultTimeout);
      }, 'getMonthlyCalendar');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return data as Map<String, dynamic>;
      } else {
        _handleHttpError(response, 'getMonthlyCalendar');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error fetching monthly calendar',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException(
          'Failed to fetch monthly calendar: $e', 0);
    }
  }

  /// Get user's installment achievements
  /// GET /api/installments/achievements
  Future<InstallmentAchievement> getAchievements() async {
    try {
      logDebug('Fetching achievements', tag: 'INSTALLMENT_SERVICE');

      final response = await _executeWithRetry(() async {
        final headers = await _getHeaders();
        return await http
            .get(
              Uri.parse('$defaultApiBaseUrl/installments/achievements'),
              headers: headers,
            )
            .timeout(_defaultTimeout);
      }, 'getAchievements');

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return InstallmentAchievement.fromJson(data);
      } else {
        _handleHttpError(response, 'getAchievements');
        throw InstallmentServiceException(
            'Unexpected error', response.statusCode);
      }
    } catch (e) {
      if (e is InstallmentServiceException) rethrow;
      logError('Error fetching achievements',
          tag: 'INSTALLMENT_SERVICE', error: e);
      throw InstallmentServiceException('Failed to fetch achievements: $e', 0);
    }
  }

  // ==========================================================================
  // CONVENIENCE METHODS
  // ==========================================================================

  /// Get active installments only
  Future<List<Installment>> getActiveInstallments() async {
    final summary = await getInstallments(status: InstallmentStatus.active);
    return summary.activeInstallments;
  }

  /// Get completed installments only
  Future<List<Installment>> getCompletedInstallments() async {
    final summary = await getInstallments(status: InstallmentStatus.completed);
    return summary.completedInstallments;
  }

  /// Get overdue installments
  Future<List<Installment>> getOverdueInstallments() async {
    final summary = await getInstallments(status: InstallmentStatus.overdue);
    return summary.overdueInstallments;
  }

  /// Check if user has a financial profile
  Future<bool> hasFinancialProfile() async {
    try {
      final profile = await getFinancialProfile();
      return profile != null;
    } catch (e) {
      return false;
    }
  }

  /// Get or create financial profile
  Future<UserFinancialProfile> getOrCreateFinancialProfile({
    required double monthlyIncome,
    required double currentBalance,
    required AgeGroup ageGroup,
  }) async {
    try {
      final profile = await getFinancialProfile();
      if (profile != null) {
        return profile;
      }
    } catch (e) {
      logDebug('No existing profile found, creating new one',
          tag: 'INSTALLMENT_SERVICE');
    }

    // Create new profile
    final newProfile = UserFinancialProfile(
      id: '', // Will be set by backend
      userId: '', // Will be set by backend
      monthlyIncome: monthlyIncome,
      currentBalance: currentBalance,
      ageGroup: ageGroup,
      updatedAt: DateTime.now(),
    );

    return await createFinancialProfile(newProfile);
  }

  /// Calculate total monthly payment obligation
  Future<double> getTotalMonthlyPayment() async {
    final summary = await getInstallments();
    return summary.totalMonthlyPayment;
  }

  /// Get next payment due date
  Future<DateTime?> getNextPaymentDate() async {
    final summary = await getInstallments();
    return summary.nextPaymentDate;
  }

  /// Check if any payment is due soon (within 7 days)
  Future<bool> hasPaymentDueSoon() async {
    final summary = await getInstallments();
    return summary.hasPaymentDueSoon;
  }

  /// Get calendar for current month
  Future<Map<String, dynamic>> getCurrentMonthCalendar() async {
    final now = DateTime.now();
    return await getMonthlyCalendar(now.year, now.month);
  }

  /// Mark installment payment as made (updates payments_made)
  Future<Installment> markPaymentMade(String installmentId) async {
    final installment = await getInstallment(installmentId);
    final newPaymentsMade = installment.paymentsMade + 1;

    return await updateInstallment(installmentId, {
      'payments_made': newPaymentsMade,
    });
  }

  /// Cancel an installment (changes status to cancelled)
  Future<Installment> cancelInstallment(String installmentId) async {
    return await updateInstallment(installmentId, {
      'status': InstallmentStatus.cancelled.toJson(),
    });
  }

  /// Add notes to an installment
  Future<Installment> addNotes(String installmentId, String notes) async {
    return await updateInstallment(installmentId, {
      'notes': notes,
    });
  }
}

/// Custom exception for installment service errors
class InstallmentServiceException implements Exception {
  final String message;
  final int statusCode;

  InstallmentServiceException(this.message, this.statusCode);

  @override
  String toString() =>
      'InstallmentServiceException: $message (Status: $statusCode)';

  /// Check if error is due to authentication
  bool get isAuthError => statusCode == 401;

  /// Check if error is due to not found
  bool get isNotFound => statusCode == 404;

  /// Check if error is due to validation
  bool get isValidationError => statusCode == 400 || statusCode == 422;

  /// Check if error is due to network issues
  bool get isNetworkError => statusCode == 0;

  /// Check if error is server-side
  bool get isServerError => statusCode >= 500;
}

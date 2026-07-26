import 'package:flutter/foundation.dart';
import '../models/installment_models.dart';
import '../services/installment_service.dart';
import '../services/logging_service.dart';

/// Installments state enum for tracking loading states
enum InstallmentsState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized installments state management provider
/// Manages installment plans, filtering, and CRUD operations
class InstallmentsProvider extends ChangeNotifier {
  /// The service is injectable so widget tests can drive the provider with a
  /// mock; production callers use the default singleton.
  InstallmentsProvider({InstallmentService? service})
      : _installmentService = service ?? InstallmentService();

  final InstallmentService _installmentService;
  int _sessionGeneration = 0;
  int _installmentsRequestId = 0;

  // State
  InstallmentsState _state = InstallmentsState.initial;
  bool _isLoading = false;
  String? _errorMessage;
  String? _successMessage;

  // Installments data
  InstallmentsSummary? _summary;
  InstallmentStatus? _selectedFilter;

  // Getters
  InstallmentsState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String? get successMessage => _successMessage;
  InstallmentsSummary? get summary => _summary;
  InstallmentStatus? get selectedFilter => _selectedFilter;

  // Convenience getters
  List<Installment> get installments => _summary?.installments ?? [];
  List<Installment> get activeInstallments =>
      _summary?.activeInstallments ?? [];
  List<Installment> get completedInstallments =>
      _summary?.completedInstallments ?? [];
  List<Installment> get overdueInstallments =>
      _summary?.overdueInstallments ?? [];
  int get totalActive => _summary?.totalActive ?? 0;
  int get totalCompleted => _summary?.totalCompleted ?? 0;
  int get totalInstallments => _summary?.totalInstallments ?? 0;
  double get totalMonthlyPayment => _summary?.totalMonthlyPayment ?? 0.0;
  double get currentInstallmentLoad => _summary?.currentInstallmentLoad ?? 0.0;
  DateTime? get nextPaymentDate => _summary?.nextPaymentDate;
  double? get nextPaymentAmount => _summary?.nextPaymentAmount;
  bool get hasPaymentDueSoon => _summary?.hasPaymentDueSoon ?? false;
  bool get hasOverduePayments => _summary?.hasOverduePayments ?? false;

  /// Get filtered installments based on selected filter
  List<Installment> get filteredInstallments {
    if (_summary == null) return [];

    switch (_selectedFilter) {
      case InstallmentStatus.active:
        return _summary!.activeInstallments;
      case InstallmentStatus.completed:
        return _summary!.completedInstallments;
      case InstallmentStatus.overdue:
        return _summary!.overdueInstallments;
      default:
        return _summary!.installments;
    }
  }

  /// Get count for a specific filter tab
  int getTabCount(InstallmentStatus? status) {
    if (_summary == null) return 0;

    switch (status) {
      case InstallmentStatus.active:
        return _summary!.totalActive;
      case InstallmentStatus.completed:
        return _summary!.totalCompleted;
      case InstallmentStatus.overdue:
        return _summary!.overdueInstallments.length;
      default:
        return _summary!.totalInstallments;
    }
  }

  /// Initialize the provider
  Future<void> initialize() async {
    if (_state != InstallmentsState.initial) return;

    final generation = _sessionGeneration;
    logInfo('Initializing InstallmentsProvider', tag: 'INSTALLMENTS_PROVIDER');
    await _loadInstallments(status: null, generation: generation);
  }

  /// Load installments with optional status filter
  Future<void> loadInstallments({InstallmentStatus? status}) {
    return _loadInstallments(
      status: status,
      generation: _sessionGeneration,
    );
  }

  Future<void> _loadInstallments({
    required InstallmentStatus? status,
    required int generation,
  }) async {
    if (!_isCurrentSession(generation)) return;
    final requestId = ++_installmentsRequestId;

    _setLoading(true);
    _state = InstallmentsState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      final summary = await _installmentService.getInstallments(status: status);
      if (!_isCurrentRequest(generation, requestId)) return;
      _summary = summary;
      _state = InstallmentsState.loaded;
      logInfo(
          'Installments loaded: ${summary.totalInstallments} total, ${summary.totalActive} active',
          tag: 'INSTALLMENTS_PROVIDER');
    } catch (e) {
      logError('Failed to load installments: $e', tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentRequest(generation, requestId)) return;
      _errorMessage = _getErrorMessage(e);
      _state = InstallmentsState.error;
    } finally {
      if (_isCurrentRequest(generation, requestId)) {
        _setLoading(false);
      }
    }
  }

  /// Refresh installments (reload with current filter)
  Future<void> refresh() async {
    final generation = _sessionGeneration;
    await _loadInstallments(
      status: _selectedFilter,
      generation: generation,
    );
  }

  /// Set the filter and reload installments
  Future<void> setFilter(InstallmentStatus? status) async {
    if (_selectedFilter == status) return;

    final generation = _sessionGeneration;
    _selectedFilter = status;
    logDebug('Filter changed to: ${status?.name ?? "all"}',
        tag: 'INSTALLMENTS_PROVIDER');
    notifyListeners();

    await _loadInstallments(status: status, generation: generation);
  }

  /// Mark a payment as made for an installment
  Future<bool> markPaymentMade(String installmentId) async {
    final generation = _sessionGeneration;
    _invalidateInstallmentSnapshot();
    try {
      logInfo('Marking payment as made for installment: $installmentId',
          tag: 'INSTALLMENTS_PROVIDER');

      await _installmentService.markPaymentMade(installmentId);
      if (!_isCurrentSession(generation)) return false;
      _successMessage = 'Payment marked as made';

      // Refresh data
      await _loadInstallments(
        status: _selectedFilter,
        generation: generation,
      );
      if (!_isCurrentSession(generation)) return false;

      logInfo('Payment marked successfully', tag: 'INSTALLMENTS_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error marking payment as made: $e',
          tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return false;
      _errorMessage = 'Failed to update payment: ${_getErrorMessage(e)}';
      notifyListeners();
      return false;
    }
  }

  /// Cancel an installment
  Future<bool> cancelInstallment(String installmentId) async {
    final generation = _sessionGeneration;
    _invalidateInstallmentSnapshot();
    try {
      logInfo('Cancelling installment: $installmentId',
          tag: 'INSTALLMENTS_PROVIDER');

      await _installmentService.cancelInstallment(installmentId);
      if (!_isCurrentSession(generation)) return false;
      _successMessage = 'Installment cancelled';

      // Refresh data
      await _loadInstallments(
        status: _selectedFilter,
        generation: generation,
      );
      if (!_isCurrentSession(generation)) return false;

      logInfo('Installment cancelled successfully',
          tag: 'INSTALLMENTS_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error cancelling installment: $e',
          tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return false;
      _errorMessage = 'Failed to cancel installment: ${_getErrorMessage(e)}';
      notifyListeners();
      return false;
    }
  }

  /// Delete an installment
  Future<bool> deleteInstallment(String installmentId) async {
    final generation = _sessionGeneration;
    _invalidateInstallmentSnapshot();
    try {
      logInfo('Deleting installment: $installmentId',
          tag: 'INSTALLMENTS_PROVIDER');

      await _installmentService.deleteInstallment(installmentId);
      if (!_isCurrentSession(generation)) return false;
      _successMessage = 'Installment deleted';

      // Refresh data
      await _loadInstallments(
        status: _selectedFilter,
        generation: generation,
      );
      if (!_isCurrentSession(generation)) return false;

      logInfo('Installment deleted successfully', tag: 'INSTALLMENTS_PROVIDER');
      notifyListeners();
      return true;
    } catch (e) {
      logError('Error deleting installment: $e', tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return false;
      _errorMessage = 'Failed to delete installment: ${_getErrorMessage(e)}';
      notifyListeners();
      return false;
    }
  }

  /// Create a new installment
  Future<Installment?> createInstallment(Installment installment) async {
    final generation = _sessionGeneration;
    _invalidateInstallmentSnapshot();
    try {
      logInfo('Creating new installment: ${installment.itemName}',
          tag: 'INSTALLMENTS_PROVIDER');

      final created = await _installmentService.createInstallment(installment);
      if (!_isCurrentSession(generation)) return null;
      _successMessage = 'Installment created successfully';

      // Refresh data
      await _loadInstallments(
        status: _selectedFilter,
        generation: generation,
      );
      if (!_isCurrentSession(generation)) return null;

      logInfo('Installment created successfully', tag: 'INSTALLMENTS_PROVIDER');
      notifyListeners();
      return created;
    } catch (e) {
      logError('Error creating installment: $e', tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return null;
      _errorMessage = 'Failed to create installment: ${_getErrorMessage(e)}';
      notifyListeners();
      return null;
    }
  }

  /// Get a single installment by ID
  Future<Installment?> getInstallment(String installmentId) async {
    final generation = _sessionGeneration;
    try {
      final installment =
          await _installmentService.getInstallment(installmentId);
      return _isCurrentSession(generation) ? installment : null;
    } catch (e) {
      logError('Error fetching installment: $e', tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return null;
      _errorMessage = 'Failed to fetch installment: ${_getErrorMessage(e)}';
      notifyListeners();
      return null;
    }
  }

  /// Add notes to an installment
  Future<bool> addNotes(String installmentId, String notes) async {
    final generation = _sessionGeneration;
    _invalidateInstallmentSnapshot();
    try {
      await _installmentService.addNotes(installmentId, notes);
      if (!_isCurrentSession(generation)) return false;
      _successMessage = 'Notes added successfully';

      // Refresh data
      await _loadInstallments(
        status: _selectedFilter,
        generation: generation,
      );
      if (!_isCurrentSession(generation)) return false;

      notifyListeners();
      return true;
    } catch (e) {
      logError('Error adding notes: $e', tag: 'INSTALLMENTS_PROVIDER');
      if (!_isCurrentSession(generation)) return false;
      _errorMessage = 'Failed to add notes: ${_getErrorMessage(e)}';
      notifyListeners();
      return false;
    }
  }

  /// Get error message from exception
  String _getErrorMessage(dynamic error) {
    if (error is InstallmentServiceException) {
      if (error.isNetworkError) {
        return 'Network error. Please check your connection.';
      } else if (error.isServerError) {
        return 'Server error. Please try again later.';
      } else if (error.isAuthError) {
        return 'Authentication error. Please log in again.';
      } else if (error.isNotFound) {
        return 'Installment not found.';
      }
      return error.message;
    }
    return 'An unexpected error occurred. Please try again.';
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  /// Clear success message
  void clearSuccess() {
    _successMessage = null;
    notifyListeners();
  }

  /// Clear all messages
  void clearMessages() {
    _errorMessage = null;
    _successMessage = null;
    notifyListeners();
  }

  /// Discard all state owned by the previous authenticated account.
  void resetSession() {
    _sessionGeneration++;
    _installmentsRequestId++;
    _state = InstallmentsState.initial;
    _isLoading = false;
    _errorMessage = null;
    _successMessage = null;
    _summary = null;
    _selectedFilter = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrentSession(int generation) => generation == _sessionGeneration;

  bool _isCurrentRequest(int generation, int requestId) =>
      _isCurrentSession(generation) && requestId == _installmentsRequestId;

  void _invalidateInstallmentSnapshot() {
    _installmentsRequestId++;
    _isLoading = false;
    if (_state == InstallmentsState.loading) {
      _state = _summary == null
          ? InstallmentsState.initial
          : InstallmentsState.loaded;
    }
  }
}

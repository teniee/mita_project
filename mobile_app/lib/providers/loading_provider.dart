import 'package:flutter/material.dart';
import '../services/logging_service.dart';

/// Centralized loading state management provider
///
/// Manages loading states for the entire app, supporting both global
/// loading state and named operation-specific loading states.
///
/// Usage:
/// ```dart
/// // Global loading
/// final loadingProvider = context.read<LoadingProvider>();
/// await loadingProvider.runWithLoading(() async {
///   await someAsyncOperation();
/// });
///
/// // Named loading for specific operations
/// await loadingProvider.runWithLoadingNamed('fetchTransactions', () async {
///   await fetchTransactions();
/// });
///
/// // Check loading state
/// if (loadingProvider.isLoadingNamed('fetchTransactions')) {
///   return CircularProgressIndicator();
/// }
/// ```
class LoadingProvider extends ChangeNotifier {
  // Global loading state
  bool _isLoading = false;

  // Named loading states for specific operations
  final Map<String, bool> _namedLoadingStates = {};

  // Error state
  String? _errorMessage;

  // Getters
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  /// Check if a specific named operation is loading
  bool isLoadingNamed(String name) => _namedLoadingStates[name] ?? false;

  /// Check if any operation is loading (global or named)
  bool get isAnyLoading =>
      _isLoading || _namedLoadingStates.values.any((loading) => loading);

  /// Get all currently loading operation names
  List<String> get activeLoadingOperations => _namedLoadingStates.entries
      .where((entry) => entry.value)
      .map((entry) => entry.key)
      .toList();

  /// Set global loading state
  void setLoading(bool loading) {
    if (_isLoading != loading) {
      _isLoading = loading;
      notifyListeners();
    }
  }

  /// Set loading state for a named operation
  void setLoadingNamed(String name, bool loading) {
    if (_namedLoadingStates[name] != loading) {
      _namedLoadingStates[name] = loading;
      notifyListeners();
    }
  }

  /// Clear error message
  void clearError() {
    if (_errorMessage != null) {
      _errorMessage = null;
      notifyListeners();
    }
  }

  /// Set error message
  void setError(String message) {
    _errorMessage = message;
    notifyListeners();
  }

  /// Run an async operation with global loading state management
  ///
  /// Automatically sets loading to true before the operation and false after.
  /// Catches and logs errors, optionally setting an error message.
  ///
  /// Returns the result of the operation, or null if an error occurred.
  Future<T?> runWithLoading<T>(
    Future<T> Function() operation, {
    String? errorMessage,
    bool showError = true,
  }) async {
    setLoading(true);
    clearError();

    try {
      final result = await operation();
      return result;
    } catch (e) {
      logError('Loading operation failed: $e', tag: 'LOADING_PROVIDER');
      if (showError) {
        setError(errorMessage ?? 'Operation failed: ${e.toString()}');
      }
      return null;
    } finally {
      setLoading(false);
    }
  }

  /// Run an async operation with named loading state management
  ///
  /// Use this for specific operations that need independent loading states.
  ///
  /// Example:
  /// ```dart
  /// await loadingProvider.runWithLoadingNamed('saveProfile', () async {
  ///   await api.saveProfile(data);
  /// });
  /// ```
  Future<T?> runWithLoadingNamed<T>(
    String name,
    Future<T> Function() operation, {
    String? errorMessage,
    bool showError = true,
  }) async {
    setLoadingNamed(name, true);
    clearError();

    try {
      final result = await operation();
      return result;
    } catch (e) {
      logError('Loading operation "$name" failed: $e', tag: 'LOADING_PROVIDER');
      if (showError) {
        setError(errorMessage ?? 'Operation "$name" failed: ${e.toString()}');
      }
      return null;
    } finally {
      setLoadingNamed(name, false);
    }
  }

  /// Run multiple operations in parallel with a single loading state
  ///
  /// All operations must complete before loading is set to false.
  Future<List<T?>> runMultipleWithLoading<T>(
    List<Future<T> Function()> operations, {
    String? name,
  }) async {
    if (name != null) {
      setLoadingNamed(name, true);
    } else {
      setLoading(true);
    }

    try {
      final results = await Future.wait(
        operations.map((op) async {
          try {
            return await op();
          } catch (e) {
            logError('Parallel operation failed: $e', tag: 'LOADING_PROVIDER');
            return null;
          }
        }),
      );
      return results;
    } finally {
      if (name != null) {
        setLoadingNamed(name, false);
      } else {
        setLoading(false);
      }
    }
  }

  /// Reset all loading states
  void reset() {
    _isLoading = false;
    _namedLoadingStates.clear();
    _errorMessage = null;
    notifyListeners();
  }

  /// Clear a specific named loading state
  void clearNamed(String name) {
    if (_namedLoadingStates.containsKey(name)) {
      _namedLoadingStates.remove(name);
      notifyListeners();
    }
  }
}

/// Extension for easy access to LoadingProvider in widgets
extension LoadingProviderExtension on BuildContext {
  /// Get LoadingProvider without listening to changes
  LoadingProvider get loadingProvider =>
      LoadingProvider(); // Will be replaced with actual provider lookup

  /// Check if global loading is active
  bool get isLoading {
    try {
      // This is a placeholder - in actual usage, use Provider.of or context.watch
      return false;
    } catch (_) {
      return false;
    }
  }
}

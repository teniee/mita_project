/*
Comprehensive Error Handling and Crash Reporting for Flutter
Provides error boundaries, crash reporting, and user-friendly error handling
*/

import 'dart:developer' as developer;
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
// import 'package:device_info_plus/device_info_plus.dart';
// import 'package:package_info_plus/package_info_plus.dart';
// import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';

// Error severity levels
enum ErrorSeverity {
  low,
  medium,
  high,
  critical,
}

// Error categories for better organization
enum ErrorCategory {
  network,
  authentication,
  validation,
  ui,
  storage,
  system,
  unknown,
}

// Error report model
class ErrorReport {
  final String id;
  final DateTime timestamp;
  final String error;
  final String? stackTrace;
  final ErrorSeverity severity;
  final ErrorCategory category;
  final Map<String, dynamic> context;
  final String appVersion;
  final String platform;
  final String deviceInfo;
  final bool isConnected;
  final String? userId;

  ErrorReport({
    required this.id,
    required this.timestamp,
    required this.error,
    this.stackTrace,
    required this.severity,
    required this.category,
    required this.context,
    required this.appVersion,
    required this.platform,
    required this.deviceInfo,
    required this.isConnected,
    this.userId,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'timestamp': timestamp.toIso8601String(),
      'error': error,
      'stackTrace': stackTrace,
      'severity': severity.toString().split('.').last,
      'category': category.toString().split('.').last,
      'context': context,
      'appVersion': appVersion,
      'platform': platform,
      'deviceInfo': deviceInfo,
      'isConnected': isConnected,
      'userId': userId,
    };
  }
}

// Main error handler class
class ErrorHandler {
  static ErrorHandler? _instance;
  static ErrorHandler get instance => _instance ??= ErrorHandler._();
  
  ErrorHandler._();

  String? _userId;
  String? _appVersion;
  String? _deviceInfo;
  late SharedPreferences _prefs;
  final List<ErrorReport> _pendingReports = [];
  Timer? _reportTimer;

  // Initialize error handling system
  Future<void> initialize({String? userId}) async {
    _userId = userId;
    _prefs = await SharedPreferences.getInstance();
    
    // Get app and device info
    await _initializeSystemInfo();
    
    // Set up Flutter error handling
    _setupFlutterErrorHandling();
    
    // Set up platform error handling
    _setupPlatformErrorHandling();
    
    // Start periodic error reporting
    _startPeriodicReporting();
    
    // Load and retry pending reports
    await _loadPendingReports();
    
    developer.log('Error handling system initialized', name: 'ErrorHandler');
  }

  // Set up Flutter framework error handling
  void _setupFlutterErrorHandling() {
    // Handle Flutter framework errors
    FlutterError.onError = (FlutterErrorDetails details) {
      // Log to console in debug mode
      if (kDebugMode) {
        FlutterError.presentError(details);
      }
      
      // Create error report
      final report = _createErrorReport(
        error: details.exception.toString(),
        stackTrace: details.stack,
        severity: ErrorSeverity.high,
        category: ErrorCategory.ui,
        context: {
          'library': details.library,
          'context': details.context?.toString(),
          'informationCollector': details.informationCollector?.toString(),
        },
      );
      
      _handleErrorReport(report);
    };

    // Handle errors not caught by Flutter
    PlatformDispatcher.instance.onError = (error, stackTrace) {
      final report = _createErrorReport(
        error: error.toString(),
        stackTrace: stackTrace,
        severity: ErrorSeverity.critical,
        category: ErrorCategory.system,
        context: {'source': 'platform_dispatcher'},
      );
      
      _handleErrorReport(report);
      return true;
    };
  }

  // Set up platform-specific error handling
  void _setupPlatformErrorHandling() {
    // Handle uncaught async errors
    runZonedGuarded(() {}, (error, stackTrace) {
      final report = _createErrorReport(
        error: error.toString(),
        stackTrace: stackTrace,
        severity: ErrorSeverity.high,
        category: ErrorCategory.system,
        context: {'source': 'async_error'},
      );
      
      _handleErrorReport(report);
    });
  }

  // Initialize system information
  Future<void> _initializeSystemInfo() async {
    try {
      // Get app version - simplified version without package_info_plus
      _appVersion = '1.0.0 (1)'; // Hardcoded for now, can be made configurable
      
      // Get basic device information without device_info_plus
      String deviceDetails = Platform.operatingSystem;
      if (Platform.isAndroid) {
        deviceDetails = 'Android Device';
      } else if (Platform.isIOS) {
        deviceDetails = 'iOS Device';
      }
      
      _deviceInfo = deviceDetails;
      
    } catch (e) {
      developer.log('Failed to initialize system info: $e', name: 'ErrorHandler');
      _appVersion = 'Unknown';
      _deviceInfo = 'Unknown';
    }
  }

  // Create standardized error report
  ErrorReport _createErrorReport({
    required String error,
    StackTrace? stackTrace,
    required ErrorSeverity severity,
    required ErrorCategory category,
    Map<String, dynamic>? context,
  }) {
    return ErrorReport(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      timestamp: DateTime.now(),
      error: error,
      stackTrace: stackTrace?.toString(),
      severity: severity,
      category: category,
      context: context ?? {},
      appVersion: _appVersion ?? 'Unknown',
      platform: Platform.operatingSystem,
      deviceInfo: _deviceInfo ?? 'Unknown',
      isConnected: true, // Will be updated when checking connectivity
      userId: _userId,
    );
  }

  // Handle error report (store and attempt to send)
  void _handleErrorReport(ErrorReport report) async {
    // Log locally
    developer.log(
      'Error reported: ${report.error}',
      name: 'ErrorHandler',
      error: report.error,
      stackTrace: report.stackTrace != null ? StackTrace.fromString(report.stackTrace!) : null,
    );

    // Check connectivity - simplified without connectivity_plus
    final isConnected = true; // Assume connected for now
    
    final updatedReport = ErrorReport(
      id: report.id,
      timestamp: report.timestamp,
      error: report.error,
      stackTrace: report.stackTrace,
      severity: report.severity,
      category: report.category,
      context: report.context,
      appVersion: report.appVersion,
      platform: report.platform,
      deviceInfo: report.deviceInfo,
      isConnected: isConnected,
      userId: report.userId,
    );

    if (isConnected) {
      // Try to send immediately
      final success = await _sendErrorReport(updatedReport);
      if (!success) {
        // Store for later if sending fails
        await _storePendingReport(updatedReport);
      }
    } else {
      // Store for later if offline
      await _storePendingReport(updatedReport);
    }
  }

  // Send error report to backend
  Future<bool> _sendErrorReport(ErrorReport report) async {
    try {
      // Replace with your actual error reporting endpoint
      const endpoint = 'https://your-api.com/api/errors/report';
      
      final response = await http.post(
        Uri.parse(endpoint),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${await _getAuthToken()}',
        },
        body: jsonEncode(report.toJson()),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode >= 200 && response.statusCode < 300) {
        developer.log('Error report sent successfully: ${report.id}', name: 'ErrorHandler');
        return true;
      } else {
        developer.log('Failed to send error report: ${response.statusCode}', name: 'ErrorHandler');
        return false;
      }
    } catch (e) {
      developer.log('Exception sending error report: $e', name: 'ErrorHandler');
      return false;
    }
  }

  // Store error report for later sending
  Future<void> _storePendingReport(ErrorReport report) async {
    try {
      _pendingReports.add(report);
      
      // Store in local storage
      final reports = _prefs.getStringList('pending_error_reports') ?? [];
      reports.add(jsonEncode(report.toJson()));
      
      // Keep only the most recent 50 reports
      if (reports.length > 50) {
        reports.removeRange(0, reports.length - 50);
      }
      
      await _prefs.setStringList('pending_error_reports', reports);
      
      developer.log('Error report stored for later: ${report.id}', name: 'ErrorHandler');
    } catch (e) {
      developer.log('Failed to store error report: $e', name: 'ErrorHandler');
    }
  }

  // Load pending reports from storage
  Future<void> _loadPendingReports() async {
    try {
      final reports = _prefs.getStringList('pending_error_reports') ?? [];
      
      for (final reportJson in reports) {
        final reportData = jsonDecode(reportJson);
        _pendingReports.add(ErrorReport(
          id: reportData['id'],
          timestamp: DateTime.parse(reportData['timestamp']),
          error: reportData['error'],
          stackTrace: reportData['stackTrace'],
          severity: ErrorSeverity.values.firstWhere(
            (e) => e.toString().split('.').last == reportData['severity'],
            orElse: () => ErrorSeverity.medium,
          ),
          category: ErrorCategory.values.firstWhere(
            (e) => e.toString().split('.').last == reportData['category'],
            orElse: () => ErrorCategory.unknown,
          ),
          context: Map<String, dynamic>.from(reportData['context'] ?? {}),
          appVersion: reportData['appVersion'],
          platform: reportData['platform'],
          deviceInfo: reportData['deviceInfo'],
          isConnected: reportData['isConnected'],
          userId: reportData['userId'],
        ));
      }
      
      developer.log('Loaded ${_pendingReports.length} pending error reports', name: 'ErrorHandler');
    } catch (e) {
      developer.log('Failed to load pending reports: $e', name: 'ErrorHandler');
    }
  }

  // Start periodic reporting of pending errors - TEMPORARILY DISABLED
  void _startPeriodicReporting() {
    // Temporarily disabled periodic error reporting to prevent recurring server errors
    developer.log('Periodic error reporting disabled due to backend server errors', name: 'ERROR_HANDLER');
    
    // TODO: Re-enable when backend is stable:
    // _reportTimer = Timer.periodic(const Duration(minutes: 5), (_) async {
    //   await _retryPendingReports();
    // });
  }

  // Retry sending pending error reports
  Future<void> _retryPendingReports() async {
    if (_pendingReports.isEmpty) return;

    // Skip connectivity check for now
    // final connectivity = await Connectivity().checkConnectivity();
    // if (connectivity == ConnectivityResult.none) return;

    final successfulReports = <ErrorReport>[];
    
    for (final report in _pendingReports) {
      final success = await _sendErrorReport(report);
      if (success) {
        successfulReports.add(report);
      }
    }

    // Remove successfully sent reports
    for (final report in successfulReports) {
      _pendingReports.remove(report);
    }

    // Update stored reports
    if (successfulReports.isNotEmpty) {
      final remainingReports = _pendingReports
          .map((r) => jsonEncode(r.toJson()))
          .toList();
      await _prefs.setStringList('pending_error_reports', remainingReports);
      
      developer.log('Sent ${successfulReports.length} pending error reports', name: 'ErrorHandler');
    }
  }

  // Get authentication token (implement based on your auth system)
  Future<String?> _getAuthToken() async {
    // Return your authentication token here
    return _prefs.getString('auth_token');
  }

  // Manual error reporting method
  static void reportError(
    dynamic error, {
    StackTrace? stackTrace,
    ErrorSeverity severity = ErrorSeverity.medium,
    ErrorCategory category = ErrorCategory.unknown,
    Map<String, dynamic>? context,
  }) {
    final report = instance._createErrorReport(
      error: error.toString(),
      stackTrace: stackTrace,
      severity: severity,
      category: category,
      context: context,
    );
    
    instance._handleErrorReport(report);
  }

  // Network error reporting
  static void reportNetworkError(
    dynamic error, {
    String? endpoint,
    int? statusCode,
    Map<String, dynamic>? requestData,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.medium,
      category: ErrorCategory.network,
      context: {
        'endpoint': endpoint,
        'statusCode': statusCode,
        'requestData': requestData,
      },
    );
  }

  // Authentication error reporting
  static void reportAuthError(
    dynamic error, {
    String? action,
    Map<String, dynamic>? context,
  }) {
    reportError(
      error,
      severity: ErrorSeverity.high,
      category: ErrorCategory.authentication,
      context: {
        'action': action,
        ...?context,
      },
    );
  }

  // Update user ID for error tracking
  void updateUserId(String? userId) {
    _userId = userId;
  }

  // Get error statistics
  Map<String, dynamic> getErrorStats() {
    final categoryCounts = <String, int>{};
    final severityCounts = <String, int>{};
    
    for (final report in _pendingReports) {
      final category = report.category.toString().split('.').last;
      final severity = report.severity.toString().split('.').last;
      
      categoryCounts[category] = (categoryCounts[category] ?? 0) + 1;
      severityCounts[severity] = (severityCounts[severity] ?? 0) + 1;
    }
    
    return {
      'pendingReports': _pendingReports.length,
      'categoryCounts': categoryCounts,
      'severityCounts': severityCounts,
    };
  }

  // Cleanup resources
  void dispose() {
    _reportTimer?.cancel();
  }
}

// Error boundary widget
class ErrorBoundary extends StatefulWidget {
  final Widget child;
  final Widget Function(BuildContext context, Object error, StackTrace? stackTrace)? errorBuilder;
  final void Function(Object error, StackTrace? stackTrace)? onError;

  const ErrorBoundary({
    Key? key,
    required this.child,
    this.errorBuilder,
    this.onError,
  }) : super(key: key);

  @override
  State<ErrorBoundary> createState() => _ErrorBoundaryState();
}

class _ErrorBoundaryState extends State<ErrorBoundary> {
  Object? _error;
  StackTrace? _stackTrace;

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return widget.errorBuilder?.call(context, _error!, _stackTrace) ??
          _defaultErrorWidget(context, _error!, _stackTrace);
    }

    return ErrorCapture(
      onError: (error, stackTrace) {
        setState(() {
          _error = error;
          _stackTrace = stackTrace;
        });
        
        widget.onError?.call(error, stackTrace);
        ErrorHandler.reportError(
          error,
          stackTrace: stackTrace,
          severity: ErrorSeverity.high,
          category: ErrorCategory.ui,
        );
      },
      child: widget.child,
    );
  }

  Widget _defaultErrorWidget(BuildContext context, Object error, StackTrace? stackTrace) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Something went wrong'),
        backgroundColor: Colors.red,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            const Text(
              'Oops! Something went wrong',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'We\'ve been notified about this issue and are working to fix it.',
              style: TextStyle(fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () {
                setState(() {
                  _error = null;
                  _stackTrace = null;
                });
              },
              child: const Text('Try Again'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () {
                Navigator.of(context).popUntil((route) => route.isFirst);
              },
              child: const Text('Go to Home'),
            ),
            if (kDebugMode) ...[
              const SizedBox(height: 24),
              Expanded(
                child: SingleChildScrollView(
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'Error: $error\n\nStack Trace:\n$stackTrace',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// Error capture widget for catching exceptions in widget tree
class ErrorCapture extends StatefulWidget {
  final Widget child;
  final void Function(Object error, StackTrace stackTrace) onError;

  const ErrorCapture({
    Key? key,
    required this.child,
    required this.onError,
  }) : super(key: key);

  @override
  State<ErrorCapture> createState() => _ErrorCaptureState();
}

class _ErrorCaptureState extends State<ErrorCapture> {
  @override
  Widget build(BuildContext context) {
    return widget.child;
  }

  @override
  void initState() {
    super.initState();
    
    // Override error handling for this widget subtree
    FlutterError.onError = (FlutterErrorDetails details) {
      widget.onError(details.exception, details.stack ?? StackTrace.current);
    };
  }
}

// Utility functions for common error scenarios
class ErrorUtils {
  // Handle and report network errors
  static void handleNetworkError(dynamic error, String endpoint) {
    String errorMessage;
    ErrorSeverity severity = ErrorSeverity.medium;

    if (error is SocketException) {
      errorMessage = 'No internet connection';
      severity = ErrorSeverity.low;
    } else if (error is TimeoutException) {
      errorMessage = 'Request timeout';
      severity = ErrorSeverity.medium;
    } else if (error is HttpException) {
      errorMessage = 'HTTP error: ${error.message}';
      severity = ErrorSeverity.medium;
    } else {
      errorMessage = 'Network error: ${error.toString()}';
      severity = ErrorSeverity.medium;
    }

    ErrorHandler.reportNetworkError(
      errorMessage,
      endpoint: endpoint,
    );
  }

  // Handle and report validation errors
  static void handleValidationError(String field, String message) {
    ErrorHandler.reportError(
      'Validation error in $field: $message',
      severity: ErrorSeverity.low,
      category: ErrorCategory.validation,
      context: {
        'field': field,
        'message': message,
      },
    );
  }

  // Handle and report storage errors
  static void handleStorageError(dynamic error, String operation) {
    ErrorHandler.reportError(
      'Storage error during $operation: ${error.toString()}',
      severity: ErrorSeverity.medium,
      category: ErrorCategory.storage,
      context: {
        'operation': operation,
      },
    );
  }
}
/// Professional Logging Service for MITA Flutter App
/// Replaces debug print statements with structured logging
/// Supports multiple log levels and proper production handling
///
library;

import 'dart:developer' as developer;
import 'dart:io';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

/// Log levels for different types of messages
enum LogLevel {
  debug, // Detailed debug information
  info, // General information
  warning, // Warning messages
  error, // Error messages
  critical, // Critical system failures
}

/// Enhanced logging service with structured logging
class LoggingService {
  static final LoggingService _instance = LoggingService._internal();
  factory LoggingService() => _instance;
  LoggingService._internal();

  static LoggingService get instance => _instance;

  // Configuration
  bool _enableConsoleLogging = kDebugMode;
  bool _enableFileLogging = false;
  bool _enablePIIMasking = true; // GDPR compliance - mask PII by default
  LogLevel _minimumLevel = kDebugMode ? LogLevel.debug : LogLevel.info;

  // Log storage for debugging
  final List<LogEntry> _logHistory = [];
  final int _maxHistorySize = 1000;

  // PII Detection Patterns (GDPR Compliance)
  static final RegExp _emailPattern = RegExp(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
  );
  static final RegExp _phonePattern = RegExp(
    r'\b\+?[1-9]\d{1,14}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
  );
  static final RegExp _creditCardPattern = RegExp(
    r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
  );
  static final RegExp _ssnPattern = RegExp(
    r'\b\d{3}-\d{2}-\d{4}\b',
  );
  static final RegExp _ibanPattern = RegExp(
    r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b',
  );
  // JWT tokens, API keys, Bearer tokens
  static final RegExp _tokenPattern = RegExp(
    r'\b(eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*|[A-Za-z0-9_-]{32,})\b',
  );
  // Password fields in JSON
  static final RegExp _passwordFieldPattern = RegExp(
    r'("password"|"passwd"|"pwd"|"secret")\s*:\s*"[^"]*"',
    caseSensitive: false,
  );

  /// Initialize logging service with configuration
  void initialize({
    bool enableConsoleLogging = true,
    bool enableFileLogging = false,
    bool enablePIIMasking = true,
    LogLevel minimumLevel = LogLevel.info,
  }) {
    _enableConsoleLogging = enableConsoleLogging && kDebugMode;
    _enableFileLogging = enableFileLogging;
    _enablePIIMasking = enablePIIMasking;
    _minimumLevel = minimumLevel;

    if (kDebugMode) {
      log('Logging service initialized (PII Masking: $enablePIIMasking)',
          level: LogLevel.info);
    }
  }

  /// Mask PII (Personally Identifiable Information) in strings
  /// GDPR Compliance - prevents sensitive data from being logged
  String _maskPII(String text) {
    if (!_enablePIIMasking || kDebugMode) {
      return text; // In debug mode, show full data for easier debugging
    }

    String masked = text;

    // Mask email addresses (show first 2 chars + domain)
    masked = masked.replaceAllMapped(_emailPattern, (match) {
      final email = match.group(0)!;
      final parts = email.split('@');
      if (parts.length == 2 && parts[0].length > 2) {
        return '${parts[0].substring(0, 2)}***@${parts[1]}';
      }
      return '***@${parts.length > 1 ? parts[1] : '***'}';
    });

    // Mask phone numbers (show last 4 digits)
    masked = masked.replaceAllMapped(_phonePattern, (match) {
      final phone = match.group(0)!.replaceAll(RegExp(r'[-\s.]'), '');
      if (phone.length > 4) {
        return '***${phone.substring(phone.length - 4)}';
      }
      return '***';
    });

    // Mask credit card numbers (show last 4 digits)
    masked = masked.replaceAllMapped(_creditCardPattern, (match) {
      final card = match.group(0)!.replaceAll(RegExp(r'[-\s]'), '');
      if (card.length >= 4) {
        return '****-****-****-${card.substring(card.length - 4)}';
      }
      return '****-****-****-****';
    });

    // Mask SSN
    masked = masked.replaceAll(_ssnPattern, '***-**-****');

    // Mask IBAN (show first 4 chars)
    masked = masked.replaceAllMapped(_ibanPattern, (match) {
      final iban = match.group(0)!;
      if (iban.length > 4) {
        return '${iban.substring(0, 4)}***';
      }
      return '****';
    });

    // Mask JWT tokens and API keys
    masked = masked.replaceAllMapped(_tokenPattern, (match) {
      final token = match.group(0)!;
      if (token.length > 8) {
        return '${token.substring(0, 8)}***';
      }
      return '***';
    });

    // Mask password fields in JSON
    masked = masked.replaceAllMapped(_passwordFieldPattern, (match) {
      final fieldName = match.group(1)!;
      return '$fieldName: "***"';
    });

    return masked;
  }

  /// Mask PII in Map data structures
  Map<String, dynamic>? _maskPIIInMap(Map<String, dynamic>? data) {
    if (data == null || !_enablePIIMasking || kDebugMode) {
      return data;
    }

    final masked = <String, dynamic>{};

    for (final entry in data.entries) {
      final key = entry.key.toLowerCase();
      final value = entry.value;

      // Sensitive field names that should always be masked
      if (_isSensitiveField(key)) {
        masked[entry.key] = '***';
      } else if (value is String) {
        masked[entry.key] = _maskPII(value);
      } else if (value is Map<String, dynamic>) {
        masked[entry.key] = _maskPIIInMap(value);
      } else if (value is List) {
        masked[entry.key] = value.map((item) {
          if (item is String) return _maskPII(item);
          if (item is Map<String, dynamic>) return _maskPIIInMap(item);
          return item;
        }).toList();
      } else {
        masked[entry.key] = value;
      }
    }

    return masked;
  }

  /// Check if field name indicates sensitive data
  bool _isSensitiveField(String fieldName) {
    final sensitive = [
      'password',
      'passwd',
      'pwd',
      'secret',
      'token',
      'api_key',
      'apikey',
      'auth',
      'authorization',
      'bearer',
      'credential',
      'private_key',
      'access_token',
      'refresh_token',
      'session_token',
      'jwt',
      'credit_card',
      'creditcard',
      'cvv',
      'cvc',
      'pin',
      'ssn',
      'social_security',
      'tax_id',
      'passport',
      'license',
      'iban',
    ];

    return sensitive.any((s) => fieldName.contains(s));
  }

  /// Log a debug message
  void debug(String message, {String? tag, Map<String, dynamic>? extra}) {
    _log(LogLevel.debug, message, tag: tag, extra: extra);
  }

  /// Log an info message
  void info(String message, {String? tag, Map<String, dynamic>? extra}) {
    _log(LogLevel.info, message, tag: tag, extra: extra);
  }

  /// Log a warning message
  void warning(String message, {String? tag, Map<String, dynamic>? extra}) {
    _log(LogLevel.warning, message, tag: tag, extra: extra);
  }

  /// Log an error message
  void error(String message,
      {String? tag,
      Map<String, dynamic>? extra,
      Object? error,
      StackTrace? stackTrace}) {
    _log(LogLevel.error, message,
        tag: tag, extra: extra, error: error, stackTrace: stackTrace);
  }

  /// Log a critical error
  void critical(String message,
      {String? tag,
      Map<String, dynamic>? extra,
      Object? error,
      StackTrace? stackTrace}) {
    _log(LogLevel.critical, message,
        tag: tag, extra: extra, error: error, stackTrace: stackTrace);
  }

  /// Generic log method
  void log(String message,
      {LogLevel level = LogLevel.info,
      String? tag,
      Map<String, dynamic>? extra}) {
    _log(level, message, tag: tag, extra: extra);
  }

  /// Internal logging implementation
  void _log(
    LogLevel level,
    String message, {
    String? tag,
    Map<String, dynamic>? extra,
    Object? error,
    StackTrace? stackTrace,
  }) {
    // Check if we should log this level
    if (!_shouldLog(level)) return;

    // Apply PII masking (GDPR Compliance)
    final maskedMessage = _maskPII(message);
    final maskedExtra = _maskPIIInMap(extra);
    final maskedError = error != null ? _maskPII(error.toString()) : null;

    final entry = LogEntry(
      level: level,
      message: maskedMessage,
      tag: tag,
      timestamp: DateTime.now(),
      extra: maskedExtra,
      error: maskedError,
      stackTrace: stackTrace,
    );

    // Add to history
    _addToHistory(entry);

    // Console logging
    if (_enableConsoleLogging) {
      _logToConsole(entry);
    }

    // File logging (future implementation)
    if (_enableFileLogging) {
      _logToFile(entry);
    }

    // Send to crash reporting in production for errors
    if (!kDebugMode &&
        (level == LogLevel.error || level == LogLevel.critical)) {
      _reportToCrashlytics(entry);
    }
  }

  /// Check if we should log this level
  bool _shouldLog(LogLevel level) {
    return level.index >= _minimumLevel.index;
  }

  /// Add entry to history
  void _addToHistory(LogEntry entry) {
    _logHistory.add(entry);

    // Keep history size manageable
    if (_logHistory.length > _maxHistorySize) {
      _logHistory.removeAt(0);
    }
  }

  /// Log to console (development only)
  void _logToConsole(LogEntry entry) {
    final levelIcon = _getLevelIcon(entry.level);
    final tag = entry.tag != null ? '[${entry.tag}] ' : '';
    final timestamp =
        entry.timestamp.toIso8601String().substring(11, 23); // HH:MM:SS.mmm

    String logMessage = '$levelIcon $timestamp $tag${entry.message}';

    // Add extra data if present
    if (entry.extra != null && entry.extra!.isNotEmpty) {
      logMessage += '\n  Extra: ${entry.extra}';
    }

    // Add error details if present
    if (entry.error != null) {
      logMessage += '\n  Error: ${entry.error}';
    }

    // Use developer.log for structured logging
    developer.log(
      logMessage,
      name: entry.tag ?? 'MITA',
      level: _getDeveloperLogLevel(entry.level),
      error: entry.error,
      stackTrace: entry.stackTrace,
    );
  }

  /// Log to file for production debugging
  void _logToFile(LogEntry entry) {
    try {
      // Only log WARNING and above to file to avoid excessive file growth
      if (entry.level.index < LogLevel.warning.index) return;

      _writeLogToFile(entry);
    } catch (e) {
      // Fallback to developer log if file logging fails
      developer.log(
        'Failed to write to log file: $e',
        name: 'LOGGING_SERVICE',
        level: 1000,
      );
    }
  }

  /// Write log entry to file with rotation
  Future<void> _writeLogToFile(LogEntry entry) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final logFile = File('${directory.path}/mita_logs.txt');

      // Check file size and rotate if needed (max 5MB)
      if (await logFile.exists()) {
        final fileSize = await logFile.length();
        if (fileSize > 5 * 1024 * 1024) {
          // 5MB limit
          await _rotateLogFile(logFile);
        }
      }

      // Format log entry for file
      final timestamp = DateTime.now().toIso8601String();
      final logLine = jsonEncode({
        'timestamp': timestamp,
        'level': entry.level.name.toUpperCase(),
        'tag': entry.tag,
        'message': entry.message,
        'extra': entry.extra,
        'error': entry.error?.toString(),
        'stackTrace': entry.stackTrace?.toString(),
      });

      // Append to log file
      await logFile.writeAsString('$logLine\n', mode: FileMode.append);
    } catch (e) {
      developer.log(
        'Error writing to log file: $e',
        name: 'LOGGING_SERVICE',
        level: 1000,
      );
    }
  }

  /// Rotate log file when it gets too large
  Future<void> _rotateLogFile(File currentFile) async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final backupFile = File('${directory.path}/mita_logs_old.txt');

      // Remove old backup if exists
      if (await backupFile.exists()) {
        await backupFile.delete();
      }

      // Move current to backup
      await currentFile.rename(backupFile.path);

      developer.log(
        'Log file rotated due to size limit',
        name: 'LOGGING_SERVICE',
        level: 800,
      );
    } catch (e) {
      developer.log(
        'Failed to rotate log file: $e',
        name: 'LOGGING_SERVICE',
        level: 1000,
      );
    }
  }

  /// Report critical errors to crash reporting
  void _reportToCrashlytics(LogEntry entry) {
    try {
      // Only report ERROR and CRITICAL level logs to avoid spam
      if (entry.level.index < LogLevel.error.index) return;

      // Don't report to Crashlytics in debug mode
      if (kDebugMode) return;

      _sendToCrashlytics(entry);
    } catch (e) {
      developer.log(
        'Failed to report to Crashlytics: $e',
        name: 'LOGGING_SERVICE',
        level: 1000,
      );
    }
  }

  /// Send error report to Firebase Crashlytics
  Future<void> _sendToCrashlytics(LogEntry entry) async {
    try {
      final crashlytics = FirebaseCrashlytics.instance;

      // Set user context for correlation
      if (entry.extra != null && entry.extra!['user_id'] != null) {
        await crashlytics.setUserIdentifier(entry.extra!['user_id'].toString());
      }

      // Add custom keys for context
      await crashlytics.setCustomKey('log_tag', entry.tag ?? 'UNKNOWN');
      await crashlytics.setCustomKey(
          'log_level', entry.level.name.toUpperCase());
      await crashlytics.setCustomKey(
          'timestamp', DateTime.now().toIso8601String());

      // Add extra context data
      if (entry.extra != null) {
        for (final key in entry.extra!.keys) {
          if (key != 'user_id') {
            // user_id already set above
            final value = entry.extra![key];
            if (value != null) {
              await crashlytics.setCustomKey('extra_$key', value.toString());
            }
          }
        }
      }

      // Report the error
      if (entry.error != null) {
        // Report with exception and stack trace
        await crashlytics.recordError(
          entry.error,
          entry.stackTrace,
          reason: '${entry.tag ?? 'UNKNOWN'}: ${entry.message}',
          printDetails: false, // Don't print to console in production
        );
      } else {
        // Report as a non-fatal message
        await crashlytics.log('${entry.tag ?? 'UNKNOWN'}: ${entry.message}');

        // For CRITICAL level without exception, create a custom error
        if (entry.level == LogLevel.critical) {
          await crashlytics.recordError(
            Exception('Critical Error: ${entry.message}'),
            null, // No stack trace available
            reason: '${entry.tag ?? 'UNKNOWN'}: Critical Error',
            printDetails: false,
          );
        }
      }
    } catch (e) {
      developer.log(
        'Error sending to Crashlytics: $e',
        name: 'LOGGING_SERVICE',
        level: 1000,
      );
    }
  }

  /// Get icon for log level
  String _getLevelIcon(LogLevel level) {
    switch (level) {
      case LogLevel.debug:
        return '🐛';
      case LogLevel.info:
        return 'ℹ️';
      case LogLevel.warning:
        return '⚠️';
      case LogLevel.error:
        return '❌';
      case LogLevel.critical:
        return '🚨';
    }
  }

  /// Convert to dart:developer log level
  int _getDeveloperLogLevel(LogLevel level) {
    switch (level) {
      case LogLevel.debug:
        return 500; // Fine
      case LogLevel.info:
        return 800; // Info
      case LogLevel.warning:
        return 900; // Warning
      case LogLevel.error:
        return 1000; // Severe
      case LogLevel.critical:
        return 1200; // Shout
    }
  }

  /// Get recent log history for debugging
  List<LogEntry> getRecentLogs({int? limit}) {
    final logs = List<LogEntry>.from(_logHistory);
    if (limit != null && logs.length > limit) {
      return logs.sublist(logs.length - limit);
    }
    return logs;
  }

  /// Clear log history
  void clearHistory() {
    _logHistory.clear();
  }

  /// Get log statistics
  Map<String, int> getLogStats() {
    final stats = <String, int>{};
    for (final level in LogLevel.values) {
      stats[level.name] = _logHistory.where((e) => e.level == level).length;
    }
    return stats;
  }
}

/// Log entry model
class LogEntry {
  final LogLevel level;
  final String message;
  final String? tag;
  final DateTime timestamp;
  final Map<String, dynamic>? extra;
  final Object? error;
  final StackTrace? stackTrace;

  LogEntry({
    required this.level,
    required this.message,
    this.tag,
    required this.timestamp,
    this.extra,
    this.error,
    this.stackTrace,
  });

  @override
  String toString() {
    return '${timestamp.toIso8601String()} [${level.name.toUpperCase()}] ${tag ?? ''}: $message';
  }
}

// Global convenience functions
void logDebug(String message, {String? tag, Map<String, dynamic>? extra}) {
  LoggingService.instance.debug(message, tag: tag, extra: extra);
}

void logInfo(String message, {String? tag, Map<String, dynamic>? extra}) {
  LoggingService.instance.info(message, tag: tag, extra: extra);
}

void logWarning(String message, {String? tag, Map<String, dynamic>? extra}) {
  LoggingService.instance.warning(message, tag: tag, extra: extra);
}

void logError(String message,
    {String? tag,
    Map<String, dynamic>? extra,
    Object? error,
    StackTrace? stackTrace}) {
  LoggingService.instance.error(message,
      tag: tag, extra: extra, error: error, stackTrace: stackTrace);
}

void logCritical(String message,
    {String? tag,
    Map<String, dynamic>? extra,
    Object? error,
    StackTrace? stackTrace}) {
  LoggingService.instance.critical(message,
      tag: tag, extra: extra, error: error, stackTrace: stackTrace);
}

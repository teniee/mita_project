/// Professional Logging Service for MITA Flutter App
/// Replaces debug print statements with structured logging
/// Supports multiple log levels and proper production handling
///
import 'dart:developer' as developer;
import 'package:flutter/foundation.dart';

/// Log levels for different types of messages
enum LogLevel {
  debug,    // Detailed debug information
  info,     // General information
  warning,  // Warning messages
  error,    // Error messages
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
  LogLevel _minimumLevel = kDebugMode ? LogLevel.debug : LogLevel.info;
  
  // Log storage for debugging
  final List<LogEntry> _logHistory = [];
  final int _maxHistorySize = 1000;

  /// Initialize logging service with configuration
  void initialize({
    bool enableConsoleLogging = true,
    bool enableFileLogging = false,
    LogLevel minimumLevel = LogLevel.info,
  }) {
    _enableConsoleLogging = enableConsoleLogging && kDebugMode;
    _enableFileLogging = enableFileLogging;
    _minimumLevel = minimumLevel;

    if (kDebugMode) {
      log('Logging service initialized', level: LogLevel.info);
    }
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
  void error(String message, {String? tag, Map<String, dynamic>? extra, Object? error, StackTrace? stackTrace}) {
    _log(LogLevel.error, message, tag: tag, extra: extra, error: error, stackTrace: stackTrace);
  }

  /// Log a critical error
  void critical(String message, {String? tag, Map<String, dynamic>? extra, Object? error, StackTrace? stackTrace}) {
    _log(LogLevel.critical, message, tag: tag, extra: extra, error: error, stackTrace: stackTrace);
  }

  /// Generic log method
  void log(String message, {LogLevel level = LogLevel.info, String? tag, Map<String, dynamic>? extra}) {
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

    final entry = LogEntry(
      level: level,
      message: message,
      tag: tag,
      timestamp: DateTime.now(),
      extra: extra,
      error: error,
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
    if (!kDebugMode && (level == LogLevel.error || level == LogLevel.critical)) {
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
    final timestamp = entry.timestamp.toIso8601String().substring(11, 23); // HH:MM:SS.mmm
    
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

  /// Log to file (future implementation)
  void _logToFile(LogEntry entry) {
    // TODO: Implement file logging for production
    // This would write to a local file for debugging purposes
  }

  /// Report critical errors to crash reporting
  void _reportToCrashlytics(LogEntry entry) {
    // TODO: Integrate with Firebase Crashlytics or Sentry
    // This would send error reports in production
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
        return 500;  // Fine
      case LogLevel.info:
        return 800;  // Info
      case LogLevel.warning:
        return 900;  // Warning
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

void logError(String message, {String? tag, Map<String, dynamic>? extra, Object? error, StackTrace? stackTrace}) {
  LoggingService.instance.error(message, tag: tag, extra: extra, error: error, stackTrace: stackTrace);
}

void logCritical(String message, {String? tag, Map<String, dynamic>? extra, Object? error, StackTrace? stackTrace}) {
  LoggingService.instance.critical(message, tag: tag, extra: extra, error: error, stackTrace: stackTrace);
}
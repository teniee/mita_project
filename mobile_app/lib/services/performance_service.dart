/// Advanced Performance Service for MITA Flutter App
/// Provides performance monitoring, memory management, and optimization
/// 
library;
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/scheduler.dart';
import 'logging_service.dart';

/// Performance metric data point
class PerformanceMetric {
  final String name;
  final double value;
  final DateTime timestamp;
  final Map<String, String> tags;

  PerformanceMetric({
    required this.name,
    required this.value,
    required this.timestamp,
    this.tags = const {},
  });

  Map<String, dynamic> toMap() {
    return {
      'name': name,
      'value': value,
      'timestamp': timestamp.toIso8601String(),
      'tags': tags,
    };
  }
}

/// Frame timing metrics
class FrameMetrics {
  final double averageFPS;
  final double worstFrame;
  final double averageFrameTime;
  final int droppedFrames;
  final int totalFrames;

  FrameMetrics({
    required this.averageFPS,
    required this.worstFrame,
    required this.averageFrameTime,
    required this.droppedFrames,
    required this.totalFrames,
  });

  Map<String, dynamic> toMap() {
    return {
      'averageFPS': averageFPS,
      'worstFrame': worstFrame,
      'averageFrameTime': averageFrameTime,
      'droppedFrames': droppedFrames,
      'totalFrames': totalFrames,
    };
  }
}

/// Memory usage information
class MemoryInfo {
  final int totalMemoryMB;
  final int usedMemoryMB;
  final int freeMemoryMB;
  final double memoryUsagePercent;
  final int dartHeapSizeMB;
  final int dartHeapUsedMB;

  MemoryInfo({
    required this.totalMemoryMB,
    required this.usedMemoryMB,
    required this.freeMemoryMB,
    required this.memoryUsagePercent,
    required this.dartHeapSizeMB,
    required this.dartHeapUsedMB,
  });

  Map<String, dynamic> toMap() {
    return {
      'totalMemoryMB': totalMemoryMB,
      'usedMemoryMB': usedMemoryMB,
      'freeMemoryMB': freeMemoryMB,
      'memoryUsagePercent': memoryUsagePercent,
      'dartHeapSizeMB': dartHeapSizeMB,
      'dartHeapUsedMB': dartHeapUsedMB,
    };
  }
}

/// Network request performance data
class NetworkMetrics {
  final String endpoint;
  final String method;
  final int responseTimeMs;
  final int statusCode;
  final int requestSizeBytes;
  final int responseSizeBytes;
  final DateTime timestamp;
  final bool isSuccess;

  NetworkMetrics({
    required this.endpoint,
    required this.method,
    required this.responseTimeMs,
    required this.statusCode,
    required this.requestSizeBytes,
    required this.responseSizeBytes,
    required this.timestamp,
    required this.isSuccess,
  });

  Map<String, dynamic> toMap() {
    return {
      'endpoint': endpoint,
      'method': method,
      'responseTimeMs': responseTimeMs,
      'statusCode': statusCode,
      'requestSizeBytes': requestSizeBytes,
      'responseSizeBytes': responseSizeBytes,
      'timestamp': timestamp.toIso8601String(),
      'isSuccess': isSuccess,
    };
  }
}

/// Cache performance metrics
class CacheMetrics {
  final String cacheName;
  final int hits;
  final int misses;
  final int totalRequests;
  final double hitRate;
  final int cacheSizeBytes;
  final DateTime lastUpdated;

  CacheMetrics({
    required this.cacheName,
    required this.hits,
    required this.misses,
    required this.totalRequests,
    required this.hitRate,
    required this.cacheSizeBytes,
    required this.lastUpdated,
  });

  Map<String, dynamic> toMap() {
    return {
      'cacheName': cacheName,
      'hits': hits,
      'misses': misses,
      'totalRequests': totalRequests,
      'hitRate': hitRate,
      'cacheSizeBytes': cacheSizeBytes,
      'lastUpdated': lastUpdated.toIso8601String(),
    };
  }
}

/// Main performance monitoring service
class PerformanceService {
  static final PerformanceService _instance = PerformanceService._internal();
  factory PerformanceService() => _instance;
  PerformanceService._internal();

  // Performance monitoring state
  bool _isMonitoring = false;
  Timer? _monitoringTimer;
  Timer? _memoryTimer;
  
  // Metrics storage
  final List<PerformanceMetric> _metrics = [];
  final List<FrameMetrics> _frameMetrics = [];
  final List<MemoryInfo> _memorySnapshots = [];
  final List<NetworkMetrics> _networkMetrics = [];
  final Map<String, CacheMetrics> _cacheMetrics = {};
  
  // Frame timing
  final List<Duration> _frameTimes = [];
  int _droppedFrames = 0;
  int _totalFrames = 0;
  
  // Memory monitoring
  int _memoryWarningCount = 0;
  
  // Performance thresholds
  static const double TARGET_FPS = 60.0;
  static const double SLOW_FRAME_THRESHOLD = 16.67; // ms for 60fps
  static const double MEMORY_WARNING_THRESHOLD = 80.0; // percent
  static const int MAX_METRICS_HISTORY = 1000;
  
  // Configuration
  bool enableFrameMonitoring = true;
  bool enableMemoryMonitoring = true;
  bool enableNetworkMonitoring = true;
  Duration monitoringInterval = const Duration(seconds: 10);

  /// Initialize performance monitoring
  Future<void> initialize() async {
    if (_isMonitoring) return;
    
    await _setupFrameCallback();
    await _startMemoryMonitoring();
    _startPeriodicMonitoring();
    
    _isMonitoring = true;
    
    logInfo('Performance monitoring initialized', tag: 'PERFORMANCE');
  }

  /// Stop performance monitoring
  void dispose() {
    _monitoringTimer?.cancel();
    _memoryTimer?.cancel();
    _isMonitoring = false;
    
    logInfo('Performance monitoring stopped', tag: 'PERFORMANCE');
  }

  /// Set up frame timing callback
  Future<void> _setupFrameCallback() async {
    if (!enableFrameMonitoring) return;
    
    SchedulerBinding.instance.addPersistentFrameCallback((duration) {
      _recordFrameTiming(duration);
    });
  }

  /// Record frame timing information
  void _recordFrameTiming(Duration frameDuration) {
    if (!enableFrameMonitoring) return;
    
    _totalFrames++;
    final frameTimeMs = frameDuration.inMicroseconds / 1000.0;
    
    _frameTimes.add(frameDuration);
    
    // Keep only recent frame times
    if (_frameTimes.length > 300) { // ~5 seconds at 60fps
      _frameTimes.removeAt(0);
    }
    
    // Check for dropped frames
    if (frameTimeMs > SLOW_FRAME_THRESHOLD) {
      _droppedFrames++;
      
      if (frameTimeMs > SLOW_FRAME_THRESHOLD * 2) {
        logWarning('Slow frame detected: ${frameTimeMs.toStringAsFixed(2)}ms', tag: 'PERFORMANCE');
      }
    }
    
    // Generate frame metrics every 5 seconds
    if (_totalFrames % 300 == 0) {
      _generateFrameMetrics();
    }
  }

  /// Generate frame performance metrics
  void _generateFrameMetrics() {
    if (_frameTimes.isEmpty) return;
    
    final frameTimes = _frameTimes.map((d) => d.inMicroseconds / 1000.0).toList();
    final averageFrameTime = frameTimes.reduce((a, b) => a + b) / frameTimes.length;
    final worstFrame = frameTimes.reduce((a, b) => a > b ? a : b);
    final averageFPS = 1000.0 / averageFrameTime;
    
    final metrics = FrameMetrics(
      averageFPS: averageFPS,
      worstFrame: worstFrame,
      averageFrameTime: averageFrameTime,
      droppedFrames: _droppedFrames,
      totalFrames: _totalFrames,
    );
    
    _frameMetrics.add(metrics);
    
    // Keep only recent metrics
    if (_frameMetrics.length > 50) {
      _frameMetrics.removeAt(0);
    }
    
    // Reset counters
    _droppedFrames = 0;
  }

  /// Start memory monitoring
  Future<void> _startMemoryMonitoring() async {
    // DISABLED: Memory monitoring creates unnecessary background timer load
    // Re-enable only for debugging performance issues
    if (!enableMemoryMonitoring) return;

    // Commented out to reduce timer load
    // _memoryTimer = Timer.periodic(const Duration(minutes: 5), (timer) {
    //   _collectMemoryInfo();
    // });

    // Initial memory snapshot only
    await _collectMemoryInfo();
  }

  /// Collect current memory information
  Future<void> _collectMemoryInfo() async {
    try {
      // Get Dart heap information
      final dartHeapInfo = await _getDartHeapInfo();
      
      // Get system memory info (platform-specific)
      final systemMemory = await _getSystemMemoryInfo();
      
      final memoryInfo = MemoryInfo(
        totalMemoryMB: systemMemory['total'] ?? 0,
        usedMemoryMB: systemMemory['used'] ?? 0,
        freeMemoryMB: systemMemory['free'] ?? 0,
        memoryUsagePercent: systemMemory['percent'] ?? 0.0,
        dartHeapSizeMB: dartHeapInfo['size'] ?? 0,
        dartHeapUsedMB: dartHeapInfo['used'] ?? 0,
      );
      
      _memorySnapshots.add(memoryInfo);
      
      // Keep only recent snapshots
      if (_memorySnapshots.length > 100) {
        _memorySnapshots.removeAt(0);
      }
      
      // Check for memory warnings
      if (memoryInfo.memoryUsagePercent > MEMORY_WARNING_THRESHOLD) {
        _memoryWarningCount++;
        logWarning('High memory usage: ${memoryInfo.memoryUsagePercent.toStringAsFixed(1)}%', tag: 'PERFORMANCE');
        
        // Suggest garbage collection
        _suggestGarbageCollection();
      }
      
    } catch (e) {
      logError('Error collecting memory info: $e', tag: 'PERFORMANCE');
    }
  }

  /// Get Dart heap information
  Future<Map<String, int>> _getDartHeapInfo() async {
    try {
      // This is a simplified approach - in production, you might use
      // more sophisticated memory profiling tools
      final info = ProcessInfo.currentRss;
      return {
        'size': info ~/ (1024 * 1024), // Convert to MB
        'used': info ~/ (1024 * 1024), // Simplified - same as size
      };
    } catch (e) {
      return {'size': 0, 'used': 0};
    }
  }

  /// Get system memory information (platform-specific)
  Future<Map<String, dynamic>> _getSystemMemoryInfo() async {
    try {
      if (Platform.isAndroid) {
        return await _getAndroidMemoryInfo();
      } else if (Platform.isIOS) {
        return await _getIOSMemoryInfo();
      }
    } catch (e) {
      logError('Error getting system memory info: $e', tag: 'PERFORMANCE');
    }
    
    return {
      'total': 0,
      'used': 0,
      'free': 0,
      'percent': 0.0,
    };
  }

  /// Get Android memory information
  Future<Map<String, dynamic>> _getAndroidMemoryInfo() async {
    // This would typically use platform channels to get actual memory info
    // For now, return mock data
    return {
      'total': 4096, // 4GB
      'used': 2048,  // 2GB
      'free': 2048,  // 2GB
      'percent': 50.0,
    };
  }

  /// Get iOS memory information
  Future<Map<String, dynamic>> _getIOSMemoryInfo() async {
    // This would typically use platform channels to get actual memory info
    // For now, return mock data
    return {
      'total': 6144, // 6GB
      'used': 2048,  // 2GB
      'free': 4096,  // 4GB
      'percent': 33.3,
    };
  }

  /// Suggest garbage collection when memory is high
  void _suggestGarbageCollection() {
    // Force garbage collection
    // Note: This is generally not recommended in production
    // but can be useful for performance monitoring
    logDebug('Suggesting garbage collection due to high memory usage', tag: 'PERFORMANCE');
  }

  /// Start periodic monitoring
  void _startPeriodicMonitoring() {
    _monitoringTimer = Timer.periodic(monitoringInterval, (timer) {
      _collectPerformanceMetrics();
    });
  }

  /// Collect general performance metrics
  void _collectPerformanceMetrics() {
    final now = DateTime.now();
    
    // Add app lifecycle metrics
    _addMetric(PerformanceMetric(
      name: 'app_lifecycle_state',
      value: SchedulerBinding.instance.lifecycleState == AppLifecycleState.resumed ? 1.0 : 0.0,
      timestamp: now,
      tags: {'state': SchedulerBinding.instance.lifecycleState.toString()},
    ));
    
    // Add memory warning count
    _addMetric(PerformanceMetric(
      name: 'memory_warnings',
      value: _memoryWarningCount.toDouble(),
      timestamp: now,
    ));
    
    // Add cache performance if available
    _updateCacheMetrics();
  }

  /// Add a performance metric
  void _addMetric(PerformanceMetric metric) {
    _metrics.add(metric);
    
    // Keep only recent metrics
    if (_metrics.length > MAX_METRICS_HISTORY) {
      _metrics.removeAt(0);
    }
  }

  /// Record network request performance
  void recordNetworkRequest({
    required String endpoint,
    required String method,
    required int responseTimeMs,
    required int statusCode,
    int requestSizeBytes = 0,
    int responseSizeBytes = 0,
  }) {
    if (!enableNetworkMonitoring) return;
    
    final metrics = NetworkMetrics(
      endpoint: endpoint,
      method: method,
      responseTimeMs: responseTimeMs,
      statusCode: statusCode,
      requestSizeBytes: requestSizeBytes,
      responseSizeBytes: responseSizeBytes,
      timestamp: DateTime.now(),
      isSuccess: statusCode >= 200 && statusCode < 300,
    );
    
    _networkMetrics.add(metrics);
    
    // Keep only recent metrics
    if (_networkMetrics.length > 500) {
      _networkMetrics.removeAt(0);
    }
    
    // Log slow requests
    if (responseTimeMs > 2000) {
      logWarning('Slow network request: $method $endpoint - ${responseTimeMs}ms', tag: 'PERFORMANCE');
    }
  }

  /// Record cache performance
  void recordCacheMetrics({
    required String cacheName,
    required int hits,
    required int misses,
    required int cacheSizeBytes,
  }) {
    final totalRequests = hits + misses;
    final hitRate = totalRequests > 0 ? (hits / totalRequests) * 100 : 0.0;
    
    _cacheMetrics[cacheName] = CacheMetrics(
      cacheName: cacheName,
      hits: hits,
      misses: misses,
      totalRequests: totalRequests,
      hitRate: hitRate,
      cacheSizeBytes: cacheSizeBytes,
      lastUpdated: DateTime.now(),
    );
  }

  /// Update cache metrics from various sources
  void _updateCacheMetrics() {
    // This would integrate with your caching systems
    // For now, we'll simulate some cache metrics
    
    recordCacheMetrics(
      cacheName: 'image_cache',
      hits: 85,
      misses: 15,
      cacheSizeBytes: 1024 * 1024 * 50, // 50MB
    );
    
    recordCacheMetrics(
      cacheName: 'api_cache',
      hits: 120,
      misses: 30,
      cacheSizeBytes: 1024 * 1024 * 10, // 10MB
    );
  }

  /// Get current frame performance
  FrameMetrics? getCurrentFrameMetrics() {
    return _frameMetrics.isNotEmpty ? _frameMetrics.last : null;
  }

  /// Get current memory information
  MemoryInfo? getCurrentMemoryInfo() {
    return _memorySnapshots.isNotEmpty ? _memorySnapshots.last : null;
  }

  /// Get network performance summary
  Map<String, dynamic> getNetworkPerformanceSummary() {
    if (_networkMetrics.isEmpty) {
      return {
        'totalRequests': 0,
        'averageResponseTime': 0.0,
        'successRate': 0.0,
        'slowRequests': 0,
      };
    }
    
    final successfulRequests = _networkMetrics.where((m) => m.isSuccess).length;
    final totalResponseTime = _networkMetrics.fold<int>(0, (sum, m) => sum + m.responseTimeMs);
    final slowRequests = _networkMetrics.where((m) => m.responseTimeMs > 2000).length;
    
    return {
      'totalRequests': _networkMetrics.length,
      'averageResponseTime': totalResponseTime / _networkMetrics.length,
      'successRate': (successfulRequests / _networkMetrics.length) * 100,
      'slowRequests': slowRequests,
    };
  }

  /// Get cache performance summary
  Map<String, CacheMetrics> getCachePerformanceSummary() {
    return Map.from(_cacheMetrics);
  }

  /// Get comprehensive performance report
  Map<String, dynamic> getPerformanceReport() {
    final currentFrame = getCurrentFrameMetrics();
    final currentMemory = getCurrentMemoryInfo();
    final networkSummary = getNetworkPerformanceSummary();
    final cacheSummary = getCachePerformanceSummary();
    
    return {
      'timestamp': DateTime.now().toIso8601String(),
      'frame_performance': currentFrame?.toMap(),
      'memory_info': currentMemory?.toMap(),
      'network_performance': networkSummary,
      'cache_performance': cacheSummary.map((k, v) => MapEntry(k, v.toMap())),
      'recommendations': _generateRecommendations(),
      'health_score': _calculateHealthScore(),
    };
  }

  /// Generate performance recommendations
  List<String> _generateRecommendations() {
    final recommendations = <String>[];
    
    // Frame performance recommendations
    final currentFrame = getCurrentFrameMetrics();
    if (currentFrame != null) {
      if (currentFrame.averageFPS < TARGET_FPS * 0.8) {
        recommendations.add('Low FPS detected (${currentFrame.averageFPS.toStringAsFixed(1)}). Consider optimizing animations and reducing widget rebuilds.');
      }
      
      if (currentFrame.droppedFrames > 10) {
        recommendations.add('${currentFrame.droppedFrames} dropped frames detected. Check for expensive operations on the main thread.');
      }
    }
    
    // Memory recommendations
    final currentMemory = getCurrentMemoryInfo();
    if (currentMemory != null && currentMemory.memoryUsagePercent > MEMORY_WARNING_THRESHOLD) {
      recommendations.add('High memory usage (${currentMemory.memoryUsagePercent.toStringAsFixed(1)}%). Consider optimizing image caching and disposing unused resources.');
    }
    
    // Network recommendations
    final networkSummary = getNetworkPerformanceSummary();
    if (networkSummary['averageResponseTime'] > 1000) {
      recommendations.add('Slow network requests detected (${networkSummary['averageResponseTime'].toStringAsFixed(0)}ms avg). Consider implementing request optimization and caching.');
    }
    
    // Cache recommendations
    final cacheSummary = getCachePerformanceSummary();
    for (final entry in cacheSummary.entries) {
      if (entry.value.hitRate < 70) {
        recommendations.add('Low cache hit rate for ${entry.key} (${entry.value.hitRate.toStringAsFixed(1)}%). Review cache strategy.');
      }
    }
    
    if (recommendations.isEmpty) {
      recommendations.add('Performance is optimal!');
    }
    
    return recommendations;
  }

  /// Calculate overall performance health score (0-100)
  double _calculateHealthScore() {
    double score = 100.0;
    
    // Frame performance impact (40% of score)
    final currentFrame = getCurrentFrameMetrics();
    if (currentFrame != null) {
      final fpsScore = (currentFrame.averageFPS / TARGET_FPS).clamp(0.0, 1.0);
      score -= (1.0 - fpsScore) * 40;
    }
    
    // Memory impact (30% of score)
    final currentMemory = getCurrentMemoryInfo();
    if (currentMemory != null) {
      final memoryScore = (100 - currentMemory.memoryUsagePercent) / 100;
      score -= (1.0 - memoryScore) * 30;
    }
    
    // Network performance impact (20% of score)
    final networkSummary = getNetworkPerformanceSummary();
    if (networkSummary['totalRequests'] > 0) {
      final networkScore = (networkSummary['successRate'] / 100.0).clamp(0.0, 1.0);
      score -= (1.0 - networkScore) * 20;
    }
    
    // Cache performance impact (10% of score)
    final cacheSummary = getCachePerformanceSummary();
    if (cacheSummary.isNotEmpty) {
      final avgHitRate = cacheSummary.values
          .map((c) => c.hitRate)
          .reduce((a, b) => a + b) / cacheSummary.length;
      final cacheScore = (avgHitRate / 100.0).clamp(0.0, 1.0);
      score -= (1.0 - cacheScore) * 10;
    }
    
    return score.clamp(0.0, 100.0);
  }

  /// Export performance data for analysis
  Future<String> exportPerformanceData() async {
    final report = getPerformanceReport();
    return jsonEncode(report);
  }

  /// Clear all performance history
  void clearPerformanceHistory() {
    _metrics.clear();
    _frameMetrics.clear();
    _memorySnapshots.clear();
    _networkMetrics.clear();
    _cacheMetrics.clear();
    _memoryWarningCount = 0;
    _droppedFrames = 0;
    _totalFrames = 0;
    
    logInfo('Performance history cleared', tag: 'PERFORMANCE');
  }
}
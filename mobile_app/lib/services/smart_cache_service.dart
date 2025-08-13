/// Smart Cache Service for MITA Flutter App
/// Intelligent multi-tier caching with analytics and optimization
/// 
library;
import 'dart:async';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'logging_service.dart';

/// Cache entry with metadata
class CacheEntry {
  final String key;
  final dynamic value;
  final DateTime createdAt;
  final DateTime? expiresAt;
  final List<String> tags;
  final int sizeBytes;
  DateTime lastAccessed;
  int accessCount;

  CacheEntry({
    required this.key,
    required this.value,
    required this.createdAt,
    this.expiresAt,
    this.tags = const [],
    required this.sizeBytes,
    DateTime? lastAccessed,
    this.accessCount = 0,
  }) : lastAccessed = lastAccessed ?? createdAt;

  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  Duration get age => DateTime.now().difference(createdAt);

  void updateAccess() {
    lastAccessed = DateTime.now();
    accessCount++;
  }

  Map<String, dynamic> toMap() {
    return {
      'key': key,
      'value': value,
      'createdAt': createdAt.toIso8601String(),
      'expiresAt': expiresAt?.toIso8601String(),
      'tags': tags,
      'sizeBytes': sizeBytes,
      'lastAccessed': lastAccessed.toIso8601String(),
      'accessCount': accessCount,
    };
  }

  factory CacheEntry.fromMap(Map<String, dynamic> map) {
    return CacheEntry(
      key: map['key'],
      value: map['value'],
      createdAt: DateTime.parse(map['createdAt']),
      expiresAt: map['expiresAt'] != null ? DateTime.parse(map['expiresAt']) : null,
      tags: List<String>.from(map['tags'] ?? []),
      sizeBytes: map['sizeBytes'] ?? 0,
      lastAccessed: DateTime.parse(map['lastAccessed']),
      accessCount: map['accessCount'] ?? 0,
    );
  }
}

/// Cache statistics
class CacheStats {
  int hits = 0;
  int misses = 0;
  int sets = 0;
  int deletes = 0;
  int evictions = 0;
  int totalSizeBytes = 0;
  int entryCount = 0;

  double get hitRate {
    final total = hits + misses;
    return total > 0 ? (hits / total) * 100 : 0.0;
  }

  double get missRate => 100.0 - hitRate;

  Map<String, dynamic> toMap() {
    return {
      'hits': hits,
      'misses': misses,
      'sets': sets,
      'deletes': deletes,
      'evictions': evictions,
      'totalSizeBytes': totalSizeBytes,
      'entryCount': entryCount,
      'hitRate': hitRate,
      'missRate': missRate,
    };
  }
}

/// Cache tier enumeration
enum CacheTier {
  memory,    // Fastest, most volatile
  persistent, // Medium speed, survives app restarts
  disk,      // Slowest, largest capacity
}

/// Abstract cache backend
abstract class CacheBackend {
  Future<dynamic> get(String key);
  Future<bool> set(String key, dynamic value, {Duration? ttl, List<String>? tags});
  Future<bool> delete(String key);
  Future<bool> exists(String key);
  Future<void> clear();
  CacheStats get stats;
  Future<void> cleanup();
}

/// Memory cache implementation
class MemoryCache implements CacheBackend {
  final int maxEntries;
  final int maxSizeBytes;
  final Map<String, CacheEntry> _cache = {};
  final CacheStats _stats = CacheStats();
  Timer? _cleanupTimer;

  MemoryCache({
    this.maxEntries = 1000,
    this.maxSizeBytes = 50 * 1024 * 1024, // 50MB
  }) {
    _startCleanupTimer();
  }

  void _startCleanupTimer() {
    _cleanupTimer = Timer.periodic(const Duration(minutes: 5), (timer) {
      cleanup();
    });
  }

  @override
  Future<dynamic> get(String key) async {
    final entry = _cache[key];
    if (entry == null) {
      _stats.misses++;
      return null;
    }

    if (entry.isExpired) {
      _cache.remove(key);
      _stats.misses++;
      _stats.evictions++;
      _updateStats();
      return null;
    }

    entry.updateAccess();
    _stats.hits++;
    return entry.value;
  }

  @override
  Future<bool> set(String key, dynamic value, {Duration? ttl, List<String>? tags}) async {
    try {
      final valueBytes = _calculateSize(value);
      
      // Check if single entry is too large
      if (valueBytes > maxSizeBytes) {
        logWarning('Value too large for memory cache: $valueBytes bytes', tag: 'CACHE');
        return false;
      }

      // Evict entries if necessary
      await _evictIfNecessary(valueBytes);

      final expiresAt = ttl != null ? DateTime.now().add(ttl) : null;
      final entry = CacheEntry(
        key: key,
        value: value,
        createdAt: DateTime.now(),
        expiresAt: expiresAt,
        tags: tags ?? [],
        sizeBytes: valueBytes,
      );

      _cache[key] = entry;
      _stats.sets++;
      _updateStats();
      return true;
    } catch (e) {
      logError('Error setting cache entry: $e', tag: 'CACHE');
      return false;
    }
  }

  @override
  Future<bool> delete(String key) async {
    final entry = _cache.remove(key);
    if (entry != null) {
      _stats.deletes++;
      _updateStats();
      return true;
    }
    return false;
  }

  @override
  Future<bool> exists(String key) async {
    final entry = _cache[key];
    return entry != null && !entry.isExpired;
  }

  @override
  Future<void> clear() async {
    _cache.clear();
    _stats.hits = 0;
    _stats.misses = 0;
    _stats.sets = 0;
    _stats.deletes = 0;
    _stats.evictions = 0;
    _updateStats();
  }

  @override
  CacheStats get stats => _stats;

  @override
  Future<void> cleanup() async {
    final expiredKeys = _cache.entries
        .where((entry) => entry.value.isExpired)
        .map((entry) => entry.key)
        .toList();

    for (final key in expiredKeys) {
      _cache.remove(key);
      _stats.evictions++;
    }

    _updateStats();

    if (expiredKeys.isNotEmpty) {
      logDebug('Cleaned up ${expiredKeys.length} expired cache entries', tag: 'CACHE');
    }
  }

  Future<void> _evictIfNecessary(int newEntrySize) async {
    // Check entry count limit
    while (_cache.length >= maxEntries) {
      await _evictLRU();
    }

    // Check size limit
    while (_stats.totalSizeBytes + newEntrySize > maxSizeBytes && _cache.isNotEmpty) {
      await _evictLRU();
    }
  }

  Future<void> _evictLRU() async {
    if (_cache.isEmpty) return;

    // Find least recently used entry
    CacheEntry? lruEntry;
    String? lruKey;

    for (final entry in _cache.entries) {
      if (lruEntry == null || entry.value.lastAccessed.isBefore(lruEntry.lastAccessed)) {
        lruEntry = entry.value;
        lruKey = entry.key;
      }
    }

    if (lruKey != null) {
      _cache.remove(lruKey);
      _stats.evictions++;
    }
  }

  int _calculateSize(dynamic value) {
    try {
      final jsonString = jsonEncode(value);
      return utf8.encode(jsonString).length;
    } catch (e) {
      // Fallback size estimation
      if (value is String) return value.length * 2;
      if (value is List) return value.length * 100; // Rough estimate
      if (value is Map) return value.length * 200; // Rough estimate
      return 1024; // Default estimate
    }
  }

  void _updateStats() {
    _stats.entryCount = _cache.length;
    _stats.totalSizeBytes = _cache.values
        .fold(0, (sum, entry) => sum + entry.sizeBytes);
  }

  void dispose() {
    _cleanupTimer?.cancel();
  }
}

/// Persistent cache using SharedPreferences
class PersistentCache implements CacheBackend {
  final String keyPrefix;
  final CacheStats _stats = CacheStats();
  SharedPreferences? _prefs;
  final Map<String, CacheEntry> _metadata = {};

  PersistentCache({this.keyPrefix = 'cache_'});

  Future<void> _ensureInitialized() async {
    _prefs ??= await SharedPreferences.getInstance();
    await _loadMetadata();
  }

  Future<void> _loadMetadata() async {
    final keys = _prefs!.getKeys().where((key) => key.startsWith(keyPrefix));
    
    for (final key in keys) {
      try {
        final data = _prefs!.getString(key);
        if (data != null) {
          final map = jsonDecode(data);
          final entry = CacheEntry.fromMap(map);
          _metadata[entry.key] = entry;
        }
      } catch (e) {
        // Remove corrupted entries
        await _prefs!.remove(key);
      }
    }

    _updateStats();
  }

  String _makeKey(String key) => '$keyPrefix$key';

  @override
  Future<dynamic> get(String key) async {
    await _ensureInitialized();
    
    final entry = _metadata[key];
    if (entry == null) {
      _stats.misses++;
      return null;
    }

    if (entry.isExpired) {
      await delete(key);
      _stats.misses++;
      return null;
    }

    entry.updateAccess();
    _stats.hits++;
    
    // Save updated metadata
    await _saveEntry(entry);
    
    return entry.value;
  }

  @override
  Future<bool> set(String key, dynamic value, {Duration? ttl, List<String>? tags}) async {
    await _ensureInitialized();

    try {
      final sizeBytes = _calculateSize(value);
      final expiresAt = ttl != null ? DateTime.now().add(ttl) : null;
      
      final entry = CacheEntry(
        key: key,
        value: value,
        createdAt: DateTime.now(),
        expiresAt: expiresAt,
        tags: tags ?? [],
        sizeBytes: sizeBytes,
      );

      await _saveEntry(entry);
      _metadata[key] = entry;
      _stats.sets++;
      _updateStats();
      
      return true;
    } catch (e) {
      logError('Error setting persistent cache entry: $e', tag: 'CACHE');
      return false;
    }
  }

  @override
  Future<bool> delete(String key) async {
    await _ensureInitialized();
    
    final prefKey = _makeKey(key);
    final existed = await _prefs!.remove(prefKey);
    
    if (_metadata.remove(key) != null) {
      _stats.deletes++;
      _updateStats();
      return true;
    }
    
    return existed;
  }

  @override
  Future<bool> exists(String key) async {
    await _ensureInitialized();
    final entry = _metadata[key];
    return entry != null && !entry.isExpired;
  }

  @override
  Future<void> clear() async {
    await _ensureInitialized();
    
    final keys = _prefs!.getKeys().where((key) => key.startsWith(keyPrefix));
    for (final key in keys) {
      await _prefs!.remove(key);
    }
    
    _metadata.clear();
    _stats.hits = 0;
    _stats.misses = 0;
    _stats.sets = 0;
    _stats.deletes = 0;
    _stats.evictions = 0;
    _updateStats();
  }

  @override
  CacheStats get stats => _stats;

  @override
  Future<void> cleanup() async {
    await _ensureInitialized();
    
    final expiredKeys = _metadata.entries
        .where((entry) => entry.value.isExpired)
        .map((entry) => entry.key)
        .toList();

    for (final key in expiredKeys) {
      await delete(key);
      _stats.evictions++;
    }

    if (expiredKeys.isNotEmpty) {
      logDebug('Cleaned up ${expiredKeys.length} expired persistent cache entries', tag: 'CACHE');
    }
  }

  Future<void> _saveEntry(CacheEntry entry) async {
    final prefKey = _makeKey(entry.key);
    final data = jsonEncode(entry.toMap());
    await _prefs!.setString(prefKey, data);
  }

  int _calculateSize(dynamic value) {
    try {
      final jsonString = jsonEncode(value);
      return utf8.encode(jsonString).length;
    } catch (e) {
      return 1024; // Default estimate
    }
  }

  void _updateStats() {
    _stats.entryCount = _metadata.length;
    _stats.totalSizeBytes = _metadata.values
        .fold(0, (sum, entry) => sum + entry.sizeBytes);
  }
}

/// Multi-tier cache manager
class SmartCacheService {
  static final SmartCacheService _instance = SmartCacheService._internal();
  factory SmartCacheService() => _instance;
  SmartCacheService._internal();

  final Map<CacheTier, CacheBackend> _tiers = {};
  final Map<String, List<String>> _keyTags = {};
  final Map<String, List<DateTime>> _accessHistory = {};
  Timer? _analyticsTimer;
  
  // Configuration
  int maxMemoryEntries = 1000;
  int maxMemorySizeBytes = 50 * 1024 * 1024; // 50MB
  Duration defaultTTL = const Duration(hours: 1);
  int promotionThreshold = 3; // Promote to higher tier after N accesses

  /// Initialize the cache service
  Future<void> initialize() async {
    _tiers[CacheTier.memory] = MemoryCache(
      maxEntries: maxMemoryEntries,
      maxSizeBytes: maxMemorySizeBytes,
    );
    
    _tiers[CacheTier.persistent] = PersistentCache();
    
    // Start analytics collection
    _startAnalytics();
    
    logInfo('Smart cache service initialized', tag: 'CACHE');
  }

  /// Get value from cache
  Future<T?> get<T>(String key, {List<String>? tags}) async {
    _recordAccess(key);
    
    // Try each tier in order (fastest first)
    for (final tier in CacheTier.values) {
      final backend = _tiers[tier];
      if (backend == null) continue;
      
      try {
        final value = await backend.get(key);
        if (value != null) {
          // Promote to higher tiers if accessed frequently
          await _promoteIfNeeded(key, value, tier);
          return value as T?;
        }
      } catch (e) {
        logError('Error getting from ${tier.name} cache: $e', tag: 'CACHE');
      }
    }
    
    return null;
  }

  /// Set value in cache
  Future<bool> set<T>(String key, T value, {
    Duration? ttl,
    List<String>? tags,
    CacheTier? preferredTier,
  }) async {
    ttl ??= defaultTTL;
    
    if (tags != null) {
      _keyTags[key] = tags;
    }

    // If preferred tier is specified, try that first
    if (preferredTier != null) {
      final backend = _tiers[preferredTier];
      if (backend != null) {
        final success = await backend.set(key, value, ttl: ttl, tags: tags);
        if (success) return true;
      }
    }

    // Try all tiers (write-through strategy)
    bool anySuccess = false;
    for (final tier in CacheTier.values) {
      final backend = _tiers[tier];
      if (backend == null) continue;
      
      try {
        final success = await backend.set(key, value, ttl: ttl, tags: tags);
        if (success) anySuccess = true;
      } catch (e) {
        logError('Error setting in ${tier.name} cache: $e', tag: 'CACHE');
      }
    }

    return anySuccess;
  }

  /// Get value or set using factory function
  Future<T> getOrSet<T>(
    String key,
    Future<T> Function() factory, {
    Duration? ttl,
    List<String>? tags,
    CacheTier? preferredTier,
  }) async {
    final cached = await get<T>(key, tags: tags);
    if (cached != null) {
      return cached;
    }

    final value = await factory();
    await set(key, value, ttl: ttl, tags: tags, preferredTier: preferredTier);
    return value;
  }

  /// Delete key from all tiers
  Future<bool> delete(String key) async {
    _keyTags.remove(key);
    _accessHistory.remove(key);
    
    bool anySuccess = false;
    for (final backend in _tiers.values) {
      try {
        final success = await backend.delete(key);
        if (success) anySuccess = true;
      } catch (e) {
        logError('Error deleting from cache: $e', tag: 'CACHE');
      }
    }

    return anySuccess;
  }

  /// Delete all keys with specified tags
  Future<int> deleteByTags(List<String> tags) async {
    int deletedCount = 0;
    
    final keysToDelete = _keyTags.entries
        .where((entry) => entry.value.any((tag) => tags.contains(tag)))
        .map((entry) => entry.key)
        .toList();

    for (final key in keysToDelete) {
      if (await delete(key)) {
        deletedCount++;
      }
    }

    return deletedCount;
  }

  /// Check if key exists in any tier
  Future<bool> exists(String key) async {
    for (final backend in _tiers.values) {
      try {
        if (await backend.exists(key)) {
          return true;
        }
      } catch (e) {
        logError('Error checking existence in cache: $e', tag: 'CACHE');
      }
    }
    return false;
  }

  /// Clear all caches
  Future<void> clear() async {
    _keyTags.clear();
    _accessHistory.clear();
    
    for (final backend in _tiers.values) {
      try {
        await backend.clear();
      } catch (e) {
        logError('Error clearing cache: $e', tag: 'CACHE');
      }
    }
  }

  /// Get comprehensive cache statistics
  Map<String, dynamic> getStats() {
    final stats = <String, dynamic>{};
    
    for (final entry in _tiers.entries) {
      stats['${entry.key.name}_cache'] = entry.value.stats.toMap();
    }

    // Overall statistics
    final totalHits = _tiers.values.fold(0, (sum, backend) => sum + backend.stats.hits);
    final totalMisses = _tiers.values.fold(0, (sum, backend) => sum + backend.stats.misses);
    final totalEntries = _tiers.values.fold(0, (sum, backend) => sum + backend.stats.entryCount);

    stats['overall'] = {
      'totalHits': totalHits,
      'totalMisses': totalMisses,
      'totalEntries': totalEntries,
      'hitRate': totalHits + totalMisses > 0 ? (totalHits / (totalHits + totalMisses)) * 100 : 0.0,
      'taggedKeys': _keyTags.length,
      'frequentlyAccessedKeys': _accessHistory.entries.where((e) => e.value.length >= promotionThreshold).length,
    };

    return stats;
  }

  /// Get cache analytics report
  Map<String, dynamic> getAnalyticsReport() {
    final now = DateTime.now();
    final oneHourAgo = now.subtract(const Duration(hours: 1));
    
    // Recent activity
    final recentActivity = <String, int>{};
    for (final entry in _accessHistory.entries) {
      final recentAccesses = entry.value.where((time) => time.isAfter(oneHourAgo)).length;
      if (recentAccesses > 0) {
        recentActivity[entry.key] = recentAccesses;
      }
    }

    // Popular keys
    final popularKeys = _accessHistory.entries
        .map((e) => {'key': e.key, 'accesses': e.value.length})
        .toList()
      ..sort((a, b) => (b['accesses'] as int).compareTo(a['accesses'] as int));

    // Tag analysis
    final tagCounts = <String, int>{};
    for (final tags in _keyTags.values) {
      for (final tag in tags) {
        tagCounts[tag] = (tagCounts[tag] ?? 0) + 1;
      }
    }

    return {
      'timestamp': now.toIso8601String(),
      'recentActivity': Map.fromEntries(
        recentActivity.entries.take(20).map((e) => MapEntry(e.key, e.value))
      ),
      'popularKeys': popularKeys.take(20).toList(),
      'tagUsage': Map.fromEntries(
        (tagCounts.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value))).take(10)
      ),
      'recommendations': _generateRecommendations(),
    };
  }

  /// Clean up expired entries in all tiers
  Future<void> cleanup() async {
    for (final backend in _tiers.values) {
      try {
        await backend.cleanup();
      } catch (e) {
        logError('Error during cache cleanup: $e', tag: 'CACHE');
      }
    }
  }

  /// Dispose resources
  void dispose() {
    _analyticsTimer?.cancel();
    
    for (final backend in _tiers.values) {
      if (backend is MemoryCache) {
        backend.dispose();
      }
    }
  }

  void _recordAccess(String key) {
    final now = DateTime.now();
    _accessHistory[key] ??= [];
    _accessHistory[key]!.add(now);
    
    // Keep only recent access history (last 100 accesses per key)
    if (_accessHistory[key]!.length > 100) {
      _accessHistory[key] = _accessHistory[key]!.sublist(_accessHistory[key]!.length - 100);
    }
  }

  Future<void> _promoteIfNeeded(String key, dynamic value, CacheTier currentTier) async {
    final accessCount = _accessHistory[key]?.length ?? 0;
    
    if (accessCount >= promotionThreshold && currentTier != CacheTier.memory) {
      // Promote to memory cache
      final memoryCache = _tiers[CacheTier.memory];
      if (memoryCache != null) {
        try {
          await memoryCache.set(key, value, tags: _keyTags[key]);
          logDebug('Promoted key $key to memory cache', tag: 'CACHE');
        } catch (e) {
          logError('Failed to promote key $key: $e', tag: 'CACHE');
        }
      }
    }
  }

  void _startAnalytics() {
    _analyticsTimer = Timer.periodic(const Duration(minutes: 10), (timer) {
      final stats = getStats();
      logDebug('Cache Stats: ${stats['overall']}', tag: 'CACHE');
    });
  }

  List<String> _generateRecommendations() {
    final recommendations = <String>[];
    final stats = getStats();
    final overallStats = stats['overall'] as Map<String, dynamic>;
    
    // Check hit rate
    final hitRate = overallStats['hitRate'] as double;
    if (hitRate < 60) {
      recommendations.add('Low overall hit rate (${hitRate.toStringAsFixed(1)}%) - consider increasing TTL or reviewing cache keys');
    }

    // Check memory usage
    final memoryStats = stats['memory_cache'] as Map<String, dynamic>?;
    if (memoryStats != null) {
      final entryCount = memoryStats['entryCount'] as int;
      if (entryCount > maxMemoryEntries * 0.8) {
        recommendations.add('Memory cache is ${((entryCount / maxMemoryEntries) * 100).toStringAsFixed(1)}% full - consider increasing size or improving eviction');
      }
    }

    // Check for unused tags
    final taggedKeysCount = overallStats['taggedKeys'] as int;
    if (taggedKeysCount < overallStats['totalEntries'] * 0.5) {
      recommendations.add('Consider using more cache tags for better organization and selective invalidation');
    }

    // Check for frequently accessed keys
    final frequentKeys = overallStats['frequentlyAccessedKeys'] as int;
    if (frequentKeys > 0) {
      recommendations.add('$frequentKeys keys are frequently accessed - ensure they are in the memory tier');
    }

    if (recommendations.isEmpty) {
      recommendations.add('Cache performance is optimal!');
    }

    return recommendations;
  }
}
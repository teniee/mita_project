import 'dart:async';
import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:crypto/crypto.dart';
import 'logging_service.dart';

/// Advanced offline service with intelligent caching and sync
class AdvancedOfflineService {
  static final AdvancedOfflineService _instance = AdvancedOfflineService._internal();
  factory AdvancedOfflineService() => _instance;
  AdvancedOfflineService._internal();

  Database? _database;
  final Connectivity _connectivity = Connectivity();
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;

  // Cache management
  final Map<String, CacheEntry> _memoryCache = {};
  final int _maxCacheSize = 100; // Maximum items in memory cache
  final Duration _defaultCacheExpiry = const Duration(hours: 1);

  // Sync management
  final List<PendingSync> _pendingSyncs = [];
  Timer? _syncTimer;
  bool _isOnline = true;
  bool _isSyncing = false;

  /// Initialize the offline service
  Future<void> initialize() async {
    await _initializeDatabase();
    await _startConnectivityMonitoring();
    await _startPeriodicSync();
    await _loadPendingSyncs();
  }

  /// Initialize SQLite database for offline storage
  Future<void> _initializeDatabase() async {
    final databasesPath = await getDatabasesPath();
    final path = join(databasesPath, 'mita_offline.db');

    _database = await openDatabase(
      path,
      version: 3,
      onCreate: _createTables,
      onUpgrade: _upgradeTables,
    );
  }

  /// Create database tables
  Future<void> _createTables(Database db, int version) async {
    // Cache table for API responses
    await db.execute('''
      CREATE TABLE cache (
        key TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        content_type TEXT,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        etag TEXT,
        last_modified TEXT,
        size INTEGER DEFAULT 0
      )
    ''');

    // Pending sync operations
    await db.execute('''
      CREATE TABLE pending_syncs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL,
        method TEXT NOT NULL,
        data TEXT,
        headers TEXT,
        priority INTEGER DEFAULT 1,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        created_at INTEGER NOT NULL,
        scheduled_at INTEGER NOT NULL
      )
    ''');

    // User data for offline access
    await db.execute('''
      CREATE TABLE offline_user_data (
        user_id INTEGER PRIMARY KEY,
        profile_data TEXT NOT NULL,
        settings TEXT,
        last_updated INTEGER NOT NULL
      )
    ''');

    // Expenses for offline access
    await db.execute('''
      CREATE TABLE offline_expenses (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_synced INTEGER DEFAULT 0,
        local_id TEXT,
        sync_hash TEXT
      )
    ''');

    // Transactions for offline access
    await db.execute('''
      CREATE TABLE offline_transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_synced INTEGER DEFAULT 0,
        local_id TEXT,
        sync_hash TEXT
      )
    ''');

    // Budget data for offline access
    await db.execute('''
      CREATE TABLE offline_budget (
        user_id INTEGER PRIMARY KEY,
        monthly_income REAL,
        savings_target REAL,
        categories TEXT,
        last_updated INTEGER NOT NULL,
        is_synced INTEGER DEFAULT 0
      )
    ''');

    // Create indexes for better performance
    await _createIndexes(db);
  }

  /// Create database indexes
  Future<void> _createIndexes(Database db) async {
    await db.execute('CREATE INDEX idx_cache_expires_at ON cache(expires_at)');
    await db.execute(
        'CREATE INDEX idx_pending_syncs_priority ON pending_syncs(priority DESC, created_at ASC)');
    await db.execute(
        'CREATE INDEX idx_offline_expenses_user_date ON offline_expenses(user_id, date DESC)');
    await db.execute(
        'CREATE INDEX idx_offline_transactions_user_date ON offline_transactions(user_id, created_at DESC)');
    await db.execute(
        'CREATE INDEX idx_offline_expenses_synced ON offline_expenses(is_synced, user_id)');
  }

  /// Upgrade database tables
  Future<void> _upgradeTables(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      await db.execute('ALTER TABLE cache ADD COLUMN size INTEGER DEFAULT 0');
    }
    if (oldVersion < 3) {
      await db.execute('ALTER TABLE pending_syncs ADD COLUMN scheduled_at INTEGER DEFAULT 0');
      await db.execute('UPDATE pending_syncs SET scheduled_at = created_at WHERE scheduled_at = 0');
    }
  }

  /// Start monitoring connectivity
  Future<void> _startConnectivityMonitoring() async {
    // Check initial connectivity
    final results = await _connectivity.checkConnectivity();
    final result = results.isNotEmpty ? results.first : ConnectivityResult.none;
    _isOnline = result != ConnectivityResult.none;

    // Listen for connectivity changes
    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(
      (List<ConnectivityResult> results) {
        final result = results.isNotEmpty ? results.first : ConnectivityResult.none;
        final wasOnline = _isOnline;
        _isOnline = result != ConnectivityResult.none;

        if (!wasOnline && _isOnline) {
          // Just came online - trigger sync
          _triggerSync();
        }
      },
    );
  }

  /// Start periodic sync timer
  Future<void> _startPeriodicSync() async {
    logInfo('Starting periodic sync timer', tag: 'OFFLINE_SERVICE');

    _syncTimer = Timer.periodic(const Duration(minutes: 5), (timer) {
      if (_isOnline && !_isSyncing) {
        logDebug('Triggering scheduled sync', tag: 'OFFLINE_SERVICE');
        _triggerSync();
      }
    });
  }

  /// Load pending syncs from database
  Future<void> _loadPendingSyncs() async {
    if (_database == null) return;

    final List<Map<String, dynamic>> results = await _database!.query(
      'pending_syncs',
      orderBy: 'priority DESC, created_at ASC',
    );

    _pendingSyncs.clear();
    for (final row in results) {
      _pendingSyncs.add(PendingSync.fromMap(row));
    }
  }

  /// Cache API response with intelligent storage
  Future<void> cacheResponse({
    required String key,
    required String data,
    String? contentType,
    Duration? expiry,
    String? etag,
    String? lastModified,
  }) async {
    if (_database == null) return;

    final now = DateTime.now().millisecondsSinceEpoch;
    final expiresAt = now + (expiry ?? _defaultCacheExpiry).inMilliseconds;
    final dataSize = utf8.encode(data).length;

    // Store in database
    await _database!.insert(
      'cache',
      {
        'key': key,
        'data': data,
        'content_type': contentType,
        'created_at': now,
        'expires_at': expiresAt,
        'etag': etag,
        'last_modified': lastModified,
        'size': dataSize,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    // Store in memory cache if small enough
    if (dataSize < 1024 * 100) {
      // 100KB limit for memory cache
      _memoryCache[key] = CacheEntry(
        data: data,
        contentType: contentType,
        createdAt: DateTime.fromMillisecondsSinceEpoch(now),
        expiresAt: DateTime.fromMillisecondsSinceEpoch(expiresAt),
        etag: etag,
        lastModified: lastModified,
      );

      // Clean memory cache if too large
      if (_memoryCache.length > _maxCacheSize) {
        _cleanMemoryCache();
      }
    }

    // Clean expired entries periodically
    if (DateTime.now().minute % 10 == 0) {
      _cleanExpiredCache();
    }
  }

  /// Get cached response
  Future<CacheEntry?> getCachedResponse(String key) async {
    // Check memory cache first
    if (_memoryCache.containsKey(key)) {
      final entry = _memoryCache[key]!;
      if (entry.expiresAt.isAfter(DateTime.now())) {
        return entry;
      } else {
        _memoryCache.remove(key);
      }
    }

    // Check database cache
    if (_database == null) return null;

    final List<Map<String, dynamic>> results = await _database!.query(
      'cache',
      where: 'key = ? AND expires_at > ?',
      whereArgs: [key, DateTime.now().millisecondsSinceEpoch],
    );

    if (results.isNotEmpty) {
      final row = results.first;
      return CacheEntry(
        data: row['data'],
        contentType: row['content_type'],
        createdAt: DateTime.fromMillisecondsSinceEpoch(row['created_at']),
        expiresAt: DateTime.fromMillisecondsSinceEpoch(row['expires_at']),
        etag: row['etag'],
        lastModified: row['last_modified'],
      );
    }

    return null;
  }

  /// Store expense offline
  Future<String> storeExpenseOffline({
    required int userId,
    required double amount,
    required String category,
    String? description,
    required DateTime date,
  }) async {
    if (_database == null) throw Exception('Database not initialized');

    final localId = _generateLocalId();
    final syncHash = _generateSyncHash({
      'user_id': userId,
      'amount': amount,
      'category': category,
      'description': description,
      'date': date.toIso8601String(),
    });

    await _database!.insert('offline_expenses', {
      'user_id': userId,
      'amount': amount,
      'category': category,
      'description': description,
      'date': date.toIso8601String(),
      'created_at': DateTime.now().toIso8601String(),
      'is_synced': 0,
      'local_id': localId,
      'sync_hash': syncHash,
    });

    // Add to sync queue
    await _addToSyncQueue(
      endpoint: '/expense/add',
      method: 'POST',
      data: {
        'amount': amount,
        'category': category,
        'description': description,
        'date': date.toIso8601String(),
        'local_id': localId,
      },
      priority: 2, // High priority for user actions
    );

    return localId;
  }

  /// Get offline expenses
  Future<List<Map<String, dynamic>>> getOfflineExpenses(int userId, {int? limit}) async {
    if (_database == null) return [];

    return await _database!.query(
      'offline_expenses',
      where: 'user_id = ?',
      whereArgs: [userId],
      orderBy: 'date DESC, created_at DESC',
      limit: limit,
    );
  }

  /// Store user data offline
  Future<void> storeUserDataOffline({
    required int userId,
    required Map<String, dynamic> profileData,
    Map<String, dynamic>? settings,
  }) async {
    if (_database == null) return;

    await _database!.insert(
      'offline_user_data',
      {
        'user_id': userId,
        'profile_data': jsonEncode(profileData),
        'settings': settings != null ? jsonEncode(settings) : null,
        'last_updated': DateTime.now().millisecondsSinceEpoch,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get offline user data
  Future<Map<String, dynamic>?> getOfflineUserData(int userId) async {
    if (_database == null) return null;

    final List<Map<String, dynamic>> results = await _database!.query(
      'offline_user_data',
      where: 'user_id = ?',
      whereArgs: [userId],
    );

    if (results.isNotEmpty) {
      final row = results.first;
      return {
        'profile_data': jsonDecode(row['profile_data']),
        'settings': row['settings'] != null ? jsonDecode(row['settings']) : null,
        'last_updated': DateTime.fromMillisecondsSinceEpoch(row['last_updated']),
      };
    }

    return null;
  }

  /// Add operation to sync queue
  Future<void> _addToSyncQueue({
    required String endpoint,
    required String method,
    Map<String, dynamic>? data,
    Map<String, String>? headers,
    int priority = 1,
    int maxRetries = 3,
    DateTime? scheduledAt,
  }) async {
    if (_database == null) return;

    final now = DateTime.now().millisecondsSinceEpoch;
    final scheduled = scheduledAt?.millisecondsSinceEpoch ?? now;

    final id = await _database!.insert('pending_syncs', {
      'endpoint': endpoint,
      'method': method,
      'data': data != null ? jsonEncode(data) : null,
      'headers': headers != null ? jsonEncode(headers) : null,
      'priority': priority,
      'retry_count': 0,
      'max_retries': maxRetries,
      'created_at': now,
      'scheduled_at': scheduled,
    });

    _pendingSyncs.add(PendingSync(
      id: id,
      endpoint: endpoint,
      method: method,
      data: data,
      headers: headers,
      priority: priority,
      retryCount: 0,
      maxRetries: maxRetries,
      createdAt: DateTime.fromMillisecondsSinceEpoch(now),
      scheduledAt: DateTime.fromMillisecondsSinceEpoch(scheduled),
    ));

    // Sort by priority
    _pendingSyncs.sort((a, b) {
      final priorityCompare = b.priority.compareTo(a.priority);
      if (priorityCompare != 0) return priorityCompare;
      return a.createdAt.compareTo(b.createdAt);
    });
  }

  /// Trigger sync process
  Future<void> _triggerSync() async {
    if (!_isOnline || _isSyncing || _pendingSyncs.isEmpty) return;

    _isSyncing = true;

    try {
      await _processPendingSyncs();
    } finally {
      _isSyncing = false;
    }
  }

  /// Process pending sync operations
  Future<void> _processPendingSyncs() async {
    final now = DateTime.now();
    final toProcess = _pendingSyncs
        .where((sync) => sync.scheduledAt.isBefore(now) || sync.scheduledAt.isAtSameMomentAs(now))
        .toList();

    for (final sync in toProcess) {
      try {
        await _processSingleSync(sync);
        await _removeSyncFromQueue(sync.id);
        _pendingSyncs.remove(sync);
      } catch (e) {
        await _handleSyncFailure(sync, e);
      }
    }
  }

  /// Process a single sync operation
  Future<void> _processSingleSync(PendingSync sync) async {
    // This would integrate with your ApiService
    // For now, this is a placeholder
    logDebug('Processing sync: ${sync.method} ${sync.endpoint}', tag: 'OFFLINE');

    // Simulate API call
    await Future.delayed(const Duration(milliseconds: 500));

    // Mark as synced in local database if it's a local record
    if (sync.data != null && sync.data!.containsKey('local_id')) {
      await _markLocalRecordAsSynced(sync.data!['local_id']);
    }
  }

  /// Handle sync failure
  Future<void> _handleSyncFailure(PendingSync sync, dynamic error) async {
    if (_database == null) return;

    final newRetryCount = sync.retryCount + 1;

    if (newRetryCount >= sync.maxRetries) {
      // Max retries reached, remove from queue
      await _removeSyncFromQueue(sync.id);
      _pendingSyncs.remove(sync);
      logError('Sync failed permanently: ${sync.endpoint} - $error', tag: 'OFFLINE');
    } else {
      // Update retry count and schedule for later
      final backoffDelay = Duration(minutes: newRetryCount * 5); // Exponential backoff
      final newScheduledAt = DateTime.now().add(backoffDelay);

      await _database!.update(
        'pending_syncs',
        {
          'retry_count': newRetryCount,
          'scheduled_at': newScheduledAt.millisecondsSinceEpoch,
        },
        where: 'id = ?',
        whereArgs: [sync.id],
      );

      sync.retryCount = newRetryCount;
      sync.scheduledAt = newScheduledAt;

      logWarning('Sync failed, retrying later: ${sync.endpoint} - $error', tag: 'OFFLINE');
    }
  }

  /// Remove sync from queue
  Future<void> _removeSyncFromQueue(int syncId) async {
    if (_database == null) return;

    await _database!.delete(
      'pending_syncs',
      where: 'id = ?',
      whereArgs: [syncId],
    );
  }

  /// Mark local record as synced
  Future<void> _markLocalRecordAsSynced(String localId) async {
    if (_database == null) return;

    await _database!.update(
      'offline_expenses',
      {'is_synced': 1},
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Clean expired cache entries
  Future<void> _cleanExpiredCache() async {
    if (_database == null) return;

    final now = DateTime.now().millisecondsSinceEpoch;

    await _database!.delete(
      'cache',
      where: 'expires_at < ?',
      whereArgs: [now],
    );

    // Clean memory cache
    _memoryCache.removeWhere((key, entry) => entry.expiresAt.isBefore(DateTime.now()));
  }

  /// Clean memory cache when it gets too large
  void _cleanMemoryCache() {
    if (_memoryCache.length <= _maxCacheSize) return;

    // Remove oldest entries
    final entries = _memoryCache.entries.toList();
    entries.sort((a, b) => a.value.createdAt.compareTo(b.value.createdAt));

    final toRemove = entries.length - _maxCacheSize;
    for (int i = 0; i < toRemove; i++) {
      _memoryCache.remove(entries[i].key);
    }
  }

  /// Generate local ID for offline records
  String _generateLocalId() {
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final random = timestamp.hashCode;
    return 'local_${timestamp}_$random';
  }

  /// Generate sync hash for duplicate detection
  String _generateSyncHash(Map<String, dynamic> data) {
    final dataString = jsonEncode(data);
    final bytes = utf8.encode(dataString);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Get sync status
  Future<SyncStatus> getSyncStatus() async {
    if (_database == null) {
      return SyncStatus(
        isOnline: _isOnline,
        isSyncing: _isSyncing,
        pendingSyncs: 0,
        failedSyncs: 0,
        cacheSize: 0,
      );
    }

    final pendingCount = await _database!.rawQuery('SELECT COUNT(*) as count FROM pending_syncs');
    final failedCount = await _database!
        .rawQuery('SELECT COUNT(*) as count FROM pending_syncs WHERE retry_count >= max_retries');
    final cacheCount = await _database!.rawQuery('SELECT COUNT(*) as count FROM cache');

    return SyncStatus(
      isOnline: _isOnline,
      isSyncing: _isSyncing,
      pendingSyncs: pendingCount.first['count'] as int,
      failedSyncs: failedCount.first['count'] as int,
      cacheSize: cacheCount.first['count'] as int,
    );
  }

  /// Clear all offline data
  Future<void> clearOfflineData() async {
    if (_database == null) return;

    await _database!.delete('cache');
    await _database!.delete('pending_syncs');
    await _database!.delete('offline_user_data');
    await _database!.delete('offline_expenses');
    await _database!.delete('offline_transactions');
    await _database!.delete('offline_budget');

    _memoryCache.clear();
    _pendingSyncs.clear();
  }

  /// Dispose resources
  void dispose() {
    _connectivitySubscription?.cancel();
    _syncTimer?.cancel();
    _database?.close();
  }
}

/// Cache entry model
class CacheEntry {
  final String data;
  final String? contentType;
  final DateTime createdAt;
  final DateTime expiresAt;
  final String? etag;
  final String? lastModified;

  CacheEntry({
    required this.data,
    this.contentType,
    required this.createdAt,
    required this.expiresAt,
    this.etag,
    this.lastModified,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);
}

/// Pending sync operation model
class PendingSync {
  final int id;
  final String endpoint;
  final String method;
  final Map<String, dynamic>? data;
  final Map<String, String>? headers;
  final int priority;
  int retryCount;
  final int maxRetries;
  final DateTime createdAt;
  DateTime scheduledAt;

  PendingSync({
    required this.id,
    required this.endpoint,
    required this.method,
    this.data,
    this.headers,
    required this.priority,
    required this.retryCount,
    required this.maxRetries,
    required this.createdAt,
    required this.scheduledAt,
  });

  factory PendingSync.fromMap(Map<String, dynamic> map) {
    return PendingSync(
      id: map['id'],
      endpoint: map['endpoint'],
      method: map['method'],
      data: map['data'] != null ? jsonDecode(map['data']) : null,
      headers: map['headers'] != null ? Map<String, String>.from(jsonDecode(map['headers'])) : null,
      priority: map['priority'],
      retryCount: map['retry_count'],
      maxRetries: map['max_retries'],
      createdAt: DateTime.fromMillisecondsSinceEpoch(map['created_at']),
      scheduledAt: DateTime.fromMillisecondsSinceEpoch(map['scheduled_at']),
    );
  }
}

/// Sync status model
class SyncStatus {
  final bool isOnline;
  final bool isSyncing;
  final int pendingSyncs;
  final int failedSyncs;
  final int cacheSize;

  SyncStatus({
    required this.isOnline,
    required this.isSyncing,
    required this.pendingSyncs,
    required this.failedSyncs,
    required this.cacheSize,
  });
}

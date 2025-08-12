import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'iap_service.dart';
import 'logging_service.dart';
import 'api_service.dart';

/// Service to manage premium feature access and enforcement
class PremiumFeatureService {
  static const String _featureCacheKey = 'premium_features_cache';
  static const String _lastFeatureCheckKey = 'last_feature_check';
  static const Duration _featureCacheValidDuration = Duration(minutes: 15);

  final IapService _iapService;
  final LoggingService _logger = LoggingService();
  final ApiService _apiService = ApiService();
  
  // Cache for feature availability
  Map<PremiumFeature, bool> _featureCache = {};
  DateTime? _lastFeatureUpdate;
  
  // Stream controllers for feature updates
  final StreamController<Map<PremiumFeature, bool>> _featureUpdateController =
      StreamController<Map<PremiumFeature, bool>>.broadcast();
  
  /// Stream of feature availability changes
  Stream<Map<PremiumFeature, bool>> get featureUpdatesStream => 
      _featureUpdateController.stream;

  PremiumFeatureService(this._iapService);

  /// Initialize the service
  Future<void> initialize() async {
    try {
      await _loadCachedFeatures();
      await refreshFeatureAvailability();
      _logger.info('Premium Feature Service initialized');
    } catch (e) {
      _logger.error('Failed to initialize Premium Feature Service: $e');
    }
  }

  /// Dispose of resources
  void dispose() {
    _featureUpdateController.close();
  }

  /// Check if a specific feature is available for the current user
  Future<bool> isFeatureAvailable(PremiumFeature feature) async {
    try {
      // Check cache first
      if (_isFeatureCacheValid() && _featureCache.containsKey(feature)) {
        return _featureCache[feature] ?? false;
      }
      
      // Check with IAP service
      final hasFeature = await _iapService.hasFeature(feature);
      
      // Update cache
      _featureCache[feature] = hasFeature;
      await _saveFeaturesCache();
      
      return hasFeature;
    } catch (e) {
      _logger.error('Failed to check feature availability for $feature: $e');
      return _featureCache[feature] ?? false;
    }
  }

  /// Get all available premium features
  Future<Set<PremiumFeature>> getAvailableFeatures() async {
    try {
      // Check cache first
      if (_isFeatureCacheValid()) {
        return _featureCache.entries
            .where((entry) => entry.value)
            .map((entry) => entry.key)
            .toSet();
      }
      
      // Refresh from IAP service
      final features = await _iapService.getAvailableFeatures();
      
      // Update cache
      _featureCache.clear();
      for (final feature in PremiumFeature.values) {
        _featureCache[feature] = features.contains(feature);
      }
      
      await _saveFeaturesCache();
      
      // Notify listeners
      _featureUpdateController.add(Map.from(_featureCache));
      
      return features;
    } catch (e) {
      _logger.error('Failed to get available features: $e');
      return {};
    }
  }

  /// Refresh feature availability from server
  Future<void> refreshFeatureAvailability() async {
    try {
      _logger.info('Refreshing feature availability');
      
      final features = await _iapService.getAvailableFeatures();
      
      // Update cache
      for (final feature in PremiumFeature.values) {
        _featureCache[feature] = features.contains(feature);
      }
      
      _lastFeatureUpdate = DateTime.now();
      await _saveFeaturesCache();
      
      // Notify listeners
      _featureUpdateController.add(Map.from(_featureCache));
      
      _logger.info('Feature availability refreshed successfully');
    } catch (e) {
      _logger.error('Failed to refresh feature availability: $e');
    }
  }

  /// Enforce premium feature access (throws exception if not available)
  Future<void> enforceFeatureAccess(PremiumFeature feature, {String? context}) async {
    final hasAccess = await isFeatureAvailable(feature);
    
    if (!hasAccess) {
      final error = 'Access denied for premium feature: $feature${context != null ? ' (Context: $context)' : ''}';
      _logger.warning(error);
      
      // Track feature access attempts for analytics
      await _trackFeatureAccessAttempt(feature, false, context);
      
      throw PremiumFeatureAccessException(
        feature: feature,
        message: error,
        context: context,
      );
    }
    
    // Track successful feature access
    await _trackFeatureAccessAttempt(feature, true, context);
  }

  /// Get feature usage limits
  Future<FeatureUsageLimits> getFeatureUsageLimits(PremiumFeature feature) async {
    try {
      final isPremium = await _iapService.isPremiumUser();
      
      switch (feature) {
        case PremiumFeature.advancedOcr:
          return FeatureUsageLimits(
            dailyLimit: isPremium ? null : 5,  // Unlimited for premium, 5 for free
            monthlyLimit: isPremium ? null : 50,
            concurrentLimit: isPremium ? 10 : 1,
          );
          
        case PremiumFeature.batchReceiptProcessing:
          return FeatureUsageLimits(
            dailyLimit: isPremium ? null : 0,  // Premium only
            batchSizeLimit: isPremium ? 50 : 0,
            concurrentLimit: isPremium ? 3 : 0,
          );
          
        case PremiumFeature.exportData:
          return FeatureUsageLimits(
            dailyLimit: isPremium ? null : 1,
            monthlyLimit: isPremium ? null : 3,
            formatRestrictions: isPremium ? [] : ['csv'],  // Premium gets all formats
          );
          
        case PremiumFeature.premiumInsights:
          return FeatureUsageLimits(
            dailyLimit: isPremium ? null : 0,  // Premium only
            insightDepth: isPremium ? 'comprehensive' : 'basic',
          );
          
        case PremiumFeature.enhancedAnalytics:
          return FeatureUsageLimits(
            historyLimit: isPremium ? null : Duration(days: 30).inDays,
            advancedMetrics: isPremium,
          );
          
        case PremiumFeature.unlimitedTransactions:
          return FeatureUsageLimits(
            monthlyLimit: isPremium ? null : 100,
          );
          
        case PremiumFeature.customCategories:
          return FeatureUsageLimits(
            categoryLimit: isPremium ? null : 0,  // Premium only
          );
          
        case PremiumFeature.prioritySupport:
          return FeatureUsageLimits(
            responseTime: isPremium ? Duration(hours: 4) : Duration(hours: 48),
            supportChannels: isPremium ? ['chat', 'email', 'phone'] : ['email'],
          );
      }
    } catch (e) {
      _logger.error('Failed to get usage limits for $feature: $e');
      return FeatureUsageLimits();
    }
  }

  /// Track feature usage for analytics and limits enforcement
  Future<void> trackFeatureUsage(
    PremiumFeature feature, {
    Map<String, dynamic>? metadata,
    int? processingTimeMs,
    bool success = true,
  }) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return;
      
      await _apiService.trackPremiumFeatureUsage(
        userId: userId,
        feature: _featureToString(feature),
        metadata: metadata,
        processingTimeMs: processingTimeMs,
        success: success,
      );
      
      _logger.debug('Tracked feature usage: $feature (success: $success)');
    } catch (e) {
      _logger.error('Failed to track feature usage: $e');
    }
  }

  /// Check if user has exceeded usage limits for a feature
  Future<bool> hasExceededUsageLimit(PremiumFeature feature) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return false;
      
      final usageData = await _apiService.getFeatureUsageStats(
        userId: userId,
        feature: _featureToString(feature),
      );
      
      final limits = await getFeatureUsageLimits(feature);
      
      // Check daily limit
      if (limits.dailyLimit != null) {
        final dailyUsage = usageData['daily_usage'] as int? ?? 0;
        if (dailyUsage >= limits.dailyLimit!) {
          return true;
        }
      }
      
      // Check monthly limit
      if (limits.monthlyLimit != null) {
        final monthlyUsage = usageData['monthly_usage'] as int? ?? 0;
        if (monthlyUsage >= limits.monthlyLimit!) {
          return true;
        }
      }
      
      return false;
    } catch (e) {
      _logger.error('Failed to check usage limits for $feature: $e');
      return false;
    }
  }

  /// Get feature usage statistics
  Future<Map<String, dynamic>> getFeatureUsageStats(PremiumFeature feature) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return {};
      
      return await _apiService.getFeatureUsageStats(
        userId: userId,
        feature: _featureToString(feature),
      );
    } catch (e) {
      _logger.error('Failed to get feature usage stats: $e');
      return {};
    }
  }

  /// Check if user can upgrade to access more features
  Future<bool> canUpgradeToPremium() async {
    final isPremium = await _iapService.isPremiumUser();
    return !isPremium;
  }

  /// Get premium upgrade benefits
  Future<List<String>> getPremiumUpgradeBenefits() async {
    return [
      'Advanced OCR with higher accuracy',
      'Batch receipt processing (up to 50 receipts)',
      'Unlimited transaction history',
      'Premium financial insights and analytics',
      'Custom spending categories',
      'Data export in multiple formats (PDF, Excel, CSV)',
      'Priority customer support',
      'Ad-free experience',
    ];
  }

  /// Show premium feature paywall
  Future<bool> showPremiumPaywall({
    required PremiumFeature feature,
    String? context,
  }) async {
    try {
      // Track paywall impression
      await _trackPaywallImpression(feature, context);
      
      // This would typically show a native dialog or navigate to subscription screen
      // For now, we'll just return false to indicate the user didn't upgrade
      return false;
    } catch (e) {
      _logger.error('Failed to show premium paywall: $e');
      return false;
    }
  }

  // Private helper methods

  bool _isFeatureCacheValid() {
    if (_lastFeatureUpdate == null) return false;
    return DateTime.now().difference(_lastFeatureUpdate!) < _featureCacheValidDuration;
  }

  Future<void> _saveFeaturesCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cacheData = {
        'features': _featureCache.map((key, value) => 
            MapEntry(_featureToString(key), value)),
        'last_update': _lastFeatureUpdate?.millisecondsSinceEpoch,
      };
      
      await prefs.setString(_featureCacheKey, jsonEncode(cacheData));
      await prefs.setInt(_lastFeatureCheckKey, DateTime.now().millisecondsSinceEpoch);
    } catch (e) {
      _logger.error('Failed to save features cache: $e');
    }
  }

  Future<void> _loadCachedFeatures() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedData = prefs.getString(_featureCacheKey);
      
      if (cachedData != null) {
        final data = jsonDecode(cachedData) as Map<String, dynamic>;
        final featuresMap = data['features'] as Map<String, dynamic>? ?? {};
        final lastUpdate = data['last_update'] as int?;
        
        _featureCache.clear();
        featuresMap.forEach((key, value) {
          final feature = _stringToFeature(key);
          if (feature != null) {
            _featureCache[feature] = value as bool;
          }
        });
        
        if (lastUpdate != null) {
          _lastFeatureUpdate = DateTime.fromMillisecondsSinceEpoch(lastUpdate);
        }
      }
    } catch (e) {
      _logger.error('Failed to load cached features: $e');
    }
  }

  Future<void> _trackFeatureAccessAttempt(
    PremiumFeature feature, 
    bool success, 
    String? context,
  ) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return;
      
      await _apiService.trackFeatureAccessAttempt(
        userId: userId,
        feature: _featureToString(feature),
        success: success,
        context: context,
      );
    } catch (e) {
      _logger.error('Failed to track feature access attempt: $e');
    }
  }

  Future<void> _trackPaywallImpression(PremiumFeature feature, String? context) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return;
      
      await _apiService.trackPaywallImpression(
        userId: userId,
        feature: _featureToString(feature),
        context: context,
      );
    } catch (e) {
      _logger.error('Failed to track paywall impression: $e');
    }
  }

  String _featureToString(PremiumFeature feature) {
    switch (feature) {
      case PremiumFeature.advancedOcr:
        return 'advanced_ocr';
      case PremiumFeature.batchReceiptProcessing:
        return 'batch_receipt_processing';
      case PremiumFeature.premiumInsights:
        return 'premium_insights';
      case PremiumFeature.enhancedAnalytics:
        return 'enhanced_analytics';
      case PremiumFeature.unlimitedTransactions:
        return 'unlimited_transactions';
      case PremiumFeature.prioritySupport:
        return 'priority_support';
      case PremiumFeature.customCategories:
        return 'custom_categories';
      case PremiumFeature.exportData:
        return 'export_data';
    }
  }

  PremiumFeature? _stringToFeature(String str) {
    switch (str) {
      case 'advanced_ocr':
        return PremiumFeature.advancedOcr;
      case 'batch_receipt_processing':
        return PremiumFeature.batchReceiptProcessing;
      case 'premium_insights':
        return PremiumFeature.premiumInsights;
      case 'enhanced_analytics':
        return PremiumFeature.enhancedAnalytics;
      case 'unlimited_transactions':
        return PremiumFeature.unlimitedTransactions;
      case 'priority_support':
        return PremiumFeature.prioritySupport;
      case 'custom_categories':
        return PremiumFeature.customCategories;
      case 'export_data':
        return PremiumFeature.exportData;
      default:
        return null;
    }
  }
}

/// Exception thrown when premium feature access is denied
class PremiumFeatureAccessException implements Exception {
  final PremiumFeature feature;
  final String message;
  final String? context;

  const PremiumFeatureAccessException({
    required this.feature,
    required this.message,
    this.context,
  });

  @override
  String toString() => 'PremiumFeatureAccessException: $message';
}

/// Feature usage limits and restrictions
class FeatureUsageLimits {
  final int? dailyLimit;
  final int? monthlyLimit;
  final int? concurrentLimit;
  final int? batchSizeLimit;
  final int? categoryLimit;
  final int? historyLimit;
  final List<String>? formatRestrictions;
  final List<String>? supportChannels;
  final String? insightDepth;
  final Duration? responseTime;
  final bool advancedMetrics;

  const FeatureUsageLimits({
    this.dailyLimit,
    this.monthlyLimit,
    this.concurrentLimit,
    this.batchSizeLimit,
    this.categoryLimit,
    this.historyLimit,
    this.formatRestrictions,
    this.supportChannels,
    this.insightDepth,
    this.responseTime,
    this.advancedMetrics = false,
  });

  bool get isUnlimited => dailyLimit == null && monthlyLimit == null;
}
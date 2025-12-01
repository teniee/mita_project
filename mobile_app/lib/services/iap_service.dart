import 'dart:async';
import 'dart:io';
import 'dart:convert';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';
import 'logging_service.dart';

/// Premium features available in MITA
enum PremiumFeature {
  advancedOcr,
  batchReceiptProcessing,
  premiumInsights,
  enhancedAnalytics,
  unlimitedTransactions,
  prioritySupport,
  customCategories,
  exportData,
}

/// Subscription status types
enum SubscriptionStatus {
  active,
  expired,
  cancelled,
  refunded,
  gracePeriod,
  billingRetry,
  pendingRenewal,
}

/// Comprehensive subscription information
class SubscriptionInfo {
  final String subscriptionId;
  final String productId;
  final SubscriptionStatus status;
  final DateTime expiresAt;
  final bool autoRenew;
  final bool trialPeriod;
  final String platform;
  final DateTime? gracePeriodExpiresAt;
  final DateTime? billingRetryUntil;
  final Map<String, dynamic> metadata;

  const SubscriptionInfo({
    required this.subscriptionId,
    required this.productId,
    required this.status,
    required this.expiresAt,
    required this.autoRenew,
    required this.trialPeriod,
    required this.platform,
    this.gracePeriodExpiresAt,
    this.billingRetryUntil,
    this.metadata = const {},
  });

  factory SubscriptionInfo.fromJson(Map<String, dynamic> json) {
    return SubscriptionInfo(
      subscriptionId: json['subscription_id'] ?? '',
      productId: json['product_id'] ?? '',
      status: SubscriptionStatus.values.firstWhere(
        (e) => e.toString().split('.').last == json['status'],
        orElse: () => SubscriptionStatus.expired,
      ),
      expiresAt: DateTime.parse(
          json['expires_at'] ?? DateTime.now().toIso8601String()),
      autoRenew: json['auto_renew'] ?? false,
      trialPeriod: json['trial_period'] ?? false,
      platform: json['platform'] ?? Platform.operatingSystem,
      gracePeriodExpiresAt: json['grace_period_expires_at'] != null
          ? DateTime.parse(json['grace_period_expires_at'])
          : null,
      billingRetryUntil: json['billing_retry_until'] != null
          ? DateTime.parse(json['billing_retry_until'])
          : null,
      metadata: json['metadata'] ?? {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'subscription_id': subscriptionId,
      'product_id': productId,
      'status': status.toString().split('.').last,
      'expires_at': expiresAt.toIso8601String(),
      'auto_renew': autoRenew,
      'trial_period': trialPeriod,
      'platform': platform,
      'grace_period_expires_at': gracePeriodExpiresAt?.toIso8601String(),
      'billing_retry_until': billingRetryUntil?.toIso8601String(),
      'metadata': metadata,
    };
  }

  bool get isActive {
    final now = DateTime.now();
    return status == SubscriptionStatus.active ||
        (status == SubscriptionStatus.gracePeriod &&
            gracePeriodExpiresAt != null &&
            gracePeriodExpiresAt!.isAfter(now)) ||
        (status == SubscriptionStatus.billingRetry &&
            billingRetryUntil != null &&
            billingRetryUntil!.isAfter(now));
  }
}

class IapService {
  static const String _premiumStatusKey = 'premium_status_cache';
  static const String _lastVerificationKey = 'last_verification_time';
  static const Duration _cacheValidDuration = Duration(minutes: 30);

  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _apiService = ApiService();
  final LoggingService _logger = LoggingService();
  StreamSubscription<List<PurchaseDetails>>? _sub;

  // Cache for premium status to avoid frequent API calls
  SubscriptionInfo? _cachedSubscriptionInfo;
  DateTime? _lastCacheUpdate;

  // Stream controllers for real-time updates
  final StreamController<bool> _premiumStatusController =
      StreamController<bool>.broadcast();
  final StreamController<Set<PremiumFeature>> _premiumFeaturesController =
      StreamController<Set<PremiumFeature>>.broadcast();

  /// Stream of premium status changes
  Stream<bool> get premiumStatusStream => _premiumStatusController.stream;

  /// Stream of available premium features
  Stream<Set<PremiumFeature>> get premiumFeaturesStream =>
      _premiumFeaturesController.stream;

  /// Initialize the IAP service and restore previous purchases
  Future<void> initialize() async {
    try {
      _sub ??= _iap.purchaseStream.listen(_handlePurchaseUpdate);

      // Load cached subscription info
      await _loadCachedSubscriptionInfo();

      // Restore previous purchases
      await restorePurchases();

      _logger.info('IAP Service initialized successfully');
    } catch (e) {
      _logger.error('Failed to initialize IAP service: $e');
      rethrow;
    }
  }

  /// Dispose of resources
  void dispose() {
    _sub?.cancel();
    _premiumStatusController.close();
    _premiumFeaturesController.close();
  }

  /// Purchase premium subscription
  Future<void> buyPremium({String productId = 'premium'}) async {
    try {
      _logger.info('Starting premium purchase for product: $productId');

      final response = await _iap.queryProductDetails({productId});
      if (response.notFoundIDs.isNotEmpty) {
        throw Exception('Product not found: $productId');
      }

      final product = response.productDetails.first;
      final purchaseParam = PurchaseParam(productDetails: product);

      _sub ??= _iap.purchaseStream.listen(_handlePurchaseUpdate);

      // Use buyNonConsumable for permanent upgrades or buyConsumable for subscriptions
      if (productId.contains('subscription')) {
        await _iap.buyNonConsumable(purchaseParam: purchaseParam);
      } else {
        await _iap.buyNonConsumable(purchaseParam: purchaseParam);
      }

      _logger.info('Purchase initiated for product: $productId');
    } catch (e) {
      _logger.error('Purchase failed: $e');
      rethrow;
    }
  }

  /// Restore previous purchases
  Future<void> restorePurchases() async {
    try {
      _logger.info('Restoring previous purchases');
      await _iap.restorePurchases();
    } catch (e) {
      _logger.error('Failed to restore purchases: $e');
      rethrow;
    }
  }

  Future<void> _handlePurchaseUpdate(List<PurchaseDetails> purchases) async {
    for (final purchase in purchases) {
      try {
        _logger.info(
            'Processing purchase: ${purchase.productID}, status: ${purchase.status}');

        switch (purchase.status) {
          case PurchaseStatus.purchased:
            await _validatePurchase(purchase);
            await _iap.completePurchase(purchase);
            await _refreshPremiumStatus();
            break;

          case PurchaseStatus.error:
            _logger.error('Purchase error: ${purchase.error}');
            break;

          case PurchaseStatus.pending:
            _logger.info('Purchase pending: ${purchase.productID}');
            break;

          case PurchaseStatus.canceled:
            _logger.info('Purchase canceled: ${purchase.productID}');
            break;

          case PurchaseStatus.restored:
            await _validatePurchase(purchase);
            await _refreshPremiumStatus();
            break;
        }
      } catch (e) {
        _logger.error('Error processing purchase ${purchase.productID}: $e');
      }
    }
  }

  Future<void> _validatePurchase(PurchaseDetails purchase) async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final receipt = purchase.verificationData.serverVerificationData;
      final platform = Platform.isIOS ? 'ios' : 'android';

      _logger.info('Validating purchase with backend: ${purchase.productID}');

      final validationResult =
          await _apiService.validateReceipt(userId, receipt, platform);

      // Store validation result in cache
      await _cacheSubscriptionInfo(validationResult);

      _logger.info('Purchase validated successfully: ${purchase.productID}');
    } catch (e) {
      _logger.error('Purchase validation failed: $e');
      rethrow;
    }
  }

  /// Get current premium status with caching
  Future<bool> isPremiumUser() async {
    try {
      // Check cache first
      if (_isCacheValid()) {
        return _cachedSubscriptionInfo?.isActive ?? false;
      }

      // Refresh from server
      await _refreshPremiumStatus();
      return _cachedSubscriptionInfo?.isActive ?? false;
    } catch (e) {
      _logger.error('Failed to check premium status: $e');
      // Fall back to cached data if available
      return _cachedSubscriptionInfo?.isActive ?? false;
    }
  }

  /// Get current subscription information
  Future<SubscriptionInfo?> getSubscriptionInfo() async {
    try {
      if (_isCacheValid()) {
        return _cachedSubscriptionInfo;
      }

      await _refreshPremiumStatus();
      return _cachedSubscriptionInfo;
    } catch (e) {
      _logger.error('Failed to get subscription info: $e');
      return _cachedSubscriptionInfo;
    }
  }

  /// Check if user has specific premium feature
  Future<bool> hasFeature(PremiumFeature feature) async {
    try {
      final isPremium = await isPremiumUser();
      if (!isPremium) return false;

      // Get available features from backend
      final features = await _getAvailableFeatures();
      return features.contains(feature);
    } catch (e) {
      _logger.error('Failed to check feature availability: $e');
      return false;
    }
  }

  /// Get all available premium features for current user
  Future<Set<PremiumFeature>> getAvailableFeatures() async {
    try {
      final isPremium = await isPremiumUser();
      if (!isPremium) return {};

      return await _getAvailableFeatures();
    } catch (e) {
      _logger.error('Failed to get available features: $e');
      return {};
    }
  }

  /// Refresh premium status from server
  Future<void> _refreshPremiumStatus() async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      _logger.info('Refreshing premium status from server');

      // Get subscription status from backend
      final response = await _apiService.getUserPremiumStatus(userId);

      if (response['subscription'] != null) {
        final subscriptionInfo =
            SubscriptionInfo.fromJson(response['subscription']);
        await _cacheSubscriptionInfo(
            {'subscription': subscriptionInfo.toJson()});

        // Update streams
        _premiumStatusController.add(subscriptionInfo.isActive);

        final features = await _getAvailableFeatures();
        _premiumFeaturesController.add(features);
      } else {
        // No active subscription
        await _clearCachedSubscriptionInfo();
        _premiumStatusController.add(false);
        _premiumFeaturesController.add({});
      }

      _logger.info('Premium status refreshed successfully');
    } catch (e) {
      _logger.error('Failed to refresh premium status: $e');
      rethrow;
    }
  }

  /// Get available premium features from backend
  Future<Set<PremiumFeature>> _getAvailableFeatures() async {
    try {
      final userId = await _apiService.getUserId();
      if (userId == null) return {};

      final response = await _apiService.getUserPremiumFeatures(userId);
      final featureNames = List<String>.from(response['features'] ?? []);

      return featureNames
          .map((name) => _parseFeatureName(name))
          .where((feature) => feature != null)
          .cast<PremiumFeature>()
          .toSet();
    } catch (e) {
      _logger.error('Failed to get available features: $e');
      return {};
    }
  }

  /// Parse feature name string to enum
  PremiumFeature? _parseFeatureName(String name) {
    switch (name) {
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

  /// Check if cache is still valid
  bool _isCacheValid() {
    if (_cachedSubscriptionInfo == null || _lastCacheUpdate == null) {
      return false;
    }

    return DateTime.now().difference(_lastCacheUpdate!) < _cacheValidDuration;
  }

  /// Cache subscription information locally
  Future<void> _cacheSubscriptionInfo(Map<String, dynamic> data) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_premiumStatusKey, jsonEncode(data));
      await prefs.setInt(
          _lastVerificationKey, DateTime.now().millisecondsSinceEpoch);

      if (data['subscription'] != null) {
        _cachedSubscriptionInfo =
            SubscriptionInfo.fromJson(data['subscription']);
      }
      _lastCacheUpdate = DateTime.now();

      _logger.debug('Subscription info cached successfully');
    } catch (e) {
      _logger.error('Failed to cache subscription info: $e');
    }
  }

  /// Load cached subscription information
  Future<void> _loadCachedSubscriptionInfo() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedData = prefs.getString(_premiumStatusKey);
      final lastVerification = prefs.getInt(_lastVerificationKey);

      if (cachedData != null && lastVerification != null) {
        final data = jsonDecode(cachedData) as Map<String, dynamic>;
        if (data['subscription'] != null) {
          _cachedSubscriptionInfo =
              SubscriptionInfo.fromJson(data['subscription']);
        }
        _lastCacheUpdate =
            DateTime.fromMillisecondsSinceEpoch(lastVerification);

        _logger.debug('Loaded cached subscription info');
      }
    } catch (e) {
      _logger.error('Failed to load cached subscription info: $e');
    }
  }

  /// Clear cached subscription information
  Future<void> _clearCachedSubscriptionInfo() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_premiumStatusKey);
      await prefs.remove(_lastVerificationKey);

      _cachedSubscriptionInfo = null;
      _lastCacheUpdate = null;

      _logger.debug('Cleared cached subscription info');
    } catch (e) {
      _logger.error('Failed to clear cached subscription info: $e');
    }
  }

  /// Force refresh premium status (ignoring cache)
  Future<void> forceRefreshPremiumStatus() async {
    await _clearCachedSubscriptionInfo();
    await _refreshPremiumStatus();
  }
}

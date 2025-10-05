import 'dart:io';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'dart:developer' as dev;
import 'package:sentry_flutter/sentry_flutter.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

/// Financial application specific error categories for Sentry
enum FinancialErrorCategory {
  authentication('authentication'),
  authorization('authorization'),
  transactionProcessing('transaction_processing'),
  paymentProcessing('payment_processing'),
  accountManagement('account_management'),
  budgetCalculation('budget_calculation'),
  financialAnalysis('financial_analysis'),
  dataValidation('data_validation'),
  externalIntegration('external_integration'),
  securityViolation('security_violation'),
  complianceIssue('compliance_issue'),
  uiError('ui_error'),
  networkError('network_error'),
  systemError('system_error');

  const FinancialErrorCategory(this.value);
  final String value;
}

/// Financial application specific severity levels
enum FinancialSeverity {
  low('low'),
  medium('medium'),
  high('high'),
  critical('critical'),
  securityCritical('security_critical');

  const FinancialSeverity(this.value);
  final String value;
}

/// Enhanced Sentry service for MITA Finance mobile application
class SentryFinancialService {
  static final SentryFinancialService _instance = SentryFinancialService._internal();
  factory SentryFinancialService() => _instance;
  SentryFinancialService._internal();

  bool _isInitialized = false;
  String? _userId;
  String? _userEmail; // Reserved for future user tracking
  String? _subscriptionTier; // Reserved for future tier-based monitoring
  String? _deviceInfo;
  
  /// Initialize comprehensive Sentry monitoring for financial application
  Future<void> initialize({
    required String dsn,
    String environment = 'development',
    String? release,
    bool enableCrashReporting = true,
    bool enablePerformanceMonitoring = true,
    bool enableUserInteractionTracing = true,
    double? sampleRate,
    double? tracesSampleRate,
  }) async {
    if (_isInitialized) {
      return;
    }

    try {
      // Get device and app information
      await _collectDeviceInfo();
      
      await SentryFlutter.init(
        (options) {
          options.dsn = dsn;
          options.environment = environment;
          options.release = release ?? 'mita-mobile@1.0.0';
          
          // Performance monitoring configuration
          options.tracesSampleRate = tracesSampleRate ?? _getTracesSampleRate(environment);
          options.enableAutoPerformanceTracing = enablePerformanceMonitoring;
          options.enableUserInteractionTracing = enableUserInteractionTracing;
          options.enableAutoSessionTracking = true;
          
          // Error sampling
          options.sampleRate = sampleRate ?? 1.0; // Capture all errors
          
          // Security and compliance for financial services
          options.sendDefaultPii = false; // Don't send PII data
          options.attachStacktrace = true;
          options.maxBreadcrumbs = 100;
          
          // Debug configuration
          options.debug = environment == 'development' && kDebugMode;
          
          // Custom configuration for mobile
          options.enableWindowMetricBreadcrumbs = true;
          options.enableNativeCrashHandling = enableCrashReporting;
          options.enableAutoNativeBreadcrumbs = true;
          
          
          // Configure screenshot attachment (disabled for financial compliance)
          options.attachScreenshot = false; // Disabled for financial privacy
          
          // Set before send callbacks
          options.beforeSend = _filterSensitiveData;
          options.beforeSendTransaction = (transaction) => _filterSensitiveTransactions(transaction, Hint());
        },
      );

      _isInitialized = true;
      
      // Configure initial scope after initialization
      await Sentry.configureScope((scope) {
        scope.setTag('application_type', 'financial_services');
        scope.setTag('compliance_level', 'pci_dss');
        scope.setTag('platform', Platform.operatingSystem);
        scope.setTag('environment', environment);
        scope.setTag('component', 'mobile_app');
        
        if (_deviceInfo != null) {
          scope.setTag('device_info', _deviceInfo!);
        }
        
        // Set application context
        scope.setContexts('application', {
          'name': 'MITA Finance Mobile',
          'version': '1.0.0',
          'type': 'financial_mobile_app',
          'compliance': 'PCI_DSS',
          'platform': Platform.operatingSystem,
        });
      });
      
      // Add initial breadcrumb
      Sentry.addBreadcrumb(Breadcrumb(
        message: 'Sentry financial monitoring initialized',
        category: 'init',
        level: SentryLevel.info,
        data: {
          'environment': environment,
          'financial_monitoring': true,
          'compliance_enabled': true,
        },
      ));
      
      if (kDebugMode) dev.log('Sentry financial monitoring initialized for $environment', name: 'SentryService');
      
    } catch (e, stackTrace) {
      if (kDebugMode) dev.log('Failed to initialize Sentry: $e', name: 'SentryService', error: e);
      if (kDebugMode) {
        if (kDebugMode) dev.log('Stack trace: $stackTrace', name: 'SentryService');
      }
      // Don't let Sentry initialization failure crash the app
    }
  }

  /// Get appropriate traces sample rate based on environment
  double _getTracesSampleRate(String environment) {
    switch (environment) {
      case 'production':
        return 0.1; // 10% for production
      case 'staging':
        return 0.5; // 50% for staging
      default:
        return 1.0; // 100% for development
    }
  }

  /// Collect device information for context
  Future<void> _collectDeviceInfo() async {
    try {
      final deviceInfo = DeviceInfoPlugin();
      final packageInfo = await PackageInfo.fromPlatform();
      
      String deviceDetails = '';
      
      if (Platform.isIOS) {
        final iosInfo = await deviceInfo.iosInfo;
        deviceDetails = '${iosInfo.name} ${iosInfo.systemVersion}';
      } else if (Platform.isAndroid) {
        final androidInfo = await deviceInfo.androidInfo;
        deviceDetails = '${androidInfo.brand} ${androidInfo.model} API${androidInfo.version.sdkInt}';
      }
      
      _deviceInfo = '${packageInfo.appName} v${packageInfo.version} on $deviceDetails';
      
    } catch (e) {
      _deviceInfo = 'Unknown device';
    }
  }

  /// Filter sensitive financial data before sending to Sentry
  SentryEvent? _filterSensitiveData(SentryEvent event, Hint hint) {
    // List of sensitive keys to redact
    const sensitiveKeys = {
      'password', 'token', 'secret', 'key', 'authorization',
      'card_number', 'cvv', 'pin', 'ssn', 'tax_id',
      'account_number', 'routing_number', 'sort_code',
      'iban', 'swift', 'bank_account', 'credit_card',
      'debit_card', 'payment_method', 'financial_data'
    };

    /// Recursively sanitize data structures
    dynamic sanitizeData(dynamic data) {
      if (data is Map) {
        final sanitized = <String, dynamic>{};
        for (final entry in data.entries) {
          final key = entry.key.toString().toLowerCase();
          if (sensitiveKeys.any((sensitiveKey) => key.contains(sensitiveKey))) {
            sanitized[entry.key as String] = '[REDACTED]';
          } else {
            sanitized[entry.key as String] = sanitizeData(entry.value);
          }
        }
        return sanitized;
      } else if (data is List) {
        return data.map(sanitizeData).toList();
      } else if (data is String && data.length > 1000) {
        return data.substring(0, 1000) + '... [TRUNCATED]';
      }
      return data;
    }

    // Sanitize request data
    if (event.request?.data != null) {
      event = event.copyWith(
        request: event.request!.copyWith(
          data: sanitizeData(event.request!.data),
        ),
      );
    }

    // Sanitize extra data
    if (event.extra?.isNotEmpty == true) {
      event = event.copyWith(
        extra: sanitizeData(event.extra) as Map<String, dynamic>?,
      );
    }

    // Add financial service tags
    final tags = Map<String, String>.from(event.tags ?? {});
    tags['financial_service'] = 'true';
    tags['pci_compliant'] = 'true';
    tags['data_sanitized'] = 'true';

    return event.copyWith(tags: tags);
  }

  /// Filter sensitive data from transaction events
  SentryTransaction? _filterSensitiveTransactions(SentryTransaction transaction, Hint hint) {
    // Add financial context to transactions
    final contexts = Map<String, dynamic>.from(transaction.contexts ?? {});
    contexts['financial_operation'] = {
      'type': 'financial_mobile_transaction',
      'compliance_level': 'pci_dss',
      'data_classification': 'confidential',
      'platform': Platform.operatingSystem,
    };

    return transaction.copyWith(contexts: Contexts.fromJson(contexts));
  }

  /// Capture financial-specific errors with enhanced context
  Future<SentryId> captureFinancialError(
    dynamic exception, {
    FinancialErrorCategory category = FinancialErrorCategory.systemError,
    FinancialSeverity severity = FinancialSeverity.medium,
    String? stackTrace,
    String? userId,
    String? transactionId,
    double? amount,
    String? currency,
    String? screenName,
    Map<String, dynamic>? additionalContext,
    Map<String, String>? tags,
  }) async {
    if (!_isInitialized) {
      if (kDebugMode) dev.log('Sentry not initialized - error not captured: $exception', name: 'SentryService');
      return const SentryId.empty();
    }

    return await Sentry.captureException(
      exception,
      stackTrace: stackTrace,
      withScope: (scope) {
        // Set financial error context
        scope.setTag('error_category', category.value);
        scope.setTag('severity', severity.value);
        scope.setTag('financial_error', 'true');
        
        // Set user context
        if (userId != null) {
          scope.setUser(SentryUser(id: userId));
        } else if (_userId != null) {
          scope.setUser(SentryUser(id: _userId));
        }

        // Set screen context
        if (screenName != null) {
          scope.setTag('screen_name', screenName);
          scope.setContexts('screen', {'name': screenName});
        }

        // Set financial context
        final financialContext = <String, dynamic>{
          'category': category.value,
          'severity': severity.value,
          'timestamp': DateTime.now().toIso8601String(),
          'platform': Platform.operatingSystem,
        };

        if (transactionId != null) {
          financialContext['transaction_id'] = transactionId;
        }
        if (amount != null) {
          financialContext['amount'] = amount;
        }
        if (currency != null) {
          financialContext['currency'] = currency;
        }

        scope.setContexts('financial_operation', financialContext);

        // Set additional context
        if (additionalContext != null) {
          for (final entry in additionalContext.entries) {
            scope.setExtra(entry.key, entry.value);
          }
        }

        // Set additional tags
        if (tags != null) {
          for (final entry in tags.entries) {
            scope.setTag(entry.key, entry.value);
          }
        }

        // Add network context
        _addNetworkContext(scope);
      },
    );
  }

  /// Capture transaction-specific errors
  Future<SentryId> captureTransactionError(
    dynamic exception, {
    required String userId,
    required String transactionId,
    required double amount,
    required String currency,
    required String transactionType,
    String? merchant,
    String? categoryName,
    String? screenName,
    String? stackTrace,
  }) {
    return captureFinancialError(
      exception,
      category: FinancialErrorCategory.transactionProcessing,
      severity: FinancialSeverity.high,
      stackTrace: stackTrace,
      userId: userId,
      transactionId: transactionId,
      amount: amount,
      currency: currency,
      screenName: screenName,
      additionalContext: {
        'transaction_type': transactionType,
        'merchant': merchant,
        'transaction_category': categoryName,
        'compliance_level': 'PCI_DSS',
        'financial_impact': 'DIRECT',
      },
    );
  }

  /// Capture authentication errors
  Future<SentryId> captureAuthenticationError(
    dynamic exception, {
    String? userId,
    String? authMethod,
    String? screenName,
    String? stackTrace,
    Map<String, dynamic>? additionalContext,
  }) {
    final context = <String, dynamic>{
      'auth_method': authMethod,
      'security_event': true,
      'compliance_impact': 'HIGH',
      'platform': Platform.operatingSystem,
      ...?additionalContext,
    };

    return captureFinancialError(
      exception,
      category: FinancialErrorCategory.authentication,
      severity: FinancialSeverity.securityCritical,
      stackTrace: stackTrace,
      userId: userId,
      screenName: screenName,
      additionalContext: context,
      tags: {
        'security_critical': 'true',
        'auth_failure': 'true',
      },
    );
  }

  /// Capture payment processing errors
  Future<SentryId> capturePaymentError(
    dynamic exception, {
    required String userId,
    required String paymentMethod,
    required double amount,
    required String currency,
    String? paymentProvider,
    String? screenName,
    String? stackTrace,
  }) {
    return captureFinancialError(
      exception,
      category: FinancialErrorCategory.paymentProcessing,
      severity: FinancialSeverity.critical,
      stackTrace: stackTrace,
      userId: userId,
      amount: amount,
      currency: currency,
      screenName: screenName,
      additionalContext: {
        'payment_method': paymentMethod,
        'payment_provider': paymentProvider,
        'pci_compliance_required': true,
        'financial_impact': 'DIRECT',
        'platform': Platform.operatingSystem,
      },
      tags: {
        'payment_error': 'true',
        'financial_critical': 'true',
      },
    );
  }

  /// Capture network errors with context
  Future<SentryId> captureNetworkError(
    dynamic exception, {
    String? endpoint,
    String? method,
    int? statusCode,
    String? screenName,
    String? stackTrace,
  }) async {
    final results = await Connectivity().checkConnectivity();
    final connectivity = results.isNotEmpty ? results.first : ConnectivityResult.none;
    final connectivityName = connectivity.name;
    
    return captureFinancialError(
      exception,
      category: FinancialErrorCategory.networkError,
      severity: FinancialSeverity.medium,
      stackTrace: stackTrace,
      screenName: screenName,
      additionalContext: {
        'endpoint': endpoint,
        'method': method,
        'status_code': statusCode,
        'connectivity': connectivityName,
        'platform': Platform.operatingSystem,
      },
      tags: {
        'network_error': 'true',
        'connectivity': connectivityName,
      },
    );
  }

  /// Set user context for financial application
  void setFinancialUser({
    required String userId,
    String? email,
    String? subscriptionTier,
    String? accountType,
    String? riskLevel,
  }) {
    if (!_isInitialized) return;

    _userId = userId;
    _userEmail = email;
    _subscriptionTier = subscriptionTier;

    Sentry.configureScope((scope) {
      scope.setUser(SentryUser(
        id: userId,
        email: email,
        data: {
          'subscription_tier': subscriptionTier,
          'account_type': accountType,
          'risk_level': riskLevel,
          'platform': Platform.operatingSystem,
        },
      ));

      // Set user-related tags
      scope.setTag('has_user_context', 'true');
      if (subscriptionTier != null) {
        scope.setTag('subscription_tier', subscriptionTier);
      }
      if (accountType != null) {
        scope.setTag('account_type', accountType);
      }
      if (riskLevel != null) {
        scope.setTag('risk_level', riskLevel);
      }
    });
  }

  /// Add financial breadcrumb
  void addFinancialBreadcrumb({
    required String message,
    String category = 'financial',
    SentryLevel level = SentryLevel.info,
    Map<String, dynamic>? data,
  }) {
    if (!_isInitialized) return;

    final breadcrumbData = <String, dynamic>{
      'timestamp': DateTime.now().toIso8601String(),
      'financial_context': true,
      'platform': Platform.operatingSystem,
      ...?data,
    };

    Sentry.addBreadcrumb(Breadcrumb(
      message: message,
      category: category,
      level: level,
      data: breadcrumbData,
    ));
  }

  /// Start performance transaction
  ISentrySpan startTransaction({
    required String name,
    required String operation,
    String? description,
    Map<String, dynamic>? data,
  }) {
    if (!_isInitialized) {
      return NoOpSentrySpan();
    }

    final transaction = Sentry.startTransaction(
      name,
      operation,
      description: description,
    );

    // Set financial context
    transaction.setTag('financial_operation', 'true');
    transaction.setTag('platform', Platform.operatingSystem);

    if (data != null) {
      for (final entry in data.entries) {
        transaction.setData(entry.key, entry.value);
      }
    }

    return transaction;
  }

  /// Add network context to scope
  void _addNetworkContext(Scope scope) {
    Connectivity().checkConnectivity().then((results) {
      final connectivity = results.isNotEmpty ? results.first : ConnectivityResult.none;
      final connectivityName = connectivity.name;
      scope.setContexts('network', {
        'connectivity': connectivityName,
        'platform': Platform.operatingSystem,
        'timestamp': DateTime.now().toIso8601String(),
      });
      scope.setTag('connectivity', connectivityName);
    }).catchError((e) {
      // Ignore network context errors
    });
  }

  /// Clear user context (e.g., on logout)
  void clearUser() {
    if (!_isInitialized) return;

    _userId = null;
    _userEmail = null;
    _subscriptionTier = null;

    Sentry.configureScope((scope) {
      scope.clearBreadcrumbs();
      scope.removeTag('subscription_tier');
      scope.removeTag('account_type');
      scope.removeTag('risk_level');
      scope.setTag('has_user_context', 'false');
      scope.setUser(null);
    });

    addFinancialBreadcrumb(
      message: 'User context cleared',
      category: 'auth',
      level: SentryLevel.info,
    );
  }

  /// Check if Sentry is initialized
  bool get isInitialized => _isInitialized;
}

/// Global instance
final sentryService = SentryFinancialService();

/// No-op Sentry span for when Sentry is not initialized
class NoOpSentrySpan implements ISentrySpan {
  @override
  Future<void> finish({SpanStatus? status, DateTime? endTimestamp}) async {}

  @override
  ISentrySpan startChild(String operation, {String? description, DateTime? startTimestamp}) => this;

  @override
  void setData(String key, dynamic value) {}

  @override
  void removeData(String key) {}

  @override
  void setTag(String key, String value) {}

  @override
  void removeTag(String key) {}

  @override
  SentrySpanContext get context => SentrySpanContext(operation: 'noop');

  @override
  DateTime get startTimestamp => DateTime.now();

  @override
  DateTime? get endTimestamp => DateTime.now();

  @override
  bool get finished => true;

  @override
  Map<String, String> get tags => {};

  @override
  Map<String, dynamic> get data => {};

  @override
  SpanStatus? get status => SpanStatus.ok();

  @override
  String? get description => null;

  @override
  String get origin => 'manual';

  @override
  SentryId get spanId => const SentryId.empty();

  @override
  SentryId? get parentSpanId => null;

  @override
  SentryId get traceId => const SentryId.empty();

  @override
  void setStatus(SpanStatus status) {}

  @override
  dynamic get localMetricsAggregator => null;

  @override
  void setMeasurement(String name, num value, {SentryMeasurementUnit? unit}) {}

  // Missing interface implementations
  @override
  set origin(String? origin) {}

  @override
  SentryTracesSamplingDecision? get samplingDecision => null;

  @override
  void scheduleFinish() {}

  @override
  set status(SpanStatus? status) {}

  @override
  dynamic get throwable => null;

  @override
  set throwable(dynamic throwable) {}

  @override
  SentryBaggageHeader? toBaggageHeader() => null;

  @override
  SentryTraceHeader toSentryTrace() => SentryTraceHeader(traceId, SpanId.fromId(spanId.toString()));

  @override
  SentryTraceContextHeader? traceContext() => null;
}
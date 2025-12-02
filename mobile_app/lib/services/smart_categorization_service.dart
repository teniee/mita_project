import 'dart:math' as math;
import 'api_service.dart';
import 'logging_service.dart';

/// Smart categorization service using AI-powered suggestions and learning algorithms
class SmartCategorizationService {
  static final SmartCategorizationService _instance =
      SmartCategorizationService._internal();
  factory SmartCategorizationService() => _instance;
  SmartCategorizationService._internal();

  final ApiService _apiService = ApiService();

  // Local ML patterns for offline categorization
  final Map<String, Map<String, double>> _merchantPatterns = {};
  final Map<String, Map<String, double>> _amountPatterns = {};
  final Map<String, Map<String, double>> _timePatterns = {};
  final Map<String, int> _userConfirmations = {};

  // Category confidence thresholds
  static const double HIGH_CONFIDENCE = 0.85;
  static const double MEDIUM_CONFIDENCE = 0.65;
  static const double LOW_CONFIDENCE = 0.40;

  /// Initialize the categorization service with user's historical data
  Future<void> initialize() async {
    try {
      logInfo('Initializing Smart Categorization Service', tag: 'SMART_CAT');

      // Load historical patterns
      await _loadHistoricalPatterns();

      // Load user preferences
      await _loadUserPreferences();

      logInfo('Smart categorization initialized successfully',
          tag: 'SMART_CAT');
    } catch (e) {
      logError('Failed to initialize smart categorization: $e',
          tag: 'SMART_CAT', error: e);
    }
  }

  /// Get AI-powered category suggestions for a transaction
  Future<List<CategorySuggestion>> getCategorySuggestions({
    required String description,
    required double amount,
    String? merchantName,
    DateTime? transactionTime,
    String? location,
  }) async {
    try {
      final suggestions = <CategorySuggestion>[];

      // 1. Try AI backend first
      try {
        final aiSuggestions = await _getAISuggestions(
          description: description,
          amount: amount,
          merchantName: merchantName,
          transactionTime: transactionTime,
        );
        suggestions.addAll(aiSuggestions);
      } catch (e) {
        logWarning('AI categorization failed, using local ML: $e',
            tag: 'SMART_CAT');
      }

      // 2. Local ML patterns as fallback/enhancement
      final localSuggestions = await _getLocalMLSuggestions(
        description: description,
        amount: amount,
        merchantName: merchantName,
        transactionTime: transactionTime,
      );

      // 3. Merge and rank suggestions
      final mergedSuggestions =
          _mergeSuggestions(suggestions, localSuggestions);

      // 4. Apply user preference learning
      final personalizedSuggestions =
          _applyUserLearning(mergedSuggestions, description);

      // 5. Sort by confidence and return top suggestions
      personalizedSuggestions
          .sort((a, b) => b.confidence.compareTo(a.confidence));

      return personalizedSuggestions.take(5).toList();
    } catch (e) {
      logError('Category suggestions failed: $e', tag: 'SMART_CAT', error: e);
      return _getFallbackSuggestions(description, amount);
    }
  }

  /// Learn from user's category confirmations
  Future<void> confirmCategory({
    required String description,
    required String selectedCategory,
    required double amount,
    String? merchantName,
    DateTime? transactionTime,
  }) async {
    try {
      // Update local learning patterns
      _updateMerchantPattern(
          merchantName ?? description.toLowerCase(), selectedCategory);
      _updateAmountPattern(amount, selectedCategory);
      _updateTimePattern(transactionTime ?? DateTime.now(), selectedCategory);

      // Track user confirmations for confidence scoring
      final key = '${description.toLowerCase()}_$selectedCategory';
      _userConfirmations[key] = (_userConfirmations[key] ?? 0) + 1;

      // Send learning data to backend
      try {
        await _apiService.updateBehavioralPreferences({
          'categorization_feedback': {
            'description': description,
            'category': selectedCategory,
            'amount': amount,
            'merchant': merchantName,
            'timestamp': DateTime.now().toIso8601String(),
          }
        });
      } catch (e) {
        logWarning('Failed to send categorization feedback to backend: $e',
            tag: 'SMART_CAT');
      }

      logDebug('Category confirmation recorded: $selectedCategory',
          tag: 'SMART_CAT');
    } catch (e) {
      logError('Failed to confirm category: $e', tag: 'SMART_CAT', error: e);
    }
  }

  /// Get spending pattern insights for categories
  Future<Map<String, SpendingPattern>> getCategoryPatterns() async {
    try {
      final patterns = <String, SpendingPattern>{};

      // Get patterns from backend
      final backendPatterns = await _apiService.getSpendingPatternAnalysis();

      // Process backend patterns
      final categoriesData =
          backendPatterns['categories'] as Map<String, dynamic>? ?? {};

      categoriesData.forEach((category, data) {
        if (data is Map<String, dynamic>) {
          patterns[category] = SpendingPattern(
            category: category,
            averageAmount: (data['average_amount'] as num?)?.toDouble() ?? 0.0,
            frequency: (data['frequency'] as num?)?.toInt() ?? 0,
            trend: data['trend'] as String? ?? 'stable',
            confidence: (data['confidence'] as num?)?.toDouble() ?? 0.5,
            timePatterns: Map<String, double>.from(data['time_patterns'] ?? {}),
            merchantPatterns:
                Map<String, double>.from(data['merchant_patterns'] ?? {}),
          );
        }
      });

      return patterns;
    } catch (e) {
      logError('Failed to get category patterns: $e',
          tag: 'SMART_CAT', error: e);
      return {};
    }
  }

  /// Get intelligent spending alerts based on patterns
  Future<List<SpendingAlert>> getSpendingAlerts() async {
    try {
      final alerts = <SpendingAlert>[];

      // Get anomalies from backend
      final anomalies = await _apiService.getSpendingAnomalies();

      for (final anomaly in anomalies) {
        alerts.add(SpendingAlert(
          id: anomaly['id']?.toString() ??
              DateTime.now().millisecondsSinceEpoch.toString(),
          type: _getAlertType(anomaly['anomaly_score'] as double? ?? 0.0),
          category: anomaly['category'] as String? ?? 'Unknown',
          amount: (anomaly['amount'] as num?)?.toDouble() ?? 0.0,
          expectedAmount:
              (anomaly['expected_amount'] as num?)?.toDouble() ?? 0.0,
          message:
              anomaly['description'] as String? ?? 'Unusual spending detected',
          confidence: (anomaly['anomaly_score'] as num?)?.toDouble() ?? 0.0,
          date: DateTime.tryParse(anomaly['date'] as String? ?? '') ??
              DateTime.now(),
          suggestions: List<String>.from(anomaly['possible_causes'] ?? []),
        ));
      }

      // Add local pattern-based alerts
      final localAlerts = _generateLocalAlerts();
      alerts.addAll(localAlerts);

      // Sort by confidence and date
      alerts.sort((a, b) {
        final confidenceCompare = b.confidence.compareTo(a.confidence);
        if (confidenceCompare != 0) return confidenceCompare;
        return b.date.compareTo(a.date);
      });

      return alerts.take(10).toList();
    } catch (e) {
      logError('Failed to get spending alerts: $e', tag: 'SMART_CAT', error: e);
      return [];
    }
  }

  /// Auto-categorize transactions using learned patterns
  Future<String?> autoCategorize({
    required String description,
    required double amount,
    String? merchantName,
    DateTime? transactionTime,
  }) async {
    try {
      final suggestions = await getCategorySuggestions(
        description: description,
        amount: amount,
        merchantName: merchantName,
        transactionTime: transactionTime,
      );

      // Only auto-categorize if we have high confidence
      if (suggestions.isNotEmpty &&
          suggestions.first.confidence >= HIGH_CONFIDENCE) {
        return suggestions.first.category;
      }

      return null;
    } catch (e) {
      logError('Auto-categorization failed: $e', tag: 'SMART_CAT', error: e);
      return null;
    }
  }

  // ============================================================================
  // PRIVATE HELPER METHODS
  // ============================================================================

  /// Get AI-powered suggestions from backend
  Future<List<CategorySuggestion>> _getAISuggestions({
    required String description,
    required double amount,
    String? merchantName,
    DateTime? transactionTime,
  }) async {
    final suggestions =
        await _apiService.getAICategorySuggestions(description, amount: amount);

    return suggestions
        .map((suggestion) => CategorySuggestion(
              category: suggestion['category'] as String,
              confidence: (suggestion['confidence'] as num?)?.toDouble() ?? 0.5,
              reason: suggestion['reason'] as String? ?? '',
              source: 'ai',
            ))
        .toList();
  }

  /// Get local ML-based suggestions
  Future<List<CategorySuggestion>> _getLocalMLSuggestions({
    required String description,
    required double amount,
    String? merchantName,
    DateTime? transactionTime,
  }) async {
    final suggestions = <CategorySuggestion>[];

    // Merchant pattern matching
    if (merchantName != null) {
      final merchantSuggestion =
          _getMerchantBasedSuggestion(merchantName.toLowerCase());
      if (merchantSuggestion != null) {
        suggestions.add(merchantSuggestion);
      }
    }

    // Amount pattern matching
    final amountSuggestion = _getAmountBasedSuggestion(amount);
    if (amountSuggestion != null) {
      suggestions.add(amountSuggestion);
    }

    // Description keyword matching
    final keywordSuggestion =
        _getKeywordBasedSuggestion(description.toLowerCase());
    if (keywordSuggestion != null) {
      suggestions.add(keywordSuggestion);
    }

    // Time pattern matching
    if (transactionTime != null) {
      final timeSuggestion = _getTimeBasedSuggestion(transactionTime);
      if (timeSuggestion != null) {
        suggestions.add(timeSuggestion);
      }
    }

    return suggestions;
  }

  /// Merge and deduplicate suggestions from multiple sources
  List<CategorySuggestion> _mergeSuggestions(
    List<CategorySuggestion> aiSuggestions,
    List<CategorySuggestion> localSuggestions,
  ) {
    final merged = <String, CategorySuggestion>{};

    // Add AI suggestions with higher base weight
    for (final suggestion in aiSuggestions) {
      merged[suggestion.category] = suggestion;
    }

    // Merge local suggestions
    for (final suggestion in localSuggestions) {
      if (merged.containsKey(suggestion.category)) {
        // Combine confidences
        final existing = merged[suggestion.category]!;
        merged[suggestion.category] = CategorySuggestion(
          category: suggestion.category,
          confidence: math.min(
              1.0, (existing.confidence + suggestion.confidence) / 2 * 1.2),
          reason: '${existing.reason}, ${suggestion.reason}',
          source: '${existing.source}+${suggestion.source}',
        );
      } else {
        merged[suggestion.category] = suggestion;
      }
    }

    return merged.values.toList();
  }

  /// Apply user learning to improve suggestions
  List<CategorySuggestion> _applyUserLearning(
    List<CategorySuggestion> suggestions,
    String description,
  ) {
    return suggestions.map((suggestion) {
      final key = '${description.toLowerCase()}_${suggestion.category}';
      final confirmations = _userConfirmations[key] ?? 0;

      // Boost confidence based on user confirmations
      double learningBoost =
          confirmations > 0 ? math.min(0.3, confirmations * 0.1) : 0.0;

      return CategorySuggestion(
        category: suggestion.category,
        confidence: math.min(1.0, suggestion.confidence + learningBoost),
        reason: suggestion.reason +
            (confirmations > 0 ? ' (User confirmed $confirmations times)' : ''),
        source: suggestion.source,
      );
    }).toList();
  }

  /// Get fallback suggestions when AI fails
  List<CategorySuggestion> _getFallbackSuggestions(
      String description, double amount) {
    final desc = description.toLowerCase();
    final suggestions = <CategorySuggestion>[];

    // Rule-based fallback categorization
    if (desc.contains('coffee') ||
        desc.contains('starbucks') ||
        desc.contains('cafe')) {
      suggestions.add(CategorySuggestion(
          category: 'Food & Dining',
          confidence: 0.8,
          reason: 'Coffee shop pattern',
          source: 'fallback'));
    } else if (desc.contains('gas') ||
        desc.contains('fuel') ||
        desc.contains('shell')) {
      suggestions.add(CategorySuggestion(
          category: 'Transportation',
          confidence: 0.8,
          reason: 'Gas station pattern',
          source: 'fallback'));
    } else if (desc.contains('grocery') ||
        desc.contains('supermarket') ||
        desc.contains('walmart')) {
      suggestions.add(CategorySuggestion(
          category: 'Food & Dining',
          confidence: 0.8,
          reason: 'Grocery pattern',
          source: 'fallback'));
    } else if (desc.contains('restaurant') ||
        desc.contains('dining') ||
        desc.contains('pizza')) {
      suggestions.add(CategorySuggestion(
          category: 'Food & Dining',
          confidence: 0.8,
          reason: 'Restaurant pattern',
          source: 'fallback'));
    } else if (desc.contains('movie') ||
        desc.contains('cinema') ||
        desc.contains('netflix')) {
      suggestions.add(CategorySuggestion(
          category: 'Entertainment',
          confidence: 0.7,
          reason: 'Entertainment pattern',
          source: 'fallback'));
    } else {
      suggestions.add(CategorySuggestion(
          category: 'General',
          confidence: 0.3,
          reason: 'Default category',
          source: 'fallback'));
    }

    return suggestions;
  }

  /// Update merchant learning patterns
  void _updateMerchantPattern(String merchant, String category) {
    _merchantPatterns.putIfAbsent(merchant, () => {});
    _merchantPatterns[merchant]![category] =
        (_merchantPatterns[merchant]![category] ?? 0.0) + 1.0;
  }

  /// Update amount learning patterns
  void _updateAmountPattern(double amount, String category) {
    final amountRange = _getAmountRange(amount);
    _amountPatterns.putIfAbsent(amountRange, () => {});
    _amountPatterns[amountRange]![category] =
        (_amountPatterns[amountRange]![category] ?? 0.0) + 1.0;
  }

  /// Update time learning patterns
  void _updateTimePattern(DateTime time, String category) {
    final timeKey = '${time.weekday}_${time.hour}';
    _timePatterns.putIfAbsent(timeKey, () => {});
    _timePatterns[timeKey]![category] =
        (_timePatterns[timeKey]![category] ?? 0.0) + 1.0;
  }

  /// Get merchant-based suggestion
  CategorySuggestion? _getMerchantBasedSuggestion(String merchant) {
    final patterns = _merchantPatterns[merchant];
    if (patterns == null || patterns.isEmpty) return null;

    final total = patterns.values.fold(0.0, (sum, count) => sum + count);
    final topCategory =
        patterns.entries.reduce((a, b) => a.value > b.value ? a : b);

    return CategorySuggestion(
      category: topCategory.key,
      confidence: topCategory.value / total,
      reason: 'Merchant pattern',
      source: 'local_ml',
    );
  }

  /// Get amount-based suggestion
  CategorySuggestion? _getAmountBasedSuggestion(double amount) {
    final range = _getAmountRange(amount);
    final patterns = _amountPatterns[range];
    if (patterns == null || patterns.isEmpty) return null;

    final total = patterns.values.fold(0.0, (sum, count) => sum + count);
    final topCategory =
        patterns.entries.reduce((a, b) => a.value > b.value ? a : b);

    return CategorySuggestion(
      category: topCategory.key,
      confidence:
          (topCategory.value / total) * 0.7, // Lower confidence for amount-only
      reason: 'Amount pattern',
      source: 'local_ml',
    );
  }

  /// Get keyword-based suggestion
  CategorySuggestion? _getKeywordBasedSuggestion(String description) {
    // Implementation of keyword matching would go here
    return null;
  }

  /// Get time-based suggestion
  CategorySuggestion? _getTimeBasedSuggestion(DateTime time) {
    final timeKey = '${time.weekday}_${time.hour}';
    final patterns = _timePatterns[timeKey];
    if (patterns == null || patterns.isEmpty) return null;

    final total = patterns.values.fold(0.0, (sum, count) => sum + count);
    final topCategory =
        patterns.entries.reduce((a, b) => a.value > b.value ? a : b);

    return CategorySuggestion(
      category: topCategory.key,
      confidence:
          (topCategory.value / total) * 0.5, // Lower confidence for time-only
      reason: 'Time pattern',
      source: 'local_ml',
    );
  }

  /// Get amount range for pattern matching
  String _getAmountRange(double amount) {
    if (amount < 10) return 'micro';
    if (amount < 50) return 'small';
    if (amount < 200) return 'medium';
    if (amount < 500) return 'large';
    return 'xlarge';
  }

  /// Load historical patterns from storage
  Future<void> _loadHistoricalPatterns() async {
    // Implementation would load from local storage
    // For now, we'll start with empty patterns
  }

  /// Load user preferences from storage
  Future<void> _loadUserPreferences() async {
    // Implementation would load from local storage
    // For now, we'll start with empty preferences
  }

  /// Get alert type based on anomaly score
  AlertType _getAlertType(double score) {
    if (score >= 0.8) return AlertType.critical;
    if (score >= 0.6) return AlertType.warning;
    return AlertType.info;
  }

  /// Generate local alerts based on patterns
  List<SpendingAlert> _generateLocalAlerts() {
    // Implementation for local pattern-based alerts
    return [];
  }

  /// Categorize a transaction (public method for tests)
  Future<String> categorizeTransaction({
    required String merchant,
    required double amount,
    required DateTime date,
    String? location,
  }) async {
    final suggestions = await getCategorySuggestions(
      description: merchant,
      amount: amount,
      merchantName: merchant,
      transactionTime: date,
      location: location,
    );

    if (suggestions.isNotEmpty) {
      return suggestions.first.category;
    }

    return 'other'; // Default category
  }
}

// ============================================================================
// DATA CLASSES
// ============================================================================

class CategorySuggestion {
  final String category;
  final double confidence;
  final String reason;
  final String source;

  CategorySuggestion({
    required this.category,
    required this.confidence,
    required this.reason,
    required this.source,
  });

  @override
  String toString() =>
      'CategorySuggestion(category: $category, confidence: ${confidence.toStringAsFixed(2)}, reason: $reason)';
}

class SpendingPattern {
  final String category;
  final double averageAmount;
  final int frequency;
  final String trend;
  final double confidence;
  final Map<String, double> timePatterns;
  final Map<String, double> merchantPatterns;

  SpendingPattern({
    required this.category,
    required this.averageAmount,
    required this.frequency,
    required this.trend,
    required this.confidence,
    required this.timePatterns,
    required this.merchantPatterns,
  });
}

class SpendingAlert {
  final String id;
  final AlertType type;
  final String category;
  final double amount;
  final double expectedAmount;
  final String message;
  final double confidence;
  final DateTime date;
  final List<String> suggestions;

  SpendingAlert({
    required this.id,
    required this.type,
    required this.category,
    required this.amount,
    required this.expectedAmount,
    required this.message,
    required this.confidence,
    required this.date,
    required this.suggestions,
  });

  double get deviationPercentage =>
      ((amount - expectedAmount) / expectedAmount * 100).abs();
}

enum AlertType { info, warning, critical }

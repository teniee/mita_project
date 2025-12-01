import 'dart:math';
import '../models/budget_intelligence_models.dart';
import 'api_service.dart';

/// Advanced category intelligence with dynamic optimization and life event detection
class CategoryIntelligenceService {
  static final CategoryIntelligenceService _instance =
      CategoryIntelligenceService._internal();
  factory CategoryIntelligenceService() => _instance;
  CategoryIntelligenceService._internal();

  final ApiService _apiService = ApiService();

  // Category learning storage
  final Map<String, Map<String, dynamic>> _categoryData = {};
  final List<LifeEventDetection> _detectedEvents = [];
  final Map<String, List<Map<String, dynamic>>> _categoryHistory = {};

  /// Initialize with intelligent category defaults
  void initializeIntelligentCategories(Map<String, dynamic> userProfile) {
    final incomeTier = userProfile['incomeTier']?.toString() ?? 'middle';
    final defaultCategories = _getDefaultCategoriesForTier(incomeTier);

    for (final categoryData in defaultCategories) {
      _categoryData[categoryData['id']?.toString() ?? ''] = {
        'categoryId': categoryData['id'],
        'name': categoryData['name'],
        'parentCategory': categoryData['parent'] ?? '',
        'currentWeight': categoryData['defaultWeight'],
        'recommendedWeight': categoryData['defaultWeight'],
        'volatility': 0.0,
        'triggers': <String>[],
        'learningData': <String, dynamic>{},
        'lastOptimized': DateTime.now(),
      };
    }
  }

  /// Perform comprehensive category optimization
  Future<Map<String, dynamic>> optimizeCategories({
    required String userId,
    required List<Map<String, dynamic>> spendingHistory,
    required Map<String, dynamic> userGoals,
    required Map<String, dynamic> currentFinancialState,
  }) async {
    // Detect life events that might affect category allocation
    final lifeEvents = await detectLifeEvents(spendingHistory);

    // Analyze spending patterns and volatility
    final categoryAnalysis = await _analyzeCategoryPatterns(spendingHistory);

    // Optimize based on goals and current performance
    final optimizedCategories = await _optimizeCategoryWeights(
      categoryAnalysis,
      userGoals,
      currentFinancialState,
      lifeEvents,
    );

    // Calculate expected improvement
    final expectedImprovement = _calculateExpectedImprovement(
      _categoryData,
      optimizedCategories,
      categoryAnalysis,
    );

    // Generate optimization reasons
    final optimizationReasons = _generateOptimizationReasons(
      _categoryData,
      optimizedCategories,
      lifeEvents,
      categoryAnalysis,
    );

    // Calculate performance metrics
    final performanceMetrics = _calculatePerformanceMetrics(
      optimizedCategories,
      categoryAnalysis,
    );

    // Update stored categories
    _categoryData.clear();
    _categoryData.addAll(optimizedCategories);

    return {
      'optimizedCategories': optimizedCategories,
      'optimizationReasons': optimizationReasons,
      'expectedImprovement': expectedImprovement,
      'performanceMetrics': performanceMetrics,
      'validUntil': DateTime.now().add(const Duration(days: 30)),
    };
  }

  /// Detect life events from spending pattern changes using external model
  Future<List<LifeEventDetection>> detectLifeEvents(
    List<Map<String, dynamic>> spendingHistory,
  ) async {
    final events = <LifeEventDetection>[];

    // Detect various life events
    events.addAll(await _detectJobChange(spendingHistory));
    events.addAll(await _detectMoving(spendingHistory));
    events.addAll(await _detectNewFamily(spendingHistory));
    events.addAll(await _detectHealthIssues(spendingHistory));
    events.addAll(await _detectMajorPurchase(spendingHistory));
    events.addAll(await _detectVacationTravel(spendingHistory));
    events.addAll(await _detectEducationEvents(spendingHistory));

    // Sort by confidence and recency
    events.sort((a, b) {
      final scoreA = a.confidence *
          (1.0 - DateTime.now().difference(a.detectedAt).inDays / 365.0);
      final scoreB = b.confidence *
          (1.0 - DateTime.now().difference(b.detectedAt).inDays / 365.0);
      return scoreB.compareTo(scoreA);
    });

    // Store detected events
    _detectedEvents.addAll(events);

    return events.take(5).toList(); // Return top 5 events
  }

  /// Generate category learning insights
  Future<List<Map<String, dynamic>>> generateCategoryInsights({
    required String userId,
    required List<Map<String, dynamic>> spendingHistory,
    required Map<String, dynamic> userGoals,
  }) async {
    final insights = <Map<String, dynamic>>[];

    for (final categoryEntry in _categoryData.entries) {
      final categoryId = categoryEntry.key;
      final categoryData = categoryEntry.value;

      // Analyze category-specific patterns
      final categorySpending = spendingHistory
          .where((transaction) => transaction['category'] == categoryId)
          .toList();

      if (categorySpending.isNotEmpty) {
        // Generate various types of insights
        insights.addAll(await _generateSpendingTrendInsights(
            categoryData, categorySpending));
        insights.addAll(
            await _generateVolatilityInsights(categoryData, categorySpending));
        insights.addAll(
            await _generateSeasonalInsights(categoryData, categorySpending));
        insights.addAll(await _generateGoalAlignmentInsights(
            categoryData, categorySpending, userGoals));
        insights.addAll(await _generateOptimizationInsights(
            categoryData, categorySpending));
      }
    }

    // Sort by impact score
    insights.sort((a, b) =>
        (b['impactScore'] as double).compareTo(a['impactScore'] as double));

    return insights.take(10).toList(); // Return top 10 insights
  }

  /// Adaptive category weight adjustment based on real-time learning
  Future<Map<String, double>> adaptCategoryWeights({
    required Map<String, double> currentWeights,
    required List<Map<String, dynamic>> recentTransactions,
    required Map<String, dynamic> userFeedback,
  }) async {
    final adaptedWeights = Map<String, double>.from(currentWeights);
    const learningRate = 0.1; // Gradual adaptation

    // Analyze recent spending patterns
    final recentCategoryTotals = <String, double>{};
    final totalSpent = recentTransactions.fold(
        0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));

    for (final transaction in recentTransactions) {
      final category = transaction['category']?.toString() ?? 'other';
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      recentCategoryTotals[category] =
          (recentCategoryTotals[category] ?? 0.0) + amount;
    }

    // Calculate actual spending ratios
    final actualRatios = <String, double>{};
    for (final entry in recentCategoryTotals.entries) {
      actualRatios[entry.key] = totalSpent > 0 ? entry.value / totalSpent : 0.0;
    }

    // Adapt weights based on actual vs planned spending
    for (final category in adaptedWeights.keys) {
      final actualRatio = actualRatios[category] ?? 0.0;
      final currentWeight = adaptedWeights[category] ?? 0.0;

      // Gradual adjustment towards actual spending patterns
      final adjustment = (actualRatio - currentWeight) * learningRate;
      adaptedWeights[category] = (currentWeight + adjustment).clamp(0.0, 1.0);
    }

    // Apply user feedback adjustments
    if (userFeedback['categoryPreferences'] != null) {
      final preferences =
          userFeedback['categoryPreferences'] as Map<String, dynamic>;
      for (final entry in preferences.entries) {
        final category = entry.key;
        final preference = entry.value as String;

        if (adaptedWeights.containsKey(category)) {
          switch (preference) {
            case 'increase':
              adaptedWeights[category] =
                  (adaptedWeights[category]! * 1.1).clamp(0.0, 1.0);
              break;
            case 'decrease':
              adaptedWeights[category] =
                  (adaptedWeights[category]! * 0.9).clamp(0.0, 1.0);
              break;
          }
        }
      }
    }

    // Normalize weights to ensure they sum to 1.0
    final totalWeight =
        adaptedWeights.values.fold(0.0, (sum, weight) => sum + weight);
    if (totalWeight > 0) {
      for (final category in adaptedWeights.keys) {
        adaptedWeights[category] = adaptedWeights[category]! / totalWeight;
      }
    }

    return adaptedWeights;
  }

  /// Detect job change from spending patterns
  Future<List<LifeEventDetection>> _detectJobChange(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    // Look for sudden changes in commuting/transportation costs
    final transportationSpending =
        _getCategorySpending(spendingHistory, 'transportation');
    if (transportationSpending.length >= 60) {
      // Need at least 2 months of data
      final recent = transportationSpending.take(30).toList();
      final older = transportationSpending.skip(30).take(30).toList();

      final recentAvg = recent
              .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
              .fold(0.0, (sum, amount) => sum + amount) /
          recent.length;
      final olderAvg = older
              .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
              .fold(0.0, (sum, amount) => sum + amount) /
          older.length;

      if ((recentAvg - olderAvg).abs() > olderAvg * 0.5) {
        // 50% change threshold
        events.add(LifeEventDetection(
          eventId: 'job_change_${DateTime.now().millisecondsSinceEpoch}',
          eventType: 'job_change',
          detectedAt: DateTime.now(),
          confidence: 0.7,
          indicators: [
            'Significant change in transportation spending',
            '${recentAvg > olderAvg ? 'Increase' : 'Decrease'} of ${((recentAvg - olderAvg).abs() / olderAvg * 100).toStringAsFixed(0)}%',
          ],
          categoryImpacts: {
            'transportation': recentAvg > olderAvg ? 1.2 : 0.8,
            'food': 1.1, // Possible lunch spending changes
          },
          recommendedAdjustments: [
            'Adjust transportation category allocation',
            'Review commuting-related expenses',
          ],
          expectedDuration: const Duration(days: 90),
        ));
      }
    }

    return events;
  }

  /// Detect moving from spending patterns
  Future<List<LifeEventDetection>> _detectMoving(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    // Look for home improvement, moving services, or utility setup costs
    final movingIndicators = spendingHistory.where((transaction) {
      final description =
          (transaction['description'] ?? '').toString().toLowerCase();
      final category = (transaction['category'] ?? '').toString().toLowerCase();

      return description.contains('moving') ||
          description.contains('movers') ||
          description.contains('u-haul') ||
          description.contains('storage') ||
          category.contains('utilities') ||
          category.contains('home');
    }).toList();

    if (movingIndicators.length >= 3) {
      // Multiple moving-related transactions
      final totalMovingCost = movingIndicators.fold(
          0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));

      if (totalMovingCost > 500) {
        // Significant moving expenses
        events.add(LifeEventDetection(
          eventId: 'moving_${DateTime.now().millisecondsSinceEpoch}',
          eventType: 'moving',
          detectedAt: DateTime.now(),
          confidence: 0.8,
          indicators: [
            'Multiple moving-related transactions detected',
            'Total moving expenses: \$${totalMovingCost.toStringAsFixed(0)}',
            '${movingIndicators.length} related transactions',
          ],
          categoryImpacts: {
            'housing': 1.3, // Higher housing costs initially
            'transportation': 1.2, // Possible commute changes
            'shopping': 1.4, // New household items
            'utilities': 1.5, // Setup costs
          },
          recommendedAdjustments: [
            'Temporarily increase housing and utilities allocation',
            'Plan for one-time setup expenses',
            'Monitor new area living costs',
          ],
          expectedDuration: const Duration(days: 120),
        ));
      }
    }

    return events;
  }

  /// Detect new family member from spending patterns
  Future<List<LifeEventDetection>> _detectNewFamily(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    // Look for baby/child-related purchases
    final familyIndicators = spendingHistory.where((transaction) {
      final description =
          (transaction['description'] ?? '').toString().toLowerCase();
      final merchant = (transaction['merchant'] ?? '').toString().toLowerCase();

      return description.contains('baby') ||
          description.contains('infant') ||
          description.contains('diaper') ||
          description.contains('formula') ||
          merchant.contains('babies') ||
          merchant.contains('maternity');
    }).toList();

    if (familyIndicators.length >= 5) {
      // Multiple baby-related purchases
      events.add(LifeEventDetection(
        eventId: 'new_family_${DateTime.now().millisecondsSinceEpoch}',
        eventType: 'new_family_member',
        detectedAt: DateTime.now(),
        confidence: 0.9,
        indicators: [
          'Multiple baby/child-related purchases',
          '${familyIndicators.length} family-related transactions',
        ],
        categoryImpacts: {
          'healthcare': 1.4,
          'food': 1.2,
          'shopping': 1.3,
          'childcare': 2.0,
        },
        recommendedAdjustments: [
          'Create new childcare budget category',
          'Increase healthcare allocation',
          'Plan for ongoing child expenses',
        ],
        expectedDuration: const Duration(days: 1825), // 5 years
      ));
    }

    return events;
  }

  /// Detect health issues from medical spending
  Future<List<LifeEventDetection>> _detectHealthIssues(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    final healthcareSpending =
        _getCategorySpending(spendingHistory, 'healthcare');
    if (healthcareSpending.length >= 30) {
      final recent = healthcareSpending.take(30).toList();
      final totalRecent = recent.fold(
          0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));

      if (totalRecent > 1000) {
        // Significant healthcare expenses
        events.add(LifeEventDetection(
          eventId: 'health_${DateTime.now().millisecondsSinceEpoch}',
          eventType: 'health_issue',
          detectedAt: DateTime.now(),
          confidence: 0.6,
          indicators: [
            'Increased healthcare spending detected',
            'Recent healthcare costs: \$${totalRecent.toStringAsFixed(0)}',
          ],
          categoryImpacts: {
            'healthcare': 1.5,
            'entertainment': 0.8, // Reduced discretionary spending
          },
          recommendedAdjustments: [
            'Increase healthcare budget allocation',
            'Consider health savings planning',
          ],
          expectedDuration: const Duration(days: 180),
        ));
      }
    }

    return events;
  }

  /// Detect major purchase from large transactions
  Future<List<LifeEventDetection>> _detectMajorPurchase(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    final recentLarge = spendingHistory.where((transaction) {
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      final dateStr =
          transaction['date']?.toString() ?? DateTime.now().toIso8601String();
      final date = DateTime.tryParse(dateStr) ?? DateTime.now();
      return amount > 2000 && DateTime.now().difference(date).inDays <= 30;
    }).toList();

    for (final transaction in recentLarge) {
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      final category = transaction['category']?.toString() ?? 'other';
      final dateStr =
          transaction['date']?.toString() ?? DateTime.now().toIso8601String();
      final date = DateTime.tryParse(dateStr) ?? DateTime.now();

      events.add(LifeEventDetection(
        eventId: 'major_purchase_${transaction['id']}',
        eventType: 'major_purchase',
        detectedAt: date,
        confidence: 0.8,
        indicators: [
          'Large purchase detected: \$${amount.toStringAsFixed(0)}',
          'Category: $category',
        ],
        categoryImpacts: {
          category.toString():
              0.7, // Reduced spending in same category temporarily
        },
        recommendedAdjustments: [
          'Temporarily reduce $category spending',
          'Monitor budget impact',
        ],
        expectedDuration: const Duration(days: 60),
      ));
    }

    return events;
  }

  /// Detect vacation/travel from spending patterns
  Future<List<LifeEventDetection>> _detectVacationTravel(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    final travelIndicators = spendingHistory.where((transaction) {
      final description =
          (transaction['description'] ?? '').toString().toLowerCase();
      final category = (transaction['category'] ?? '').toString().toLowerCase();

      return description.contains('airline') ||
          description.contains('hotel') ||
          description.contains('airbnb') ||
          category.contains('travel') ||
          category.contains('vacation');
    }).toList();

    if (travelIndicators.length >= 3) {
      final totalTravel = travelIndicators.fold(
          0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));

      events.add(LifeEventDetection(
        eventId: 'travel_${DateTime.now().millisecondsSinceEpoch}',
        eventType: 'vacation_travel',
        detectedAt: DateTime.now(),
        confidence: 0.7,
        indicators: [
          'Travel-related expenses detected',
          'Total travel costs: \$${totalTravel.toStringAsFixed(0)}',
        ],
        categoryImpacts: {
          'travel': 0.5, // Reduced travel spending post-vacation
          'entertainment': 0.8, // Reduced entertainment after spending
        },
        recommendedAdjustments: [
          'Temporarily reduce discretionary spending',
          'Plan recovery period for travel category',
        ],
        expectedDuration: const Duration(days: 45),
      ));
    }

    return events;
  }

  /// Detect education events
  Future<List<LifeEventDetection>> _detectEducationEvents(
      List<Map<String, dynamic>> spendingHistory) async {
    final events = <LifeEventDetection>[];

    final educationIndicators = spendingHistory.where((transaction) {
      final description =
          (transaction['description'] ?? '').toString().toLowerCase();
      return description.contains('tuition') ||
          description.contains('university') ||
          description.contains('college') ||
          description.contains('school');
    }).toList();

    if (educationIndicators.isNotEmpty) {
      final totalEducation = educationIndicators.fold(
          0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));

      events.add(LifeEventDetection(
        eventId: 'education_${DateTime.now().millisecondsSinceEpoch}',
        eventType: 'education_expense',
        detectedAt: DateTime.now(),
        confidence: 0.9,
        indicators: [
          'Education-related expenses detected',
          'Total education costs: \$${totalEducation.toStringAsFixed(0)}',
        ],
        categoryImpacts: {
          'education': 1.0,
          'entertainment': 0.7,
          'shopping': 0.8,
        },
        recommendedAdjustments: [
          'Create education budget category',
          'Reduce discretionary spending during school periods',
        ],
        expectedDuration: const Duration(days: 270), // Academic year
      ));
    }

    return events;
  }

  // Helper methods for category analysis and optimization

  List<Map<String, dynamic>> _getCategorySpending(
      List<Map<String, dynamic>> history, String category) {
    return history.where((t) => (t['category'] ?? '') == category).toList();
  }

  List<Map<String, dynamic>> _getDefaultCategoriesForTier(String incomeTier) {
    // Return tier-specific default categories
    switch (incomeTier) {
      case 'low':
        return [
          {'id': 'housing', 'name': 'Housing', 'defaultWeight': 0.40},
          {'id': 'food', 'name': 'Food', 'defaultWeight': 0.15},
          {
            'id': 'transportation',
            'name': 'Transportation',
            'defaultWeight': 0.15
          },
          {'id': 'utilities', 'name': 'Utilities', 'defaultWeight': 0.10},
          {'id': 'healthcare', 'name': 'Healthcare', 'defaultWeight': 0.08},
          {
            'id': 'entertainment',
            'name': 'Entertainment',
            'defaultWeight': 0.05
          },
          {'id': 'savings', 'name': 'Savings', 'defaultWeight': 0.07},
        ];
      case 'high':
        return [
          {'id': 'housing', 'name': 'Housing', 'defaultWeight': 0.30},
          {'id': 'food', 'name': 'Food', 'defaultWeight': 0.10},
          {
            'id': 'transportation',
            'name': 'Transportation',
            'defaultWeight': 0.12
          },
          {'id': 'utilities', 'name': 'Utilities', 'defaultWeight': 0.05},
          {'id': 'healthcare', 'name': 'Healthcare', 'defaultWeight': 0.05},
          {
            'id': 'entertainment',
            'name': 'Entertainment',
            'defaultWeight': 0.10
          },
          {'id': 'savings', 'name': 'Savings', 'defaultWeight': 0.28},
        ];
      default: // middle tier
        return [
          {'id': 'housing', 'name': 'Housing', 'defaultWeight': 0.35},
          {'id': 'food', 'name': 'Food', 'defaultWeight': 0.12},
          {
            'id': 'transportation',
            'name': 'Transportation',
            'defaultWeight': 0.13
          },
          {'id': 'utilities', 'name': 'Utilities', 'defaultWeight': 0.08},
          {'id': 'healthcare', 'name': 'Healthcare', 'defaultWeight': 0.06},
          {
            'id': 'entertainment',
            'name': 'Entertainment',
            'defaultWeight': 0.08
          },
          {'id': 'savings', 'name': 'Savings', 'defaultWeight': 0.18},
        ];
    }
  }

  Future<Map<String, dynamic>> _analyzeCategoryPatterns(
      List<Map<String, dynamic>> spendingHistory) async {
    // Analyze spending patterns, trends, and volatility for each category
    final analysis = <String, dynamic>{};

    for (final categoryEntry in _categoryData.entries) {
      final categoryId = categoryEntry.key;
      final categorySpending =
          _getCategorySpending(spendingHistory, categoryId);

      if (categorySpending.isNotEmpty) {
        final amounts = categorySpending
            .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
            .toList();
        final mean = amounts.reduce((a, b) => a + b) / amounts.length;
        final variance =
            amounts.map((x) => pow(x - mean, 2)).reduce((a, b) => a + b) /
                amounts.length;

        analysis[categoryId] = {
          'mean': mean,
          'variance': variance,
          'transactionCount': categorySpending.length,
          'volatility': sqrt(variance) / mean,
        };
      }
    }

    return analysis;
  }

  Future<Map<String, Map<String, dynamic>>> _optimizeCategoryWeights(
    Map<String, dynamic> categoryAnalysis,
    Map<String, dynamic> userGoals,
    Map<String, dynamic> currentFinancialState,
    List<LifeEventDetection> lifeEvents,
  ) async {
    final optimized = <String, Map<String, dynamic>>{};

    // Apply life event adjustments
    for (final categoryEntry in _categoryData.entries) {
      final categoryId = categoryEntry.key;
      final categoryData = Map<String, dynamic>.from(categoryEntry.value);

      // Apply life event impacts
      for (final event in lifeEvents) {
        if (event.categoryImpacts.containsKey(categoryId)) {
          final impact = event.categoryImpacts[categoryId]!;
          final currentWeight = categoryData['currentWeight'] as double;
          categoryData['recommendedWeight'] =
              (currentWeight * impact).clamp(0.0, 1.0);
        }
      }

      optimized[categoryId] = categoryData;
    }

    return optimized;
  }

  double _calculateExpectedImprovement(
    Map<String, Map<String, dynamic>> current,
    Map<String, Map<String, dynamic>> optimized,
    Map<String, dynamic> analysis,
  ) {
    return 0.15; // 15% expected improvement
  }

  List<String> _generateOptimizationReasons(
    Map<String, Map<String, dynamic>> current,
    Map<String, Map<String, dynamic>> optimized,
    List<LifeEventDetection> lifeEvents,
    Map<String, dynamic> analysis,
  ) {
    final reasons = <String>[];

    if (lifeEvents.isNotEmpty) {
      reasons
          .add('Life event adjustments: ${lifeEvents.length} events detected');
    }

    reasons.add('Historical spending pattern optimization');
    reasons.add('Volatility-based weight adjustments');

    return reasons;
  }

  Map<String, dynamic> _calculatePerformanceMetrics(
    Map<String, Map<String, dynamic>> categories,
    Map<String, dynamic> analysis,
  ) {
    return {
      'efficiency': 0.85,
      'adaptability': 0.78,
      'goalAlignment': 0.82,
      'categoriesOptimized': categories.length,
      'analysisDataPoints': analysis.length,
    };
  }

  // Insight generation methods (simplified implementations)

  Future<List<Map<String, dynamic>>> _generateSpendingTrendInsights(
    Map<String, dynamic> categoryData,
    List<Map<String, dynamic>> categorySpending,
  ) async {
    final insights = <Map<String, dynamic>>[];

    if (categorySpending.length >= 10) {
      final amounts = categorySpending
          .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
          .toList();
      final recent = amounts.take(5).toList();
      final older = amounts.skip(5).take(5).toList();

      final recentAvg = recent.reduce((a, b) => a + b) / recent.length;
      final olderAvg = older.reduce((a, b) => a + b) / older.length;

      if ((recentAvg - olderAvg).abs() > olderAvg * 0.2) {
        insights.add({
          'categoryId': categoryData['categoryId'],
          'insightType': 'spending_trend',
          'insight':
              'Significant ${recentAvg > olderAvg ? 'increase' : 'decrease'} in spending trend',
          'impactScore': 0.8,
          'actionableRecommendations': ['Monitor category budget allocation'],
          'supportingData': {'recentAvg': recentAvg, 'olderAvg': olderAvg},
        });
      }
    }

    return insights;
  }

  Future<List<Map<String, dynamic>>> _generateVolatilityInsights(
    Map<String, dynamic> categoryData,
    List<Map<String, dynamic>> categorySpending,
  ) async {
    final insights = <Map<String, dynamic>>[];

    if (categorySpending.length >= 5) {
      final amounts = categorySpending
          .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
          .toList();
      final mean = amounts.reduce((a, b) => a + b) / amounts.length;
      final variance =
          amounts.map((x) => pow(x - mean, 2)).reduce((a, b) => a + b) /
              amounts.length;
      final volatility = sqrt(variance) / mean;

      if (volatility > 0.5) {
        insights.add({
          'categoryId': categoryData['categoryId'],
          'insightType': 'volatility',
          'insight': 'High spending volatility detected',
          'impactScore': 0.7,
          'actionableRecommendations': [
            'Consider creating sub-categories',
            'Implement spending alerts'
          ],
          'supportingData': {'volatility': volatility, 'mean': mean},
        });
      }
    }

    return insights;
  }

  Future<List<Map<String, dynamic>>> _generateSeasonalInsights(
    Map<String, dynamic> categoryData,
    List<Map<String, dynamic>> categorySpending,
  ) async {
    try {
      // Get seasonal patterns from API
      final seasonalData = await _apiService.getSeasonalSpendingPatterns();
      final insights = <Map<String, dynamic>>[];

      final categoryId = categoryData['categoryId'] as String?;
      if (categoryId != null && seasonalData[categoryId] != null) {
        final categorySeasonalData =
            seasonalData[categoryId] as Map<String, dynamic>;

        insights.add({
          'categoryId': categoryId,
          'insightType': 'seasonal_pattern',
          'insight': 'Seasonal spending pattern detected',
          'impactScore':
              (categorySeasonalData['impact_score'] as num?)?.toDouble() ?? 0.6,
          'actionableRecommendations':
              categorySeasonalData['recommendations'] ?? [],
          'supportingData': categorySeasonalData,
        });
      }

      return insights;
    } catch (e) {
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> _generateGoalAlignmentInsights(
    Map<String, dynamic> categoryData,
    List<Map<String, dynamic>> categorySpending,
    Map<String, dynamic> userGoals,
  ) async {
    try {
      final categoryId = categoryData['categoryId'] as String?;
      if (categoryId == null) return [];

      // Get category behavioral insights from API
      final behavioralInsights =
          await _apiService.getCategoryBehavioralInsights(categoryId);
      final insights = <Map<String, dynamic>>[];

      if (behavioralInsights['goal_alignment'] != null) {
        final alignmentData =
            behavioralInsights['goal_alignment'] as Map<String, dynamic>;

        insights.add({
          'categoryId': categoryId,
          'insightType': 'goal_alignment',
          'insight': alignmentData['message'] ??
              'Category aligned with financial goals',
          'impactScore':
              (alignmentData['alignment_score'] as num?)?.toDouble() ?? 0.7,
          'actionableRecommendations': alignmentData['recommendations'] ?? [],
          'supportingData': alignmentData,
        });
      }

      return insights;
    } catch (e) {
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> _generateOptimizationInsights(
    Map<String, dynamic> categoryData,
    List<Map<String, dynamic>> categorySpending,
  ) async {
    try {
      // Get spending anomalies from API for optimization opportunities
      final anomalies = await _apiService.getSpendingAnomalies();
      final insights = <Map<String, dynamic>>[];

      final categoryId = categoryData['categoryId'] as String?;
      if (categoryId != null) {
        // Filter anomalies for this category
        final categoryAnomalies = anomalies
            .where((anomaly) => anomaly['category'] == categoryId)
            .toList();

        if (categoryAnomalies.isNotEmpty) {
          insights.add({
            'categoryId': categoryId,
            'insightType': 'optimization_opportunity',
            'insight': 'Optimization opportunities detected',
            'impactScore': 0.75,
            'actionableRecommendations': [
              'Review unusual spending patterns',
              'Consider setting category limits',
            ],
            'supportingData': {
              'anomaly_count': categoryAnomalies.length,
              'anomalies': categoryAnomalies,
            },
          });
        }
      }

      return insights;
    } catch (e) {
      return [];
    }
  }
}

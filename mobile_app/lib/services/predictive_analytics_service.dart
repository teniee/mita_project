import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'income_service.dart';
import 'spending_pattern_analyzer.dart';
import 'logging_service.dart';

/// Advanced predictive analytics service that forecasts future spending,
/// identifies upcoming financial challenges, and provides proactive recommendations.
class PredictiveAnalyticsService extends ChangeNotifier {
  static final PredictiveAnalyticsService _instance = PredictiveAnalyticsService._internal();
  factory PredictiveAnalyticsService() => _instance;
  PredictiveAnalyticsService._internal();

  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();
  final SpendingPatternAnalyzer _patternAnalyzer = SpendingPatternAnalyzer();

  // Prediction state
  Map<String, FinancialPrediction> _predictions = {};
  List<FutureRisk> _risks = [];
  List<FutureOpportunity> _opportunities = [];
  Map<String, CashFlowProjection> _cashFlowProjections = {};
  SeasonalAnalysis? _seasonalAnalysis;

  // Prediction models
  final Map<String, PredictionModel> _models = {};
  Timer? _predictionUpdateTimer;

  // Configuration
  static const int DEFAULT_PREDICTION_DAYS = 90;
  static const double MIN_PREDICTION_CONFIDENCE = 0.6;
  static const int MAX_PREDICTION_SCENARIOS = 5;

  // Getters
  Map<String, FinancialPrediction> get predictions => _predictions;
  List<FutureRisk> get risks => _risks;
  List<FutureOpportunity> get opportunities => _opportunities;
  Map<String, CashFlowProjection> get cashFlowProjections => _cashFlowProjections;
  SeasonalAnalysis? get seasonalAnalysis => _seasonalAnalysis;

  /// Initialize the predictive analytics service
  Future<void> initialize() async {
    try {
      logInfo('Initializing Predictive Analytics Service', tag: 'PREDICTIVE');

      // Initialize prediction models
      await _initializePredictionModels();

      // Load historical data for predictions
      await _loadHistoricalData();

      // Generate initial predictions
      await generatePredictions();

      // Analyze seasonal patterns
      await analyzeSeasonalPatterns();

      // Start periodic updates
      _startPeriodicUpdates();

      logInfo('Predictive analytics initialized successfully', tag: 'PREDICTIVE');
      notifyListeners();
    } catch (e) {
      logError('Failed to initialize predictive analytics: $e', tag: 'PREDICTIVE', error: e);
    }
  }

  /// Generate comprehensive financial predictions
  Future<void> generatePredictions({int daysAhead = DEFAULT_PREDICTION_DAYS}) async {
    try {
      logInfo('Generating financial predictions for $daysAhead days', tag: 'PREDICTIVE');

      _predictions = {};

      // Get AI-powered predictions from backend
      final aiPredictions = await _getAIPredictions(daysAhead);

      // Generate local model predictions
      final localPredictions = await _generateLocalPredictions(daysAhead);

      // Merge and validate predictions
      _predictions = await _mergePredictions(aiPredictions, localPredictions);

      // Generate cash flow projections
      await _generateCashFlowProjections(daysAhead);

      // Identify risks and opportunities
      await _analyzeRisksAndOpportunities();

      notifyListeners();
    } catch (e) {
      logError('Prediction generation failed: $e', tag: 'PREDICTIVE', error: e);
      _predictions = {};
    }
  }

  /// Predict spending for a specific category
  Future<CategoryPrediction> predictCategorySpending(String category, {int daysAhead = 30}) async {
    try {
      // Get category patterns
      final patterns = _patternAnalyzer.patterns;
      final categoryPattern = patterns?[category];

      if (categoryPattern == null) {
        return CategoryPrediction(
          category: category,
          predictedAmount: 0.0,
          confidence: 0.0,
          scenarios: [],
          factors: ['No historical data available'],
        );
      }

      // Apply multiple prediction models
      final scenarios = await _generatePredictionScenarios(categoryPattern, daysAhead);

      // Calculate weighted prediction
      final weightedPrediction = _calculateWeightedPrediction(scenarios);

      // Identify influencing factors
      final factors = _identifyInfluencingFactors(categoryPattern, daysAhead);

      return CategoryPrediction(
        category: category,
        predictedAmount: weightedPrediction.amount,
        confidence: weightedPrediction.probability,
        scenarios: scenarios,
        factors: factors,
        trend: categoryPattern.trend,
        riskLevel: _assessPredictionRisk(weightedPrediction, categoryPattern),
      );
    } catch (e) {
      logError('Category prediction failed for $category: $e', tag: 'PREDICTIVE', error: e);
      return CategoryPrediction(
        category: category,
        predictedAmount: 0.0,
        confidence: 0.0,
        scenarios: [],
        factors: ['Prediction error'],
      );
    }
  }

  /// Analyze seasonal spending patterns
  Future<void> analyzeSeasonalPatterns() async {
    try {
      logInfo('Analyzing seasonal patterns', tag: 'PREDICTIVE');

      // Get seasonal analysis from backend
      final backendSeasonality = await _apiService.getSeasonalSpendingPatterns();

      // Process seasonal data
      final monthlyPatterns = <int, double>{};
      final categorySeasonality = <String, Map<int, double>>{};
      final holidayImpact = <String, double>{};

      if (backendSeasonality['monthly_patterns'] != null) {
        final monthly = backendSeasonality['monthly_patterns'] as Map<String, dynamic>;
        monthly.forEach((month, factor) {
          monthlyPatterns[int.parse(month)] = (factor as num).toDouble();
        });
      }

      if (backendSeasonality['category_seasonality'] != null) {
        final categories = backendSeasonality['category_seasonality'] as Map<String, dynamic>;
        categories.forEach((category, data) {
          if (data is Map<String, dynamic>) {
            final patterns = <int, double>{};
            data.forEach((month, factor) {
              patterns[int.parse(month)] = (factor as num).toDouble();
            });
            categorySeasonality[category] = patterns;
          }
        });
      }

      if (backendSeasonality['holiday_impact'] != null) {
        final holidays = backendSeasonality['holiday_impact'] as Map<String, dynamic>;
        holidays.forEach((holiday, impact) {
          holidayImpact[holiday] = (impact as num).toDouble();
        });
      }

      _seasonalAnalysis = SeasonalAnalysis(
        monthlyPatterns: monthlyPatterns,
        categorySeasonality: categorySeasonality,
        holidayImpact: holidayImpact,
        yearOverYearGrowth: (backendSeasonality['yoy_growth'] as num?)?.toDouble() ?? 0.0,
        confidence: (backendSeasonality['confidence'] as num?)?.toDouble() ?? 0.7,
      );

      notifyListeners();
    } catch (e) {
      logError('Seasonal analysis failed: $e', tag: 'PREDICTIVE', error: e);
      _seasonalAnalysis = null;
    }
  }

  /// Get spending forecast for specific date range
  Future<SpendingForecast> getSpendingForecast({
    required DateTime startDate,
    required DateTime endDate,
    List<String>? categories,
  }) async {
    try {
      final daysDifference = endDate.difference(startDate).inDays;

      // Generate predictions for the period
      await generatePredictions(daysAhead: daysDifference);

      // Filter by categories if specified
      final relevantPredictions = categories != null
          ? Map.fromEntries(_predictions.entries.where((e) => categories.contains(e.key)))
          : _predictions;

      // Calculate total forecast
      double totalPredicted = 0.0;
      double weightedConfidence = 0.0;
      final categoryForecasts = <String, double>{};

      relevantPredictions.forEach((category, prediction) {
        final amount = prediction.amount;
        totalPredicted += amount;
        weightedConfidence += prediction.confidence * amount;
        categoryForecasts[category] = amount;
      });

      if (totalPredicted > 0) {
        weightedConfidence /= totalPredicted;
      }

      return SpendingForecast(
        startDate: startDate,
        endDate: endDate,
        totalPredicted: totalPredicted,
        categoryForecasts: categoryForecasts,
        confidence: weightedConfidence,
        scenarios: await _generateForecastScenarios(relevantPredictions),
        riskFactors: await _identifyForecastRisks(relevantPredictions),
      );
    } catch (e) {
      logError('Spending forecast failed: $e', tag: 'PREDICTIVE', error: e);
      return SpendingForecast(
        startDate: startDate,
        endDate: endDate,
        totalPredicted: 0.0,
        categoryForecasts: {},
        confidence: 0.0,
        scenarios: [],
        riskFactors: [],
      );
    }
  }

  /// Get budget burn rate analysis
  Future<BurnRateAnalysis> analyzeBudgetBurnRate(
      Map<String, double> budget, Map<String, double> currentSpending,
      {int remainingDays = 15}) async {
    try {
      final analysis = <String, CategoryBurnRate>{};

      budget.forEach((category, budgetAmount) {
        final spent = currentSpending[category] ?? 0.0;
        final remaining = budgetAmount - spent;
        final daysElapsed = 30 - remainingDays;

        final dailyBurnRate = daysElapsed > 0 ? spent / daysElapsed : 0.0;
        final projectedSpending = dailyBurnRate * 30;

        final burnRate = budgetAmount > 0 ? projectedSpending / budgetAmount : 0.0;

        analysis[category] = CategoryBurnRate(
          category: category,
          budgetAmount: budgetAmount,
          spentAmount: spent,
          remainingAmount: remaining,
          dailyBurnRate: dailyBurnRate,
          projectedTotalSpending: projectedSpending,
          burnRateRatio: burnRate,
          daysToExhaustion:
              remaining > 0 && dailyBurnRate > 0 ? (remaining / dailyBurnRate).round() : null,
          riskLevel: _assessBurnRateRisk(burnRate),
        );
      });

      return BurnRateAnalysis(
        categoryAnalysis: analysis,
        overallBurnRate: _calculateOverallBurnRate(analysis),
        projectedOverspend: _calculateProjectedOverspend(analysis),
        recommendedActions: _generateBurnRateRecommendations(analysis),
      );
    } catch (e) {
      logError('Burn rate analysis failed: $e', tag: 'PREDICTIVE', error: e);
      return BurnRateAnalysis(
        categoryAnalysis: {},
        overallBurnRate: 0.0,
        projectedOverspend: 0.0,
        recommendedActions: [],
      );
    }
  }

  /// Get early warning alerts
  List<PredictiveAlert> getEarlyWarningAlerts() {
    final alerts = <PredictiveAlert>[];

    // Risk-based alerts
    for (final risk in _risks) {
      if (risk.severity == RiskSeverity.high) {
        alerts.add(PredictiveAlert(
          id: 'risk_${risk.id}',
          type: AlertType.risk,
          severity: risk.severity,
          title: risk.title,
          message: risk.description,
          category: risk.category,
          predictedDate: risk.timeframe,
          confidence: risk.probability,
          actionRequired: true,
          recommendations: risk.mitigation,
        ));
      }
    }

    // Opportunity alerts
    for (final opportunity in _opportunities) {
      if (opportunity.impact == ImpactLevel.high) {
        alerts.add(PredictiveAlert(
          id: 'opp_${opportunity.id}',
          type: AlertType.opportunity,
          severity: RiskSeverity.medium,
          title: opportunity.title,
          message: opportunity.description,
          category: opportunity.category,
          predictedDate: DateTime.now().add(const Duration(days: 7)),
          confidence: opportunity.confidence,
          actionRequired: false,
          recommendations: opportunity.actionSteps,
        ));
      }
    }

    // Sort by severity and confidence
    alerts.sort((a, b) {
      final severityCompare = b.severity.index.compareTo(a.severity.index);
      if (severityCompare != 0) return severityCompare;
      return b.confidence.compareTo(a.confidence);
    });

    return alerts.take(10).toList();
  }

  // ============================================================================
  // PRIVATE HELPER METHODS
  // ============================================================================

  /// Initialize prediction models
  Future<void> _initializePredictionModels() async {
    // Initialize different prediction models
    _models['trend'] = PredictionModel('Trend Analysis', 0.3);
    _models['seasonal'] = PredictionModel('Seasonal Patterns', 0.25);
    _models['regression'] = PredictionModel('Linear Regression', 0.2);
    _models['ai'] = PredictionModel('AI Neural Network', 0.25);
  }

  /// Load historical data for predictions
  Future<void> _loadHistoricalData() async {
    try {
      // Load transaction history, patterns, and contextual data
      logDebug('Loading historical data for predictions', tag: 'PREDICTIVE');
    } catch (e) {
      logWarning('Failed to load historical data: $e', tag: 'PREDICTIVE');
    }
  }

  /// Get AI-powered predictions from backend
  Future<Map<String, FinancialPrediction>> _getAIPredictions(int daysAhead) async {
    try {
      final predictions = <String, FinancialPrediction>{};

      final aiResult = await _apiService.getAISpendingPrediction(daysAhead: daysAhead);

      if (aiResult['predictions'] != null) {
        final predictionsData = aiResult['predictions'] as Map<String, dynamic>;

        predictionsData.forEach((category, data) {
          if (data is Map<String, dynamic>) {
            predictions[category] = FinancialPrediction(
              category: category,
              amount: (data['predicted_amount'] as num?)?.toDouble() ?? 0.0,
              confidence: (data['confidence'] as num?)?.toDouble() ?? 0.5,
              timeframe: daysAhead,
              method: PredictionMethod.ai,
              factors: List<String>.from(data['influencing_factors'] ?? []),
            );
          }
        });
      }

      return predictions;
    } catch (e) {
      logWarning('AI predictions failed: $e', tag: 'PREDICTIVE');
      return {};
    }
  }

  /// Generate local model predictions
  Future<Map<String, FinancialPrediction>> _generateLocalPredictions(int daysAhead) async {
    final predictions = <String, FinancialPrediction>{};

    final patterns = _patternAnalyzer.patterns;
    if (patterns == null) return predictions;

    for (final pattern in patterns.entries) {
      final category = pattern.key;
      final patternData = pattern.value;

      // Apply trend analysis
      final trendPrediction = _applyTrendModel(patternData, daysAhead);

      // Apply seasonal adjustment
      final seasonalAdjustment = _applySeasonalModel(category, daysAhead);

      // Combine models
      final combinedAmount = trendPrediction * seasonalAdjustment;
      final confidence = _calculateCombinedConfidence(patternData);

      predictions[category] = FinancialPrediction(
        category: category,
        amount: combinedAmount,
        confidence: confidence,
        timeframe: daysAhead,
        method: PredictionMethod.hybrid,
        factors: [
          'Historical trend: ${patternData.trend.name}',
          'Pattern confidence: ${(patternData.confidence * 100).toStringAsFixed(1)}%',
          'Seasonal adjustment: ${(seasonalAdjustment * 100 - 100).toStringAsFixed(1)}%',
        ],
      );
    }

    return predictions;
  }

  /// Merge AI and local predictions
  Future<Map<String, FinancialPrediction>> _mergePredictions(
    Map<String, FinancialPrediction> aiPredictions,
    Map<String, FinancialPrediction> localPredictions,
  ) async {
    final merged = <String, FinancialPrediction>{};

    // Get all categories
    final allCategories = {...aiPredictions.keys, ...localPredictions.keys};

    for (final category in allCategories) {
      final aiPred = aiPredictions[category];
      final localPred = localPredictions[category];

      if (aiPred != null && localPred != null) {
        // Merge both predictions with confidence-based weighting
        final aiWeight = aiPred.confidence;
        final localWeight = localPred.confidence;
        final totalWeight = aiWeight + localWeight;

        if (totalWeight > 0) {
          final mergedAmount =
              (aiPred.amount * aiWeight + localPred.amount * localWeight) / totalWeight;
          final mergedConfidence = math.min(1.0, (aiWeight + localWeight) / 2);

          merged[category] = FinancialPrediction(
            category: category,
            amount: mergedAmount,
            confidence: mergedConfidence,
            timeframe: aiPred.timeframe,
            method: PredictionMethod.ensemble,
            factors: [...aiPred.factors, ...localPred.factors],
          );
        }
      } else if (aiPred != null) {
        merged[category] = aiPred;
      } else if (localPred != null) {
        merged[category] = localPred;
      }
    }

    return merged;
  }

  /// Generate cash flow projections
  Future<void> _generateCashFlowProjections(int daysAhead) async {
    _cashFlowProjections = {};

    // This would generate detailed cash flow projections
    // For now, we'll create a simple projection
    final totalPredicted = _predictions.values.fold<double>(0, (sum, pred) => sum + pred.amount);

    _cashFlowProjections['total'] = CashFlowProjection(
      period: 'monthly',
      inflow: 0.0, // Would be calculated from income data
      outflow: totalPredicted,
      netFlow: -totalPredicted,
      confidence: _predictions.values.isEmpty
          ? 0.0
          : _predictions.values.fold<double>(0, (sum, pred) => sum + pred.confidence) /
              _predictions.length,
    );
  }

  /// Analyze risks and opportunities
  Future<void> _analyzeRisksAndOpportunities() async {
    _risks = [];
    _opportunities = [];

    // Analyze predictions for risks
    for (final prediction in _predictions.entries) {
      final category = prediction.key;
      final pred = prediction.value;

      // High spending risk
      if (pred.confidence > 0.7 && pred.amount > 1000) {
        _risks.add(FutureRisk(
          id: 'high_spending_$category',
          type: RiskType.overspending,
          severity: RiskSeverity.medium,
          title: 'Potential overspending in $category',
          description:
              'Predicted spending of \$${pred.amount.toStringAsFixed(2)} is above normal levels',
          category: category,
          probability: pred.confidence,
          timeframe: DateTime.now().add(Duration(days: pred.timeframe)),
          impact: _calculateRiskImpact(pred.amount),
          mitigation: [
            'Monitor $category expenses closely',
            'Set stricter budget limits',
            'Look for alternatives to reduce costs',
          ],
        ));
      }

      // Low confidence opportunity
      if (pred.confidence < 0.5 && pred.amount < 500) {
        _opportunities.add(FutureOpportunity(
          id: 'savings_$category',
          type: OpportunityType.savings,
          title: 'Potential savings in $category',
          description: 'Low predicted spending could free up budget for other goals',
          category: category,
          confidence: 1.0 - pred.confidence,
          impact: ImpactLevel.medium,
          potentialValue: pred.amount * 0.2, // 20% potential savings
          timeframe: Duration(days: pred.timeframe),
          actionSteps: [
            'Review $category budget allocation',
            'Consider reallocating unused funds',
            'Explore investment opportunities',
          ],
        ));
      }
    }
  }

  /// Generate prediction scenarios
  Future<List<PredictionScenario>> _generatePredictionScenarios(
    SpendingPattern pattern,
    int daysAhead,
  ) async {
    final scenarios = <PredictionScenario>[];

    final baseAmount = pattern.averageAmount * (daysAhead / 30.0);

    // Conservative scenario
    scenarios.add(PredictionScenario(
      name: 'Conservative',
      probability: 0.7,
      amount: baseAmount * 0.8,
      description: 'Below average spending pattern',
    ));

    // Most likely scenario
    scenarios.add(PredictionScenario(
      name: 'Most Likely',
      probability: 0.8,
      amount: baseAmount,
      description: 'Expected spending based on historical patterns',
    ));

    // Aggressive scenario
    scenarios.add(PredictionScenario(
      name: 'High',
      probability: 0.3,
      amount: baseAmount * 1.3,
      description: 'Above average spending pattern',
    ));

    return scenarios;
  }

  /// Start periodic prediction updates
  void _startPeriodicUpdates() {
    _predictionUpdateTimer = Timer.periodic(
      const Duration(hours: 6), // Update every 6 hours
      (timer) => generatePredictions(),
    );
  }

  /// Calculate weighted prediction from scenarios
  PredictionScenario _calculateWeightedPrediction(List<PredictionScenario> scenarios) {
    if (scenarios.isEmpty) {
      return PredictionScenario(
          name: 'Default', probability: 0.0, amount: 0.0, description: 'No data');
    }

    double weightedAmount = 0.0;
    double totalProbability = 0.0;

    for (final scenario in scenarios) {
      weightedAmount += scenario.amount * scenario.probability;
      totalProbability += scenario.probability;
    }

    if (totalProbability > 0) {
      weightedAmount /= totalProbability;
    }

    return PredictionScenario(
      name: 'Weighted Average',
      probability: totalProbability / scenarios.length,
      amount: weightedAmount,
      description: 'Probability-weighted prediction',
    );
  }

  /// Apply trend model
  double _applyTrendModel(SpendingPattern pattern, int daysAhead) {
    final baseAmount = pattern.averageAmount * (daysAhead / 30.0);

    switch (pattern.trend) {
      case TrendDirection.increasing:
        return baseAmount * (1 + pattern.variability * 0.1);
      case TrendDirection.decreasing:
        return baseAmount * (1 - pattern.variability * 0.1);
      case TrendDirection.stable:
        return baseAmount;
    }
  }

  /// Apply seasonal model
  double _applySeasonalModel(String category, int daysAhead) {
    if (_seasonalAnalysis == null) return 1.0;

    final futureDate = DateTime.now().add(Duration(days: daysAhead));
    final month = futureDate.month;

    final categorySeasonality = _seasonalAnalysis!.categorySeasonality[category];
    if (categorySeasonality != null && categorySeasonality.containsKey(month)) {
      return categorySeasonality[month]!;
    }

    return _seasonalAnalysis!.monthlyPatterns[month] ?? 1.0;
  }

  /// Calculate combined confidence
  double _calculateCombinedConfidence(SpendingPattern pattern) {
    return math.min(1.0, pattern.confidence * pattern.consistency);
  }

  @override
  void dispose() {
    _predictionUpdateTimer?.cancel();
    super.dispose();
  }

  // Placeholder implementations for complex methods
  List<String> _identifyInfluencingFactors(SpendingPattern pattern, int daysAhead) => [];
  PredictionRisk _assessPredictionRisk(PredictionScenario prediction, SpendingPattern pattern) =>
      PredictionRisk.low;
  Future<List<ForecastScenario>> _generateForecastScenarios(
          Map<String, FinancialPrediction> predictions) async =>
      [];
  Future<List<String>> _identifyForecastRisks(Map<String, FinancialPrediction> predictions) async =>
      [];
  BurnRateRisk _assessBurnRateRisk(double burnRate) => burnRate > 1.2
      ? BurnRateRisk.high
      : burnRate > 1.0
          ? BurnRateRisk.medium
          : BurnRateRisk.low;
  double _calculateOverallBurnRate(Map<String, CategoryBurnRate> analysis) => 1.0;
  double _calculateProjectedOverspend(Map<String, CategoryBurnRate> analysis) => 0.0;
  List<String> _generateBurnRateRecommendations(Map<String, CategoryBurnRate> analysis) => [];
  double _calculateRiskImpact(double amount) => amount / 1000.0;
}

// ============================================================================
// DATA CLASSES
// ============================================================================

class FinancialPrediction {
  final String category;
  final double amount;
  final double confidence;
  final int timeframe;
  final PredictionMethod method;
  final List<String> factors;

  FinancialPrediction({
    required this.category,
    required this.amount,
    required this.confidence,
    required this.timeframe,
    required this.method,
    required this.factors,
  });
}

class CategoryPrediction {
  final String category;
  final double predictedAmount;
  final double confidence;
  final List<PredictionScenario> scenarios;
  final List<String> factors;
  final TrendDirection? trend;
  final PredictionRisk? riskLevel;

  CategoryPrediction({
    required this.category,
    required this.predictedAmount,
    required this.confidence,
    required this.scenarios,
    required this.factors,
    this.trend,
    this.riskLevel,
  });
}

class PredictionScenario {
  final String name;
  final double probability;
  final double amount;
  final String description;

  PredictionScenario({
    required this.name,
    required this.probability,
    required this.amount,
    required this.description,
  });
}

class SeasonalAnalysis {
  final Map<int, double> monthlyPatterns;
  final Map<String, Map<int, double>> categorySeasonality;
  final Map<String, double> holidayImpact;
  final double yearOverYearGrowth;
  final double confidence;

  SeasonalAnalysis({
    required this.monthlyPatterns,
    required this.categorySeasonality,
    required this.holidayImpact,
    required this.yearOverYearGrowth,
    required this.confidence,
  });
}

class SpendingForecast {
  final DateTime startDate;
  final DateTime endDate;
  final double totalPredicted;
  final Map<String, double> categoryForecasts;
  final double confidence;
  final List<ForecastScenario> scenarios;
  final List<String> riskFactors;

  SpendingForecast({
    required this.startDate,
    required this.endDate,
    required this.totalPredicted,
    required this.categoryForecasts,
    required this.confidence,
    required this.scenarios,
    required this.riskFactors,
  });
}

class BurnRateAnalysis {
  final Map<String, CategoryBurnRate> categoryAnalysis;
  final double overallBurnRate;
  final double projectedOverspend;
  final List<String> recommendedActions;

  BurnRateAnalysis({
    required this.categoryAnalysis,
    required this.overallBurnRate,
    required this.projectedOverspend,
    required this.recommendedActions,
  });
}

class CategoryBurnRate {
  final String category;
  final double budgetAmount;
  final double spentAmount;
  final double remainingAmount;
  final double dailyBurnRate;
  final double projectedTotalSpending;
  final double burnRateRatio;
  final int? daysToExhaustion;
  final BurnRateRisk riskLevel;

  CategoryBurnRate({
    required this.category,
    required this.budgetAmount,
    required this.spentAmount,
    required this.remainingAmount,
    required this.dailyBurnRate,
    required this.projectedTotalSpending,
    required this.burnRateRatio,
    this.daysToExhaustion,
    required this.riskLevel,
  });
}

class FutureRisk {
  final String id;
  final RiskType type;
  final RiskSeverity severity;
  final String title;
  final String description;
  final String? category;
  final double probability;
  final DateTime timeframe;
  final double impact;
  final List<String> mitigation;

  FutureRisk({
    required this.id,
    required this.type,
    required this.severity,
    required this.title,
    required this.description,
    this.category,
    required this.probability,
    required this.timeframe,
    required this.impact,
    required this.mitigation,
  });
}

class FutureOpportunity {
  final String id;
  final OpportunityType type;
  final String title;
  final String description;
  final String? category;
  final double confidence;
  final ImpactLevel impact;
  final double potentialValue;
  final Duration timeframe;
  final List<String> actionSteps;

  FutureOpportunity({
    required this.id,
    required this.type,
    required this.title,
    required this.description,
    this.category,
    required this.confidence,
    required this.impact,
    required this.potentialValue,
    required this.timeframe,
    required this.actionSteps,
  });
}

class CashFlowProjection {
  final String period;
  final double inflow;
  final double outflow;
  final double netFlow;
  final double confidence;

  CashFlowProjection({
    required this.period,
    required this.inflow,
    required this.outflow,
    required this.netFlow,
    required this.confidence,
  });
}

class PredictiveAlert {
  final String id;
  final AlertType type;
  final RiskSeverity severity;
  final String title;
  final String message;
  final String? category;
  final DateTime predictedDate;
  final double confidence;
  final bool actionRequired;
  final List<String> recommendations;

  PredictiveAlert({
    required this.id,
    required this.type,
    required this.severity,
    required this.title,
    required this.message,
    this.category,
    required this.predictedDate,
    required this.confidence,
    required this.actionRequired,
    required this.recommendations,
  });
}

class PredictionModel {
  final String name;
  final double weight;

  PredictionModel(this.name, this.weight);
}

// Enums
enum PredictionMethod { ai, statistical, hybrid, ensemble }

enum PredictionRisk { low, medium, high }

enum BurnRateRisk { low, medium, high }

enum RiskType { overspending, cashflow, budget, seasonal }

enum RiskSeverity { low, medium, high, critical }

enum OpportunityType { savings, investment, optimization, goal }

enum ImpactLevel { low, medium, high }

enum AlertType { risk, opportunity, warning, info }

class ForecastScenario {
  final String name;
  final double probability;
  final Map<String, double> categoryAmounts;

  ForecastScenario({
    required this.name,
    required this.probability,
    required this.categoryAmounts,
  });
}

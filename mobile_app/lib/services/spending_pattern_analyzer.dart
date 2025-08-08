import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'income_service.dart';
import 'logging_service.dart';

/// Advanced spending pattern analysis engine that identifies user behavioral patterns,
/// spending habits, and provides actionable insights for financial improvement.
class SpendingPatternAnalyzer extends ChangeNotifier {
  static final SpendingPatternAnalyzer _instance = SpendingPatternAnalyzer._internal();
  factory SpendingPatternAnalyzer() => _instance;
  SpendingPatternAnalyzer._internal();

  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();

  // Analysis state
  Map<String, SpendingPattern>? _patterns;
  Map<String, List<SpendingTrend>> _trends = {};
  List<BehavioralInsight> _insights = [];
  List<SpendingAnomaly> _anomalies = [];
  Map<String, SpendingVelocity> _velocityAnalysis = {};
  
  // Pattern detection thresholds
  static const double ANOMALY_THRESHOLD = 2.0; // Standard deviations
  static const int MIN_TRANSACTIONS_FOR_PATTERN = 3;
  static const int ANALYSIS_WINDOW_DAYS = 90;

  // Getters
  Map<String, SpendingPattern>? get patterns => _patterns;
  Map<String, List<SpendingTrend>> get trends => _trends;
  List<BehavioralInsight> get insights => _insights;
  List<SpendingAnomaly> get anomalies => _anomalies;
  Map<String, SpendingVelocity> get velocityAnalysis => _velocityAnalysis;

  /// Initialize the pattern analyzer with historical data
  Future<void> initialize() async {
    try {
      logInfo('Initializing Spending Pattern Analyzer', tag: 'PATTERN_ANALYZER');
      
      // Load historical spending data
      await _loadHistoricalData();
      
      // Analyze current patterns
      await analyzePatterns();
      
      // Detect spending anomalies
      await detectAnomalies();
      
      // Generate behavioral insights
      await generateInsights();
      
      logInfo('Pattern analyzer initialized successfully', tag: 'PATTERN_ANALYZER');
      notifyListeners();
      
    } catch (e) {
      logError('Failed to initialize pattern analyzer: $e', tag: 'PATTERN_ANALYZER', error: e);
    }
  }

  /// Analyze spending patterns from transaction history
  Future<void> analyzePatterns() async {
    try {
      logInfo('Analyzing spending patterns', tag: 'PATTERN_ANALYZER');

      // Get comprehensive pattern analysis from backend
      final backendPatterns = await _apiService.getSpendingPatternAnalysis();
      
      _patterns = {};
      final patternsData = backendPatterns['patterns'] as Map<String, dynamic>? ?? {};
      
      // Process backend patterns
      patternsData.forEach((category, data) {
        if (data is Map<String, dynamic>) {
          _patterns![category] = SpendingPattern(
            category: category,
            averageAmount: (data['average_amount'] as num?)?.toDouble() ?? 0.0,
            medianAmount: (data['median_amount'] as num?)?.toDouble() ?? 0.0,
            frequency: (data['frequency'] as num?)?.toInt() ?? 0,
            trend: _parseTrend(data['trend'] as String?),
            seasonality: Map<String, double>.from(data['seasonality'] ?? {}),
            dayOfWeekPatterns: Map<String, double>.from(data['day_patterns'] ?? {}),
            timeOfDayPatterns: Map<String, double>.from(data['time_patterns'] ?? {}),
            merchantConcentration: (data['merchant_concentration'] as num?)?.toDouble() ?? 0.0,
            variability: (data['variability'] as num?)?.toDouble() ?? 0.0,
            consistency: (data['consistency'] as num?)?.toDouble() ?? 0.0,
            confidence: (data['confidence'] as num?)?.toDouble() ?? 0.5,
          );
        }
      });

      // Analyze spending velocity
      await _analyzeSpendingVelocity();
      
      // Detect trending patterns
      await _analyzeTrends();

      notifyListeners();
      
    } catch (e) {
      logError('Pattern analysis failed: $e', tag: 'PATTERN_ANALYZER', error: e);
      _patterns = {};
    }
  }

  /// Detect spending anomalies and unusual patterns
  Future<void> detectAnomalies() async {
    try {
      logInfo('Detecting spending anomalies', tag: 'PATTERN_ANALYZER');

      _anomalies = [];
      
      // Get anomalies from backend
      final backendAnomalies = await _apiService.getSpendingAnomalies();
      
      for (final anomaly in backendAnomalies) {
        if (anomaly is Map<String, dynamic>) {
          _anomalies.add(SpendingAnomaly(
            id: anomaly['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
            type: _parseAnomalyType(anomaly['type'] as String?),
            category: anomaly['category'] as String? ?? 'Unknown',
            amount: (anomaly['amount'] as num?)?.toDouble() ?? 0.0,
            expectedAmount: (anomaly['expected_amount'] as num?)?.toDouble() ?? 0.0,
            deviationScore: (anomaly['anomaly_score'] as num?)?.toDouble() ?? 0.0,
            date: DateTime.tryParse(anomaly['date'] as String? ?? '') ?? DateTime.now(),
            merchant: anomaly['merchant'] as String?,
            description: anomaly['description'] as String? ?? '',
            possibleCauses: List<String>.from(anomaly['possible_causes'] ?? []),
            severity: _calculateSeverity(anomaly['anomaly_score'] as num? ?? 0),
            confidence: (anomaly['confidence'] as num?)?.toDouble() ?? 0.5,
          ));
        }
      }

      // Local anomaly detection for additional insights
      await _detectLocalAnomalies();

      // Sort by severity and date
      _anomalies.sort((a, b) {
        final severityCompare = b.severity.index.compareTo(a.severity.index);
        if (severityCompare != 0) return severityCompare;
        return b.date.compareTo(a.date);
      });

      notifyListeners();
      
    } catch (e) {
      logError('Anomaly detection failed: $e', tag: 'PATTERN_ANALYZER', error: e);
      _anomalies = [];
    }
  }

  /// Generate behavioral insights from spending patterns
  Future<void> generateInsights() async {
    try {
      logInfo('Generating behavioral insights', tag: 'PATTERN_ANALYZER');

      _insights = [];

      // Get behavioral insights from backend
      final backendInsights = await _apiService.getBehavioralInsights();
      
      // Process insights if they exist
      final insightsList = backendInsights['insights'] as List<dynamic>? ?? [];
      
      for (final insight in insightsList) {
        if (insight is Map<String, dynamic>) {
          _insights.add(BehavioralInsight(
            id: insight['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
            type: _parseInsightType(insight['type'] as String?),
            title: insight['title'] as String? ?? '',
            message: insight['message'] as String? ?? '',
            category: insight['category'] as String?,
            impact: _parseImpactLevel(insight['impact'] as String?),
            confidence: (insight['confidence'] as num?)?.toDouble() ?? 0.5,
            actionable: insight['actionable'] as bool? ?? false,
            recommendations: List<String>.from(insight['recommendations'] ?? []),
            relatedPatterns: List<String>.from(insight['related_patterns'] ?? []),
            timeframe: insight['timeframe'] as String? ?? 'current',
          ));
        }
      }

      // Generate local insights from patterns
      await _generateLocalInsights();

      // Sort by impact and confidence
      _insights.sort((a, b) {
        final impactCompare = b.impact.index.compareTo(a.impact.index);
        if (impactCompare != 0) return impactCompare;
        return b.confidence.compareTo(a.confidence);
      });

      notifyListeners();
      
    } catch (e) {
      logError('Insight generation failed: $e', tag: 'PATTERN_ANALYZER', error: e);
      _insights = [];
    }
  }

  /// Analyze spending velocity and predict future spending
  Future<void> _analyzeSpendingVelocity() async {
    try {
      _velocityAnalysis = {};

      if (_patterns == null) return;

      for (final pattern in _patterns!.entries) {
        final category = pattern.key;
        final patternData = pattern.value;

        // Calculate current velocity
        final currentVelocity = _calculateCurrentVelocity(patternData);
        
        // Predict future spending
        final prediction = _predictCategorySpending(patternData, daysAhead: 30);

        _velocityAnalysis[category] = SpendingVelocity(
          category: category,
          currentRate: currentVelocity,
          averageRate: patternData.averageAmount,
          acceleration: _calculateAcceleration(patternData),
          predictedAmount: prediction,
          confidence: patternData.confidence,
          timeToLimit: _calculateTimeToLimit(patternData, currentVelocity),
          riskLevel: _assessVelocityRisk(currentVelocity, patternData.averageAmount),
        );
      }
      
    } catch (e) {
      logError('Velocity analysis failed: $e', tag: 'PATTERN_ANALYZER', error: e);
    }
  }

  /// Analyze spending trends over time
  Future<void> _analyzeTrends() async {
    try {
      _trends = {};

      if (_patterns == null) return;

      for (final pattern in _patterns!.entries) {
        final category = pattern.key;
        final patternData = pattern.value;

        final trends = <SpendingTrend>[];

        // Weekly trend
        trends.add(SpendingTrend(
          period: TrendPeriod.weekly,
          direction: patternData.trend,
          magnitude: _calculateTrendMagnitude(patternData, TrendPeriod.weekly),
          confidence: patternData.confidence,
          significance: _calculateTrendSignificance(patternData, TrendPeriod.weekly),
        ));

        // Monthly trend
        trends.add(SpendingTrend(
          period: TrendPeriod.monthly,
          direction: patternData.trend,
          magnitude: _calculateTrendMagnitude(patternData, TrendPeriod.monthly),
          confidence: patternData.confidence,
          significance: _calculateTrendSignificance(patternData, TrendPeriod.monthly),
        ));

        _trends[category] = trends;
      }
      
    } catch (e) {
      logError('Trend analysis failed: $e', tag: 'PATTERN_ANALYZER', error: e);
    }
  }

  /// Get spending insights for a specific category
  List<BehavioralInsight> getCategoryInsights(String category) {
    return _insights.where((insight) => 
      insight.category == category || 
      insight.relatedPatterns.contains(category)
    ).toList();
  }

  /// Get spending forecast for next period
  Map<String, double> getSpendingForecast({int daysAhead = 30}) {
    final forecast = <String, double>{};
    
    if (_patterns == null) return forecast;

    for (final pattern in _patterns!.entries) {
      final category = pattern.key;
      final patternData = pattern.value;
      
      forecast[category] = _predictCategorySpending(patternData, daysAhead: daysAhead);
    }

    return forecast;
  }

  /// Get personalized spending recommendations
  List<SpendingRecommendation> getPersonalizedRecommendations() {
    final recommendations = <SpendingRecommendation>[];

    // Generate recommendations based on anomalies
    for (final anomaly in _anomalies) {
      if (anomaly.severity == AnomalySeverity.high) {
        recommendations.add(SpendingRecommendation(
          type: RecommendationType.reduction,
          category: anomaly.category,
          title: 'High spending alert in ${anomaly.category}',
          description: 'You spent ${anomaly.deviationScore.toStringAsFixed(1)}x more than usual',
          potentialSavings: anomaly.amount - anomaly.expectedAmount,
          confidence: anomaly.confidence,
          actionSteps: [
            'Review recent ${anomaly.category} transactions',
            'Set spending limits for this category',
            'Consider alternative options',
          ],
        ));
      }
    }

    // Generate recommendations based on velocity analysis
    for (final velocity in _velocityAnalysis.entries) {
      if (velocity.value.riskLevel == VelocityRisk.high) {
        recommendations.add(SpendingRecommendation(
          type: RecommendationType.caution,
          category: velocity.key,
          title: 'Rapid spending increase in ${velocity.key}',
          description: 'Current spending rate may exceed budget',
          potentialSavings: velocity.value.predictedAmount - velocity.value.averageRate,
          confidence: velocity.value.confidence,
          actionSteps: [
            'Slow down spending in this category',
            'Review upcoming expenses',
            'Consider budget reallocation',
          ],
        ));
      }
    }

    // Sort by potential impact
    recommendations.sort((a, b) => b.potentialSavings.compareTo(a.potentialSavings));

    return recommendations.take(10).toList();
  }

  // ============================================================================
  // PRIVATE HELPER METHODS
  // ============================================================================

  /// Load historical spending data
  Future<void> _loadHistoricalData() async {
    try {
      // Historical data would be loaded from API or local storage
      logDebug('Loading historical spending data', tag: 'PATTERN_ANALYZER');
    } catch (e) {
      logWarning('Failed to load historical data: $e', tag: 'PATTERN_ANALYZER');
    }
  }

  /// Detect local anomalies using statistical methods
  Future<void> _detectLocalAnomalies() async {
    // Implementation for local anomaly detection
    // This would use statistical methods like z-score analysis
  }

  /// Generate local behavioral insights
  Future<void> _generateLocalInsights() async {
    if (_patterns == null) return;

    // Weekend vs weekday spending patterns
    for (final pattern in _patterns!.entries) {
      final patternData = pattern.value;
      final weekendSpending = (patternData.dayOfWeekPatterns['6'] ?? 0.0) + 
                             (patternData.dayOfWeekPatterns['7'] ?? 0.0);
      final weekdaySpending = patternData.dayOfWeekPatterns.entries
          .where((e) => !['6', '7'].contains(e.key))
          .fold(0.0, (sum, entry) => sum + entry.value);

      if (weekendSpending > weekdaySpending * 1.5) {
        _insights.add(BehavioralInsight(
          id: 'weekend_${pattern.key}',
          type: InsightType.pattern,
          title: 'Weekend spending pattern',
          message: 'You tend to spend significantly more on ${pattern.key} during weekends',
          category: pattern.key,
          impact: ImpactLevel.medium,
          confidence: 0.8,
          actionable: true,
          recommendations: [
            'Plan weekend activities in advance',
            'Set weekend spending limits',
            'Consider free weekend alternatives',
          ],
          relatedPatterns: ['weekend_overspending'],
          timeframe: 'ongoing',
        ));
      }
    }
  }

  /// Calculate current spending velocity
  double _calculateCurrentVelocity(SpendingPattern pattern) {
    // This would calculate based on recent transactions
    return pattern.averageAmount * 1.1; // Placeholder
  }

  /// Calculate spending acceleration
  double _calculateAcceleration(SpendingPattern pattern) {
    // This would calculate rate of change in spending velocity
    return pattern.trend == TrendDirection.increasing ? 0.1 : 
           pattern.trend == TrendDirection.decreasing ? -0.1 : 0.0;
  }

  /// Predict category spending for future period
  double _predictCategorySpending(SpendingPattern pattern, {required int daysAhead}) {
    final baseAmount = pattern.averageAmount;
    final trendMultiplier = pattern.trend == TrendDirection.increasing ? 1.1 :
                           pattern.trend == TrendDirection.decreasing ? 0.9 : 1.0;
    
    // Apply seasonality if available
    final seasonalAdjustment = _getSeasonalAdjustment(pattern, daysAhead);
    
    return baseAmount * trendMultiplier * seasonalAdjustment * (daysAhead / 30.0);
  }

  /// Get seasonal adjustment factor
  double _getSeasonalAdjustment(SpendingPattern pattern, int daysAhead) {
    final futureMonth = DateTime.now().add(Duration(days: daysAhead)).month.toString();
    return pattern.seasonality[futureMonth] ?? 1.0;
  }

  /// Calculate time to reach spending limit
  Duration? _calculateTimeToLimit(SpendingPattern pattern, double currentRate) {
    // This would be implemented based on budget limits
    return null;
  }

  /// Assess velocity risk level
  VelocityRisk _assessVelocityRisk(double currentRate, double averageRate) {
    final ratio = currentRate / averageRate;
    if (ratio > 1.5) return VelocityRisk.high;
    if (ratio > 1.2) return VelocityRisk.medium;
    return VelocityRisk.low;
  }

  /// Calculate trend magnitude
  double _calculateTrendMagnitude(SpendingPattern pattern, TrendPeriod period) {
    // Implementation would analyze historical data for trend strength
    return pattern.variability; // Placeholder
  }

  /// Calculate trend significance
  double _calculateTrendSignificance(SpendingPattern pattern, TrendPeriod period) {
    // Implementation would calculate statistical significance
    return pattern.confidence;
  }

  /// Parse trend direction from string
  TrendDirection _parseTrend(String? trend) {
    switch (trend?.toLowerCase()) {
      case 'increasing': return TrendDirection.increasing;
      case 'decreasing': return TrendDirection.decreasing;
      case 'stable': return TrendDirection.stable;
      default: return TrendDirection.stable;
    }
  }

  /// Parse anomaly type from string
  AnomalyType _parseAnomalyType(String? type) {
    switch (type?.toLowerCase()) {
      case 'amount': return AnomalyType.amount;
      case 'frequency': return AnomalyType.frequency;
      case 'merchant': return AnomalyType.merchant;
      case 'time': return AnomalyType.time;
      default: return AnomalyType.amount;
    }
  }

  /// Parse insight type from string
  InsightType _parseInsightType(String? type) {
    switch (type?.toLowerCase()) {
      case 'pattern': return InsightType.pattern;
      case 'trend': return InsightType.trend;
      case 'anomaly': return InsightType.anomaly;
      case 'optimization': return InsightType.optimization;
      default: return InsightType.pattern;
    }
  }

  /// Parse impact level from string
  ImpactLevel _parseImpactLevel(String? impact) {
    switch (impact?.toLowerCase()) {
      case 'high': return ImpactLevel.high;
      case 'medium': return ImpactLevel.medium;
      case 'low': return ImpactLevel.low;
      default: return ImpactLevel.medium;
    }
  }

  /// Calculate anomaly severity
  AnomalySeverity _calculateSeverity(num score) {
    if (score >= 0.8) return AnomalySeverity.high;
    if (score >= 0.5) return AnomalySeverity.medium;
    return AnomalySeverity.low;
  }
}

// ============================================================================
// DATA CLASSES
// ============================================================================

class SpendingPattern {
  final String category;
  final double averageAmount;
  final double medianAmount;
  final int frequency;
  final TrendDirection trend;
  final Map<String, double> seasonality;
  final Map<String, double> dayOfWeekPatterns;
  final Map<String, double> timeOfDayPatterns;
  final double merchantConcentration;
  final double variability;
  final double consistency;
  final double confidence;

  SpendingPattern({
    required this.category,
    required this.averageAmount,
    required this.medianAmount,
    required this.frequency,
    required this.trend,
    required this.seasonality,
    required this.dayOfWeekPatterns,
    required this.timeOfDayPatterns,
    required this.merchantConcentration,
    required this.variability,
    required this.consistency,
    required this.confidence,
  });
}

class SpendingTrend {
  final TrendPeriod period;
  final TrendDirection direction;
  final double magnitude;
  final double confidence;
  final double significance;

  SpendingTrend({
    required this.period,
    required this.direction,
    required this.magnitude,
    required this.confidence,
    required this.significance,
  });
}

class BehavioralInsight {
  final String id;
  final InsightType type;
  final String title;
  final String message;
  final String? category;
  final ImpactLevel impact;
  final double confidence;
  final bool actionable;
  final List<String> recommendations;
  final List<String> relatedPatterns;
  final String timeframe;

  BehavioralInsight({
    required this.id,
    required this.type,
    required this.title,
    required this.message,
    this.category,
    required this.impact,
    required this.confidence,
    required this.actionable,
    required this.recommendations,
    required this.relatedPatterns,
    required this.timeframe,
  });
}

class SpendingAnomaly {
  final String id;
  final AnomalyType type;
  final String category;
  final double amount;
  final double expectedAmount;
  final double deviationScore;
  final DateTime date;
  final String? merchant;
  final String description;
  final List<String> possibleCauses;
  final AnomalySeverity severity;
  final double confidence;

  SpendingAnomaly({
    required this.id,
    required this.type,
    required this.category,
    required this.amount,
    required this.expectedAmount,
    required this.deviationScore,
    required this.date,
    this.merchant,
    required this.description,
    required this.possibleCauses,
    required this.severity,
    required this.confidence,
  });

  double get deviationPercentage => ((amount - expectedAmount) / expectedAmount * 100);
}

class SpendingVelocity {
  final String category;
  final double currentRate;
  final double averageRate;
  final double acceleration;
  final double predictedAmount;
  final double confidence;
  final Duration? timeToLimit;
  final VelocityRisk riskLevel;

  SpendingVelocity({
    required this.category,
    required this.currentRate,
    required this.averageRate,
    required this.acceleration,
    required this.predictedAmount,
    required this.confidence,
    this.timeToLimit,
    required this.riskLevel,
  });
}

class SpendingRecommendation {
  final RecommendationType type;
  final String category;
  final String title;
  final String description;
  final double potentialSavings;
  final double confidence;
  final List<String> actionSteps;

  SpendingRecommendation({
    required this.type,
    required this.category,
    required this.title,
    required this.description,
    required this.potentialSavings,
    required this.confidence,
    required this.actionSteps,
  });
}

// Enums
enum TrendDirection { increasing, decreasing, stable }
enum TrendPeriod { weekly, monthly, quarterly }
enum InsightType { pattern, trend, anomaly, optimization }
enum ImpactLevel { low, medium, high }
enum AnomalyType { amount, frequency, merchant, time }
enum AnomalySeverity { low, medium, high }
enum VelocityRisk { low, medium, high }
enum RecommendationType { reduction, increase, reallocation, caution, opportunity }
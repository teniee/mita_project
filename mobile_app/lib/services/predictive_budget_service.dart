import 'dart:math';
import '../models/budget_intelligence_models.dart';

/// Prediction model types
enum PredictionModel {
  linearRegression,
  exponentialSmoothing,
  seasonalDecomposition,
  neuralNetwork,
  ensemble,
}

/// Advanced predictive budget forecasting with ML-based models
class PredictiveBudgetService {
  static final PredictiveBudgetService _instance = PredictiveBudgetService._internal();
  factory PredictiveBudgetService() => _instance;
  PredictiveBudgetService._internal();

  /// Generate comprehensive budget predictions using external models
  Future<PredictiveBudgetAnalysis> generateBudgetPredictions({
    required List<Map<String, dynamic>> historicalData,
    required Map<String, dynamic> currentFinancialState,
    required List<Map<String, dynamic>> externalFactors,
    int forecastDays = 30,
    bool includeSeasonality = true,
  }) async {
    // Select optimal prediction model
    final primaryModel = await _selectOptimalModel(historicalData);

    // Generate daily forecasts
    final dailyForecasts = await _generateDailyForecasts(
      historicalData,
      currentFinancialState,
      forecastDays,
      primaryModel,
    );

    // Generate weekly forecasts
    final weeklyForecasts = await _generateWeeklyForecasts(
      historicalData,
      currentFinancialState,
      forecastDays ~/ 7,
      primaryModel,
    );

    // Generate monthly forecasts
    final monthlyForecasts = await _generateMonthlyForecasts(
      historicalData,
      currentFinancialState,
      3, // 3 months ahead
      primaryModel,
    );

    // Identify risks and opportunities
    final riskWarnings = await _identifyRiskAlerts(dailyForecasts, currentFinancialState);

    // Calculate overall confidence
    final overallConfidence = _calculateOverallConfidence(
      dailyForecasts,
      historicalData.length,
      primaryModel,
    );

    // Generate trend analysis
    final trendAnalysis =
        await _generateTrendAnalysis(dailyForecasts, weeklyForecasts, monthlyForecasts);

    return PredictiveBudgetAnalysis(
      forecasts: dailyForecasts,
      trendAnalysis: trendAnalysis,
      riskWarnings: riskWarnings,
      overallConfidence: overallConfidence,
    );
  }

  /// Generate simple budget forecast for single prediction
  Future<BudgetForecast> generateSingleForecast({
    required List<Map<String, dynamic>> historicalData,
    required DateTime forecastDate,
    String category = 'overall',
  }) async {
    final model = await _selectOptimalModel(historicalData);
    final prediction = await _applyPredictionModel(
      model,
      historicalData,
      {},
      forecastDate,
      'daily',
    );

    return BudgetForecast(
      forecastedDailyBudget: (prediction['amount'] as num).toDouble(),
      confidence: (prediction['confidence'] as num).toDouble(),
      primaryFactor: 'historical_trend',
      contributingFactors: Map<String, double>.from(prediction['factors'] as Map),
      forecastDate: forecastDate,
    );
  }

  /// Predict short-term budget adjustments
  Future<List<BudgetForecast>> predictShortTermAdjustments({
    required List<Map<String, dynamic>> recentTransactions,
    required double currentDailyBudget,
    int daysAhead = 7,
  }) async {
    final forecasts = <BudgetForecast>[];
    final baseDate = DateTime.now();

    for (int i = 1; i <= daysAhead; i++) {
      final forecastDate = baseDate.add(Duration(days: i));

      // Apply velocity-based adjustments
      final velocityAdjustment = _calculateVelocityAdjustment(recentTransactions, forecastDate);
      final adjustedBudget = currentDailyBudget * velocityAdjustment;

      // Apply temporal factors
      final temporalMultiplier = _getTemporalMultiplier(forecastDate);
      final finalBudget = adjustedBudget * temporalMultiplier;

      forecasts.add(BudgetForecast(
        forecastedDailyBudget: finalBudget,
        confidence: 0.8,
        primaryFactor: 'velocity_adjustment',
        contributingFactors: {
          'velocityAdjustment': velocityAdjustment,
          'temporalMultiplier': temporalMultiplier,
          'baseBudget': currentDailyBudget,
        },
        forecastDate: forecastDate,
      ));
    }

    return forecasts;
  }

  /// Select optimal prediction model based on data characteristics
  Future<PredictionModel> _selectOptimalModel(List<Map<String, dynamic>> historicalData) async {
    if (historicalData.length < 30) {
      return PredictionModel.linearRegression; // Simple model for limited data
    }

    // Analyze data characteristics
    final hasSeasonality = _detectSeasonality(historicalData);
    final hasVolatility = _detectVolatility(historicalData);
    final dataQuality = _assessDataQuality(historicalData);

    if (dataQuality > 0.8 && historicalData.length > 180) {
      return PredictionModel.ensemble; // Best model for high-quality, abundant data
    } else if (hasSeasonality && historicalData.length > 90) {
      return PredictionModel.seasonalDecomposition;
    } else if (hasVolatility) {
      return PredictionModel.exponentialSmoothing;
    } else {
      return PredictionModel.linearRegression;
    }
  }

  /// Generate daily budget forecasts using external BudgetForecast model
  Future<List<BudgetForecast>> _generateDailyForecasts(
    List<Map<String, dynamic>> historicalData,
    Map<String, dynamic> currentState,
    int forecastDays,
    PredictionModel model,
  ) async {
    final forecasts = <BudgetForecast>[];
    final baseDate = DateTime.now();

    for (int i = 1; i <= forecastDays; i++) {
      final forecastDate = baseDate.add(Duration(days: i));
      final prediction = await _applyPredictionModel(
        model,
        historicalData,
        currentState,
        forecastDate,
        'daily',
      );

      forecasts.add(BudgetForecast(
        forecastedDailyBudget: (prediction['amount'] as num).toDouble(),
        confidence: (prediction['confidence'] as num).toDouble(),
        primaryFactor: _getPrimaryFactor(model),
        contributingFactors: Map<String, double>.from(prediction['factors'] as Map),
        forecastDate: forecastDate,
      ));
    }

    return forecasts;
  }

  /// Generate weekly budget forecasts
  Future<List<BudgetForecast>> _generateWeeklyForecasts(
    List<Map<String, dynamic>> historicalData,
    Map<String, dynamic> currentState,
    int forecastWeeks,
    PredictionModel model,
  ) async {
    final forecasts = <BudgetForecast>[];
    final baseDate = DateTime.now();

    for (int i = 1; i <= forecastWeeks; i++) {
      final forecastDate = baseDate.add(Duration(days: i * 7));
      final prediction = await _applyPredictionModel(
        model,
        historicalData,
        currentState,
        forecastDate,
        'weekly',
      );

      forecasts.add(BudgetForecast(
        forecastedDailyBudget: (prediction['amount'] as num).toDouble() * 7, // Convert to weekly
        confidence: (prediction['confidence'] as num).toDouble(),
        primaryFactor: _getPrimaryFactor(model),
        contributingFactors: Map<String, double>.from(prediction['factors'] as Map),
        forecastDate: forecastDate,
      ));
    }

    return forecasts;
  }

  /// Generate monthly budget forecasts
  Future<List<BudgetForecast>> _generateMonthlyForecasts(
    List<Map<String, dynamic>> historicalData,
    Map<String, dynamic> currentState,
    int forecastMonths,
    PredictionModel model,
  ) async {
    final forecasts = <BudgetForecast>[];
    final baseDate = DateTime.now();

    for (int i = 1; i <= forecastMonths; i++) {
      final forecastDate = DateTime(baseDate.year, baseDate.month + i, 1);
      final prediction = await _applyPredictionModel(
        model,
        historicalData,
        currentState,
        forecastDate,
        'monthly',
      );

      forecasts.add(BudgetForecast(
        forecastedDailyBudget: (prediction['amount'] as num).toDouble() * 30, // Convert to monthly
        confidence: (prediction['confidence'] as num).toDouble(),
        primaryFactor: _getPrimaryFactor(model),
        contributingFactors: Map<String, double>.from(prediction['factors'] as Map),
        forecastDate: forecastDate,
      ));
    }

    return forecasts;
  }

  /// Apply prediction model to generate forecast
  Future<Map<String, dynamic>> _applyPredictionModel(
    PredictionModel model,
    List<Map<String, dynamic>> historicalData,
    Map<String, dynamic> currentState,
    DateTime forecastDate,
    String timeframe,
  ) async {
    switch (model) {
      case PredictionModel.linearRegression:
        return _applyLinearRegression(historicalData, forecastDate, timeframe);
      case PredictionModel.exponentialSmoothing:
        return _applyExponentialSmoothing(historicalData, forecastDate, timeframe);
      case PredictionModel.seasonalDecomposition:
        return _applySeasonalDecomposition(historicalData, forecastDate, timeframe);
      case PredictionModel.neuralNetwork:
        return _applyNeuralNetwork(historicalData, currentState, forecastDate, timeframe);
      case PredictionModel.ensemble:
        return _applyEnsembleModel(historicalData, currentState, forecastDate, timeframe);
    }
  }

  /// Linear regression prediction
  Map<String, dynamic> _applyLinearRegression(
    List<Map<String, dynamic>> data,
    DateTime forecastDate,
    String timeframe,
  ) {
    if (data.isEmpty) {
      return _getDefaultPrediction(forecastDate);
    }

    // Extract amounts and calculate trend
    final amounts = data.map((d) => (d['amount'] as num?)?.toDouble() ?? 0.0).toList();
    final mean = amounts.reduce((a, b) => a + b) / amounts.length;

    // Simple trend calculation
    final trend = amounts.length > 1 ? (amounts.last - amounts.first) / amounts.length : 0.0;
    final daysDiff = forecastDate
        .difference(
            DateTime.parse(data.last['date']?.toString() ?? DateTime.now().toIso8601String()))
        .inDays;

    final predictedAmount = mean + (trend * daysDiff);
    final standardError = _calculateStandardError(amounts, mean);

    return {
      'amount': max(0, predictedAmount),
      'confidence': 0.7,
      'upperBound': predictedAmount + (1.96 * standardError),
      'lowerBound': max(0, predictedAmount - (1.96 * standardError)),
      'quality': 'moderate',
      'factors': {
        'trend': trend,
        'historicalMean': mean,
        'dataPoints': data.length,
      },
    };
  }

  /// Exponential smoothing prediction
  Map<String, dynamic> _applyExponentialSmoothing(
    List<Map<String, dynamic>> data,
    DateTime forecastDate,
    String timeframe,
  ) {
    if (data.isEmpty) {
      return _getDefaultPrediction(forecastDate);
    }

    final amounts = data.map((d) => (d['amount'] as num?)?.toDouble() ?? 0.0).toList();
    const alpha = 0.3; // Smoothing parameter

    double smoothedValue = amounts.first;
    for (int i = 1; i < amounts.length; i++) {
      smoothedValue = alpha * amounts[i] + (1 - alpha) * smoothedValue;
    }

    final standardError = _calculateStandardError(amounts, smoothedValue);

    return {
      'amount': max(0, smoothedValue),
      'confidence': 0.75,
      'upperBound': smoothedValue + (1.96 * standardError),
      'lowerBound': max(0, smoothedValue - (1.96 * standardError)),
      'quality': 'good',
      'factors': {
        'smoothedValue': smoothedValue,
        'alpha': alpha,
        'dataPoints': data.length,
      },
    };
  }

  /// Seasonal decomposition prediction
  Map<String, dynamic> _applySeasonalDecomposition(
    List<Map<String, dynamic>> data,
    DateTime forecastDate,
    String timeframe,
  ) {
    // Simplified seasonal adjustment
    final basePredicition = _applyExponentialSmoothing(data, forecastDate, timeframe);
    final seasonalMultiplier = _getSeasonalMultiplier(forecastDate, timeframe);

    final adjustedAmount = (basePredicition['amount'] as double) * seasonalMultiplier;

    return {
      'amount': max(0, adjustedAmount),
      'confidence': 0.8,
      'upperBound': adjustedAmount * 1.2,
      'lowerBound': adjustedAmount * 0.8,
      'quality': 'good',
      'factors': {
        'baseAmount': basePredicition['amount'],
        'seasonalMultiplier': seasonalMultiplier,
        'seasonalAdjustment': true,
      },
    };
  }

  /// Neural network prediction (simplified)
  Map<String, dynamic> _applyNeuralNetwork(
    List<Map<String, dynamic>> data,
    Map<String, dynamic> currentState,
    DateTime forecastDate,
    String timeframe,
  ) {
    // Simplified neural network simulation
    final basePredicition = _applySeasonalDecomposition(data, forecastDate, timeframe);
    final adjustmentFactor = 1.0 + (Random().nextDouble() * 0.1 - 0.05); // ±5% adjustment

    final adjustedAmount = (basePredicition['amount'] as double) * adjustmentFactor;

    return {
      'amount': max(0, adjustedAmount),
      'confidence': 0.85,
      'upperBound': adjustedAmount * 1.15,
      'lowerBound': adjustedAmount * 0.85,
      'quality': 'high',
      'factors': {
        'neuralNetworkOutput': adjustedAmount,
        'adjustmentFactor': adjustmentFactor,
        'featureComplexity': 'high',
      },
    };
  }

  /// Ensemble model prediction
  Map<String, dynamic> _applyEnsembleModel(
    List<Map<String, dynamic>> data,
    Map<String, dynamic> currentState,
    DateTime forecastDate,
    String timeframe,
  ) {
    // Combine multiple models
    final linearPred = _applyLinearRegression(data, forecastDate, timeframe);
    final exponentialPred = _applyExponentialSmoothing(data, forecastDate, timeframe);
    final seasonalPred = _applySeasonalDecomposition(data, forecastDate, timeframe);

    // Weighted average
    const weights = [0.2, 0.3, 0.5]; // Favor seasonal decomposition
    final ensembleAmount = (linearPred['amount'] as double) * weights[0] +
        (exponentialPred['amount'] as double) * weights[1] +
        (seasonalPred['amount'] as double) * weights[2];

    return {
      'amount': max(0, ensembleAmount),
      'confidence': 0.9,
      'upperBound': ensembleAmount * 1.1,
      'lowerBound': ensembleAmount * 0.9,
      'quality': 'excellent',
      'factors': {
        'ensembleComponents': 3,
        'linearWeight': weights[0],
        'exponentialWeight': weights[1],
        'seasonalWeight': weights[2],
      },
    };
  }

  // Helper methods for calculations

  String _getPrimaryFactor(PredictionModel model) {
    switch (model) {
      case PredictionModel.linearRegression:
        return 'linear_trend';
      case PredictionModel.exponentialSmoothing:
        return 'exponential_smoothing';
      case PredictionModel.seasonalDecomposition:
        return 'seasonal_pattern';
      case PredictionModel.neuralNetwork:
        return 'neural_network';
      case PredictionModel.ensemble:
        return 'ensemble_prediction';
    }
  }

  double _calculateVelocityAdjustment(
      List<Map<String, dynamic>> recentTransactions, DateTime forecastDate) {
    if (recentTransactions.length < 5) return 1.0;

    final recentSpending = recentTransactions
        .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
        .reduce((a, b) => a + b);

    final avgDaily = recentSpending / recentTransactions.length;

    // Adjust based on recent velocity
    if (avgDaily > 80) return 0.9; // High spending - reduce budget
    if (avgDaily < 30) return 1.1; // Low spending - increase budget
    return 1.0; // Normal spending
  }

  double _getTemporalMultiplier(DateTime date) {
    // Weekend boost
    if (date.weekday >= 6) return 1.15;

    // Month-end effect
    final daysInMonth = DateTime(date.year, date.month + 1, 0).day;
    if (date.day > daysInMonth - 5) return 1.1;

    return 1.0;
  }

  double _calculateStandardError(List<double> amounts, double mean) {
    if (amounts.length <= 1) return mean * 0.2;

    final variance =
        amounts.map((x) => pow(x - mean, 2)).reduce((a, b) => a + b) / (amounts.length - 1);
    return sqrt(variance / amounts.length);
  }

  double _getSeasonalMultiplier(DateTime date, String timeframe) {
    // Simplified seasonal adjustments
    switch (timeframe) {
      case 'daily':
        return date.weekday >= 6 ? 1.15 : 1.0; // Weekend increase
      case 'weekly':
        return date.month == 12 ? 1.3 : 1.0; // December increase
      case 'monthly':
        final seasonalMonths = {12: 1.3, 11: 1.15, 1: 0.85, 2: 0.9};
        return seasonalMonths[date.month] ?? 1.0;
      default:
        return 1.0;
    }
  }

  Map<String, dynamic> _getDefaultPrediction(DateTime forecastDate) {
    return {
      'amount': 50.0, // Default daily amount
      'confidence': 0.3,
      'upperBound': 75.0,
      'lowerBound': 25.0,
      'quality': 'low',
      'factors': {'default': true, 'reason': 'insufficient_data'},
    };
  }

  // Additional helper methods for data analysis

  bool _detectSeasonality(List<Map<String, dynamic>> data) {
    return data.length >= 90; // Simplified - need 3 months for seasonality
  }

  bool _detectVolatility(List<Map<String, dynamic>> data) {
    if (data.length < 10) return false;

    final amounts = data.map((d) => (d['amount'] as num?)?.toDouble() ?? 0.0).toList();
    final mean = amounts.reduce((a, b) => a + b) / amounts.length;
    final standardDeviation =
        sqrt(amounts.map((x) => pow(x - mean, 2)).reduce((a, b) => a + b) / amounts.length);

    return (standardDeviation / mean) > 0.3; // High volatility if CV > 30%
  }

  double _assessDataQuality(List<Map<String, dynamic>> data) {
    if (data.isEmpty) return 0.0;

    double qualityScore = 0.5; // Base score

    // More data = higher quality
    if (data.length >= 180)
      qualityScore += 0.3;
    else if (data.length >= 90)
      qualityScore += 0.2;
    else if (data.length >= 30) qualityScore += 0.1;

    // Consistency check
    final nonZeroCount = data.where((d) => (d['amount'] as num?)?.toDouble() != 0.0).length;
    final consistencyRatio = nonZeroCount / data.length;
    qualityScore += consistencyRatio * 0.2;

    return qualityScore.clamp(0.0, 1.0);
  }

  double _calculateOverallConfidence(
    List<BudgetForecast> forecasts,
    int dataPoints,
    PredictionModel model,
  ) {
    if (forecasts.isEmpty) return 0.0;

    final avgConfidence =
        forecasts.map((f) => f.confidence).reduce((a, b) => a + b) / forecasts.length;

    // Adjust based on data quantity and model sophistication
    double adjustment = 0.0;
    if (dataPoints >= 180) adjustment += 0.1;
    if (model == PredictionModel.ensemble) adjustment += 0.1;

    return (avgConfidence + adjustment).clamp(0.0, 1.0);
  }

  Future<List<String>> _identifyRiskAlerts(
    List<BudgetForecast> forecasts,
    Map<String, dynamic> currentState,
  ) async {
    final alerts = <String>[];

    // Check for increasing spending trends
    if (forecasts.length >= 7) {
      final weekTrend = forecasts.take(7).map((f) => f.forecastedDailyBudget).toList();
      final isIncreasing = weekTrend.last > weekTrend.first * 1.2;
      if (isIncreasing) {
        alerts.add('Spending trend is increasing - consider budget review');
      }
    }

    // Check for potential budget overruns
    final currentBudget = (currentState['monthlyBudget'] as num?)?.toDouble() ?? 0.0;
    if (forecasts.length >= 30) {
      final projectedMonthly =
          forecasts.take(30).map((f) => f.forecastedDailyBudget).reduce((a, b) => a + b);
      if (projectedMonthly > currentBudget * 1.1) {
        alerts.add(
            'Risk of exceeding monthly budget by ${((projectedMonthly / currentBudget - 1) * 100).toStringAsFixed(0)}%');
      }
    }

    return alerts;
  }

  Future<List<String>> _identifyOpportunities(
    List<BudgetForecast> forecasts,
    Map<String, dynamic> currentState,
  ) async {
    final opportunities = <String>[];

    // Check for potential savings
    final currentBudget = (currentState['monthlyBudget'] as num?)?.toDouble() ?? 0.0;
    if (forecasts.length >= 30) {
      final projectedMonthly =
          forecasts.take(30).map((f) => f.forecastedDailyBudget).reduce((a, b) => a + b);
      if (projectedMonthly < currentBudget * 0.9) {
        final savings = currentBudget - projectedMonthly;
        opportunities.add('Opportunity to save \$${savings.toStringAsFixed(0)} this month');
      }
    }

    // Check for consistent under-forecasting
    final consistentUnder = forecasts.take(7).every((f) => f.confidence > 0.8);
    if (consistentUnder) {
      opportunities.add('High confidence predictions - consider increasing savings goals');
    }

    return opportunities;
  }

  Future<Map<String, double>> _generateTrendAnalysis(
    List<BudgetForecast> dailyForecasts,
    List<BudgetForecast> weeklyForecasts,
    List<BudgetForecast> monthlyForecasts,
  ) async {
    final trends = <String, double>{};

    // Daily trend
    if (dailyForecasts.length >= 7) {
      final earlyWeek =
          dailyForecasts.take(7).map((f) => f.forecastedDailyBudget).reduce((a, b) => a + b) / 7;
      final lateWeek = dailyForecasts.length >= 14
          ? dailyForecasts
                  .skip(7)
                  .take(7)
                  .map((f) => f.forecastedDailyBudget)
                  .reduce((a, b) => a + b) /
              7
          : earlyWeek;
      trends['daily_trend'] = (lateWeek - earlyWeek) / earlyWeek;
    }

    // Weekly trend
    if (weeklyForecasts.length >= 2) {
      final trend =
          (weeklyForecasts[1].forecastedDailyBudget - weeklyForecasts[0].forecastedDailyBudget) /
              weeklyForecasts[0].forecastedDailyBudget;
      trends['weekly_trend'] = trend;
    }

    // Monthly trend
    if (monthlyForecasts.length >= 2) {
      final trend =
          (monthlyForecasts[1].forecastedDailyBudget - monthlyForecasts[0].forecastedDailyBudget) /
              monthlyForecasts[0].forecastedDailyBudget;
      trends['monthly_trend'] = trend;
    }

    return trends;
  }
}

/// Dynamic Financial Threshold Service for Mobile App
///
/// This service provides access to economically-sound, contextual financial
/// thresholds by communicating with the MITA backend's dynamic threshold service.
///
/// All hardcoded financial thresholds in the mobile app should be replaced
/// with calls to this service for personalized, income-appropriate values.

import 'dart:async';
import 'package:logging/logging.dart';

import 'api_service.dart';

final _logger = Logger('DynamicThresholdService');

enum ThresholdType {
  budgetAllocation('budget_allocation'),
  spendingPattern('spending_pattern'),
  healthScoring('health_scoring'),
  savingsTarget('savings_target'),
  goalConstraint('goal_constraint'),
  behavioralTrigger('behavioral_trigger');

  const ThresholdType(this.value);
  final String value;
}

class UserContext {
  final double monthlyIncome;
  final int age;
  final String region;
  final int familySize;
  final double debtToIncomeRatio;
  final int monthsOfData;
  final double currentSavingsRate;
  final String housingStatus;
  final String lifeStage;

  UserContext({
    required this.monthlyIncome,
    this.age = 35,
    this.region = 'US',
    this.familySize = 1,
    this.debtToIncomeRatio = 0.0,
    this.monthsOfData = 6,
    this.currentSavingsRate = 0.0,
    this.housingStatus = 'rent',
    this.lifeStage = 'single',
  });

  Map<String, dynamic> toJson() {
    return {
      'monthly_income': monthlyIncome,
      'age': age,
      'region': region,
      'family_size': familySize,
      'debt_to_income_ratio': debtToIncomeRatio,
      'months_of_data': monthsOfData,
      'current_savings_rate': currentSavingsRate,
      'housing_status': housingStatus,
      'life_stage': lifeStage,
    };
  }
}

class DynamicThresholds {
  final Map<String, dynamic> data;

  DynamicThresholds(this.data);

  // Budget allocation getters
  double get housingAllocation => _getDouble('housing', 0.30);
  double get foodAllocation => _getDouble('food', 0.12);
  double get transportAllocation => _getDouble('transport', 0.15);
  double get entertainmentAllocation => _getDouble('entertainment', 0.08);
  double get savingsAllocation => _getDouble('savings', 0.12);

  // Spending pattern getters
  double get smallPurchaseThreshold =>
      _getDouble('small_purchase_threshold', 20.0);
  double get mediumPurchaseThreshold =>
      _getDouble('medium_purchase_threshold', 100.0);
  double get largePurchaseThreshold =>
      _getDouble('large_purchase_threshold', 500.0);
  double get categoryConcentrationThreshold =>
      _getDouble('category_concentration_threshold', 0.5);
  double get monthlyVarianceThreshold =>
      _getDouble('monthly_variance_threshold', 0.3);
  double get impulseThreshold => _getDouble('impulse_buying_threshold', 0.6);

  // Health scoring getters
  Map<String, double> get gradeBoundaries => _getMap('grade_boundaries');
  Map<String, double> get componentExpectations =>
      _getMap('component_expectations');

  // Savings target getters
  double get targetSavingsRate => _getDouble('target_savings_rate', 0.12);
  double get minimumSavingsRate => _getDouble('minimum_savings_rate', 0.05);
  double get emergencyFundMonths => _getDouble('emergency_fund_months', 3.0);

  // Goal constraint getters
  double get maximumTimelineYears =>
      _getDouble('maximum_goal_timeline_years', 5.0);
  double get minimumMonthlyContribution =>
      _getDouble('minimum_monthly_contribution', 50.0);
  double get maximumMonthlyContribution =>
      _getDouble('maximum_monthly_contribution', 1000.0);

  // Behavioral trigger getters
  double get totalBudgetVarianceThreshold =>
      _getDouble('total_budget_variance_threshold', 1.1);
  double get weekendOverspendingMultiplier =>
      _getDouble('weekend_overspending_multiplier', 1.3);

  double _getDouble(String key, double defaultValue) {
    return (data[key] as num?)?.toDouble() ?? defaultValue;
  }

  Map<String, double> _getMap(String key) {
    final map = data[key] as Map<String, dynamic>?;
    if (map == null) return <String, double>{};

    return map.map((k, v) => MapEntry(k, (v as num).toDouble()));
  }
}

class HousingAffordabilityThresholds {
  final double recommendedRatio;
  final double maximumRatio;
  final double comfortableRatio;
  final double regionalAdjustmentFactor;

  HousingAffordabilityThresholds({
    required this.recommendedRatio,
    required this.maximumRatio,
    required this.comfortableRatio,
    required this.regionalAdjustmentFactor,
  });

  factory HousingAffordabilityThresholds.fromJson(Map<String, dynamic> json) {
    return HousingAffordabilityThresholds(
      recommendedRatio: (json['recommended_housing_ratio'] as num).toDouble(),
      maximumRatio: (json['maximum_housing_ratio'] as num).toDouble(),
      comfortableRatio: (json['comfortable_housing_ratio'] as num).toDouble(),
      regionalAdjustmentFactor:
          (json['regional_adjustment_factor'] as num).toDouble(),
    );
  }
}

class DynamicThresholdService {
  static final DynamicThresholdService _instance =
      DynamicThresholdService._internal();
  factory DynamicThresholdService() => _instance;
  DynamicThresholdService._internal();

  final ApiService _apiService = ApiService();

  // Cache for thresholds to avoid excessive API calls
  final Map<String, DynamicThresholds> _thresholdCache = {};
  final Map<String, HousingAffordabilityThresholds> _housingCache = {};
  final Duration _cacheExpiry = const Duration(hours: 6); // Cache for 6 hours
  DateTime? _lastCacheUpdate;

  /// Get dynamic thresholds for a specific type and user context
  Future<DynamicThresholds> getThresholds(
    ThresholdType type,
    UserContext userContext,
  ) async {
    final cacheKey =
        '${type.value}_${userContext.monthlyIncome}_${userContext.region}';

    // Check cache first
    if (_isValidCache() && _thresholdCache.containsKey(cacheKey)) {
      _logger.info('Returning cached thresholds for ${type.value}');
      return _thresholdCache[cacheKey]!;
    }

    try {
      _logger.info('Fetching dynamic thresholds for ${type.value}');

      final response = await _apiService.post(
        '/financial/dynamic-thresholds',
        data: {
          'threshold_type': type.value,
          'user_context': userContext.toJson(),
        },
      );

      if (response.statusCode == 200) {
        final thresholds =
            DynamicThresholds(response.data as Map<String, dynamic>);
        _thresholdCache[cacheKey] = thresholds;
        _lastCacheUpdate = DateTime.now();

        _logger.info('Successfully fetched dynamic thresholds');
        return thresholds;
      } else {
        throw Exception('Failed to fetch thresholds: ${response.statusCode}');
      }
    } catch (e) {
      _logger.severe('Error fetching dynamic thresholds: $e');

      // Return fallback thresholds based on type
      return _getFallbackThresholds(type, userContext);
    }
  }

  /// Get housing affordability thresholds
  Future<HousingAffordabilityThresholds> getHousingThresholds(
    UserContext userContext,
  ) async {
    final cacheKey =
        'housing_${userContext.monthlyIncome}_${userContext.region}';

    if (_isValidCache() && _housingCache.containsKey(cacheKey)) {
      return _housingCache[cacheKey]!;
    }

    try {
      final response = await _apiService.post(
        '/financial/housing-affordability',
        data: {'user_context': userContext.toJson()},
      );

      if (response.statusCode == 200) {
        final thresholds = HousingAffordabilityThresholds.fromJson(
            response.data as Map<String, dynamic>);
        _housingCache[cacheKey] = thresholds;
        return thresholds;
      } else {
        throw Exception(
            'Failed to fetch housing thresholds: ${response.statusCode}');
      }
    } catch (e) {
      _logger.severe('Error fetching housing thresholds: $e');
      return _getFallbackHousingThresholds(userContext);
    }
  }

  /// Get income-appropriate savings rate target
  Future<double> getSavingsRateTarget(
    double monthlyIncome, {
    int age = 35,
    String region = 'US',
    double debtToIncomeRatio = 0.0,
  }) async {
    final userContext = UserContext(
      monthlyIncome: monthlyIncome,
      age: age,
      region: region,
      debtToIncomeRatio: debtToIncomeRatio,
    );

    final thresholds =
        await getThresholds(ThresholdType.savingsTarget, userContext);
    return thresholds.targetSavingsRate;
  }

  /// Get income-appropriate small purchase threshold
  Future<double> getSmallPurchaseThreshold(
    double monthlyIncome, {
    String region = 'US',
  }) async {
    final userContext = UserContext(
      monthlyIncome: monthlyIncome,
      region: region,
    );

    final thresholds =
        await getThresholds(ThresholdType.spendingPattern, userContext);
    return thresholds.smallPurchaseThreshold;
  }

  /// Get emergency fund target months
  Future<double> getEmergencyFundTarget(
    double monthlyIncome, {
    int familySize = 1,
    String region = 'US',
  }) async {
    final userContext = UserContext(
      monthlyIncome: monthlyIncome,
      familySize: familySize,
      region: region,
    );

    final thresholds =
        await getThresholds(ThresholdType.savingsTarget, userContext);
    return thresholds.emergencyFundMonths;
  }

  /// Get goal timeline constraints
  Future<Map<String, double>> getGoalConstraints(
    double monthlyIncome,
    int age, {
    String region = 'US',
  }) async {
    final userContext = UserContext(
      monthlyIncome: monthlyIncome,
      age: age,
      region: region,
    );

    final thresholds =
        await getThresholds(ThresholdType.goalConstraint, userContext);

    return {
      'maximum_timeline_years': thresholds.maximumTimelineYears,
      'minimum_monthly_contribution': thresholds.minimumMonthlyContribution,
      'maximum_monthly_contribution': thresholds.maximumMonthlyContribution,
    };
  }

  /// Get budget allocation ratios
  Future<Map<String, double>> getBudgetAllocations(
    double monthlyIncome, {
    int age = 35,
    String region = 'US',
    int familySize = 1,
  }) async {
    final userContext = UserContext(
      monthlyIncome: monthlyIncome,
      age: age,
      region: region,
      familySize: familySize,
    );

    final thresholds =
        await getThresholds(ThresholdType.budgetAllocation, userContext);

    return {
      'housing': thresholds.housingAllocation,
      'food': thresholds.foodAllocation,
      'transport': thresholds.transportAllocation,
      'entertainment': thresholds.entertainmentAllocation,
      'savings': thresholds.savingsAllocation,
    };
  }

  /// Clear the cache (useful for testing or when user data changes significantly)
  void clearCache() {
    _thresholdCache.clear();
    _housingCache.clear();
    _lastCacheUpdate = null;
    _logger.info('Threshold cache cleared');
  }

  bool _isValidCache() {
    if (_lastCacheUpdate == null) return false;
    return DateTime.now().difference(_lastCacheUpdate!) < _cacheExpiry;
  }

  /// Fallback thresholds when API is unavailable
  DynamicThresholds _getFallbackThresholds(
      ThresholdType type, UserContext userContext) {
    _logger.warning('Using fallback thresholds for ${type.value}');

    switch (type) {
      case ThresholdType.budgetAllocation:
        return DynamicThresholds({
          'housing': userContext.monthlyIncome < 3000
              ? 0.40
              : userContext.monthlyIncome < 8000
                  ? 0.30
                  : 0.25,
          'food': userContext.monthlyIncome < 3000 ? 0.15 : 0.12,
          'transport': 0.15,
          'entertainment': userContext.monthlyIncome < 3000 ? 0.05 : 0.08,
          'savings': userContext.monthlyIncome < 3000 ? 0.05 : 0.12,
        });

      case ThresholdType.spendingPattern:
        return DynamicThresholds({
          'small_purchase_threshold':
              (userContext.monthlyIncome * 0.005).clamp(5.0, 100.0),
          'medium_purchase_threshold': userContext.monthlyIncome * 0.02,
          'large_purchase_threshold': userContext.monthlyIncome * 0.10,
          'category_concentration_threshold': 0.6,
          'monthly_variance_threshold': 0.3,
          'impulse_buying_threshold': 0.6,
        });

      case ThresholdType.savingsTarget:
        final baseSavingsRate = userContext.monthlyIncome < 3000
            ? 0.05
            : userContext.monthlyIncome < 8000
                ? 0.12
                : 0.18;
        return DynamicThresholds({
          'target_savings_rate': baseSavingsRate,
          'minimum_savings_rate': baseSavingsRate * 0.5,
          'emergency_fund_months': userContext.familySize > 1 ? 4.0 : 3.0,
        });

      case ThresholdType.goalConstraint:
        return DynamicThresholds({
          'maximum_goal_timeline_years': userContext.age < 30 ? 7.0 : 5.0,
          'minimum_monthly_contribution': userContext.monthlyIncome * 0.05,
          'maximum_monthly_contribution': userContext.monthlyIncome * 0.25,
        });

      default:
        return DynamicThresholds({});
    }
  }

  HousingAffordabilityThresholds _getFallbackHousingThresholds(
      UserContext userContext) {
    final baseRatio = userContext.monthlyIncome < 3000
        ? 0.40
        : userContext.monthlyIncome < 8000
            ? 0.30
            : 0.25;

    return HousingAffordabilityThresholds(
      recommendedRatio: baseRatio,
      maximumRatio: baseRatio * 1.25,
      comfortableRatio: baseRatio * 0.85,
      regionalAdjustmentFactor: 1.0,
    );
  }
}

/// Convenience functions for common threshold requests
class ThresholdHelper {
  static final DynamicThresholdService _service = DynamicThresholdService();

  /// Get maximum savings rate for income tier (replaces hardcoded values)
  static Future<double> getMaxSavingsRate(double monthlyIncome) async {
    final constraints = await _service.getGoalConstraints(monthlyIncome, 35);
    return constraints['maximum_monthly_contribution']! / monthlyIncome;
  }

  /// Get income-appropriate goal timeline
  static Future<double> getMaxGoalTimelineYears(
      double monthlyIncome, int age) async {
    final constraints = await _service.getGoalConstraints(monthlyIncome, age);
    return constraints['maximum_timeline_years']!;
  }

  /// Replace hardcoded small purchase amounts
  static Future<double> getIncomeRelativeAmount(
      double monthlyIncome, double percentage) async {
    final threshold = await _service.getSmallPurchaseThreshold(monthlyIncome);
    return threshold * percentage;
  }

  /// Check if user is near housing affordability limits
  static Future<bool> isHousingAffordable(
    double monthlyIncome,
    double monthlyHousingCost, {
    String region = 'US',
  }) async {
    final userContext =
        UserContext(monthlyIncome: monthlyIncome, region: region);
    final thresholds = await _service.getHousingThresholds(userContext);

    final currentRatio = monthlyHousingCost / monthlyIncome;
    return currentRatio <= thresholds.recommendedRatio;
  }
}

import 'dart:math';
import '../models/budget_intelligence_models.dart';
import 'country_profiles_service.dart';

/// Enhanced income classification with smooth tier transitions and intelligent blending
class EnhancedIncomeService {
  static final EnhancedIncomeService _instance = EnhancedIncomeService._internal();
  factory EnhancedIncomeService() => _instance;
  EnhancedIncomeService._internal();

  final _countryProfilesService = CountryProfilesService();

  /// Transition zone width (percentage of threshold)
  static const double _transitionZoneWidth = 0.15; // 15% transition zone

  /// Enhanced income classification with geographic awareness
  Future<IncomeClassificationResult> classifyIncomeEnhanced(
    double monthlyIncome, {
    String? countryCode,
    String? stateCode,
  }) async {
    try {
      // Get regional data for geographic-aware classification
      final regionalData = await _getRegionalIncomeData(countryCode, stateCode);
      
      // Use regional thresholds if available, otherwise default
      final tierThresholds = regionalData?.tierThresholds ?? _getDefaultTierThresholds();
      
      // Classify with smooth transitions
      return _classifyWithTransitions(monthlyIncome, tierThresholds, regionalData);
    } catch (e) {
      // Fallback to basic classification
      return _createFallbackClassification(monthlyIncome);
    }
  }

  /// Calculate blended budget parameters based on classification
  Map<String, double> calculateBlendedBudgetParameters(IncomeClassificationResult classification) {
    if (!classification.isInTransition) {
      return _getBudgetParametersForTier(classification.primaryTier);
    }

    // Blend parameters from both tiers
    final primaryParams = _getBudgetParametersForTier(classification.primaryTier);
    final secondaryParams = _getBudgetParametersForTier(classification.secondaryTier!);
    
    return {
      'fixedCommitmentRatio': primaryParams['fixedCommitmentRatio']! * classification.primaryWeight +
                             secondaryParams['fixedCommitmentRatio']! * classification.secondaryWeight,
      'savingsTargetRatio': primaryParams['savingsTargetRatio']! * classification.primaryWeight +
                           secondaryParams['savingsTargetRatio']! * classification.secondaryWeight,
      'redistributionBuffer': primaryParams['redistributionBuffer']! * classification.primaryWeight +
                             secondaryParams['redistributionBuffer']! * classification.secondaryWeight,
    };
  }

  /// Generate human-readable explanation of tier classification
  String generateTierExplanation(IncomeClassificationResult classification) {
    if (!classification.isInTransition) {
      return 'Your income places you in the ${_tierToString(classification.primaryTier)} tier';
    } else {
      return 'Your income is transitioning between ${_tierToString(classification.secondaryTier!)} and ${_tierToString(classification.primaryTier)} tiers (${(classification.primaryWeight * 100).round()}% ${_tierToString(classification.primaryTier)})';
    }
  }

  /// Classify income with smooth tier transitions
  IncomeClassificationResult _classifyWithTransitions(
    double monthlyIncome,
    Map<IncomeTier, double> tierThresholds,
    RegionalIncomeData? regionalData,
  ) {
    // Sort thresholds to identify boundaries
    final sortedThresholds = tierThresholds.entries.toList()
      ..sort((a, b) => a.value.compareTo(b.value));

    // Find base tier
    IncomeTier baseTier = IncomeTier.low;
    for (final entry in sortedThresholds) {
      if (monthlyIncome >= entry.value) {
        baseTier = entry.key;
      } else {
        break;
      }
    }

    // Check for transition zones
    for (int i = 0; i < sortedThresholds.length; i++) {
      final threshold = sortedThresholds[i].value;
      final tier = sortedThresholds[i].key;
      
      final lowerBound = threshold * (1.0 - _transitionZoneWidth);
      final upperBound = threshold * (1.0 + _transitionZoneWidth);
      
      if (monthlyIncome >= lowerBound && monthlyIncome <= upperBound) {
        // In transition zone
        final transitionFactor = (monthlyIncome - lowerBound) / (upperBound - lowerBound);
        final smoothFactor = _sigmoidTransition(transitionFactor);
        
        final lowerTier = i > 0 ? sortedThresholds[i - 1].key : IncomeTier.low;
        final upperTier = tier;
        
        return IncomeClassificationResult(
          primaryTier: smoothFactor > 0.5 ? upperTier : lowerTier,
          secondaryTier: smoothFactor > 0.5 ? lowerTier : upperTier,
          primaryWeight: smoothFactor > 0.5 ? smoothFactor : 1.0 - smoothFactor,
          secondaryWeight: smoothFactor > 0.5 ? 1.0 - smoothFactor : smoothFactor,
          transitionFactor: smoothFactor,
          isInTransition: true,
          metadata: {
            'monthlyIncome': monthlyIncome,
            'threshold': threshold,
            'transitionZone': '${_tierToString(lowerTier)}_to_${_tierToString(upperTier)}',
            'regionalData': regionalData?.regionId ?? 'default',
          },
        );
      }
    }
    
    // Not in transition zone
    return IncomeClassificationResult(
      primaryTier: baseTier,
      primaryWeight: 1.0,
      secondaryWeight: 0.0,
      transitionFactor: 0.0,
      isInTransition: false,
      metadata: {
        'monthlyIncome': monthlyIncome,
        'solidTier': true,
        'regionalData': regionalData?.regionId ?? 'default',
      },
    );
  }

  /// Create fallback classification for error cases
  IncomeClassificationResult _createFallbackClassification(double monthlyIncome) {
    // Simple tier classification without transitions
    IncomeTier tier;
    if (monthlyIncome < 3000) {
      tier = IncomeTier.low;
    } else if (monthlyIncome < 4500) {
      tier = IncomeTier.lowerMiddle;
    } else if (monthlyIncome < 7000) {
      tier = IncomeTier.middle;
    } else if (monthlyIncome < 12000) {
      tier = IncomeTier.upperMiddle;
    } else {
      tier = IncomeTier.high;
    }

    return IncomeClassificationResult(
      primaryTier: tier,
      primaryWeight: 1.0,
      secondaryWeight: 0.0,
      transitionFactor: 0.0,
      isInTransition: false,
      metadata: {
        'monthlyIncome': monthlyIncome,
        'fallback': true,
      },
    );
  }

  /// Get regional income data from CountryProfilesService
  Future<RegionalIncomeData?> _getRegionalIncomeData(String? countryCode, String? stateCode) async {
    if (countryCode == null) return null;

    try {
      // Get real thresholds from CountryProfilesService
      final thresholdsMap = _countryProfilesService.getIncomeThresholds(
        countryCode,
        stateCode: stateCode,
      );

      // Convert string keys to IncomeTier enum
      final tierThresholds = <IncomeTier, double>{
        IncomeTier.low: 0.0,
        IncomeTier.lowerMiddle: _countryProfilesService.annualToMonthly(thresholdsMap['low'] ?? 36000.0),
        IncomeTier.middle: _countryProfilesService.annualToMonthly(thresholdsMap['lower_middle'] ?? 57600.0),
        IncomeTier.upperMiddle: _countryProfilesService.annualToMonthly(thresholdsMap['middle'] ?? 86400.0),
        IncomeTier.high: _countryProfilesService.annualToMonthly(thresholdsMap['upper_middle'] ?? 144000.0),
      };

      // Calculate median income from thresholds
      final medianIncome = tierThresholds[IncomeTier.middle] ?? 4800.0;

      return RegionalIncomeData(
        regionId: '${countryCode}_${stateCode ?? 'default'}',
        regionName: _countryProfilesService.getCountryName(countryCode),
        tierThresholds: tierThresholds,
        medianIncome: medianIncome,
        costOfLivingAdjustments: <String, dynamic>{
          'currency': _countryProfilesService.getCurrency(countryCode),
          'hasSubregions': _countryProfilesService.hasSubregions(countryCode),
        },
        lastUpdated: DateTime.now(),
      );
    } catch (e) {
      return null;
    }
  }

  /// Get default tier thresholds
  Map<IncomeTier, double> _getDefaultTierThresholds() {
    return <IncomeTier, double>{
      IncomeTier.low: 0.0,
      IncomeTier.lowerMiddle: 3000.0,
      IncomeTier.middle: 4500.0,
      IncomeTier.upperMiddle: 7000.0,
      IncomeTier.high: 12000.0,
    };
  }

  /// Get budget parameters for a specific tier
  Map<String, double> _getBudgetParametersForTier(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return <String, double>{
          'fixedCommitmentRatio': 0.65,
          'savingsTargetRatio': 0.05,
          'redistributionBuffer': 0.20,
        };
      case IncomeTier.lowerMiddle:
        return <String, double>{
          'fixedCommitmentRatio': 0.58,
          'savingsTargetRatio': 0.08,
          'redistributionBuffer': 0.18,
        };
      case IncomeTier.middle:
        return <String, double>{
          'fixedCommitmentRatio': 0.52,
          'savingsTargetRatio': 0.15,
          'redistributionBuffer': 0.15,
        };
      case IncomeTier.upperMiddle:
        return <String, double>{
          'fixedCommitmentRatio': 0.45,
          'savingsTargetRatio': 0.22,
          'redistributionBuffer': 0.12,
        };
      case IncomeTier.high:
        return <String, double>{
          'fixedCommitmentRatio': 0.40,
          'savingsTargetRatio': 0.30,
          'redistributionBuffer': 0.10,
        };
    }
  }

  /// Sigmoid transition function for smooth blending
  double _sigmoidTransition(double x) {
    return 1.0 / (1.0 + exp(-6.0 * (x - 0.5)));
  }

  /// Convert tier enum to string
  String _tierToString(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'Low Income';
      case IncomeTier.lowerMiddle:
        return 'Lower Middle';
      case IncomeTier.middle:
        return 'Middle Income';
      case IncomeTier.upperMiddle:
        return 'Upper Middle';
      case IncomeTier.high:
        return 'High Income';
    }
  }
}
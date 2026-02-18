import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import 'country_profiles_service.dart';
import 'location_service.dart';

/// Income classification enum - matches backend 5-level system
enum IncomeTier {
  low, // < $3,000
  lowerMiddle, // $3,000 - $4,500
  middle, // $4,500 - $7,000
  upperMiddle, // $7,000 - $12,000
  high, // > $12,000
}

/// Income classification service for MITA
/// Handles income band classification, peer comparison, and income-based features
class IncomeService {
  // Singleton pattern
  static final IncomeService _instance = IncomeService._internal();
  factory IncomeService() => _instance;
  IncomeService._internal();

  // Services
  final CountryProfilesService _countryService = CountryProfilesService();
  final LocationService _locationService = LocationService();

  /// Income band thresholds (monthly income) - matches backend 5-level system
  /// UPDATED: Economically justified thresholds based on US Census data
  static const double lowThreshold = 3000.0; // $36K annually
  static const double lowerMiddleThreshold = 4800.0; // $57.6K annually
  static const double middleThreshold = 7200.0; // $86.4K annually
  static const double upperMiddleThreshold = 12000.0; // $144K annually

  /// Classify income into 5 tiers (legacy method - uses default US thresholds)
  IncomeTier classifyIncome(double monthlyIncome) {
    if (monthlyIncome < lowThreshold) {
      return IncomeTier.low;
    } else if (monthlyIncome < lowerMiddleThreshold) {
      return IncomeTier.lowerMiddle;
    } else if (monthlyIncome < middleThreshold) {
      return IncomeTier.middle;
    } else if (monthlyIncome < upperMiddleThreshold) {
      return IncomeTier.upperMiddle;
    } else {
      return IncomeTier.high;
    }
  }

  /// Classify income based on user's location (recommended method)
  Future<IncomeTier> classifyIncomeByLocation(double monthlyIncome) async {
    final location = await _locationService.getUserLocation();
    final countryCode = location['country'] ?? 'US';
    final stateCode = location['state'];

    return classifyIncomeForLocation(monthlyIncome, countryCode,
        stateCode: stateCode);
  }

  /// Classify income for specific location
  IncomeTier classifyIncomeForLocation(double monthlyIncome, String countryCode,
      {String? stateCode}) {
    final thresholds =
        _countryService.getIncomeThresholds(countryCode, stateCode: stateCode);
    final annualIncome = monthlyIncome * 12;

    if (annualIncome <= thresholds['low']!) {
      return IncomeTier.low;
    } else if (annualIncome <= thresholds['lower_middle']!) {
      return IncomeTier.lowerMiddle;
    } else if (annualIncome <= thresholds['middle']!) {
      return IncomeTier.middle;
    } else if (annualIncome <= thresholds['upper_middle']!) {
      return IncomeTier.upperMiddle;
    } else {
      return IncomeTier.high;
    }
  }

  /// Get income tier display name (Enhanced with behavioral insights)
  String getIncomeTierName(IncomeTier tier, {bool useOptimizedNames = true}) {
    if (useOptimizedNames) {
      // Optimized names based on behavioral analysis
      switch (tier) {
        case IncomeTier.low:
          return 'Foundation Builder';
        case IncomeTier.lowerMiddle:
          return 'Momentum Builder';
        case IncomeTier.middle:
          return 'Strategic Achiever';
        case IncomeTier.upperMiddle:
          return 'Wealth Accelerator';
        case IncomeTier.high:
          return 'Legacy Builder';
      }
    } else {
      // Original names for compatibility
      switch (tier) {
        case IncomeTier.low:
          return 'Essential Earner';
        case IncomeTier.lowerMiddle:
          return 'Rising Saver';
        case IncomeTier.middle:
          return 'Growing Professional';
        case IncomeTier.upperMiddle:
          return 'Established Professional';
        case IncomeTier.high:
          return 'High Achiever';
      }
    }
  }

  /// Get income tier description (Enhanced with behavioral insights)
  String getIncomeTierDescription(IncomeTier tier,
      {bool useOptimizedDescriptions = true}) {
    if (useOptimizedDescriptions) {
      // Optimized descriptions based on behavioral analysis
      switch (tier) {
        case IncomeTier.low:
          return 'Build your financial foundation through daily progress and smart essentials management';
        case IncomeTier.lowerMiddle:
          return 'Create momentum through systematic saving and strategic growth opportunities';
        case IncomeTier.middle:
          return 'Achieve strategic financial goals through balanced optimization and smart investments';
        case IncomeTier.upperMiddle:
          return 'Accelerate wealth building through sophisticated strategies and diversified growth';
        case IncomeTier.high:
          return 'Build lasting legacy through advanced wealth strategies and generational planning';
      }
    } else {
      // Original descriptions for compatibility
      switch (tier) {
        case IncomeTier.low:
          return 'Focus on essential spending and smart budgeting';
        case IncomeTier.lowerMiddle:
          return 'Build emergency fund while growing your income';
        case IncomeTier.middle:
          return 'Balance growth opportunities with financial stability';
        case IncomeTier.upperMiddle:
          return 'Accelerate wealth building and investment growth';
        case IncomeTier.high:
          return 'Optimize investments and advanced wealth strategies';
      }
    }
  }

  /// Get income range string for display (updated with economically accurate thresholds)
  String getIncomeRangeString(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'Under \$3,000/month';
      case IncomeTier.lowerMiddle:
        return '\$3,000 - \$4,800/month';
      case IncomeTier.middle:
        return '\$4,800 - \$7,200/month';
      case IncomeTier.upperMiddle:
        return '\$7,200 - \$12,000/month';
      case IncomeTier.high:
        return 'Over \$12,000/month';
    }
  }

  /// Get income range string for display based on user's location
  Future<String> getIncomeRangeStringByLocation(IncomeTier tier) async {
    final location = await _locationService.getUserLocation();
    final countryCode = location['country'] ?? 'US';
    final stateCode = location['state'];

    return getIncomeRangeStringForLocation(tier, countryCode,
        stateCode: stateCode);
  }

  /// Get income range string for specific location
  String getIncomeRangeStringForLocation(IncomeTier tier, String countryCode,
      {String? stateCode}) {
    final thresholds =
        _countryService.getIncomeThresholds(countryCode, stateCode: stateCode);
    final currency = _countryService.getCurrency(countryCode);

    final lowMonthly = (thresholds['low']! / 12).round();
    final lowerMiddleMonthly = (thresholds['lower_middle']! / 12).round();
    final middleMonthly = (thresholds['middle']! / 12).round();
    final upperMiddleMonthly = (thresholds['upper_middle']! / 12).round();

    switch (tier) {
      case IncomeTier.low:
        return 'Under ${_formatCurrency(lowMonthly.toDouble(), currency)}/month';
      case IncomeTier.lowerMiddle:
        return '${_formatCurrency(lowMonthly.toDouble(), currency)} - ${_formatCurrency(lowerMiddleMonthly.toDouble(), currency)}/month';
      case IncomeTier.middle:
        return '${_formatCurrency(lowerMiddleMonthly.toDouble(), currency)} - ${_formatCurrency(middleMonthly.toDouble(), currency)}/month';
      case IncomeTier.upperMiddle:
        return '${_formatCurrency(middleMonthly.toDouble(), currency)} - ${_formatCurrency(upperMiddleMonthly.toDouble(), currency)}/month';
      case IncomeTier.high:
        return 'Over ${_formatCurrency(upperMiddleMonthly.toDouble(), currency)}/month';
    }
  }

  /// Format currency for display
  String _formatCurrency(double amount, String currency) {
    final formattedAmount = amount >= 1000
        ? '${(amount / 1000).toStringAsFixed(0)}K'
        : amount.toStringAsFixed(0);

    switch (currency) {
      case 'USD':
        return '\$$formattedAmount';
      case 'CAD':
        return 'C\$$formattedAmount';
      case 'GBP':
        return '£$formattedAmount';
      case 'EUR':
        return '€$formattedAmount';
      case 'BGN':
        return '$formattedAmount лв';
      case 'JPY':
        return '¥$formattedAmount';
      default:
        return '$formattedAmount $currency';
    }
  }

  /// Get primary color for income tier (Enhanced with behavioral color psychology)
  Color getIncomeTierPrimaryColor(IncomeTier tier,
      {bool useBehavioralColors = true}) {
    if (useBehavioralColors) {
      // Behavioral color psychology optimized colors
      switch (tier) {
        case IncomeTier.low:
          return AppColors.success; // Green - Growth, stability, hope
        case IncomeTier.lowerMiddle:
          return AppColors.info; // Blue - Trust, progress, reliability
        case IncomeTier.middle:
          return AppColors
              .categoryEntertainment; // Purple - Sophistication, strategy
        case IncomeTier.upperMiddle:
          return AppColors.warning; // Gold - Achievement, value, success
        case IncomeTier.high:
          return AppColors.primary; // Deep Blue - Wisdom, legacy, permanence
      }
    } else {
      // Original colors for compatibility
      switch (tier) {
        case IncomeTier.low:
          return AppColors.success; // Green - Growth mindset
        case IncomeTier.lowerMiddle:
          return AppColors.chart7; // Cyan - Rising opportunities
        case IncomeTier.middle:
          return AppColors.info; // Blue - Professional
        case IncomeTier.upperMiddle:
          return AppColors.categoryEducation; // Deep Purple - Established
        case IncomeTier.high:
          return AppColors.categoryEntertainment; // Purple - Premium
      }
    }
  }

  /// Get secondary color for income tier
  Color getIncomeTierSecondaryColor(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return AppColors.successLight; // Light green
      case IncomeTier.lowerMiddle:
        return AppColors.info.withValues(alpha: 0.1); // Light cyan
      case IncomeTier.middle:
        return AppColors.info.withValues(alpha: 0.15); // Light blue
      case IncomeTier.upperMiddle:
        return AppColors.categoryEducation
            .withValues(alpha: 0.1); // Light deep purple
      case IncomeTier.high:
        return AppColors.categoryEntertainment
            .withValues(alpha: 0.1); // Light purple
    }
  }

  /// Get icon for income tier
  IconData getIncomeTierIcon(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return Icons.trending_up_rounded;
      case IncomeTier.lowerMiddle:
        return Icons.savings_rounded;
      case IncomeTier.middle:
        return Icons.business_center_rounded;
      case IncomeTier.upperMiddle:
        return Icons.account_balance_rounded;
      case IncomeTier.high:
        return Icons.diamond_rounded;
    }
  }

  /// Calculate percentage of income for spending amount
  double getIncomePercentage(double amount, double monthlyIncome) {
    if (monthlyIncome <= 0) return 0.0;
    return (amount / monthlyIncome) * 100;
  }

  /// Get spending percentage category
  String getSpendingPercentageCategory(double percentage) {
    if (percentage < 5) return 'Minimal';
    if (percentage < 15) return 'Low';
    if (percentage < 30) return 'Moderate';
    if (percentage < 50) return 'High';
    return 'Significant';
  }

  /// Get default budget weights by income tier
  Map<String, double> getDefaultBudgetWeights(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return {
          'housing': 0.40, // Higher for essential housing
          'food': 0.15, // Budget-conscious food spending
          'transportation': 0.15,
          'utilities': 0.10,
          'healthcare': 0.08,
          'entertainment': 0.05, // Lower entertainment budget
          'savings': 0.07, // Conservative savings goal
        };
      case IncomeTier.lowerMiddle:
        return {
          'housing': 0.38, // Slightly lower housing costs
          'food': 0.14,
          'transportation': 0.15,
          'utilities': 0.09,
          'healthcare': 0.07,
          'entertainment': 0.06,
          'savings': 0.11, // Building emergency fund
        };
      case IncomeTier.middle:
        return {
          'housing': 0.35, // Balanced housing costs
          'food': 0.12,
          'transportation': 0.15,
          'utilities': 0.08,
          'healthcare': 0.06,
          'entertainment': 0.08,
          'savings': 0.16, // Moderate savings goal
        };
      case IncomeTier.upperMiddle:
        return {
          'housing': 0.32, // Lower housing percentage
          'food': 0.11,
          'transportation': 0.13,
          'utilities': 0.06,
          'healthcare': 0.05,
          'entertainment': 0.09,
          'savings': 0.24, // Higher savings rate
        };
      case IncomeTier.high:
        return {
          'housing': 0.30, // Lower percentage for housing
          'food': 0.10,
          'transportation': 0.12,
          'utilities': 0.05,
          'healthcare': 0.05,
          'entertainment': 0.10,
          'savings': 0.28, // Aggressive savings goal
        };
    }
  }

  /// Get peer comparison message
  String getPeerComparisonMessage(IncomeTier tier, String category,
      double userSpending, double peerAverage) {
    final tierName = getIncomeTierName(tier);
    final difference = ((userSpending - peerAverage) / peerAverage * 100).abs();
    final isHigher = userSpending > peerAverage;

    if (difference < 10) {
      return 'Your $category spending is similar to other ${tierName}s';
    } else if (isHigher) {
      return 'You spend ${difference.toStringAsFixed(0)}% more on $category than other ${tierName}s';
    } else {
      return 'You spend ${difference.toStringAsFixed(0)}% less on $category than other ${tierName}s';
    }
  }

  /// Get income-appropriate financial tips
  List<String> getFinancialTips(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return [
          'Focus on the 50/30/20 rule: 50% needs, 30% wants, 20% savings',
          'Look for free entertainment options in your community',
          'Cook meals at home to reduce food expenses',
          'Consider generic brands for everyday items',
          'Build an emergency fund, even if it\'s \$5-10 per week',
          'Use apps to find discounts and cashback opportunities',
        ];
      case IncomeTier.lowerMiddle:
        return [
          'Aim for a 10-15% savings rate as your income grows',
          'Build your emergency fund to \$1,000 first',
          'Start learning about basic investing concepts',
          'Look for opportunities to increase your income',
          'Consider community college courses for skill development',
          'Track all expenses to identify saving opportunities',
        ];
      case IncomeTier.middle:
        return [
          'Increase your savings rate to 15-20% of income',
          'Consider investing in low-cost index funds',
          'Negotiate better rates for insurance and utilities',
          'Look into employer 401(k) matching opportunities',
          'Set up automatic transfers to savings accounts',
          'Consider a side hustle to boost income',
        ];
      case IncomeTier.upperMiddle:
        return [
          'Aim for a 20-25% savings rate',
          'Maximize employer 401(k) matching',
          'Consider opening a Roth IRA',
          'Start building a diversified investment portfolio',
          'Look into tax-loss harvesting strategies',
          'Consider hiring a fee-only financial advisor',
        ];
      case IncomeTier.high:
        return [
          'Aim for a 25-30% savings rate',
          'Diversify investments across asset classes',
          'Consider tax-advantaged accounts (IRA, 401k)',
          'Look into real estate investment opportunities',
          'Work with a financial advisor for complex planning',
          'Focus on tax optimization strategies',
        ];
    }
  }

  /// Get goal suggestions based on income tier
  List<Map<String, dynamic>> getGoalSuggestions(
      IncomeTier tier, double monthlyIncome) {
    switch (tier) {
      case IncomeTier.low:
        return [
          {
            'title': 'Emergency Fund',
            'description': 'Build a \$500 emergency fund',
            'target_amount': 500.0,
            'monthly_target': monthlyIncome * 0.05,
            'priority': 'high',
            'icon': Icons.security_rounded,
          },
          {
            'title': 'Debt Reduction',
            'description': 'Pay down high-interest debt',
            'target_amount': monthlyIncome * 2,
            'monthly_target': monthlyIncome * 0.10,
            'priority': 'high',
            'icon': Icons.trending_down_rounded,
          },
          {
            'title': 'Skill Development',
            'description': 'Invest in career growth',
            'target_amount': 200.0,
            'monthly_target': 50.0,
            'priority': 'medium',
            'icon': Icons.school_rounded,
          },
        ];
      case IncomeTier.lowerMiddle:
        return [
          {
            'title': 'Emergency Fund',
            'description': 'Build a \$1,000 emergency fund',
            'target_amount': 1000.0,
            'monthly_target': monthlyIncome * 0.07,
            'priority': 'high',
            'icon': Icons.security_rounded,
          },
          {
            'title': 'Debt Payoff',
            'description': 'Eliminate high-interest debt',
            'target_amount': monthlyIncome * 3,
            'monthly_target': monthlyIncome * 0.12,
            'priority': 'high',
            'icon': Icons.trending_down_rounded,
          },
          {
            'title': 'Career Investment',
            'description': 'Certification or skill upgrade',
            'target_amount': 1000.0,
            'monthly_target': monthlyIncome * 0.05,
            'priority': 'medium',
            'icon': Icons.school_rounded,
          },
        ];
      case IncomeTier.middle:
        return [
          {
            'title': 'Emergency Fund',
            'description': 'Build 3-month emergency fund',
            'target_amount': monthlyIncome * 3,
            'monthly_target': monthlyIncome * 0.08,
            'priority': 'high',
            'icon': Icons.security_rounded,
          },
          {
            'title': 'Investment Portfolio',
            'description': 'Start investing for the future',
            'target_amount': monthlyIncome * 6,
            'monthly_target': monthlyIncome * 0.15,
            'priority': 'high',
            'icon': Icons.trending_up_rounded,
          },
          {
            'title': 'Home Down Payment',
            'description': 'Save for property purchase',
            'target_amount': 25000.0,
            'monthly_target': monthlyIncome * 0.10,
            'priority': 'medium',
            'icon': Icons.home_rounded,
          },
        ];
      case IncomeTier.upperMiddle:
        return [
          {
            'title': 'Investment Growth',
            'description': 'Build substantial investment portfolio',
            'target_amount': monthlyIncome * 10,
            'monthly_target': monthlyIncome * 0.18,
            'priority': 'high',
            'icon': Icons.trending_up_rounded,
          },
          {
            'title': 'Property Investment',
            'description': 'Down payment for investment property',
            'target_amount': 50000.0,
            'monthly_target': monthlyIncome * 0.12,
            'priority': 'medium',
            'icon': Icons.home_work_rounded,
          },
          {
            'title': 'Retirement Acceleration',
            'description': 'Max out retirement accounts',
            'target_amount': 30000.0,
            'monthly_target': 2500.0,
            'priority': 'high',
            'icon': Icons.account_balance_rounded,
          },
        ];
      case IncomeTier.high:
        return [
          {
            'title': 'Investment Growth',
            'description': 'Aggressive investment strategy',
            'target_amount': monthlyIncome * 12,
            'monthly_target': monthlyIncome * 0.20,
            'priority': 'high',
            'icon': Icons.trending_up_rounded,
          },
          {
            'title': 'Real Estate',
            'description': 'Investment property fund',
            'target_amount': 100000.0,
            'monthly_target': monthlyIncome * 0.15,
            'priority': 'medium',
            'icon': Icons.business_rounded,
          },
          {
            'title': 'Tax Optimization',
            'description': 'Maximize tax-advantaged accounts',
            'target_amount': 22500.0, // 401k max contribution
            'monthly_target': 1875.0,
            'priority': 'high',
            'icon': Icons.account_balance_rounded,
          },
        ];
    }
  }

  /// Get budget template based on income tier
  Map<String, dynamic> getBudgetTemplate(
      IncomeTier tier, double monthlyIncome) {
    final weights = getDefaultBudgetWeights(tier);
    final template = <String, dynamic>{};

    weights.forEach((category, weight) {
      template[category] = (monthlyIncome * weight).round().toDouble();
    });

    return {
      'monthly_income': monthlyIncome,
      'income_tier': tier.toString(),
      'allocations': template,
      'total_allocated':
          template.values.fold<double>(0, (sum, amount) => sum + amount),
      'remaining': monthlyIncome -
          template.values.fold<double>(0, (sum, amount) => sum + amount),
    };
  }

  /// Get personalized onboarding message
  String getOnboardingMessage(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'Every dollar counts! Let\'s create a budget that helps you grow your financial foundation step by step.';
      case IncomeTier.lowerMiddle:
        return 'You\'re building momentum! Let\'s create a budget that accelerates your path to financial stability.';
      case IncomeTier.middle:
        return 'You\'re in a great position to build wealth! Let\'s optimize your budget for both current needs and future growth.';
      case IncomeTier.upperMiddle:
        return 'Your income is strong! Let\'s focus on advanced strategies to accelerate your wealth building journey.';
      case IncomeTier.high:
        return 'With your strong income, let\'s focus on maximizing your wealth-building potential and smart tax strategies.';
    }
  }

  /// Get spending insights based on income context
  Map<String, dynamic> getSpendingInsights(
      double amount, String category, double monthlyIncome) {
    final tier = classifyIncome(monthlyIncome);
    final percentage = getIncomePercentage(amount, monthlyIncome);
    final weights = getDefaultBudgetWeights(tier);
    final recommendedAmount =
        monthlyIncome * (weights[category.toLowerCase()] ?? 0.1);

    return {
      'amount': amount,
      'category': category,
      'monthly_income': monthlyIncome,
      'income_tier': tier.toString(),
      'percentage_of_income': percentage,
      'percentage_category': getSpendingPercentageCategory(percentage),
      'recommended_amount': recommendedAmount,
      'vs_recommended': amount - recommendedAmount,
      'is_over_recommended': amount > recommendedAmount,
      'tier_color': getIncomeTierPrimaryColor(tier),
    };
  }

  // ===========================================================================
  // ENHANCED BEHAVIORAL ECONOMICS METHODS
  // ===========================================================================

  /// Get behavioral spending patterns for income tier
  Map<String, dynamic> getBehavioralSpendingPatterns(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return {
          'spending_velocity': 'high', // Weekly/bi-weekly cycles
          'decision_time': 'immediate', // Quick decisions due to necessity
          'risk_tolerance': 'very_low',
          'planning_horizon': 'immediate_to_monthly',
          'primary_stressors': ['basic_needs_uncertainty', 'paycheck_anxiety'],
          'mental_accounting_buckets': ['essential', 'non_essential'],
          'nudge_responsiveness': {
            'loss_framing': 0.9,
            'scarcity_framing': 0.8,
            'social_proof': 0.7,
            'automated_savings': 0.6,
          },
          'optimal_budget_frequency': 'daily',
          'celebration_frequency': 'weekly',
        };
      case IncomeTier.lowerMiddle:
        return {
          'spending_velocity': 'moderate',
          'decision_time': 'hours_to_days',
          'risk_tolerance': 'low_moderate',
          'planning_horizon': 'monthly_to_quarterly',
          'primary_stressors': [
            'lifestyle_inflation',
            'emergency_fund_anxiety'
          ],
          'mental_accounting_buckets': [
            'needs',
            'wants',
            'emergency',
            'goals',
            'future'
          ],
          'nudge_responsiveness': {
            'progress_tracking': 0.8,
            'peer_comparison': 0.7,
            'goal_visualization': 0.8,
            'automated_increases': 0.6,
          },
          'optimal_budget_frequency': 'weekly',
          'celebration_frequency': 'monthly',
        };
      case IncomeTier.middle:
        return {
          'spending_velocity': 'monthly',
          'decision_time': 'days_to_weeks',
          'risk_tolerance': 'moderate',
          'planning_horizon': 'quarterly_to_yearly',
          'primary_stressors': ['investment_paralysis', 'lifestyle_comparison'],
          'mental_accounting_buckets': [
            'fixed',
            'variable',
            'emergency',
            'short_term',
            'long_term',
            'tax_advantaged',
            'fun'
          ],
          'nudge_responsiveness': {
            'opportunity_cost': 0.8,
            'status_enhancement': 0.6,
            'complexity_management': 0.7,
            'peer_benchmarking': 0.8,
          },
          'optimal_budget_frequency': 'monthly',
          'celebration_frequency': 'quarterly',
        };
      case IncomeTier.upperMiddle:
        return {
          'spending_velocity': 'quarterly',
          'decision_time': 'weeks_to_months',
          'risk_tolerance': 'moderate_high',
          'planning_horizon': 'yearly_to_multi_year',
          'primary_stressors': ['optimization_paralysis', 'tax_efficiency'],
          'mental_accounting_buckets': [
            'fixed',
            'variable',
            'emergency',
            'short_term',
            'long_term',
            'tax_advantaged',
            'fun',
            'business',
            'real_estate'
          ],
          'nudge_responsiveness': {
            'tax_efficiency': 0.9,
            'legacy_framing': 0.7,
            'restraint_coaching': 0.6,
            'professional_guidance': 0.8,
          },
          'optimal_budget_frequency': 'quarterly',
          'celebration_frequency': 'semi_annually',
        };
      case IncomeTier.high:
        return {
          'spending_velocity': 'annually',
          'decision_time': 'months_to_years',
          'risk_tolerance': 'high',
          'planning_horizon': 'multi_year_to_generational',
          'primary_stressors': ['wealth_preservation', 'complex_tax_scenarios'],
          'mental_accounting_buckets': [
            'fixed',
            'variable',
            'emergency',
            'short_term',
            'long_term',
            'tax_advantaged',
            'fun',
            'business',
            'real_estate',
            'trust',
            'charity',
            'education'
          ],
          'nudge_responsiveness': {
            'impact_framing': 0.9,
            'legacy_protection': 0.8,
            'complexity_simplification': 0.7,
            'generational_planning': 0.9,
          },
          'optimal_budget_frequency': 'annually',
          'celebration_frequency': 'annually',
        };
    }
  }

  /// Get tier-specific behavioral nudges
  List<Map<String, dynamic>> getTierSpecificNudges(IncomeTier tier,
      Map<String, double>? currentSpending, double monthlyIncome) {
    final patterns = getBehavioralSpendingPatterns(tier);
    final nudges = <Map<String, dynamic>>[];

    switch (tier) {
      case IncomeTier.low:
        nudges.addAll([
          {
            'type': 'loss_framing',
            'message':
                'Protect your \$${_calculateWeeklyProgress(currentSpending, monthlyIncome).toStringAsFixed(0)} weekly progress',
            'effectiveness': patterns['nudge_responsiveness']['loss_framing'],
            'frequency': 'daily',
          },
          {
            'type': 'social_proof',
            'message':
                '73% of Foundation Builders cook dinner at home to save money',
            'effectiveness': patterns['nudge_responsiveness']['social_proof'],
            'frequency': 'weekly',
          },
          {
            'type': 'micro_savings',
            'message':
                'Save your spare change automatically - every \$5 counts!',
            'effectiveness': patterns['nudge_responsiveness']
                ['automated_savings'],
            'frequency': 'daily',
          },
        ]);
        break;
      case IncomeTier.lowerMiddle:
        nudges.addAll([
          {
            'type': 'progress_framing',
            'message':
                'You\'re ${_calculateEmergencyFundProgress(currentSpending, monthlyIncome).toStringAsFixed(0)}% to your \$1,000 safety net',
            'effectiveness': patterns['nudge_responsiveness']
                ['progress_tracking'],
            'frequency': 'weekly',
          },
          {
            'type': 'peer_comparison',
            'message':
                'Others at your level save \$${_calculatePeerAverageSavings(tier, monthlyIncome).toStringAsFixed(0)}/month on average',
            'effectiveness': patterns['nudge_responsiveness']
                ['peer_comparison'],
            'frequency': 'monthly',
          },
        ]);
        break;
      case IncomeTier.middle:
        nudges.addAll([
          {
            'type': 'opportunity_cost',
            'message':
                'That \$200 dinner could be \$600 in your investment account in 10 years',
            'effectiveness': patterns['nudge_responsiveness']
                ['opportunity_cost'],
            'frequency': 'contextual',
          },
          {
            'type': 'status_enhancement',
            'message':
                'Smart strategists max their 401k match - don\'t leave free money on the table',
            'effectiveness': patterns['nudge_responsiveness']
                ['status_enhancement'],
            'frequency': 'quarterly',
          },
        ]);
        break;
      case IncomeTier.upperMiddle:
        nudges.addAll([
          {
            'type': 'tax_efficiency',
            'message':
                'Save \$${_calculateTaxSavingsOpportunity(monthlyIncome).toStringAsFixed(0)} annually with this tax strategy',
            'effectiveness': patterns['nudge_responsiveness']['tax_efficiency'],
            'frequency': 'quarterly',
          },
          {
            'type': 'legacy_framing',
            'message':
                'Build generational wealth systematically with your current income level',
            'effectiveness': patterns['nudge_responsiveness']['legacy_framing'],
            'frequency': 'annually',
          },
        ]);
        break;
      case IncomeTier.high:
        nudges.addAll([
          {
            'type': 'impact_framing',
            'message':
                'Your wealth can change lives for generations - make it count',
            'effectiveness': patterns['nudge_responsiveness']['impact_framing'],
            'frequency': 'quarterly',
          },
          {
            'type': 'legacy_protection',
            'message':
                'Preserve and grow what you\'ve built through strategic planning',
            'effectiveness': patterns['nudge_responsiveness']
                ['legacy_protection'],
            'frequency': 'annually',
          },
        ]);
        break;
    }

    return nudges;
  }

  /// Check if user is near tier boundary for transition management
  bool isNearTierBoundary(double monthlyIncome, IncomeTier currentTier) {
    final annualIncome = monthlyIncome * 12;

    switch (currentTier) {
      case IncomeTier.low:
        const nextThreshold = 3000 * 12; // $36K annual
        return (nextThreshold - annualIncome) / nextThreshold <
            0.05; // Within 5%
      case IncomeTier.lowerMiddle:
        const nextThreshold = 4800 * 12; // $57.6K annual (CORRECTED)
        return (nextThreshold - annualIncome) / nextThreshold < 0.05;
      case IncomeTier.middle:
        const nextThreshold = 7200 * 12; // $86.4K annual (CORRECTED)
        return (nextThreshold - annualIncome) / nextThreshold < 0.05;
      case IncomeTier.upperMiddle:
        const nextThreshold = 12000 * 12; // $144K annual
        return (nextThreshold - annualIncome) / nextThreshold < 0.05;
      case IncomeTier.high:
        return false; // Highest tier
    }
  }

  /// Get next tier information for motivation
  Map<String, dynamic>? getNextTierInfo(
      IncomeTier currentTier, double monthlyIncome) {
    if (currentTier == IncomeTier.high) return null;

    final nextTier = IncomeTier.values[currentTier.index + 1];
    final nextTierName = getIncomeTierName(nextTier);

    double nextThreshold;
    switch (currentTier) {
      case IncomeTier.low:
        nextThreshold = 3000;
        break;
      case IncomeTier.lowerMiddle:
        nextThreshold = 4800; // CORRECTED
        break;
      case IncomeTier.middle:
        nextThreshold = 7200; // CORRECTED
        break;
      case IncomeTier.upperMiddle:
        nextThreshold = 12000;
        break;
      case IncomeTier.high:
        return null;
    }

    final amountNeeded = nextThreshold - monthlyIncome;
    final percentageComplete =
        (monthlyIncome / nextThreshold * 100).clamp(0.0, 100.0);

    return {
      'next_tier': nextTier,
      'next_tier_name': nextTierName,
      'amount_needed': amountNeeded,
      'percentage_complete': percentageComplete,
      'monthly_threshold': nextThreshold,
      'motivation_message':
          'You\'re ${percentageComplete.toStringAsFixed(1)}% of the way to becoming a $nextTierName!',
    };
  }

  // Private helper methods for behavioral calculations
  double _calculateWeeklyProgress(
      Map<String, double>? spending, double monthlyIncome) {
    if (spending == null) return 0.0;
    final totalSpent = spending.values.fold(0.0, (sum, amount) => sum + amount);
    final weeklyBudget = monthlyIncome / 4.33; // Average weeks per month
    return (weeklyBudget - (totalSpent / 4.33)).clamp(0.0, double.infinity);
  }

  double _calculateEmergencyFundProgress(
      Map<String, double>? spending, double monthlyIncome) {
    // Simulate emergency fund progress - in real app, this would come from user data
    final savingsAmount = spending?['savings'] ?? (monthlyIncome * 0.05);
    const targetEmergencyFund = 1000.0; // Target for lower-middle tier
    return (savingsAmount / targetEmergencyFund * 100).clamp(0.0, 100.0);
  }

  double _calculatePeerAverageSavings(IncomeTier tier, double monthlyIncome) {
    final weights = getDefaultBudgetWeights(tier);
    return monthlyIncome * (weights['savings'] ?? 0.1);
  }

  double _calculateTaxSavingsOpportunity(double monthlyIncome) {
    // Simplified tax savings calculation for upper-middle tier
    final annualIncome = monthlyIncome * 12;
    return annualIncome * 0.03; // Assume 3% tax savings opportunity
  }

  /// Get tier as string for API compatibility
  String getTierString(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'low';
      case IncomeTier.lowerMiddle:
        return 'mid_low';
      case IncomeTier.middle:
        return 'mid';
      case IncomeTier.upperMiddle:
        return 'mid_high';
      case IncomeTier.high:
        return 'high';
    }
  }

  /// Get tier display name for UI
  String getTierDisplayName(IncomeTier tier) {
    return getIncomeTierName(tier);
  }

  /// Get tier income range for display
  String getTierRange(IncomeTier tier) {
    return getIncomeRangeString(tier);
  }
}

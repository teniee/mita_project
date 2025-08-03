import 'package:flutter/material.dart';
import 'country_profiles_service.dart';
import 'location_service.dart';

/// Income classification enum - matches backend 5-level system
enum IncomeTier {
  low,           // < $3,000
  lowerMiddle,   // $3,000 - $4,500  
  middle,        // $4,500 - $7,000
  upperMiddle,   // $7,000 - $12,000
  high,          // > $12,000
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
  static const double lowThreshold = 3000.0;
  static const double lowerMiddleThreshold = 4500.0;
  static const double middleThreshold = 7000.0;
  static const double upperMiddleThreshold = 12000.0;

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
    
    return classifyIncomeForLocation(monthlyIncome, countryCode, stateCode: stateCode);
  }

  /// Classify income for specific location
  IncomeTier classifyIncomeForLocation(double monthlyIncome, String countryCode, {String? stateCode}) {
    final thresholds = _countryService.getIncomeThresholds(countryCode, stateCode: stateCode);
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

  /// Get income tier display name
  String getIncomeTierName(IncomeTier tier) {
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

  /// Get income tier description
  String getIncomeTierDescription(IncomeTier tier) {
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

  /// Get income range string for display (legacy method - uses default US thresholds)
  String getIncomeRangeString(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return 'Under \$3,000/month';
      case IncomeTier.lowerMiddle:
        return '\$3,000 - \$4,500/month';
      case IncomeTier.middle:
        return '\$4,500 - \$7,000/month';
      case IncomeTier.upperMiddle:
        return '\$7,000 - \$12,000/month';
      case IncomeTier.high:
        return 'Over \$12,000/month';
    }
  }

  /// Get income range string for display based on user's location
  Future<String> getIncomeRangeStringByLocation(IncomeTier tier) async {
    final location = await _locationService.getUserLocation();
    final countryCode = location['country'] ?? 'US';
    final stateCode = location['state'];
    
    return getIncomeRangeStringForLocation(tier, countryCode, stateCode: stateCode);
  }

  /// Get income range string for specific location
  String getIncomeRangeStringForLocation(IncomeTier tier, String countryCode, {String? stateCode}) {
    final thresholds = _countryService.getIncomeThresholds(countryCode, stateCode: stateCode);
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

  /// Get primary color for income tier
  Color getIncomeTierPrimaryColor(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return const Color(0xFF4CAF50); // Green - Growth mindset
      case IncomeTier.lowerMiddle:
        return const Color(0xFF00BCD4); // Cyan - Rising opportunities
      case IncomeTier.middle:
        return const Color(0xFF2196F3); // Blue - Professional
      case IncomeTier.upperMiddle:
        return const Color(0xFF673AB7); // Deep Purple - Established
      case IncomeTier.high:
        return const Color(0xFF9C27B0); // Purple - Premium
    }
  }

  /// Get secondary color for income tier
  Color getIncomeTierSecondaryColor(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low:
        return const Color(0xFFE8F5E8); // Light green
      case IncomeTier.lowerMiddle:
        return const Color(0xFFE0F7FA); // Light cyan
      case IncomeTier.middle:
        return const Color(0xFFE3F2FD); // Light blue
      case IncomeTier.upperMiddle:
        return const Color(0xFFEDE7F6); // Light deep purple
      case IncomeTier.high:
        return const Color(0xFFF3E5F5); // Light purple
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
          'housing': 0.40,      // Higher for essential housing
          'food': 0.15,         // Budget-conscious food spending
          'transportation': 0.15,
          'utilities': 0.10,
          'healthcare': 0.08,
          'entertainment': 0.05, // Lower entertainment budget
          'savings': 0.07,       // Conservative savings goal
        };
      case IncomeTier.lowerMiddle:
        return {
          'housing': 0.38,      // Slightly lower housing costs
          'food': 0.14,
          'transportation': 0.15,
          'utilities': 0.09,
          'healthcare': 0.07,
          'entertainment': 0.06,
          'savings': 0.11,       // Building emergency fund
        };
      case IncomeTier.middle:
        return {
          'housing': 0.35,      // Balanced housing costs
          'food': 0.12,
          'transportation': 0.15,
          'utilities': 0.08,
          'healthcare': 0.06,
          'entertainment': 0.08,
          'savings': 0.16,       // Moderate savings goal
        };
      case IncomeTier.upperMiddle:
        return {
          'housing': 0.32,      // Lower housing percentage
          'food': 0.11,
          'transportation': 0.13,
          'utilities': 0.06,
          'healthcare': 0.05,
          'entertainment': 0.09,
          'savings': 0.24,       // Higher savings rate
        };
      case IncomeTier.high:
        return {
          'housing': 0.30,      // Lower percentage for housing
          'food': 0.10,
          'transportation': 0.12,
          'utilities': 0.05,
          'healthcare': 0.05,
          'entertainment': 0.10,
          'savings': 0.28,       // Aggressive savings goal
        };
    }
  }

  /// Get peer comparison message
  String getPeerComparisonMessage(IncomeTier tier, String category, double userSpending, double peerAverage) {
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
  List<Map<String, dynamic>> getGoalSuggestions(IncomeTier tier, double monthlyIncome) {
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
  Map<String, dynamic> getBudgetTemplate(IncomeTier tier, double monthlyIncome) {
    final weights = getDefaultBudgetWeights(tier);
    final template = <String, dynamic>{};
    
    weights.forEach((category, weight) {
      template[category] = (monthlyIncome * weight).round().toDouble();
    });
    
    return {
      'monthly_income': monthlyIncome,
      'income_tier': tier.toString(),
      'allocations': template,
      'total_allocated': template.values.fold<double>(0, (sum, amount) => sum + amount),
      'remaining': monthlyIncome - template.values.fold<double>(0, (sum, amount) => sum + amount),
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
  Map<String, dynamic> getSpendingInsights(double amount, String category, double monthlyIncome) {
    final tier = classifyIncome(monthlyIncome);
    final percentage = getIncomePercentage(amount, monthlyIncome);
    final weights = getDefaultBudgetWeights(tier);
    final recommendedAmount = monthlyIncome * (weights[category.toLowerCase()] ?? 0.1);
    
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
}
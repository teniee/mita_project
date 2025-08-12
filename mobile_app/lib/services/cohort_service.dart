import 'package:flutter/material.dart';
import 'income_service.dart';
import 'api_service.dart';

/// Cohort-based recommendations service for MITA
/// Provides personalized recommendations based on user's income tier and peer behavior
class CohortService {
  static final CohortService _instance = CohortService._internal();
  factory CohortService() => _instance;
  CohortService._internal();

  final IncomeService _incomeService = IncomeService();
  final ApiService _apiService = ApiService();

  /// Get cohort-specific spending recommendations
  Future<Map<String, dynamic>> getCohortSpendingRecommendations(
    double monthlyIncome, {
    Map<String, double>? currentSpending,
  }) async {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    
    try {
      // Try to get real peer comparison data
      final peerData = await _apiService.getPeerComparison();
      return _generateRecommendationsFromPeerData(tier, monthlyIncome, peerData, currentSpending);
    } catch (e) {
      // Fallback to tier-based recommendations
      return _generateTierBasedRecommendations(tier, monthlyIncome, currentSpending);
    }
  }

  /// Get cohort-based goal suggestions
  List<Map<String, dynamic>> getCohortGoalSuggestions(
    double monthlyIncome, {
    List<Map<String, dynamic>>? existingGoals,
  }) {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    final suggestions = _incomeService.getGoalSuggestions(tier, monthlyIncome);
    
    // Filter out existing goals and add cohort context
    final existingTitles = existingGoals?.map((g) => g['title']).toSet() ?? <String>{};
    
    return suggestions.where((goal) => !existingTitles.contains(goal['title'])).map((goal) {
      return {
        ...goal,
        'cohort_context': _getGoalCohortContext(tier, goal['category'] as String? ?? 'general'),
        'peer_adoption': _getGoalPeerAdoption(tier, goal['category'] as String? ?? 'general'),
      };
    }).toList();
  }

  /// Get cohort-based habit recommendations
  List<Map<String, dynamic>> getCohortHabitRecommendations(double monthlyIncome) {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    
    switch (tier) {
      case IncomeTier.low:
        return [
          {
            'title': 'Daily Expense Tracking',
            'description': 'Track every expense for better awareness',
            'frequency': 'daily',
            'impact': 'high',
            'peer_adoption': '78%',
            'icon': Icons.edit_rounded,
            'color': Colors.green.shade600,
          },
          {
            'title': 'Weekly Budget Review',
            'description': 'Review and adjust weekly spending',
            'frequency': 'weekly',
            'impact': 'medium',
            'peer_adoption': '65%',
            'icon': Icons.analytics_rounded,
            'color': Colors.blue.shade600,
          },
          {
            'title': 'Meal Planning Sunday',
            'description': 'Plan meals to reduce food waste and costs',
            'frequency': 'weekly',
            'impact': 'high',
            'peer_adoption': '82%',
            'icon': Icons.restaurant_menu_rounded,
            'color': Colors.orange.shade600,
          },
        ];
      case IncomeTier.lowerMiddle:
        return [
          {
            'title': 'Emergency Fund Building',
            'description': 'Build emergency fund with consistent contributions',
            'frequency': 'monthly',
            'impact': 'high',
            'peer_adoption': '73%',
            'icon': Icons.security_rounded,
            'color': Colors.cyan.shade600,
          },
          {
            'title': 'Skill Development Investment',
            'description': 'Invest in courses and certifications',
            'frequency': 'quarterly',
            'impact': 'high',
            'peer_adoption': '68%',
            'icon': Icons.school_rounded,
            'color': Colors.teal.shade600,
          },
          {
            'title': 'Debt Snowball Method',
            'description': 'Systematically pay down high-interest debt',
            'frequency': 'monthly',
            'impact': 'high',
            'peer_adoption': '81%',
            'icon': Icons.trending_down_rounded,
            'color': Colors.orange.shade600,
          },
        ];
      case IncomeTier.middle:
        return [
          {
            'title': 'Investment Research Hour',
            'description': 'Spend time researching investment opportunities',
            'frequency': 'weekly',
            'impact': 'high',
            'peer_adoption': '71%',
            'icon': Icons.trending_up_rounded,
            'color': Colors.green.shade600,
          },
          {
            'title': 'Automated Savings',
            'description': 'Set up automatic transfers to savings',
            'frequency': 'monthly',
            'impact': 'high',
            'peer_adoption': '89%',
            'icon': Icons.savings_rounded,
            'color': Colors.blue.shade600,
          },
          {
            'title': 'Expense Category Review',
            'description': 'Analyze spending by category monthly',
            'frequency': 'monthly',
            'impact': 'medium',
            'peer_adoption': '67%',
            'icon': Icons.pie_chart_rounded,
            'color': Colors.purple.shade600,
          },
        ];
      case IncomeTier.upperMiddle:
        return [
          {
            'title': 'Advanced Portfolio Management',
            'description': 'Diversify investments across asset classes',
            'frequency': 'monthly',
            'impact': 'high',
            'peer_adoption': '79%',
            'icon': Icons.pie_chart_outline_rounded,
            'color': Colors.deepPurple.shade600,
          },
          {
            'title': 'Tax Loss Harvesting',
            'description': 'Optimize taxes through strategic selling',
            'frequency': 'quarterly',
            'impact': 'medium',
            'peer_adoption': '64%',
            'icon': Icons.receipt_long_rounded,
            'color': Colors.indigo.shade600,
          },
          {
            'title': 'Real Estate Research',
            'description': 'Explore property investment opportunities',
            'frequency': 'quarterly',
            'impact': 'medium',
            'peer_adoption': '58%',
            'icon': Icons.home_rounded,
            'color': Colors.brown.shade600,
          },
        ];
      case IncomeTier.high:
        return [
          {
            'title': 'Portfolio Rebalancing',
            'description': 'Quarterly review and rebalance investments',
            'frequency': 'quarterly',
            'impact': 'high',
            'peer_adoption': '85%',
            'icon': Icons.account_balance_rounded,
            'color': Colors.green.shade600,
          },
          {
            'title': 'Tax Strategy Planning',
            'description': 'Monthly tax optimization review',
            'frequency': 'monthly',
            'impact': 'high',
            'peer_adoption': '78%',
            'icon': Icons.calculate_rounded,
            'color': Colors.blue.shade600,
          },
          {
            'title': 'Financial Advisor Meeting',
            'description': 'Regular meetings with financial advisor',
            'frequency': 'quarterly',
            'impact': 'medium',
            'peer_adoption': '63%',
            'icon': Icons.person_rounded,
            'color': Colors.purple.shade600,
          },
        ];
    }
  }

  /// Get personalized insights based on cohort behavior
  List<String> getCohortPersonalizedInsights(
    double monthlyIncome, {
    Map<String, double>? userSpending,
    Map<String, dynamic>? userBehavior,
  }) {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    final tierName = _incomeService.getIncomeTierName(tier);
    
    List<String> insights = [];
    
    // Add tier-specific insights
    insights.addAll(_getTierSpecificInsights(tier, tierName));
    
    // Add spending-based insights if available
    if (userSpending != null) {
      insights.addAll(_getSpendingBasedInsights(tier, monthlyIncome, userSpending));
    }
    
    // Add behavioral insights if available
    if (userBehavior != null) {
      insights.addAll(_getBehaviorBasedInsights(tier, userBehavior));
    }
    
    return insights.take(5).toList(); // Limit to top 5 insights
  }

  /// Get cohort-based budget optimization suggestions
  Map<String, dynamic> getCohortBudgetOptimization(
    double monthlyIncome,
    Map<String, double> currentAllocations,
  ) {
    final tier = _incomeService.classifyIncome(monthlyIncome);
    final recommendedWeights = _incomeService.getDefaultBudgetWeights(tier);
    
    final optimizations = <String, dynamic>{};
    final suggestions = <String>[];
    
    recommendedWeights.forEach((category, recommendedWeight) {
      final recommendedAmount = monthlyIncome * recommendedWeight;
      final currentAmount = currentAllocations[category] ?? 0.0;
      final difference = currentAmount - recommendedAmount;
      final percentageDiff = (difference / recommendedAmount * 100).abs();
      
      if (percentageDiff > 20) { // If more than 20% different from recommended
        if (difference > 0) {
          // Overspending in this category
          optimizations[category] = {
            'status': 'over',
            'current': currentAmount,
            'recommended': recommendedAmount,
            'difference': difference,
            'suggestion': _getOverspendingSuggestion(tier, category, difference),
          };
          suggestions.add('Consider reducing $category spending by \$${difference.toStringAsFixed(0)}');
        } else {
          // Underspending in this category
          optimizations[category] = {
            'status': 'under',
            'current': currentAmount,
            'recommended': recommendedAmount,
            'difference': difference.abs(),
            'suggestion': _getUnderspendingSuggestion(tier, category, difference.abs()),
          };
          suggestions.add('You have room to increase $category spending by \$${difference.abs().toStringAsFixed(0)}');
        }
      }
    });
    
    return {
      'optimizations': optimizations,
      'suggestions': suggestions,
      'overall_score': _calculateOptimizationScore(optimizations),
      'peer_comparison': _getPeerBudgetComparison(tier, currentAllocations, monthlyIncome),
    };
  }

  // Private helper methods
  
  Map<String, dynamic> _generateRecommendationsFromPeerData(
    IncomeTier tier,
    double monthlyIncome,
    Map<String, dynamic> peerData,
    Map<String, double>? currentSpending,
  ) {
    final recommendations = <String>[];
    final categories = peerData['categories'] as Map<String, dynamic>? ?? {};
    
    categories.forEach((category, data) {
      final peerAverage = data['peer_average'] as double? ?? 0.0;
      final userAmount = currentSpending?[category] ?? 0.0;
      
      if (userAmount > peerAverage * 1.2) {
        recommendations.add('Your $category spending is 20% above peer average. Consider reducing by \$${(userAmount - peerAverage).toStringAsFixed(0)}');
      } else if (userAmount < peerAverage * 0.8) {
        recommendations.add('Your $category spending is below peer average. You may have room to optimize this category');
      }
    });
    
    return {
      'recommendations': recommendations,
      'peer_data': peerData,
      'tier': tier.toString(),
    };
  }

  Map<String, dynamic> _generateTierBasedRecommendations(
    IncomeTier tier,
    double monthlyIncome,
    Map<String, double>? currentSpending,
  ) {
    final tips = _incomeService.getFinancialTips(tier);
    final budgetWeights = _incomeService.getDefaultBudgetWeights(tier);
    
    final recommendations = <String>[];
    recommendations.addAll(tips.take(3));
    
    if (currentSpending != null) {
      budgetWeights.forEach((category, weight) {
        final recommended = monthlyIncome * weight;
        final current = currentSpending[category] ?? 0.0;
        final difference = (current - recommended).abs();
        
        if (difference > monthlyIncome * 0.05) { // If difference is > 5% of income
          if (current > recommended) {
            recommendations.add('Consider reducing $category spending by \$${difference.toStringAsFixed(0)}');
          } else {
            recommendations.add('You have room to allocate \$${difference.toStringAsFixed(0)} more to $category');
          }
        }
      });
    }
    
    return {
      'recommendations': recommendations,
      'tier': tier.toString(),
      'budget_weights': budgetWeights,
    };
  }

  String _getGoalCohortContext(IncomeTier tier, String category) {
    final tierName = _incomeService.getIncomeTierName(tier);
    
    switch (category) {
      case 'emergency':
        return '${tierName}s typically build emergency funds over 8-12 months';
      case 'investment':
        return 'Most ${tierName}s start investing within their first 2 years';
      case 'debt':
        return '${tierName}s usually prioritize high-interest debt elimination';
      case 'tax':
        return 'Tax optimization becomes important at higher income levels';
      default:
        return '${tierName}s find this goal achievable and worthwhile';
    }
  }

  double _getGoalPeerAdoption(IncomeTier tier, String category) {
    switch (tier) {
      case IncomeTier.low:
        return category == 'emergency' ? 0.89 : category == 'debt' ? 0.76 : 0.45;
      case IncomeTier.lowerMiddle:
        return category == 'emergency' ? 0.84 : category == 'debt' ? 0.79 : category == 'education' ? 0.68 : 0.52;
      case IncomeTier.middle:
        return category == 'investment' ? 0.82 : category == 'emergency' ? 0.71 : 0.58;
      case IncomeTier.upperMiddle:
        return category == 'investment' ? 0.86 : category == 'tax' ? 0.74 : category == 'property' ? 0.61 : 0.64;
      case IncomeTier.high:
        return category == 'tax' ? 0.91 : category == 'investment' ? 0.88 : 0.67;
    }
  }

  List<String> _getTierSpecificInsights(IncomeTier tier, String tierName) {
    switch (tier) {
      case IncomeTier.low:
        return [
          '${tierName}s who track daily expenses save 23% more on average',
          'Meal planning can reduce food costs by 15-20% for your income group',
          'Building a \$500 emergency fund is the top priority for 89% of peers',
        ];
      case IncomeTier.lowerMiddle:
        return [
          '${tierName}s who build emergency funds first avoid 68% more financial stress',
          'Skill development investments increase income by 18% within 2 years',
          'Debt elimination strategies save \$2,400 annually on average for your tier',
        ];
      case IncomeTier.middle:
        return [
          '${tierName}s who invest early see 40% better long-term outcomes',
          'Automating savings increases success rates by 65% in your tier',
          'Career development investments pay off 3x faster at your income level',
        ];
      case IncomeTier.upperMiddle:
        return [
          '${tierName}s who diversify investments see 28% higher returns',
          'Tax optimization strategies save an average of \$4,200 annually',
          'Property investments become viable at your income level for 61% of peers',
        ];
      case IncomeTier.high:
        return [
          '${tierName}s who optimize taxes save an average of \$12,000 annually',
          'Portfolio diversification becomes critical at your income level',
          'Working with a financial advisor shows 45% better returns for peers',
        ];
    }
  }

  List<String> _getSpendingBasedInsights(
    IncomeTier tier,
    double monthlyIncome,
    Map<String, double> userSpending,
  ) {
    final insights = <String>[];
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    
    userSpending.forEach((category, amount) {
      final percentage = _incomeService.getIncomePercentage(amount, monthlyIncome);
      final recommendedPercentage = (weights[category] ?? 0.1) * 100;
      
      if (percentage > recommendedPercentage * 1.3) {
        insights.add('Your $category spending (${percentage.toStringAsFixed(1)}%) is above the recommended ${recommendedPercentage.toStringAsFixed(1)}%');
      }
    });
    
    return insights;
  }

  List<String> _getBehaviorBasedInsights(
    IncomeTier tier,
    Map<String, dynamic> userBehavior,
  ) {
    final insights = <String>[];
    
    // Add insights based on behavior patterns
    if (userBehavior['weekend_spending_spike'] == true) {
      insights.add('Your weekend spending patterns suggest emotional spending - common in your income tier');
    }
    
    if (userBehavior['goal_completion_rate'] != null) {
      final rate = userBehavior['goal_completion_rate'] as double;
      if (rate > 0.8) {
        insights.add('Your goal completion rate (${(rate * 100).toStringAsFixed(0)}%) is above average for your tier');
      }
    }
    
    return insights;
  }

  String _getOverspendingSuggestion(IncomeTier tier, String category, double amount) {
    switch (category) {
      case 'food':
        return tier == IncomeTier.low 
          ? 'Try meal planning and cooking at home more often'
          : 'Consider reducing dining out frequency';
      case 'transportation':
        return 'Look into carpooling, public transit, or bike commuting options';
      case 'entertainment':
        return 'Explore free community events and activities';
      default:
        return 'Review recent purchases in this category for optimization opportunities';
    }
  }

  String _getUnderspendingSuggestion(IncomeTier tier, String category, double amount) {
    switch (category) {
      case 'savings':
        return 'Consider increasing your savings rate for better financial security';
      case 'healthcare':
        return 'Don\'t neglect preventive healthcare - it saves money long-term';
      case 'education':
        return 'Investing in skills development can boost your earning potential';
      default:
        return 'You have budget flexibility in this category if needed';
    }
  }

  double _calculateOptimizationScore(Map<String, dynamic> optimizations) {
    if (optimizations.isEmpty) return 100.0;
    
    final penalties = optimizations.values.map((opt) {
      final difference = opt['difference'] as double;
      final recommended = opt['recommended'] as double;
      return (difference / recommended * 100).clamp(0.0, 50.0);
    }).fold<double>(0.0, (sum, penalty) => sum + penalty);
    
    return (100 - penalties / optimizations.length).clamp(0.0, 100.0);
  }

  Map<String, dynamic> _getPeerBudgetComparison(
    IncomeTier tier,
    Map<String, double> currentAllocations,
    double monthlyIncome,
  ) {
    final tierName = _incomeService.getIncomeTierName(tier);
    final comparison = <String, dynamic>{};
    
    currentAllocations.forEach((category, amount) {
      final percentage = _incomeService.getIncomePercentage(amount, monthlyIncome);
      comparison[category] = {
        'your_percentage': percentage,
        'peer_average': _getPeerAveragePercentage(tier, category),
        'comparison': percentage > _getPeerAveragePercentage(tier, category) ? 'above' : 'below',
      };
    });
    
    return {
      'tier_name': tierName,
      'categories': comparison,
      'overall_vs_peers': _getOverallPeerComparison(comparison),
    };
  }

  double _getPeerAveragePercentage(IncomeTier tier, String category) {
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    return (weights[category] ?? 0.1) * 100;
  }

  String _getOverallPeerComparison(Map<String, dynamic> comparison) {
    final aboveCount = comparison.values.where((c) => c['comparison'] == 'above').length;
    final totalCount = comparison.length;
    final percentage = (aboveCount / totalCount * 100).round();
    
    if (percentage > 60) {
      return 'You spend more than peers in most categories';
    } else if (percentage < 40) {
      return 'You spend less than peers in most categories';
    } else {
      return 'Your spending patterns are similar to peer averages';
    }
  }
}
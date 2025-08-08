import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'income_service.dart';
import 'logging_service.dart';

/// Personalized budget recommendation engine using behavioral economics and AI
class PersonalizedBudgetEngine {
  static final PersonalizedBudgetEngine _instance = PersonalizedBudgetEngine._internal();
  factory PersonalizedBudgetEngine() => _instance;
  PersonalizedBudgetEngine._internal();

  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();
  
  // User financial profile data
  Map<String, dynamic>? _userProfile;
  Map<String, dynamic>? _spendingHistory;
  Map<String, dynamic>? _behaviorProfile;
  Map<String, dynamic>? _peerData;
  
  /// Initialize the budget engine with user data
  Future<void> initialize() async {
    try {
      logInfo('Initializing Personalized Budget Engine', tag: 'BUDGET_ENGINE');
      
      // Load user profile and financial data
      await _loadUserProfile();
      await _loadSpendingHistory();
      await _loadBehaviorProfile();
      await _loadPeerData();
      
      logInfo('Budget engine initialized successfully', tag: 'BUDGET_ENGINE');
    } catch (e) {
      logError('Failed to initialize budget engine: $e', tag: 'BUDGET_ENGINE', error: e);
    }
  }

  /// Generate personalized budget recommendations
  Future<BudgetRecommendation> generateRecommendations({
    required double monthlyIncome,
    String? location,
    List<String>? financialGoals,
    Map<String, double>? currentSpending,
    BudgetStyle? preferredStyle,
  }) async {
    try {
      logInfo('Generating personalized budget for income: \$${monthlyIncome.toStringAsFixed(2)}', tag: 'BUDGET_ENGINE');
      
      // 1. Determine income tier and base recommendations
      final incomeTier = _incomeService.classifyIncome(monthlyIncome);
      final baseRecommendations = await _getBaseRecommendations(monthlyIncome, incomeTier);
      
      // 2. Apply behavioral adjustments
      final behavioralAdjustments = await _applyBehavioralAdjustments(
        baseRecommendations, 
        _behaviorProfile,
        incomeTier
      );
      
      // 3. Incorporate spending history patterns
      final historyAdjusted = _incorporateSpendingHistory(
        behavioralAdjustments,
        currentSpending ?? {},
        monthlyIncome
      );
      
      // 4. Apply peer comparison insights
      final peerAdjusted = await _applyPeerInsights(
        historyAdjusted,
        monthlyIncome,
        incomeTier
      );
      
      // 5. Incorporate goals and priorities
      final goalOptimized = _optimizeForGoals(
        peerAdjusted,
        financialGoals ?? [],
        monthlyIncome
      );
      
      // 6. Apply location-based adjustments
      final locationAdjusted = _applyLocationAdjustments(
        goalOptimized,
        location,
        incomeTier
      );
      
      // 7. Generate final recommendations with insights
      final finalRecommendation = await _generateFinalRecommendation(
        locationAdjusted,
        monthlyIncome,
        incomeTier,
        preferredStyle ?? BudgetStyle.balanced
      );
      
      logInfo('Budget recommendations generated successfully', tag: 'BUDGET_ENGINE');
      return finalRecommendation;
      
    } catch (e) {
      logError('Failed to generate budget recommendations: $e', tag: 'BUDGET_ENGINE', error: e);
      return _getFallbackRecommendation(monthlyIncome);
    }
  }

  /// Generate smart budget optimizations based on spending patterns
  Future<List<BudgetOptimization>> generateOptimizations({
    required Map<String, double> currentBudget,
    required Map<String, double> actualSpending,
    required double monthlyIncome,
  }) async {
    try {
      final optimizations = <BudgetOptimization>[];
      
      // 1. Identify overspending categories
      final overspendingOptimizations = _identifyOverspendingOptimizations(
        currentBudget,
        actualSpending
      );
      optimizations.addAll(overspendingOptimizations);
      
      // 2. Find underspending opportunities
      final underspendingOptimizations = _identifyUnderspendingOptimizations(
        currentBudget,
        actualSpending,
        monthlyIncome
      );
      optimizations.addAll(underspendingOptimizations);
      
      // 3. Behavioral pattern optimizations
      final behavioralOptimizations = await _identifyBehavioralOptimizations(
        currentBudget,
        actualSpending,
        monthlyIncome
      );
      optimizations.addAll(behavioralOptimizations);
      
      // 4. Peer comparison optimizations
      final peerOptimizations = await _identifyPeerOptimizations(
        currentBudget,
        actualSpending,
        monthlyIncome
      );
      optimizations.addAll(peerOptimizations);
      
      // Sort by potential savings impact
      optimizations.sort((a, b) => b.potentialSavings.compareTo(a.potentialSavings));
      
      return optimizations.take(8).toList();
      
    } catch (e) {
      logError('Failed to generate budget optimizations: $e', tag: 'BUDGET_ENGINE', error: e);
      return [];
    }
  }

  /// Get budget insights and explanations
  Future<List<BudgetInsight>> getBudgetInsights({
    required Map<String, double> currentBudget,
    required double monthlyIncome,
  }) async {
    try {
      final insights = <BudgetInsight>[];
      
      // 1. Income allocation insights
      final allocationInsights = _generateAllocationInsights(currentBudget, monthlyIncome);
      insights.addAll(allocationInsights);
      
      // 2. Behavioral pattern insights
      final behaviorInsights = await _generateBehaviorInsights(currentBudget);
      insights.addAll(behaviorInsights);
      
      // 3. Peer comparison insights
      final peerInsights = await _generatePeerInsights(currentBudget, monthlyIncome);
      insights.addAll(peerInsights);
      
      // 4. Goal alignment insights
      final goalInsights = _generateGoalInsights(currentBudget, monthlyIncome);
      insights.addAll(goalInsights);
      
      // 5. Risk assessment insights
      final riskInsights = _generateRiskInsights(currentBudget, monthlyIncome);
      insights.addAll(riskInsights);
      
      // Sort by priority and relevance
      insights.sort((a, b) => b.priority.index.compareTo(a.priority.index));
      
      return insights.take(10).toList();
      
    } catch (e) {
      logError('Failed to generate budget insights: $e', tag: 'BUDGET_ENGINE', error: e);
      return [];
    }
  }

  /// Generate dynamic budget adjustments based on real-time spending
  Future<BudgetAdjustment> generateDynamicAdjustment({
    required Map<String, double> currentBudget,
    required Map<String, double> monthToDateSpending,
    required int remainingDays,
    required double monthlyIncome,
  }) async {
    try {
      final adjustments = <CategoryAdjustment>[];
      
      // Calculate spending velocity for each category
      final velocityAnalysis = _calculateSpendingVelocity(
        currentBudget,
        monthToDateSpending,
        remainingDays
      );
      
      // Identify categories needing adjustment
      for (final analysis in velocityAnalysis.entries) {
        final category = analysis.key;
        final data = analysis.value;
        
        if (data['needs_adjustment'] == true) {
          final adjustment = CategoryAdjustment(
            category: category,
            currentAmount: currentBudget[category] ?? 0.0,
            recommendedAmount: data['recommended_amount'] as double,
            reason: data['reason'] as String,
            confidence: data['confidence'] as double,
            urgency: data['urgency'] as AdjustmentUrgency,
          );
          adjustments.add(adjustment);
        }
      }
      
      // Generate redistribution suggestions
      final redistributions = _generateRedistributionSuggestions(
        adjustments,
        currentBudget,
        monthlyIncome
      );
      
      return BudgetAdjustment(
        adjustments: adjustments,
        redistributions: redistributions,
        totalImpact: adjustments.fold<double>(0, (sum, adj) => sum + adj.impact),
        confidence: adjustments.isEmpty ? 0.0 : 
          adjustments.fold<double>(0, (sum, adj) => sum + adj.confidence) / adjustments.length,
        implementationSteps: _generateImplementationSteps(adjustments),
      );
      
    } catch (e) {
      logError('Failed to generate dynamic adjustment: $e', tag: 'BUDGET_ENGINE', error: e);
      return BudgetAdjustment(adjustments: [], redistributions: [], totalImpact: 0.0, confidence: 0.0, implementationSteps: []);
    }
  }

  /// Get budget recommendations for specific income tiers
  Future<Map<String, BudgetAllocation>> getIncomeBasedRecommendations(List<double> incomeList) async {
    final recommendations = <String, BudgetAllocation>{};
    
    for (final income in incomeList) {
      final tier = _incomeService.classifyIncome(income);
      final recommendation = await generateRecommendations(monthlyIncome: income);
      
      recommendations[tier.name] = BudgetAllocation(
        allocations: recommendation.categoryAllocations,
        confidence: recommendation.confidence,
        behavioralAlignment: recommendation.behavioralScore,
        optimizationOpportunities: recommendation.optimizationTips,
      );
    }
    
    return recommendations;
  }

  // ============================================================================
  // PRIVATE HELPER METHODS
  // ============================================================================

  /// Load user profile data
  Future<void> _loadUserProfile() async {
    try {
      _userProfile = await _apiService.getUserProfile();
    } catch (e) {
      logWarning('Failed to load user profile: $e', tag: 'BUDGET_ENGINE');
      _userProfile = null;
    }
  }

  /// Load spending history data
  Future<void> _loadSpendingHistory() async {
    try {
      _spendingHistory = await _apiService.getSpendingPatternAnalysis();
    } catch (e) {
      logWarning('Failed to load spending history: $e', tag: 'BUDGET_ENGINE');
      _spendingHistory = null;
    }
  }

  /// Load behavioral profile data
  Future<void> _loadBehaviorProfile() async {
    try {
      _behaviorProfile = await _apiService.getBehavioralAnalysis();
    } catch (e) {
      logWarning('Failed to load behavior profile: $e', tag: 'BUDGET_ENGINE');
      _behaviorProfile = null;
    }
  }

  /// Load peer comparison data
  Future<void> _loadPeerData() async {
    try {
      _peerData = await _apiService.getPeerComparison();
    } catch (e) {
      logWarning('Failed to load peer data: $e', tag: 'BUDGET_ENGINE');
      _peerData = null;
    }
  }

  /// Get base budget recommendations for income tier
  Future<Map<String, double>> _getBaseRecommendations(double income, IncomeTier tier) async {
    try {
      // Get backend recommendations
      final backendRecs = await _apiService.getIncomeBasedBudgetRecommendations(income);
      return Map<String, double>.from(backendRecs['allocations'] ?? {});
    } catch (e) {
      // Fallback to service-based recommendations
      final weights = _incomeService.getDefaultBudgetWeights(tier);
      return weights.map((key, weight) => MapEntry(key, income * weight));
    }
  }

  /// Apply behavioral adjustments to base recommendations
  Future<Map<String, double>> _applyBehavioralAdjustments(
    Map<String, double> baseAmounts,
    Map<String, dynamic>? behaviorProfile,
    IncomeTier tier
  ) async {
    if (behaviorProfile == null) return baseAmounts;
    
    final adjusted = Map<String, double>.from(baseAmounts);
    final spendingPersonality = behaviorProfile['spending_personality'] as String? ?? 'balanced';
    final keyTraits = List<String>.from(behaviorProfile['key_traits'] ?? []);
    
    // Apply personality-based adjustments
    switch (spendingPersonality) {
      case 'conservative':
        adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 1.15;
        adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 0.85;
        break;
      case 'aggressive':
        adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 1.20;
        adjusted['shopping'] = (adjusted['shopping'] ?? 0.0) * 1.10;
        adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 0.90;
        break;
      case 'inconsistent':
        // More conservative budgets for inconsistent spenders
        adjusted.updateAll((key, value) => value * 0.95);
        adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 1.10;
        break;
    }
    
    // Apply trait-based adjustments
    for (final trait in keyTraits) {
      switch (trait) {
        case 'weekend_overspending':
          adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 0.90;
          break;
        case 'impulse_buying':
          adjusted['shopping'] = (adjusted['shopping'] ?? 0.0) * 0.85;
          adjusted['entertainment'] = (adjusted['entertainment'] ?? 0.0) * 0.90;
          break;
        case 'goal_oriented':
          adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 1.10;
          break;
      }
    }
    
    return _normalizeAllocations(adjusted);
  }

  /// Incorporate spending history into recommendations
  Map<String, double> _incorporateSpendingHistory(
    Map<String, double> baseAmounts,
    Map<String, double> currentSpending,
    double income
  ) {
    if (currentSpending.isEmpty) return baseAmounts;
    
    final adjusted = Map<String, double>.from(baseAmounts);
    final totalCurrent = currentSpending.values.fold(0.0, (sum, amount) => sum + amount);
    
    if (totalCurrent > 0) {
      // Blend historical patterns with recommendations (60% historical, 40% recommended)
      currentSpending.forEach((category, amount) {
        final currentWeight = amount / totalCurrent;
        final recommendedWeight = (adjusted[category] ?? 0.0) / income;
        final blendedWeight = (currentWeight * 0.6) + (recommendedWeight * 0.4);
        adjusted[category] = income * blendedWeight;
      });
    }
    
    return _normalizeAllocations(adjusted);
  }

  /// Apply peer comparison insights
  Future<Map<String, double>> _applyPeerInsights(
    Map<String, double> baseAmounts,
    double income,
    IncomeTier tier
  ) async {
    if (_peerData == null) return baseAmounts;
    
    final adjusted = Map<String, double>.from(baseAmounts);
    final peerCategories = _peerData!['categories'] as Map<String, dynamic>? ?? {};
    
    // Apply peer comparison adjustments cautiously
    peerCategories.forEach((category, data) {
      if (data is Map<String, dynamic>) {
        final peerAverage = (data['peer_average'] as num?)?.toDouble() ?? 0.0;
        final currentAmount = adjusted[category] ?? 0.0;
        
        // If user's allocation is significantly different from peers, nudge towards peer average
        final difference = (peerAverage - currentAmount).abs();
        if (difference > currentAmount * 0.3) {
          // Move 25% towards peer average
          adjusted[category] = currentAmount + ((peerAverage - currentAmount) * 0.25);
        }
      }
    });
    
    return _normalizeAllocations(adjusted);
  }

  /// Optimize allocations for financial goals
  Map<String, double> _optimizeForGoals(
    Map<String, double> baseAmounts,
    List<String> goals,
    double income
  ) {
    if (goals.isEmpty) return baseAmounts;
    
    final adjusted = Map<String, double>.from(baseAmounts);
    
    // Adjust based on goal priorities
    for (final goal in goals) {
      switch (goal.toLowerCase()) {
        case 'emergency_fund':
        case 'savings':
          adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 1.15;
          break;
        case 'debt_payoff':
          adjusted['debt'] = (adjusted['debt'] ?? 0.0) * 1.20;
          break;
        case 'investment':
          adjusted['investments'] = (adjusted['investments'] ?? income * 0.05) * 1.25;
          break;
        case 'travel':
          adjusted['travel'] = (adjusted['travel'] ?? income * 0.03) * 1.50;
          break;
        case 'home_purchase':
          adjusted['savings'] = (adjusted['savings'] ?? 0.0) * 1.25;
          break;
      }
    }
    
    return _normalizeAllocations(adjusted);
  }

  /// Apply location-based cost-of-living adjustments
  Map<String, double> _applyLocationAdjustments(
    Map<String, double> baseAmounts,
    String? location,
    IncomeTier tier
  ) {
    if (location == null) return baseAmounts;
    
    final adjusted = Map<String, double>.from(baseAmounts);
    
    // Apply basic cost-of-living adjustments
    // This would be enhanced with real location data
    final highCostAreas = ['san francisco', 'new york', 'los angeles', 'seattle'];
    final lowCostAreas = ['kansas city', 'oklahoma city', 'memphis', 'birmingham'];
    
    if (highCostAreas.any((area) => location.toLowerCase().contains(area))) {
      adjusted['housing'] = (adjusted['housing'] ?? 0.0) * 1.25;
      adjusted['food'] = (adjusted['food'] ?? 0.0) * 1.15;
      adjusted['transportation'] = (adjusted['transportation'] ?? 0.0) * 1.10;
    } else if (lowCostAreas.any((area) => location.toLowerCase().contains(area))) {
      adjusted['housing'] = (adjusted['housing'] ?? 0.0) * 0.80;
      adjusted['food'] = (adjusted['food'] ?? 0.0) * 0.90;
      adjusted['transportation'] = (adjusted['transportation'] ?? 0.0) * 0.85;
    }
    
    return _normalizeAllocations(adjusted);
  }

  /// Generate final recommendation with insights
  Future<BudgetRecommendation> _generateFinalRecommendation(
    Map<String, double> allocations,
    double income,
    IncomeTier tier,
    BudgetStyle style
  ) async {
    final insights = await getBudgetInsights(currentBudget: allocations, monthlyIncome: income);
    final optimizations = await generateOptimizations(
      currentBudget: allocations,
      actualSpending: {},
      monthlyIncome: income
    );
    
    return BudgetRecommendation(
      categoryAllocations: allocations,
      totalAllocated: allocations.values.fold(0.0, (sum, amount) => sum + amount),
      monthlyIncome: income,
      incomeTier: tier,
      budgetStyle: style,
      confidence: _calculateConfidence(allocations, income),
      behavioralScore: _calculateBehavioralAlignment(allocations),
      savingsRate: ((allocations['savings'] ?? 0.0) / income * 100),
      insights: insights.map((i) => i.message).toList(),
      optimizationTips: optimizations.map((o) => o.description).toList(),
      riskFactors: _identifyRiskFactors(allocations, income),
      nextReviewDate: DateTime.now().add(const Duration(days: 30)),
    );
  }

  /// Normalize allocations to ensure they sum correctly
  Map<String, double> _normalizeAllocations(Map<String, double> allocations) {
    final total = allocations.values.fold(0.0, (sum, amount) => sum + amount);
    if (total <= 0) return allocations;
    
    final targetSum = allocations.values.first; // Use income as target
    final scaleFactor = targetSum / total;
    
    return allocations.map((key, value) => MapEntry(key, value * scaleFactor));
  }

  /// Calculate spending velocity for dynamic adjustments
  Map<String, Map<String, dynamic>> _calculateSpendingVelocity(
    Map<String, double> budget,
    Map<String, double> spending,
    int remainingDays
  ) {
    final analysis = <String, Map<String, dynamic>>{};
    final daysInMonth = 30;
    final daysPassed = daysInMonth - remainingDays;
    
    budget.forEach((category, budgetAmount) {
      final spentAmount = spending[category] ?? 0.0;
      final dailyBudget = budgetAmount / daysInMonth;
      final actualDailySpending = daysPassed > 0 ? spentAmount / daysPassed : 0.0;
      final projectedMonthlySpending = actualDailySpending * daysInMonth;
      
      final velocity = budgetAmount > 0 ? projectedMonthlySpending / budgetAmount : 0.0;
      final needsAdjustment = velocity > 1.2 || velocity < 0.5;
      
      analysis[category] = {
        'velocity': velocity,
        'needs_adjustment': needsAdjustment,
        'recommended_amount': needsAdjustment ? projectedMonthlySpending * 1.1 : budgetAmount,
        'reason': _getVelocityReason(velocity),
        'confidence': _getVelocityConfidence(velocity, daysPassed),
        'urgency': _getVelocityUrgency(velocity),
      };
    });
    
    return analysis;
  }

  /// Generate implementation steps for budget adjustments
  List<String> _generateImplementationSteps(List<CategoryAdjustment> adjustments) {
    final steps = <String>[];
    
    if (adjustments.isNotEmpty) {
      steps.add('Review the recommended budget adjustments below');
      steps.add('Identify which changes are most important for your goals');
      steps.add('Implement high-priority adjustments first');
      steps.add('Set up tracking to monitor the impact of changes');
      steps.add('Review and refine your budget in 2 weeks');
    }
    
    return steps;
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  String _getVelocityReason(double velocity) {
    if (velocity > 1.5) return 'Spending significantly above budget';
    if (velocity > 1.2) return 'Trending over budget';
    if (velocity < 0.5) return 'Well under budget - consider reallocation';
    return 'Spending on track';
  }

  double _getVelocityConfidence(double velocity, int daysPassed) {
    if (daysPassed < 7) return 0.4; // Low confidence early in month
    if (daysPassed < 15) return 0.7; // Medium confidence mid-month
    return 0.9; // High confidence late in month
  }

  AdjustmentUrgency _getVelocityUrgency(double velocity) {
    if (velocity > 1.5) return AdjustmentUrgency.high;
    if (velocity > 1.2 || velocity < 0.5) return AdjustmentUrgency.medium;
    return AdjustmentUrgency.low;
  }

  double _calculateConfidence(Map<String, double> allocations, double income) {
    // Implementation for confidence calculation
    return 0.85;
  }

  double _calculateBehavioralAlignment(Map<String, double> allocations) {
    // Implementation for behavioral alignment calculation
    return 0.80;
  }

  List<String> _identifyRiskFactors(Map<String, double> allocations, double income) {
    final risks = <String>[];
    
    final savingsRate = (allocations['savings'] ?? 0.0) / income;
    if (savingsRate < 0.10) {
      risks.add('Low savings rate (below 10%)');
    }
    
    final housingRate = (allocations['housing'] ?? 0.0) / income;
    if (housingRate > 0.35) {
      risks.add('High housing costs (above 35% of income)');
    }
    
    return risks;
  }

  // Fallback methods
  BudgetRecommendation _getFallbackRecommendation(double income) {
    final tier = _incomeService.classifyIncome(income);
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    final allocations = weights.map((key, weight) => MapEntry(key, income * weight));
    
    return BudgetRecommendation(
      categoryAllocations: allocations,
      totalAllocated: income,
      monthlyIncome: income,
      incomeTier: tier,
      budgetStyle: BudgetStyle.balanced,
      confidence: 0.5,
      behavioralScore: 0.5,
      savingsRate: ((allocations['savings'] ?? 0.0) / income * 100),
      insights: ['Using standard budget allocation for your income level'],
      optimizationTips: ['Customize your budget based on actual spending patterns'],
      riskFactors: [],
      nextReviewDate: DateTime.now().add(const Duration(days: 30)),
    );
  }

  // Placeholder implementations for complex analysis methods
  List<BudgetOptimization> _identifyOverspendingOptimizations(
    Map<String, double> budget,
    Map<String, double> spending
  ) => [];

  List<BudgetOptimization> _identifyUnderspendingOptimizations(
    Map<String, double> budget,
    Map<String, double> spending,
    double income
  ) => [];

  Future<List<BudgetOptimization>> _identifyBehavioralOptimizations(
    Map<String, double> budget,
    Map<String, double> spending,
    double income
  ) async => [];

  Future<List<BudgetOptimization>> _identifyPeerOptimizations(
    Map<String, double> budget,
    Map<String, double> spending,
    double income
  ) async => [];

  List<BudgetInsight> _generateAllocationInsights(
    Map<String, double> budget,
    double income
  ) => [];

  Future<List<BudgetInsight>> _generateBehaviorInsights(
    Map<String, double> budget
  ) async => [];

  Future<List<BudgetInsight>> _generatePeerInsights(
    Map<String, double> budget,
    double income
  ) async => [];

  List<BudgetInsight> _generateGoalInsights(
    Map<String, double> budget,
    double income
  ) => [];

  List<BudgetInsight> _generateRiskInsights(
    Map<String, double> budget,
    double income
  ) => [];

  List<BudgetRedistribution> _generateRedistributionSuggestions(
    List<CategoryAdjustment> adjustments,
    Map<String, double> budget,
    double income
  ) => [];
}

// ============================================================================
// DATA CLASSES
// ============================================================================

class BudgetRecommendation {
  final Map<String, double> categoryAllocations;
  final double totalAllocated;
  final double monthlyIncome;
  final IncomeTier incomeTier;
  final BudgetStyle budgetStyle;
  final double confidence;
  final double behavioralScore;
  final double savingsRate;
  final List<String> insights;
  final List<String> optimizationTips;
  final List<String> riskFactors;
  final DateTime nextReviewDate;

  BudgetRecommendation({
    required this.categoryAllocations,
    required this.totalAllocated,
    required this.monthlyIncome,
    required this.incomeTier,
    required this.budgetStyle,
    required this.confidence,
    required this.behavioralScore,
    required this.savingsRate,
    required this.insights,
    required this.optimizationTips,
    required this.riskFactors,
    required this.nextReviewDate,
  });
}

class BudgetOptimization {
  final String category;
  final String description;
  final double potentialSavings;
  final OptimizationType type;
  final double confidence;
  final List<String> actionSteps;

  BudgetOptimization({
    required this.category,
    required this.description,
    required this.potentialSavings,
    required this.type,
    required this.confidence,
    required this.actionSteps,
  });
}

class BudgetInsight {
  final String message;
  final InsightPriority priority;
  final String category;
  final InsightType type;
  final double relevanceScore;

  BudgetInsight({
    required this.message,
    required this.priority,
    required this.category,
    required this.type,
    required this.relevanceScore,
  });
}

class BudgetAdjustment {
  final List<CategoryAdjustment> adjustments;
  final List<BudgetRedistribution> redistributions;
  final double totalImpact;
  final double confidence;
  final List<String> implementationSteps;

  BudgetAdjustment({
    required this.adjustments,
    required this.redistributions,
    required this.totalImpact,
    required this.confidence,
    required this.implementationSteps,
  });
}

class CategoryAdjustment {
  final String category;
  final double currentAmount;
  final double recommendedAmount;
  final String reason;
  final double confidence;
  final AdjustmentUrgency urgency;

  CategoryAdjustment({
    required this.category,
    required this.currentAmount,
    required this.recommendedAmount,
    required this.reason,
    required this.confidence,
    required this.urgency,
  });

  double get impact => (recommendedAmount - currentAmount).abs();
}

class BudgetAllocation {
  final Map<String, double> allocations;
  final double confidence;
  final double behavioralAlignment;
  final List<String> optimizationOpportunities;

  BudgetAllocation({
    required this.allocations,
    required this.confidence,
    required this.behavioralAlignment,
    required this.optimizationOpportunities,
  });
}

enum BudgetStyle { conservative, balanced, aggressive, custom }
enum OptimizationType { reduction, reallocation, increase, behavioral }
enum InsightPriority { low, medium, high, critical }
enum InsightType { warning, opportunity, achievement, information }
enum AdjustmentUrgency { low, medium, high }

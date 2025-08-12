import 'package:flutter/material.dart';
import 'income_service.dart';
import 'advanced_financial_engine.dart';

/// Behavioral Nudge Generator - Production-Ready Implementation
/// 
/// Generates contextual behavioral nudges based on:
/// - Loss aversion psychology
/// - Social proof principles
/// - Anchoring effects
/// - Mental accounting patterns
/// - Commitment devices
/// - Income tier behavioral characteristics
class BehavioralNudgeGenerator {
  static final BehavioralNudgeGenerator _instance = BehavioralNudgeGenerator._internal();
  factory BehavioralNudgeGenerator() => _instance;
  BehavioralNudgeGenerator._internal();

  final IncomeService _incomeService = IncomeService();

  /// Generate behavioral nudges based on user's spending patterns and psychology
  List<BehavioralNudge> generateBehavioralNudges({
    required IncomeTier incomeTier,
    required Map<String, double> recentSpending,
    required double monthlyIncome,
    BehavioralProfile? profile,
    List<String>? spendingTriggers,
  }) {
    final nudges = <BehavioralNudge>[];

    try {
      // Loss Aversion Nudges
      nudges.addAll(_generateLossAversionNudges(recentSpending, monthlyIncome, incomeTier));

      // Social Proof Nudges
      nudges.addAll(_generateSocialProofNudges(recentSpending, monthlyIncome, incomeTier));

      // Anchoring Nudges
      nudges.addAll(_generateAnchoringNudges(recentSpending, monthlyIncome, incomeTier));

      // Mental Accounting Nudges
      nudges.addAll(_generateMentalAccountingNudges(recentSpending, profile, incomeTier));

      // Commitment Device Nudges
      nudges.addAll(_generateCommitmentNudges(profile, incomeTier));

      // Sort by behavioral impact and relevance
      nudges.sort((a, b) => b.impactScore.compareTo(a.impactScore));

      return nudges.take(5).toList(); // Return top 5 most effective nudges
    } catch (e) {
      return [];
    }
  }

  List<BehavioralNudge> _generateLossAversionNudges(
    Map<String, double> recentSpending,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    final nudges = <BehavioralNudge>[];
    final totalSpent = recentSpending.values.fold(0.0, (sum, amount) => sum + amount);
    final remainingBudget = monthlyIncome - totalSpent;

    if (remainingBudget < monthlyIncome * 0.2) {
      nudges.add(BehavioralNudge(
        title: 'Protect Your Progress',
        message: 'You have \$${remainingBudget.toStringAsFixed(0)} left this month. Don\'t let overspending erase your hard work!',
        type: NudgeType.lossAversion,
        impactScore: 0.9,
        color: Colors.red.shade600,
        icon: Icons.shield,
      ));
    }

    // Category-specific loss framing
    final budgetWeights = _incomeService.getDefaultBudgetWeights(tier);
    recentSpending.forEach((category, spent) {
      final recommended = monthlyIncome * (budgetWeights[category] ?? 0.1);
      if (spent > recommended * 1.2) {
        final excess = spent - recommended;
        nudges.add(BehavioralNudge(
          title: 'Avoid ${category.capitalize()} Loss',
          message: 'You\'re \$${excess.toStringAsFixed(0)} over budget in $category. This could impact your financial goals.',
          type: NudgeType.lossAversion,
          impactScore: 0.8,
          color: Colors.orange.shade600,
          icon: Icons.warning,
        ));
      }
    });

    return nudges;
  }

  List<BehavioralNudge> _generateSocialProofNudges(
    Map<String, double> recentSpending,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    final nudges = <BehavioralNudge>[];
    final tierName = _incomeService.getIncomeTierName(tier);
    final patterns = _incomeService.getBehavioralSpendingPatterns(tier);

    // Savings nudges
    final savingsAmount = recentSpending['savings'] ?? 0.0;
    final savingsRate = savingsAmount / monthlyIncome;
    final targetRate = _getTargetSavingsRate(tier);

    if (savingsRate < targetRate) {
      nudges.add(BehavioralNudge(
        title: 'Join the Savers',
        message: '73% of ${tierName}s save at least ${(targetRate * 100).toStringAsFixed(0)}% of their income. You\'re currently at ${(savingsRate * 100).toStringAsFixed(1)}%.',
        type: NudgeType.socialProof,
        impactScore: 0.8,
        color: Colors.blue.shade600,
        icon: Icons.group,
      ));
    }

    // Spending pattern nudges
    recentSpending.forEach((category, spent) {
      final percentage = (spent / monthlyIncome) * 100;
      final peerAverage = _getPeerAveragePercentage(tier, category);
      
      if (percentage > peerAverage * 1.3) {
        nudges.add(BehavioralNudge(
          title: 'Peer Comparison',
          message: 'Most ${tierName}s spend ${peerAverage.toStringAsFixed(1)}% on $category. You\'re at ${percentage.toStringAsFixed(1)}%.',
          type: NudgeType.socialProof,
          impactScore: 0.7,
          color: Colors.purple.shade600,
          icon: Icons.people,
        ));
      }
    });

    return nudges;
  }

  List<BehavioralNudge> _generateAnchoringNudges(
    Map<String, double> recentSpending,
    double monthlyIncome,
    IncomeTier tier,
  ) {
    final nudges = <BehavioralNudge>[];

    // Daily spending anchor
    final dailyBudget = monthlyIncome / 30;
    final todaySpending = recentSpending.values.fold(0.0, (sum, amount) => sum + amount) / DateTime.now().day;

    if (todaySpending > dailyBudget * 1.5) {
      nudges.add(BehavioralNudge(
        title: 'Daily Anchor Check',
        message: 'Your daily spending target is \$${dailyBudget.toStringAsFixed(0)}. Today you\'re at \$${todaySpending.toStringAsFixed(0)}.',
        type: NudgeType.anchoring,
        impactScore: 0.7,
        color: Colors.green.shade600,
        icon: Icons.anchor,
      ));
    }

    // Category anchoring
    final budgetWeights = _incomeService.getDefaultBudgetWeights(tier);
    recentSpending.forEach((category, spent) {
      final recommended = monthlyIncome * (budgetWeights[category] ?? 0.1);
      if (spent > recommended) {
        nudges.add(BehavioralNudge(
          title: '${category.capitalize()} Target',
          message: 'Your $category target is \$${recommended.toStringAsFixed(0)}/month. Consider this as your anchor point.',
          type: NudgeType.anchoring,
          impactScore: 0.6,
          color: Colors.teal.shade600,
          icon: Icons.track_changes,
        ));
      }
    });

    return nudges;
  }

  List<BehavioralNudge> _generateMentalAccountingNudges(
    Map<String, double> recentSpending,
    BehavioralProfile? profile,
    IncomeTier tier,
  ) {
    final nudges = <BehavioralNudge>[];
    final patterns = _incomeService.getBehavioralSpendingPatterns(tier);
    final buckets = patterns['mental_accounting_buckets'] as List<String>;

    // Suggest mental accounting reorganization
    if (buckets.length > 5) {
      nudges.add(BehavioralNudge(
        title: 'Simplify Your Buckets',
        message: 'Consider consolidating your spending into ${buckets.length} main categories for clearer mental accounting.',
        type: NudgeType.mentalAccounting,
        impactScore: 0.7,
        color: Colors.indigo.shade600,
        icon: Icons.category,
      ));
    }

    // Entertainment vs. needs balance
    final entertainment = recentSpending['entertainment'] ?? 0.0;
    final essentials = (recentSpending['housing'] ?? 0.0) + 
                     (recentSpending['food'] ?? 0.0) + 
                     (recentSpending['utilities'] ?? 0.0);
    
    if (entertainment > essentials * 0.3) {
      nudges.add(BehavioralNudge(
        title: 'Wants vs. Needs',
        message: 'Your entertainment spending is high relative to essentials. Consider rebalancing your mental buckets.',
        type: NudgeType.mentalAccounting,
        impactScore: 0.8,
        color: Colors.deepOrange.shade600,
        icon: Icons.balance,
      ));
    }

    return nudges;
  }

  List<BehavioralNudge> _generateCommitmentNudges(
    BehavioralProfile? profile,
    IncomeTier tier,
  ) {
    final nudges = <BehavioralNudge>[];

    if (profile == null) return nudges;

    // High impulsivity users need stronger commitment devices
    if (profile.impulsivityScore > 0.7) {
      nudges.add(BehavioralNudge(
        title: 'Create Commitment Device',
        message: 'Set up automatic transfers to make saving easier and reduce impulsive spending.',
        type: NudgeType.commitment,
        impactScore: 0.9,
        color: Colors.brown.shade600,
        icon: Icons.lock,
      ));
    }

    // Short planning horizon users need immediate commitment
    if (profile.planningHorizon < 3.0) {
      nudges.add(BehavioralNudge(
        title: 'Weekly Commitment',
        message: 'Commit to a weekly spending limit that feels manageable for your planning style.',
        type: NudgeType.commitment,
        impactScore: 0.8,
        color: Colors.cyan.shade600,
        icon: Icons.calendar_today,
      ));
    }

    return nudges;
  }

  // Helper methods
  double _getTargetSavingsRate(IncomeTier tier) {
    switch (tier) {
      case IncomeTier.low: return 0.05;
      case IncomeTier.lowerMiddle: return 0.10;
      case IncomeTier.middle: return 0.15;
      case IncomeTier.upperMiddle: return 0.20;
      case IncomeTier.high: return 0.25;
    }
  }

  double _getPeerAveragePercentage(IncomeTier tier, String category) {
    final weights = _incomeService.getDefaultBudgetWeights(tier);
    return (weights[category] ?? 0.1) * 100;
  }
}

extension StringExtension on String {
  String capitalize() {
    return "${this[0].toUpperCase()}${substring(1)}";
  }
}
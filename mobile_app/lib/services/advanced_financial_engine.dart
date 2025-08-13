import 'package:flutter/foundation.dart';

/// Advanced Financial Engine stub implementation
class AdvancedFinancialEngine extends ChangeNotifier {
  AdvancedFinancialEngine();
}

/// Financial Goal data class
class FinancialGoal {
  final String id;
  final String title;
  final String category;
  final double targetAmount;
  final double currentAmount;
  final double monthlyContribution;
  final DateTime targetDate;
  final bool isActive;

  FinancialGoal({
    required this.id,
    required this.title,
    required this.category,
    required this.targetAmount,
    required this.currentAmount,
    required this.monthlyContribution,
    required this.targetDate,
    required this.isActive,
  });
}

/// Behavioral Profile data class
class BehavioralProfile {
  final String riskTolerance;
  final String spendingPattern;
  final String motivationType;

  BehavioralProfile({
    required this.riskTolerance,
    required this.spendingPattern,
    required this.motivationType,
  });
}
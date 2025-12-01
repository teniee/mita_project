import 'package:flutter/foundation.dart';

/// Enums

/// Category of the installment purchase
enum InstallmentCategory {
  electronics,
  clothing,
  furniture,
  travel,
  education,
  health,
  groceries,
  utilities,
  other;

  String toJson() => name;

  static InstallmentCategory fromJson(String json) {
    return InstallmentCategory.values.firstWhere(
      (e) => e.name == json,
      orElse: () => InstallmentCategory.other,
    );
  }

  String get displayName {
    switch (this) {
      case InstallmentCategory.electronics:
        return 'Electronics';
      case InstallmentCategory.clothing:
        return 'Clothing';
      case InstallmentCategory.furniture:
        return 'Furniture';
      case InstallmentCategory.travel:
        return 'Travel';
      case InstallmentCategory.education:
        return 'Education';
      case InstallmentCategory.health:
        return 'Health';
      case InstallmentCategory.groceries:
        return 'Groceries';
      case InstallmentCategory.utilities:
        return 'Utilities';
      case InstallmentCategory.other:
        return 'Other';
    }
  }
}

/// Age group classification for financial profiling
enum AgeGroup {
  age18_24,
  age25_34,
  age35_44,
  age45Plus;

  String toJson() {
    switch (this) {
      case AgeGroup.age18_24:
        return '18-24';
      case AgeGroup.age25_34:
        return '25-34';
      case AgeGroup.age35_44:
        return '35-44';
      case AgeGroup.age45Plus:
        return '45+';
    }
  }

  static AgeGroup fromJson(String json) {
    switch (json) {
      case '18-24':
        return AgeGroup.age18_24;
      case '25-34':
        return AgeGroup.age25_34;
      case '35-44':
        return AgeGroup.age35_44;
      case '45+':
        return AgeGroup.age45Plus;
      default:
        return AgeGroup.age25_34;
    }
  }

  String get displayName {
    switch (this) {
      case AgeGroup.age18_24:
        return '18-24';
      case AgeGroup.age25_34:
        return '25-34';
      case AgeGroup.age35_44:
        return '35-44';
      case AgeGroup.age45Plus:
        return '45+';
    }
  }
}

/// Risk level assessment for installment decisions
enum RiskLevel {
  green,
  yellow,
  orange,
  red;

  String toJson() => name;

  static RiskLevel fromJson(String json) {
    return RiskLevel.values.firstWhere(
      (e) => e.name == json,
      orElse: () => RiskLevel.yellow,
    );
  }

  String get displayName {
    switch (this) {
      case RiskLevel.green:
        return 'Low Risk';
      case RiskLevel.yellow:
        return 'Moderate Risk';
      case RiskLevel.orange:
        return 'High Risk';
      case RiskLevel.red:
        return 'Critical Risk';
    }
  }
}

/// Status of an installment plan
enum InstallmentStatus {
  active,
  completed,
  cancelled,
  overdue;

  String toJson() => name;

  static InstallmentStatus fromJson(String json) {
    return InstallmentStatus.values.firstWhere(
      (e) => e.name == json,
      orElse: () => InstallmentStatus.active,
    );
  }

  String get displayName {
    switch (this) {
      case InstallmentStatus.active:
        return 'Active';
      case InstallmentStatus.completed:
        return 'Completed';
      case InstallmentStatus.cancelled:
        return 'Cancelled';
      case InstallmentStatus.overdue:
        return 'Overdue';
    }
  }

  bool get isActive => this == InstallmentStatus.active;
  bool get isCompleted => this == InstallmentStatus.completed;
  bool get isCancelled => this == InstallmentStatus.cancelled;
  bool get isOverdue => this == InstallmentStatus.overdue;
}

/// Models

/// User's financial profile for installment calculations
@immutable
class UserFinancialProfile {
  final String id;
  final String userId;
  final double? monthlyIncome;
  final double? currentBalance;
  final AgeGroup? ageGroup;
  final double? creditCardDebt;
  final double? creditCardPayment;
  final double? otherLoansPayment;
  final double? rentPayment;
  final double? subscriptionsPayment;
  final bool planningMortgage;
  final DateTime updatedAt;

  const UserFinancialProfile({
    required this.id,
    required this.userId,
    this.monthlyIncome,
    this.currentBalance,
    this.ageGroup,
    this.creditCardDebt,
    this.creditCardPayment,
    this.otherLoansPayment,
    this.rentPayment,
    this.subscriptionsPayment,
    this.planningMortgage = false,
    required this.updatedAt,
  });

  factory UserFinancialProfile.fromJson(Map<String, dynamic> json) {
    return UserFinancialProfile(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      monthlyIncome: json['monthly_income'] != null
          ? (json['monthly_income'] as num).toDouble()
          : null,
      currentBalance: json['current_balance'] != null
          ? (json['current_balance'] as num).toDouble()
          : null,
      ageGroup: json['age_group'] != null
          ? AgeGroup.fromJson(json['age_group'] as String)
          : null,
      creditCardDebt: json['credit_card_debt'] != null
          ? (json['credit_card_debt'] as num).toDouble()
          : null,
      creditCardPayment: json['credit_card_payment'] != null
          ? (json['credit_card_payment'] as num).toDouble()
          : null,
      otherLoansPayment: json['other_loans_payment'] != null
          ? (json['other_loans_payment'] as num).toDouble()
          : null,
      rentPayment: json['rent_payment'] != null
          ? (json['rent_payment'] as num).toDouble()
          : null,
      subscriptionsPayment: json['subscriptions_payment'] != null
          ? (json['subscriptions_payment'] as num).toDouble()
          : null,
      planningMortgage: json['planning_mortgage'] as bool? ?? false,
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'monthly_income': monthlyIncome,
      'current_balance': currentBalance,
      'age_group': ageGroup?.toJson(),
      'credit_card_debt': creditCardDebt,
      'credit_card_payment': creditCardPayment,
      'other_loans_payment': otherLoansPayment,
      'rent_payment': rentPayment,
      'subscriptions_payment': subscriptionsPayment,
      'planning_mortgage': planningMortgage,
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  UserFinancialProfile copyWith({
    String? id,
    String? userId,
    double? monthlyIncome,
    double? currentBalance,
    AgeGroup? ageGroup,
    double? creditCardDebt,
    double? creditCardPayment,
    double? otherLoansPayment,
    double? rentPayment,
    double? subscriptionsPayment,
    bool? planningMortgage,
    DateTime? updatedAt,
  }) {
    return UserFinancialProfile(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      monthlyIncome: monthlyIncome ?? this.monthlyIncome,
      currentBalance: currentBalance ?? this.currentBalance,
      ageGroup: ageGroup ?? this.ageGroup,
      creditCardDebt: creditCardDebt ?? this.creditCardDebt,
      creditCardPayment: creditCardPayment ?? this.creditCardPayment,
      otherLoansPayment: otherLoansPayment ?? this.otherLoansPayment,
      rentPayment: rentPayment ?? this.rentPayment,
      subscriptionsPayment: subscriptionsPayment ?? this.subscriptionsPayment,
      planningMortgage: planningMortgage ?? this.planningMortgage,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// Calculate total monthly obligations
  double get totalMonthlyObligations {
    return (creditCardPayment ?? 0) +
        (otherLoansPayment ?? 0) +
        (rentPayment ?? 0) +
        (subscriptionsPayment ?? 0);
  }

  /// Check if profile has sufficient data for calculations
  bool get hasCompleteProfile {
    return monthlyIncome != null && currentBalance != null && ageGroup != null;
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is UserFinancialProfile &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          userId == other.userId;

  @override
  int get hashCode => id.hashCode ^ userId.hashCode;
}

/// Risk factor identified during installment calculation
@immutable
class RiskFactor {
  final String factor;
  final String severity;
  final String message;
  final String? stat;

  const RiskFactor({
    required this.factor,
    required this.severity,
    required this.message,
    this.stat,
  });

  factory RiskFactor.fromJson(Map<String, dynamic> json) {
    return RiskFactor(
      factor: json['factor'] as String,
      severity: json['severity'] as String,
      message: json['message'] as String,
      stat: json['stat'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'factor': factor,
      'severity': severity,
      'message': message,
      if (stat != null) 'stat': stat,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RiskFactor &&
          runtimeType == other.runtimeType &&
          factor == other.factor &&
          severity == other.severity &&
          message == other.message &&
          stat == other.stat;

  @override
  int get hashCode =>
      factor.hashCode ^ severity.hashCode ^ message.hashCode ^ stat.hashCode;
}

/// Alternative recommendation for an installment purchase
@immutable
class AlternativeRecommendation {
  final String recommendationType;
  final String title;
  final String description;
  final double? savingsAmount;
  final int? timeNeededDays;

  const AlternativeRecommendation({
    required this.recommendationType,
    required this.title,
    required this.description,
    this.savingsAmount,
    this.timeNeededDays,
  });

  factory AlternativeRecommendation.fromJson(Map<String, dynamic> json) {
    return AlternativeRecommendation(
      recommendationType: json['recommendation_type'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      savingsAmount: json['savings_amount'] != null
          ? (json['savings_amount'] as num).toDouble()
          : null,
      timeNeededDays: json['time_needed_days'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recommendation_type': recommendationType,
      'title': title,
      'description': description,
      if (savingsAmount != null) 'savings_amount': savingsAmount,
      if (timeNeededDays != null) 'time_needed_days': timeNeededDays,
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AlternativeRecommendation &&
          runtimeType == other.runtimeType &&
          recommendationType == other.recommendationType &&
          title == other.title;

  @override
  int get hashCode => recommendationType.hashCode ^ title.hashCode;
}

/// Input for installment calculator
@immutable
class InstallmentCalculatorInput {
  final double purchaseAmount;
  final InstallmentCategory category;
  final int numPayments;
  final double interestRate;
  final double? monthlyIncome;
  final double? currentBalance;
  final AgeGroup? ageGroup;
  final int activeInstallmentsCount;
  final double activeInstallmentsMonthly;
  final double creditCardDebt;
  final double otherMonthlyObligations;
  final bool planningMortgage;

  const InstallmentCalculatorInput({
    required this.purchaseAmount,
    required this.category,
    required this.numPayments,
    required this.interestRate,
    this.monthlyIncome,
    this.currentBalance,
    this.ageGroup,
    this.activeInstallmentsCount = 0,
    this.activeInstallmentsMonthly = 0.0,
    this.creditCardDebt = 0.0,
    this.otherMonthlyObligations = 0.0,
    this.planningMortgage = false,
  });

  Map<String, dynamic> toJson() {
    return {
      'purchase_amount': purchaseAmount,
      'category': category.toJson(),
      'num_payments': numPayments,
      'interest_rate': interestRate,
      if (monthlyIncome != null) 'monthly_income': monthlyIncome,
      if (currentBalance != null) 'current_balance': currentBalance,
      if (ageGroup != null) 'age_group': ageGroup!.toJson(),
      'active_installments_count': activeInstallmentsCount,
      'active_installments_monthly': activeInstallmentsMonthly,
      'credit_card_debt': creditCardDebt,
      'other_monthly_obligations': otherMonthlyObligations,
      'planning_mortgage': planningMortgage,
    };
  }

  InstallmentCalculatorInput copyWith({
    double? purchaseAmount,
    InstallmentCategory? category,
    int? numPayments,
    double? interestRate,
    double? monthlyIncome,
    double? currentBalance,
    AgeGroup? ageGroup,
    int? activeInstallmentsCount,
    double? activeInstallmentsMonthly,
    double? creditCardDebt,
    double? otherMonthlyObligations,
    bool? planningMortgage,
  }) {
    return InstallmentCalculatorInput(
      purchaseAmount: purchaseAmount ?? this.purchaseAmount,
      category: category ?? this.category,
      numPayments: numPayments ?? this.numPayments,
      interestRate: interestRate ?? this.interestRate,
      monthlyIncome: monthlyIncome ?? this.monthlyIncome,
      currentBalance: currentBalance ?? this.currentBalance,
      ageGroup: ageGroup ?? this.ageGroup,
      activeInstallmentsCount:
          activeInstallmentsCount ?? this.activeInstallmentsCount,
      activeInstallmentsMonthly:
          activeInstallmentsMonthly ?? this.activeInstallmentsMonthly,
      creditCardDebt: creditCardDebt ?? this.creditCardDebt,
      otherMonthlyObligations:
          otherMonthlyObligations ?? this.otherMonthlyObligations,
      planningMortgage: planningMortgage ?? this.planningMortgage,
    );
  }
}

/// Output from installment calculator
@immutable
class InstallmentCalculatorOutput {
  final RiskLevel riskLevel;
  final double riskScore;
  final String verdict;
  final double monthlyPayment;
  final double totalInterest;
  final double totalCost;
  final double firstPaymentAmount;
  final List<Map<String, dynamic>> paymentSchedule;
  final double? dtiRatio;
  final double? paymentToIncomeRatio;
  final double? remainingMonthlyFunds;
  final double? balanceAfterFirstPayment;
  final List<RiskFactor> riskFactors;
  final String personalizedMessage;
  final AlternativeRecommendation? alternativeRecommendation;
  final List<String> warnings;
  final List<String> tips;
  final List<String> statistics;
  final double? potentialLateFee;
  final double? potentialOverdraft;
  final String? hiddenCostMessage;

  const InstallmentCalculatorOutput({
    required this.riskLevel,
    required this.riskScore,
    required this.verdict,
    required this.monthlyPayment,
    required this.totalInterest,
    required this.totalCost,
    required this.firstPaymentAmount,
    required this.paymentSchedule,
    this.dtiRatio,
    this.paymentToIncomeRatio,
    this.remainingMonthlyFunds,
    this.balanceAfterFirstPayment,
    required this.riskFactors,
    required this.personalizedMessage,
    this.alternativeRecommendation,
    required this.warnings,
    required this.tips,
    required this.statistics,
    this.potentialLateFee,
    this.potentialOverdraft,
    this.hiddenCostMessage,
  });

  factory InstallmentCalculatorOutput.fromJson(Map<String, dynamic> json) {
    return InstallmentCalculatorOutput(
      riskLevel: RiskLevel.fromJson(json['risk_level'] as String),
      riskScore: (json['risk_score'] as num).toDouble(),
      verdict: json['verdict'] as String,
      monthlyPayment: (json['monthly_payment'] as num).toDouble(),
      totalInterest: (json['total_interest'] as num).toDouble(),
      totalCost: (json['total_cost'] as num).toDouble(),
      firstPaymentAmount: (json['first_payment_amount'] as num).toDouble(),
      paymentSchedule: (json['payment_schedule'] as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList(),
      dtiRatio: json['dti_ratio'] != null
          ? (json['dti_ratio'] as num).toDouble()
          : null,
      paymentToIncomeRatio: json['payment_to_income_ratio'] != null
          ? (json['payment_to_income_ratio'] as num).toDouble()
          : null,
      remainingMonthlyFunds: json['remaining_monthly_funds'] != null
          ? (json['remaining_monthly_funds'] as num).toDouble()
          : null,
      balanceAfterFirstPayment: json['balance_after_first_payment'] != null
          ? (json['balance_after_first_payment'] as num).toDouble()
          : null,
      riskFactors: (json['risk_factors'] as List)
          .map((e) => RiskFactor.fromJson(e as Map<String, dynamic>))
          .toList(),
      personalizedMessage: json['personalized_message'] as String,
      alternativeRecommendation: json['alternative_recommendation'] != null
          ? AlternativeRecommendation.fromJson(
              json['alternative_recommendation'] as Map<String, dynamic>)
          : null,
      warnings: (json['warnings'] as List).map((e) => e as String).toList(),
      tips: (json['tips'] as List).map((e) => e as String).toList(),
      statistics: (json['statistics'] as List).map((e) => e as String).toList(),
      potentialLateFee: json['potential_late_fee'] != null
          ? (json['potential_late_fee'] as num).toDouble()
          : null,
      potentialOverdraft: json['potential_overdraft'] != null
          ? (json['potential_overdraft'] as num).toDouble()
          : null,
      hiddenCostMessage: json['hidden_cost_message'] as String?,
    );
  }

  /// Check if the recommendation is to proceed with the installment
  bool get shouldProceed =>
      riskLevel == RiskLevel.green || riskLevel == RiskLevel.yellow;

  /// Check if there are critical warnings
  bool get hasCriticalWarnings => riskLevel == RiskLevel.red;

  /// Check if there are high risk factors
  bool get hasHighRisk =>
      riskLevel == RiskLevel.orange || riskLevel == RiskLevel.red;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is InstallmentCalculatorOutput &&
          runtimeType == other.runtimeType &&
          riskLevel == other.riskLevel &&
          verdict == other.verdict;

  @override
  int get hashCode => riskLevel.hashCode ^ verdict.hashCode;
}

/// Installment payment plan
@immutable
class Installment {
  final String id;
  final String userId;
  final String itemName;
  final InstallmentCategory category;
  final double totalAmount;
  final double paymentAmount;
  final double interestRate;
  final int totalPayments;
  final int paymentsMade;
  final String paymentFrequency;
  final DateTime firstPaymentDate;
  final DateTime nextPaymentDate;
  final DateTime finalPaymentDate;
  final InstallmentStatus status;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Installment({
    required this.id,
    required this.userId,
    required this.itemName,
    required this.category,
    required this.totalAmount,
    required this.paymentAmount,
    required this.interestRate,
    required this.totalPayments,
    required this.paymentsMade,
    required this.paymentFrequency,
    required this.firstPaymentDate,
    required this.nextPaymentDate,
    required this.finalPaymentDate,
    required this.status,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Installment.fromJson(Map<String, dynamic> json) {
    return Installment(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      itemName: json['item_name'] as String,
      category: InstallmentCategory.fromJson(json['category'] as String),
      totalAmount: (json['total_amount'] as num).toDouble(),
      paymentAmount: (json['payment_amount'] as num).toDouble(),
      interestRate: (json['interest_rate'] as num).toDouble(),
      totalPayments: json['total_payments'] as int,
      paymentsMade: json['payments_made'] as int,
      paymentFrequency: json['payment_frequency'] as String,
      firstPaymentDate: DateTime.parse(json['first_payment_date'] as String),
      nextPaymentDate: DateTime.parse(json['next_payment_date'] as String),
      finalPaymentDate: DateTime.parse(json['final_payment_date'] as String),
      status: InstallmentStatus.fromJson(json['status'] as String),
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'item_name': itemName,
      'category': category.toJson(),
      'total_amount': totalAmount,
      'payment_amount': paymentAmount,
      'interest_rate': interestRate,
      'total_payments': totalPayments,
      'payments_made': paymentsMade,
      'payment_frequency': paymentFrequency,
      'first_payment_date': firstPaymentDate.toIso8601String(),
      'next_payment_date': nextPaymentDate.toIso8601String(),
      'final_payment_date': finalPaymentDate.toIso8601String(),
      'status': status.toJson(),
      if (notes != null) 'notes': notes,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  Installment copyWith({
    String? id,
    String? userId,
    String? itemName,
    InstallmentCategory? category,
    double? totalAmount,
    double? paymentAmount,
    double? interestRate,
    int? totalPayments,
    int? paymentsMade,
    String? paymentFrequency,
    DateTime? firstPaymentDate,
    DateTime? nextPaymentDate,
    DateTime? finalPaymentDate,
    InstallmentStatus? status,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Installment(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      itemName: itemName ?? this.itemName,
      category: category ?? this.category,
      totalAmount: totalAmount ?? this.totalAmount,
      paymentAmount: paymentAmount ?? this.paymentAmount,
      interestRate: interestRate ?? this.interestRate,
      totalPayments: totalPayments ?? this.totalPayments,
      paymentsMade: paymentsMade ?? this.paymentsMade,
      paymentFrequency: paymentFrequency ?? this.paymentFrequency,
      firstPaymentDate: firstPaymentDate ?? this.firstPaymentDate,
      nextPaymentDate: nextPaymentDate ?? this.nextPaymentDate,
      finalPaymentDate: finalPaymentDate ?? this.finalPaymentDate,
      status: status ?? this.status,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  // Calculated fields

  /// Progress percentage (0-100)
  double get progressPercentage {
    if (totalPayments == 0) return 0;
    return (paymentsMade / totalPayments * 100).clamp(0, 100);
  }

  /// Number of remaining payments
  int get remainingPayments {
    return (totalPayments - paymentsMade).clamp(0, totalPayments);
  }

  /// Total amount paid so far
  double get totalPaid {
    return paymentAmount * paymentsMade;
  }

  /// Remaining balance to be paid
  double get remainingBalance {
    return totalAmount - totalPaid;
  }

  /// Check if the next payment is due soon (within 7 days)
  bool get isPaymentDueSoon {
    final now = DateTime.now();
    final daysUntilPayment = nextPaymentDate.difference(now).inDays;
    return daysUntilPayment >= 0 && daysUntilPayment <= 7;
  }

  /// Check if the installment is overdue
  bool get isOverdue {
    return status.isOverdue || DateTime.now().isAfter(nextPaymentDate);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Installment &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          userId == other.userId;

  @override
  int get hashCode => id.hashCode ^ userId.hashCode;
}

/// Summary of user's installments
@immutable
class InstallmentsSummary {
  final int totalActive;
  final int totalCompleted;
  final double totalMonthlyPayment;
  final DateTime? nextPaymentDate;
  final double? nextPaymentAmount;
  final List<Installment> installments;
  final double currentInstallmentLoad;
  final String loadMessage;

  const InstallmentsSummary({
    required this.totalActive,
    required this.totalCompleted,
    required this.totalMonthlyPayment,
    this.nextPaymentDate,
    this.nextPaymentAmount,
    required this.installments,
    required this.currentInstallmentLoad,
    required this.loadMessage,
  });

  factory InstallmentsSummary.fromJson(Map<String, dynamic> json) {
    return InstallmentsSummary(
      totalActive: json['total_active'] as int,
      totalCompleted: json['total_completed'] as int,
      totalMonthlyPayment: (json['total_monthly_payment'] as num).toDouble(),
      nextPaymentDate: json['next_payment_date'] != null
          ? DateTime.parse(json['next_payment_date'] as String)
          : null,
      nextPaymentAmount: json['next_payment_amount'] != null
          ? (json['next_payment_amount'] as num).toDouble()
          : null,
      installments: (json['installments'] as List)
          .map((e) => Installment.fromJson(e as Map<String, dynamic>))
          .toList(),
      currentInstallmentLoad:
          (json['current_installment_load'] as num).toDouble(),
      loadMessage: json['load_message'] as String,
    );
  }

  /// Get only active installments
  List<Installment> get activeInstallments {
    return installments.where((i) => i.status.isActive).toList();
  }

  /// Get only completed installments
  List<Installment> get completedInstallments {
    return installments.where((i) => i.status.isCompleted).toList();
  }

  /// Get overdue installments
  List<Installment> get overdueInstallments {
    return installments.where((i) => i.isOverdue).toList();
  }

  /// Check if any payment is due soon
  bool get hasPaymentDueSoon {
    return installments.any((i) => i.isPaymentDueSoon);
  }

  /// Check if there are any overdue payments
  bool get hasOverduePayments {
    return overdueInstallments.isNotEmpty;
  }

  /// Total number of installments
  int get totalInstallments => installments.length;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is InstallmentsSummary &&
          runtimeType == other.runtimeType &&
          totalActive == other.totalActive &&
          totalCompleted == other.totalCompleted;

  @override
  int get hashCode => totalActive.hashCode ^ totalCompleted.hashCode;
}

/// User's installment achievements and statistics
@immutable
class InstallmentAchievement {
  final String id;
  final String userId;
  final int installmentsCompleted;
  final int calculationsPerformed;
  final int calculationsDeclined;
  final int daysWithoutNewInstallment;
  final int maxDaysStreak;
  final double interestSaved;
  final String achievementLevel;
  final DateTime? lastCalculationDate;
  final DateTime updatedAt;

  const InstallmentAchievement({
    required this.id,
    required this.userId,
    required this.installmentsCompleted,
    required this.calculationsPerformed,
    required this.calculationsDeclined,
    required this.daysWithoutNewInstallment,
    required this.maxDaysStreak,
    required this.interestSaved,
    required this.achievementLevel,
    this.lastCalculationDate,
    required this.updatedAt,
  });

  factory InstallmentAchievement.fromJson(Map<String, dynamic> json) {
    return InstallmentAchievement(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      installmentsCompleted: json['installments_completed'] as int,
      calculationsPerformed: json['calculations_performed'] as int,
      calculationsDeclined: json['calculations_declined'] as int,
      daysWithoutNewInstallment: json['days_without_new_installment'] as int,
      maxDaysStreak: json['max_days_streak'] as int,
      interestSaved: (json['interest_saved'] as num).toDouble(),
      achievementLevel: json['achievement_level'] as String,
      lastCalculationDate: json['last_calculation_date'] != null
          ? DateTime.parse(json['last_calculation_date'] as String)
          : null,
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'installments_completed': installmentsCompleted,
      'calculations_performed': calculationsPerformed,
      'calculations_declined': calculationsDeclined,
      'days_without_new_installment': daysWithoutNewInstallment,
      'max_days_streak': maxDaysStreak,
      'interest_saved': interestSaved,
      'achievement_level': achievementLevel,
      if (lastCalculationDate != null)
        'last_calculation_date': lastCalculationDate!.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  /// Calculate the decline rate (percentage of calculations declined)
  double get declineRate {
    if (calculationsPerformed == 0) return 0;
    return (calculationsDeclined / calculationsPerformed * 100).clamp(0, 100);
  }

  /// Check if the user is on a good streak
  bool get isOnGoodStreak => daysWithoutNewInstallment >= 7;

  /// Check if the user has reached a milestone
  bool get hasCompletedInstallments => installmentsCompleted > 0;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is InstallmentAchievement &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          userId == other.userId;

  @override
  int get hashCode => id.hashCode ^ userId.hashCode;
}

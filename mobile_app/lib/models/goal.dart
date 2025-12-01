/// MODULE 5: Budgeting Goals - Goal Model
/// Complete model for budgeting goals with all fields and methods

class Goal {
  final String id;
  final String title;
  final String? description;
  final String? category;
  final double targetAmount;
  final double savedAmount;
  final double? monthlyContribution;
  final String status; // active, completed, paused, cancelled
  final double progress; // 0-100
  final DateTime? targetDate;
  final DateTime createdAt;
  final DateTime lastUpdated;
  final DateTime? completedAt;
  final String? priority; // high, medium, low

  Goal({
    required this.id,
    required this.title,
    this.description,
    this.category,
    required this.targetAmount,
    required this.savedAmount,
    this.monthlyContribution,
    this.status = 'active',
    this.progress = 0.0,
    this.targetDate,
    required this.createdAt,
    required this.lastUpdated,
    this.completedAt,
    this.priority = 'medium',
  });

  /// Create Goal from JSON (API response)
  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String?,
      category: json['category'] as String?,
      targetAmount: _parseDouble(json['target_amount']),
      savedAmount: _parseDouble(json['saved_amount'] ?? json['current_amount']),
      monthlyContribution: json['monthly_contribution'] != null
          ? _parseDouble(json['monthly_contribution'])
          : null,
      status: json['status'] as String? ?? 'active',
      progress: _parseDouble(json['progress'] ?? 0),
      targetDate: json['target_date'] != null
          ? DateTime.parse(json['target_date'] as String)
          : (json['deadline'] != null
              ? DateTime.parse(json['deadline'] as String)
              : null),
      createdAt: DateTime.parse(json['created_at'] as String),
      lastUpdated: DateTime.parse(json['last_updated'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      priority: json['priority'] as String? ?? 'medium',
    );
  }

  /// Convert Goal to JSON (for API requests)
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'category': category,
      'target_amount': targetAmount,
      'saved_amount': savedAmount,
      'monthly_contribution': monthlyContribution,
      'status': status,
      'progress': progress,
      'target_date': targetDate?.toIso8601String().split('T')[0],
      'priority': priority,
    };
  }

  /// Helper to parse numbers from API (handles both int and double)
  static double _parseDouble(dynamic value) {
    if (value == null) return 0.0;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }

  /// Calculate remaining amount to reach goal
  double get remainingAmount =>
      (targetAmount - savedAmount).clamp(0, double.infinity);

  /// Check if goal is completed
  bool get isCompleted => status == 'completed' || progress >= 100;

  /// Check if goal is overdue
  bool get isOverdue {
    if (targetDate == null || isCompleted) return false;
    return targetDate!.isBefore(DateTime.now());
  }

  /// Get days until target date
  int? get daysUntilTarget {
    if (targetDate == null) return null;
    return targetDate!.difference(DateTime.now()).inDays;
  }

  /// Get status color based on progress and deadline
  String get statusColor {
    if (isCompleted) return 'green';
    if (isOverdue) return 'red';
    if (progress >= 70) return 'yellow';
    return 'blue';
  }

  /// Get progress percentage as string
  String get progressPercentage => '${progress.toStringAsFixed(0)}%';

  /// Get formatted target amount
  String get formattedTargetAmount => '\$${targetAmount.toStringAsFixed(0)}';

  /// Get formatted saved amount
  String get formattedSavedAmount => '\$${savedAmount.toStringAsFixed(0)}';

  /// Get formatted remaining amount
  String get formattedRemainingAmount =>
      '\$${remainingAmount.toStringAsFixed(0)}';

  /// Get formatted monthly contribution
  String? get formattedMonthlyContribution => monthlyContribution != null
      ? '\$${monthlyContribution!.toStringAsFixed(0)}'
      : null;

  /// Copy with method for updating fields
  Goal copyWith({
    String? id,
    String? title,
    String? description,
    String? category,
    double? targetAmount,
    double? savedAmount,
    double? monthlyContribution,
    String? status,
    double? progress,
    DateTime? targetDate,
    DateTime? createdAt,
    DateTime? lastUpdated,
    DateTime? completedAt,
    String? priority,
  }) {
    return Goal(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      category: category ?? this.category,
      targetAmount: targetAmount ?? this.targetAmount,
      savedAmount: savedAmount ?? this.savedAmount,
      monthlyContribution: monthlyContribution ?? this.monthlyContribution,
      status: status ?? this.status,
      progress: progress ?? this.progress,
      targetDate: targetDate ?? this.targetDate,
      createdAt: createdAt ?? this.createdAt,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      completedAt: completedAt ?? this.completedAt,
      priority: priority ?? this.priority,
    );
  }

  @override
  String toString() {
    return 'Goal(id: $id, title: $title, progress: $progressPercentage, status: $status)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Goal && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;
}

/// Goal categories available in the app
class GoalCategories {
  static const String savings = 'Savings';
  static const String travel = 'Travel';
  static const String emergency = 'Emergency';
  static const String technology = 'Technology';
  static const String education = 'Education';
  static const String health = 'Health';
  static const String home = 'Home';
  static const String vehicle = 'Vehicle';
  static const String investment = 'Investment';
  static const String other = 'Other';

  static List<String> get all => [
        savings,
        travel,
        emergency,
        technology,
        education,
        health,
        home,
        vehicle,
        investment,
        other,
      ];
}

/// Goal priorities
class GoalPriorities {
  static const String high = 'high';
  static const String medium = 'medium';
  static const String low = 'low';

  static List<String> get all => [high, medium, low];
}

/// Goal statuses
class GoalStatuses {
  static const String active = 'active';
  static const String completed = 'completed';
  static const String paused = 'paused';
  static const String cancelled = 'cancelled';

  static List<String> get all => [active, completed, paused, cancelled];
}

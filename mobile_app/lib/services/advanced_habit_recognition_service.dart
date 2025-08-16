import 'dart:math';
import '../models/budget_intelligence_models.dart';

/// Advanced AI-powered habit recognition and behavioral analysis system
class AdvancedHabitRecognitionService {
  static final AdvancedHabitRecognitionService _instance = AdvancedHabitRecognitionService._internal();
  factory AdvancedHabitRecognitionService() => _instance;
  AdvancedHabitRecognitionService._internal();

  /// Analyze spending habits from transaction history using behavioral patterns
  Future<HabitAnalysisResult> analyzeSpendingHabits(
    List<Map<String, dynamic>> transactionHistory,
  ) async {
    if (transactionHistory.isEmpty) {
      return HabitAnalysisResult(
        detectedHabits: [],
        categoryRiskScores: {},
        recommendations: ['Insufficient transaction history for habit analysis'],
        overallHabitScore: 0.5,
        insights: {'dataQuality': 'insufficient'},
      );
    }

    // Detect various spending habits
    final detectedHabits = <DetectedHabit>[];
    
    // Impulse buying detection
    final impulseHabit = await _detectImpulseBuying(transactionHistory);
    if (impulseHabit != null) detectedHabits.add(impulseHabit);
    
    // Subscription creep detection
    final subscriptionHabit = await _detectSubscriptionCreep(transactionHistory);
    if (subscriptionHabit != null) detectedHabits.add(subscriptionHabit);
    
    // Weekend overspending detection
    final weekendHabit = await _detectWeekendOverspending(transactionHistory);
    if (weekendHabit != null) detectedHabits.add(weekendHabit);
    
    // Emotional spending detection
    final emotionalHabit = await _detectEmotionalSpending(transactionHistory);
    if (emotionalHabit != null) detectedHabits.add(emotionalHabit);
    
    // Convenience spending detection
    final convenienceHabit = await _detectConvenienceSpending(transactionHistory);
    if (convenienceHabit != null) detectedHabits.add(convenienceHabit);
    
    // Social spending detection
    final socialHabit = await _detectSocialSpending(transactionHistory);
    if (socialHabit != null) detectedHabits.add(socialHabit);

    // Calculate category risk scores
    final categoryRiskScores = _calculateCategoryRiskScores(detectedHabits, transactionHistory);
    
    // Generate recommendations
    final recommendations = _generateRecommendations(detectedHabits, categoryRiskScores);
    
    // Calculate overall habit score
    final overallHabitScore = _calculateOverallHabitScore(detectedHabits, categoryRiskScores);
    
    // Generate insights
    final insights = _generateInsights(detectedHabits, transactionHistory);

    return HabitAnalysisResult(
      detectedHabits: detectedHabits,
      categoryRiskScores: categoryRiskScores,
      recommendations: recommendations,
      overallHabitScore: overallHabitScore,
      insights: insights,
    );
  }

  /// Generate behavioral corrections based on detected habits
  Future<List<BehavioralCorrection>> generateBehavioralCorrections(
    List<DetectedHabit> detectedHabits,
  ) async {
    final corrections = <BehavioralCorrection>[];
    
    for (final habit in detectedHabits) {
      if (habit.confidence > 0.6 && habit.impactScore > 0.3) {
        final correction = await _createBehavioralCorrection(habit);
        corrections.add(correction);
      }
    }
    
    return corrections;
  }

  /// Predict habit formation risk for new spending patterns
  Future<double> predictHabitFormationRisk(
    List<Map<String, dynamic>> recentTransactions,
    String category,
  ) async {
    if (recentTransactions.length < 5) return 0.0;
    
    var riskScore = 0.0;
    
    // Frequency risk
    final categoryTransactions = recentTransactions
        .where((t) => t['category'] == category)
        .toList();
    
    if (categoryTransactions.length >= 3) {
      riskScore += 0.3; // High frequency
      
      // Check for consistent timing (same day of week or time)
      final times = categoryTransactions
          .map((t) => DateTime.tryParse(t['date']?.toString() ?? ''))
          .where((date) => date != null)
          .toList();
      
      if (times.length >= 3) {
        final dayOfWeekConsistency = _calculateDayOfWeekConsistency(times.cast<DateTime>());
        riskScore += dayOfWeekConsistency * 0.2;
      }
    }
    
    // Amount consistency risk
    final amounts = categoryTransactions
        .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
        .toList();
    
    if (amounts.isNotEmpty) {
      final amountConsistency = _calculateAmountConsistency(amounts);
      riskScore += amountConsistency * 0.2;
    }
    
    // Location/merchant consistency
    final merchants = categoryTransactions
        .map((t) => t['merchant']?.toString() ?? '')
        .where((m) => m.isNotEmpty)
        .toSet();
    
    if (merchants.length == 1 && categoryTransactions.length >= 3) {
      riskScore += 0.3; // Same merchant repeatedly
    }
    
    return riskScore.clamp(0.0, 1.0);
  }

  // Habit detection methods

  Future<DetectedHabit?> _detectImpulseBuying(List<Map<String, dynamic>> transactions) async {
    final indicators = <String>[];
    final evidenceTransactions = <String>[];
    var confidence = 0.0;
    var impactScore = 0.0;
    
    // Look for large, unplanned purchases
    final sortedTransactions = List<Map<String, dynamic>>.from(transactions);
    sortedTransactions.sort((a, b) {
      final amountA = (a['amount'] as num?)?.toDouble() ?? 0.0;
      final amountB = (b['amount'] as num?)?.toDouble() ?? 0.0;
      return amountB.compareTo(amountA);
    });
    
    final totalSpending = transactions.fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
    final averageTransaction = totalSpending / transactions.length;
    
    // Find transactions 3x above average
    final largeTransactions = sortedTransactions
        .where((t) => ((t['amount'] as num?)?.toDouble() ?? 0.0) > averageTransaction * 3)
        .toList();
    
    if (largeTransactions.length >= 2) {
      indicators.add('Multiple large transactions above average spending');
      confidence += 0.3;
      impactScore += 0.4;
      
      for (final transaction in largeTransactions.take(3)) {
        evidenceTransactions.add(transaction['id']?.toString() ?? '');
      }
    }
    
    // Look for quick successive purchases
    final quickPurchases = _findQuickSuccessivePurchases(transactions);
    if (quickPurchases >= 3) {
      indicators.add('Pattern of quick successive purchases detected');
      confidence += 0.4;
      impactScore += 0.3;
    }
    
    // Look for non-essential categories
    final nonEssentialSpending = _calculateNonEssentialSpending(transactions);
    if (nonEssentialSpending > 0.3) {
      indicators.add('High spending in non-essential categories (${(nonEssentialSpending * 100).round()}%)');
      confidence += 0.3;
      impactScore += 0.2;
    }
    
    if (confidence > 0.5) {
      return DetectedHabit(
        habitId: 'impulse_buying_${DateTime.now().millisecondsSinceEpoch}',
        habitName: 'Impulse Buying',
        category: 'spending_behavior',
        confidence: confidence.clamp(0.0, 1.0),
        impactScore: impactScore.clamp(0.0, 1.0),
        indicators: indicators,
        evidenceTransactions: evidenceTransactions,
        parameters: {
          'largeTransactionCount': largeTransactions.length,
          'quickPurchases': quickPurchases,
          'nonEssentialRatio': nonEssentialSpending,
        },
        firstDetected: DateTime.now(),
        lastObserved: DateTime.now(),
        observationCount: 1,
      );
    }
    
    return null;
  }

  Future<DetectedHabit?> _detectSubscriptionCreep(List<Map<String, dynamic>> transactions) async {
    final subscriptions = <String, List<Map<String, dynamic>>>{};
    
    // Group recurring transactions by merchant/description
    for (final transaction in transactions) {
      final merchant = transaction['merchant']?.toString() ?? '';
      final description = transaction['description']?.toString() ?? '';
      final key = merchant.isNotEmpty ? merchant : description;
      
      if (key.isNotEmpty) {
        subscriptions.putIfAbsent(key, () => []).add(transaction);
      }
    }
    
    // Find potential subscription services
    final potentialSubscriptions = subscriptions.entries
        .where((entry) => entry.value.length >= 2)
        .where((entry) => _isLikelySubscription(entry.value))
        .toList();
    
    if (potentialSubscriptions.length >= 3) {
      final totalSubscriptionCost = potentialSubscriptions
          .expand((entry) => entry.value)
          .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
      
      final monthlySubscriptionCost = totalSubscriptionCost / 
          (transactions.length / 30); // Rough monthly estimate
      
      return DetectedHabit(
        habitId: 'subscription_creep_${DateTime.now().millisecondsSinceEpoch}',
        habitName: 'Subscription Creep',
        category: 'recurring_spending',
        confidence: 0.8,
        impactScore: (monthlySubscriptionCost / 100).clamp(0.0, 1.0),
        indicators: [
          '${potentialSubscriptions.length} recurring subscriptions detected',
          'Estimated monthly cost: \$${monthlySubscriptionCost.toStringAsFixed(2)}',
        ],
        evidenceTransactions: potentialSubscriptions
            .expand((entry) => entry.value)
            .take(5)
            .map((t) => t['id']?.toString() ?? '')
            .toList(),
        parameters: {
          'subscriptionCount': potentialSubscriptions.length,
          'monthlyEstimate': monthlySubscriptionCost,
        },
        firstDetected: DateTime.now(),
        lastObserved: DateTime.now(),
        observationCount: 1,
      );
    }
    
    return null;
  }

  Future<DetectedHabit?> _detectWeekendOverspending(List<Map<String, dynamic>> transactions) async {
    final weekdaySpending = <double>[];
    final weekendSpending = <double>[];
    
    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ?? DateTime.now();
      final amount = (transaction['amount'] as num?)?.toDouble() ?? 0.0;
      
      if (date.weekday >= 6) {
        weekendSpending.add(amount);
      } else {
        weekdaySpending.add(amount);
      }
    }
    
    if (weekdaySpending.isNotEmpty && weekendSpending.isNotEmpty) {
      final weekdayAvg = weekdaySpending.reduce((a, b) => a + b) / weekdaySpending.length;
      final weekendAvg = weekendSpending.reduce((a, b) => a + b) / weekendSpending.length;
      
      if (weekendAvg > weekdayAvg * 1.5) {
        final overspendingRatio = weekendAvg / weekdayAvg;
        
        return DetectedHabit(
          habitId: 'weekend_overspending_${DateTime.now().millisecondsSinceEpoch}',
          habitName: 'Weekend Overspending',
          category: 'temporal_spending',
          confidence: 0.9,
          impactScore: ((overspendingRatio - 1) / 2).clamp(0.0, 1.0),
          indicators: [
            'Weekend spending is ${((overspendingRatio - 1) * 100).round()}% higher than weekdays',
            'Average weekend: \$${weekendAvg.toStringAsFixed(2)}, weekday: \$${weekdayAvg.toStringAsFixed(2)}',
          ],
          evidenceTransactions: [],
          parameters: {
            'overspendingRatio': overspendingRatio,
            'weekendAverage': weekendAvg,
            'weekdayAverage': weekdayAvg,
          },
          firstDetected: DateTime.now(),
          lastObserved: DateTime.now(),
          observationCount: 1,
        );
      }
    }
    
    return null;
  }

  Future<DetectedHabit?> _detectEmotionalSpending(List<Map<String, dynamic>> transactions) async {
    // Look for clustering of purchases in short time periods
    final purchasesByDay = <String, List<Map<String, dynamic>>>{};
    
    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ?? DateTime.now();
      final dateKey = '${date.year}-${date.month}-${date.day}';
      purchasesByDay.putIfAbsent(dateKey, () => []).add(transaction);
    }
    
    // Find days with unusually high transaction counts or amounts
    final heavySpendingDays = purchasesByDay.entries
        .where((entry) => entry.value.length >= 4 || 
            entry.value.fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0)) > 200)
        .toList();
    
    if (heavySpendingDays.length >= 2) {
      final totalHeavySpending = heavySpendingDays
          .expand((entry) => entry.value)
          .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
      
      return DetectedHabit(
        habitId: 'emotional_spending_${DateTime.now().millisecondsSinceEpoch}',
        habitName: 'Emotional Spending',
        category: 'behavioral_spending',
        confidence: 0.7,
        impactScore: (totalHeavySpending / 500).clamp(0.0, 1.0),
        indicators: [
          '${heavySpendingDays.length} days with heavy spending patterns',
          'Pattern suggests stress or emotional purchasing',
        ],
        evidenceTransactions: heavySpendingDays
            .expand((entry) => entry.value)
            .take(5)
            .map((t) => t['id']?.toString() ?? '')
            .toList(),
        parameters: {
          'heavySpendingDays': heavySpendingDays.length,
          'totalHeavySpending': totalHeavySpending,
        },
        firstDetected: DateTime.now(),
        lastObserved: DateTime.now(),
        observationCount: 1,
      );
    }
    
    return null;
  }

  Future<DetectedHabit?> _detectConvenienceSpending(List<Map<String, dynamic>> transactions) async {
    // Look for delivery fees, convenience stores, etc.
    final convenienceCategories = ['delivery', 'convenience_store', 'gas_station', 'fast_food'];
    final convenienceTransactions = transactions
        .where((t) => convenienceCategories.contains(t['category']))
        .toList();
    
    if (convenienceTransactions.length >= transactions.length * 0.2) {
      final convenienceSpending = convenienceTransactions
          .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
      
      return DetectedHabit(
        habitId: 'convenience_spending_${DateTime.now().millisecondsSinceEpoch}',
        habitName: 'Convenience Spending',
        category: 'lifestyle_spending',
        confidence: 0.8,
        impactScore: (convenienceSpending / 300).clamp(0.0, 1.0),
        indicators: [
          '${((convenienceTransactions.length / transactions.length) * 100).round()}% of transactions are convenience-based',
          'Total convenience spending: \$${convenienceSpending.toStringAsFixed(2)}',
        ],
        evidenceTransactions: convenienceTransactions
            .take(5)
            .map((t) => t['id']?.toString() ?? '')
            .toList(),
        parameters: {
          'convenienceRatio': convenienceTransactions.length / transactions.length,
          'convenienceSpending': convenienceSpending,
        },
        firstDetected: DateTime.now(),
        lastObserved: DateTime.now(),
        observationCount: 1,
      );
    }
    
    return null;
  }

  Future<DetectedHabit?> _detectSocialSpending(List<Map<String, dynamic>> transactions) async {
    // Look for restaurant, entertainment, and social categories
    final socialCategories = ['restaurant', 'entertainment', 'bars', 'events'];
    final socialTransactions = transactions
        .where((t) => socialCategories.contains(t['category']))
        .toList();
    
    if (socialTransactions.length >= 5) {
      final socialSpending = socialTransactions
          .fold(0.0, (sum, t) => sum + ((t['amount'] as num?)?.toDouble() ?? 0.0));
      
      // Check for group purchase patterns (similar amounts, same dates)
      final groupPurchases = _findGroupPurchasePatterns(socialTransactions);
      
      if (groupPurchases >= 3 || socialSpending > 400) {
        return DetectedHabit(
          habitId: 'social_spending_${DateTime.now().millisecondsSinceEpoch}',
          habitName: 'Social Spending',
          category: 'social_spending',
          confidence: 0.75,
          impactScore: (socialSpending / 500).clamp(0.0, 1.0),
          indicators: [
            '${socialTransactions.length} social spending transactions',
            'Total social spending: \$${socialSpending.toStringAsFixed(2)}',
            if (groupPurchases >= 3) 'Group purchase patterns detected',
          ],
          evidenceTransactions: socialTransactions
              .take(5)
              .map((t) => t['id']?.toString() ?? '')
              .toList(),
          parameters: {
            'socialTransactionCount': socialTransactions.length,
            'socialSpending': socialSpending,
            'groupPurchases': groupPurchases,
          },
          firstDetected: DateTime.now(),
          lastObserved: DateTime.now(),
          observationCount: 1,
        );
      }
    }
    
    return null;
  }

  // Helper methods

  int _findQuickSuccessivePurchases(List<Map<String, dynamic>> transactions) {
    var quickPurchases = 0;
    
    for (int i = 0; i < transactions.length - 1; i++) {
      final currentDate = DateTime.tryParse(transactions[i]['date']?.toString() ?? '') ?? DateTime.now();
      final nextDate = DateTime.tryParse(transactions[i + 1]['date']?.toString() ?? '') ?? DateTime.now();
      
      if (nextDate.difference(currentDate).inMinutes <= 30) {
        quickPurchases++;
      }
    }
    
    return quickPurchases;
  }

  double _calculateNonEssentialSpending(List<Map<String, dynamic>> transactions) {
    final essentialCategories = ['groceries', 'utilities', 'housing', 'transportation', 'healthcare'];
    final nonEssentialTransactions = transactions
        .where((t) => !essentialCategories.contains(t['category']))
        .toList();
    
    if (transactions.isEmpty) return 0.0;
    return nonEssentialTransactions.length / transactions.length;
  }

  bool _isLikelySubscription(List<Map<String, dynamic>> transactions) {
    if (transactions.length < 2) return false;
    
    // Check for recurring amounts
    final amounts = transactions
        .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
        .toList();
    
    final uniqueAmounts = amounts.toSet();
    if (uniqueAmounts.length <= 2) {
      // Check for monthly frequency
      final dates = transactions
          .map((t) => DateTime.tryParse(t['date']?.toString() ?? ''))
          .where((date) => date != null)
          .cast<DateTime>()
          .toList();
      
      if (dates.length >= 2) {
        dates.sort();
        final avgDaysBetween = _calculateAverageDaysBetween(dates);
        return avgDaysBetween >= 25 && avgDaysBetween <= 35; // Monthly-ish
      }
    }
    
    return false;
  }

  double _calculateDayOfWeekConsistency(List<DateTime> dates) {
    if (dates.length < 3) return 0.0;
    
    final dayOfWeekCounts = <int, int>{};
    for (final date in dates) {
      dayOfWeekCounts[date.weekday] = (dayOfWeekCounts[date.weekday] ?? 0) + 1;
    }
    
    final maxCount = dayOfWeekCounts.values.reduce(max);
    return maxCount / dates.length;
  }

  double _calculateAmountConsistency(List<double> amounts) {
    if (amounts.length < 2) return 0.0;
    
    final mean = amounts.reduce((a, b) => a + b) / amounts.length;
    final variance = amounts
        .map((amount) => pow(amount - mean, 2))
        .reduce((a, b) => a + b) / amounts.length;
    
    final standardDeviation = sqrt(variance);
    final coefficientOfVariation = mean > 0 ? standardDeviation / mean : 1.0;
    
    return 1.0 - coefficientOfVariation.clamp(0.0, 1.0);
  }

  double _calculateAverageDaysBetween(List<DateTime> sortedDates) {
    if (sortedDates.length < 2) return 0.0;
    
    var totalDays = 0;
    for (int i = 1; i < sortedDates.length; i++) {
      totalDays += sortedDates[i].difference(sortedDates[i - 1]).inDays;
    }
    
    return totalDays / (sortedDates.length - 1);
  }

  int _findGroupPurchasePatterns(List<Map<String, dynamic>> transactions) {
    var groupPurchases = 0;
    
    // Group by date
    final transactionsByDate = <String, List<Map<String, dynamic>>>{};
    for (final transaction in transactions) {
      final date = DateTime.tryParse(transaction['date']?.toString() ?? '') ?? DateTime.now();
      final dateKey = '${date.year}-${date.month}-${date.day}';
      transactionsByDate.putIfAbsent(dateKey, () => []).add(transaction);
    }
    
    // Look for multiple transactions on same day with similar amounts
    for (final dayTransactions in transactionsByDate.values) {
      if (dayTransactions.length >= 2) {
        final amounts = dayTransactions
            .map((t) => (t['amount'] as num?)?.toDouble() ?? 0.0)
            .toList();
        
        // Check for similar amounts (within 20% of each other)
        for (int i = 0; i < amounts.length - 1; i++) {
          for (int j = i + 1; j < amounts.length; j++) {
            final ratio = amounts[i] > 0 ? amounts[j] / amounts[i] : 0.0;
            if (ratio >= 0.8 && ratio <= 1.2) {
              groupPurchases++;
              break;
            }
          }
        }
      }
    }
    
    return groupPurchases;
  }

  Map<String, double> _calculateCategoryRiskScores(
    List<DetectedHabit> habits,
    List<Map<String, dynamic>> transactions,
  ) {
    final riskScores = <String, double>{};
    
    for (final habit in habits) {
      final category = habit.category;
      final riskContribution = habit.confidence * habit.impactScore;
      riskScores[category] = (riskScores[category] ?? 0.0) + riskContribution;
    }
    
    // Normalize scores
    final maxScore = riskScores.values.isEmpty ? 1.0 : riskScores.values.reduce(max);
    if (maxScore > 0) {
      for (final key in riskScores.keys) {
        riskScores[key] = (riskScores[key]! / maxScore).clamp(0.0, 1.0);
      }
    }
    
    return riskScores;
  }

  List<String> _generateRecommendations(
    List<DetectedHabit> habits,
    Map<String, double> categoryRiskScores,
  ) {
    final recommendations = <String>[];
    
    for (final habit in habits) {
      switch (habit.habitName) {
        case 'Impulse Buying':
          recommendations.add('Implement a 24-hour waiting period for non-essential purchases over \$50');
          recommendations.add('Create a dedicated "impulse budget" to satisfy spontaneous desires within limits');
          break;
        case 'Subscription Creep':
          recommendations.add('Review and audit all recurring subscriptions monthly');
          recommendations.add('Cancel unused subscriptions and consolidate similar services');
          break;
        case 'Weekend Overspending':
          recommendations.add('Set a specific weekend spending budget and track it closely');
          recommendations.add('Plan weekend activities that don\'t require high spending');
          break;
        case 'Emotional Spending':
          recommendations.add('Identify emotional triggers and develop alternative coping strategies');
          recommendations.add('Implement a "pause and reflect" rule before making purchases');
          break;
        case 'Convenience Spending':
          recommendations.add('Plan ahead to reduce reliance on convenience options');
          recommendations.add('Batch errands and meal prep to avoid last-minute expenses');
          break;
        case 'Social Spending':
          recommendations.add('Set boundaries for social spending and communicate them with friends');
          recommendations.add('Suggest lower-cost social activities and take turns hosting');
          break;
      }
    }
    
    return recommendations.take(5).toList();
  }

  double _calculateOverallHabitScore(
    List<DetectedHabit> habits,
    Map<String, double> categoryRiskScores,
  ) {
    if (habits.isEmpty) return 0.5; // Neutral score
    
    final weightedScore = habits.fold(0.0, (sum, habit) => 
        sum + (habit.confidence * habit.impactScore));
    
    return (weightedScore / habits.length).clamp(0.0, 1.0);
  }

  Map<String, dynamic> _generateInsights(
    List<DetectedHabit> habits,
    List<Map<String, dynamic>> transactions,
  ) {
    return {
      'totalHabitsDetected': habits.length,
      'highConfidenceHabits': habits.where((h) => h.confidence > 0.8).length,
      'highImpactHabits': habits.where((h) => h.impactScore > 0.6).length,
      'dataQuality': transactions.length >= 50 ? 'good' : transactions.length >= 20 ? 'moderate' : 'limited',
      'analysisDate': DateTime.now().toIso8601String(),
    };
  }

  Future<BehavioralCorrection> _createBehavioralCorrection(DetectedHabit habit) async {
    return BehavioralCorrection(
      habitId: habit.habitId,
      correctionType: _getCorrectionType(habit.habitName),
      budgetMultiplier: _getBudgetMultiplier(habit),
      bufferMultiplier: _getBufferMultiplier(habit),
      categoryAdjustments: _getCategoryAdjustments(habit),
      interventions: _getInterventions(habit),
      expectedImpact: habit.impactScore * habit.confidence,
    );
  }

  String _getCorrectionType(String habitName) {
    switch (habitName) {
      case 'Impulse Buying':
        return 'impulse_control';
      case 'Subscription Creep':
        return 'subscription_management';
      case 'Weekend Overspending':
        return 'temporal_control';
      case 'Emotional Spending':
        return 'emotional_regulation';
      case 'Convenience Spending':
        return 'planning_improvement';
      case 'Social Spending':
        return 'social_boundary_setting';
      default:
        return 'general_awareness';
    }
  }

  double _getBudgetMultiplier(DetectedHabit habit) {
    // Reduce budget allocation based on habit severity
    final severity = habit.confidence * habit.impactScore;
    return 1.0 - (severity * 0.2); // Reduce by up to 20%
  }

  double _getBufferMultiplier(DetectedHabit habit) {
    // Increase buffer for high-risk habits
    final risk = habit.confidence * habit.impactScore;
    return 1.0 + (risk * 0.3); // Increase buffer by up to 30%
  }

  Map<String, double> _getCategoryAdjustments(DetectedHabit habit) {
    // Return category-specific adjustments based on habit type
    switch (habit.habitName) {
      case 'Impulse Buying':
        return {'shopping': 0.8, 'entertainment': 0.9};
      case 'Convenience Spending':
        return {'food': 0.85, 'delivery': 0.7};
      case 'Social Spending':
        return {'restaurant': 0.9, 'entertainment': 0.85};
      default:
        return {};
    }
  }

  List<String> _getInterventions(DetectedHabit habit) {
    switch (habit.habitName) {
      case 'Impulse Buying':
        return ['24-hour rule', 'impulse budget allocation', 'need vs want assessment'];
      case 'Subscription Creep':
        return ['monthly subscription audit', 'usage tracking', 'cancellation reminders'];
      case 'Weekend Overspending':
        return ['weekend budget cap', 'activity planning', 'spending alerts'];
      case 'Emotional Spending':
        return ['trigger identification', 'alternative activities', 'mindfulness practices'];
      case 'Convenience Spending':
        return ['meal planning', 'batch shopping', 'preparation reminders'];
      case 'Social Spending':
        return ['group budget discussion', 'cost-sharing strategies', 'alternative suggestions'];
      default:
        return ['spending awareness', 'budget tracking'];
    }
  }
}
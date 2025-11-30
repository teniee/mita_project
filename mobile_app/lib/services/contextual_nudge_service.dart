import 'dart:math';
import '../models/budget_intelligence_models.dart';

/// Contextual nudge optimization service with A/B testing and personalization
class ContextualNudgeService {
  static final ContextualNudgeService _instance = ContextualNudgeService._internal();
  factory ContextualNudgeService() => _instance;
  ContextualNudgeService._internal();

  final Map<String, List<NudgeEffectivenessResult>> _userNudgeHistory = {};
  final Map<String, Map<NudgeType, double>> _personalizedEffectiveness = {};

  /// Generate a personalized nudge for the given context
  Future<PersonalizedNudge> generatePersonalizedNudge({
    required String userId,
    required NudgeContext context,
    required Map<String, dynamic> contextData,
  }) async {
    // Analyze user's nudge history to determine most effective nudge type
    final mostEffectiveNudgeType = await _determineMostEffectiveNudgeType(userId, context);

    // Generate personalized message based on context and user data
    final personalizedMessage = await _generatePersonalizedMessage(
      mostEffectiveNudgeType,
      context,
      contextData,
      userId,
    );

    // Calculate expected effectiveness based on historical data
    final expectedEffectiveness =
        _calculateExpectedEffectiveness(userId, mostEffectiveNudgeType, context);

    return PersonalizedNudge(
      nudgeId: 'nudge_${DateTime.now().millisecondsSinceEpoch}',
      nudgeType: mostEffectiveNudgeType,
      context: context,
      message: personalizedMessage['message']!,
      actionText: personalizedMessage['actionText']!,
      expectedEffectiveness: expectedEffectiveness,
      personalizedData: {
        'userId': userId,
        'baselineEffectiveness': _getBaselineEffectiveness(mostEffectiveNudgeType),
        'personalizedFactors': personalizedMessage['factors'],
        'contextData': contextData,
      },
      createdAt: DateTime.now(),
      expiresAt: _calculateExpirationTime(context),
    );
  }

  /// Record the effectiveness of a nudge for learning
  Future<void> recordNudgeEffectiveness({
    required String userId,
    required String nudgeId,
    required bool wasEffective,
    required Map<String, dynamic> outcomeMetadata,
  }) async {
    final effectiveness = wasEffective ? 1.0 : 0.0;

    final result = NudgeEffectivenessResult(
      nudgeId: nudgeId,
      wasEffective: wasEffective,
      effectiveness: effectiveness,
      metadata: {
        'userId': userId,
        'outcome': outcomeMetadata,
        'timestamp': DateTime.now().toIso8601String(),
      },
      recordedAt: DateTime.now(),
    );

    // Store in user's nudge history
    _userNudgeHistory.putIfAbsent(userId, () => []).add(result);

    // Update personalized effectiveness scores
    await _updatePersonalizedEffectiveness(userId, result);
  }

  /// Get nudge recommendations for different contexts
  Future<List<PersonalizedNudge>> getNudgeRecommendations({
    required String userId,
    required List<NudgeContext> contexts,
    required Map<String, dynamic> userData,
  }) async {
    final recommendations = <PersonalizedNudge>[];

    for (final context in contexts) {
      final nudge = await generatePersonalizedNudge(
        userId: userId,
        context: context,
        contextData: {
          'userData': userData,
          'context': context.toString(),
        },
      );
      recommendations.add(nudge);
    }

    // Sort by expected effectiveness
    recommendations.sort((a, b) => b.expectedEffectiveness.compareTo(a.expectedEffectiveness));

    return recommendations.take(3).toList(); // Return top 3 recommendations
  }

  /// A/B test different nudge variations
  Future<Map<String, double>> runNudgeABTest({
    required List<NudgeType> nudgeTypes,
    required NudgeContext context,
    required Map<String, dynamic> testData,
    int testDurationDays = 7,
  }) async {
    final results = <String, double>{};

    // Simulate A/B test results based on nudge type effectiveness
    for (final nudgeType in nudgeTypes) {
      final baselineEffectiveness = _getBaselineEffectiveness(nudgeType);
      final contextMultiplier = _getContextMultiplier(nudgeType, context);

      // Add some randomness to simulate real A/B test variance
      final variance = (Random().nextDouble() - 0.5) * 0.2; // ±10% variance
      final testEffectiveness =
          (baselineEffectiveness * contextMultiplier + variance).clamp(0.0, 1.0);

      results[nudgeType.toString()] = testEffectiveness;
    }

    return results;
  }

  /// Get nudge analytics for a user
  Future<Map<String, dynamic>> getNudgeAnalytics(String userId) async {
    final history = _userNudgeHistory[userId] ?? [];

    if (history.isEmpty) {
      return {
        'totalNudges': 0,
        'overallEffectiveness': 0.0,
        'bestNudgeTypes': <String>[],
        'contextEffectiveness': <String, double>{},
        'improvementTrend': 'insufficient_data',
      };
    }

    // Calculate overall effectiveness
    final overallEffectiveness =
        history.fold(0.0, (sum, result) => sum + result.effectiveness) / history.length;

    // Find best performing nudge types
    final nudgeTypeEffectiveness = <String, List<double>>{};
    for (final result in history) {
      // Extract nudge type from metadata if available
      final nudgeType = result.metadata['nudgeType']?.toString() ?? 'unknown';
      nudgeTypeEffectiveness.putIfAbsent(nudgeType, () => []).add(result.effectiveness);
    }

    final bestNudgeTypes = nudgeTypeEffectiveness.entries
        .map((entry) => {
              'type': entry.key,
              'effectiveness': entry.value.reduce((a, b) => a + b) / entry.value.length,
            })
        .toList()
      ..sort((a, b) => (b['effectiveness'] as double).compareTo(a['effectiveness'] as double));

    // Calculate improvement trend
    final recentEffectiveness = history.length >= 10
        ? history.skip(history.length - 10).fold(0.0, (sum, result) => sum + result.effectiveness) /
            10
        : overallEffectiveness;

    final earlyEffectiveness = history.length >= 10
        ? history.take(10).fold(0.0, (sum, result) => sum + result.effectiveness) / 10
        : overallEffectiveness;

    String improvementTrend;
    if (recentEffectiveness > earlyEffectiveness + 0.1) {
      improvementTrend = 'improving';
    } else if (recentEffectiveness < earlyEffectiveness - 0.1) {
      improvementTrend = 'declining';
    } else {
      improvementTrend = 'stable';
    }

    return {
      'totalNudges': history.length,
      'overallEffectiveness': overallEffectiveness,
      'bestNudgeTypes': bestNudgeTypes.take(3).map((e) => e['type']).toList(),
      'contextEffectiveness': _calculateContextEffectiveness(history),
      'improvementTrend': improvementTrend,
      'recentEffectiveness': recentEffectiveness,
      'dataQuality': history.length >= 20
          ? 'good'
          : history.length >= 10
              ? 'moderate'
              : 'limited',
    };
  }

  // Private helper methods

  Future<NudgeType> _determineMostEffectiveNudgeType(String userId, NudgeContext context) async {
    final personalizedScores = _personalizedEffectiveness[userId];

    if (personalizedScores == null || personalizedScores.isEmpty) {
      // Use baseline effectiveness for new users
      return _getDefaultNudgeTypeForContext(context);
    }

    // Find the nudge type with highest personalized effectiveness for this user
    final sortedTypes = personalizedScores.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return sortedTypes.first.key;
  }

  Future<Map<String, String>> _generatePersonalizedMessage(
    NudgeType nudgeType,
    NudgeContext context,
    Map<String, dynamic> contextData,
    String userId,
  ) async {
    final templates = _getNudgeTemplates(nudgeType, context);
    final selectedTemplate = templates[Random().nextInt(templates.length)];

    // Personalize the message with context data
    final personalizedMessage = _personalizeMessage(selectedTemplate['message']!, contextData);
    final personalizedAction = _personalizeMessage(selectedTemplate['action']!, contextData);

    return {
      'message': personalizedMessage,
      'actionText': personalizedAction,
      'factors': selectedTemplate['factors']!,
    };
  }

  double _calculateExpectedEffectiveness(String userId, NudgeType nudgeType, NudgeContext context) {
    final personalizedScore = _personalizedEffectiveness[userId]?[nudgeType];
    final baselineScore = _getBaselineEffectiveness(nudgeType);
    final contextMultiplier = _getContextMultiplier(nudgeType, context);

    if (personalizedScore != null) {
      return (personalizedScore * contextMultiplier).clamp(0.0, 1.0);
    } else {
      return (baselineScore * contextMultiplier).clamp(0.0, 1.0);
    }
  }

  DateTime? _calculateExpirationTime(NudgeContext context) {
    switch (context) {
      case NudgeContext.beforePurchase:
        return DateTime.now().add(const Duration(minutes: 30));
      case NudgeContext.afterPurchase:
        return DateTime.now().add(const Duration(hours: 2));
      case NudgeContext.dailyCheckin:
        return DateTime.now().add(const Duration(hours: 24));
      case NudgeContext.weeklyReview:
        return DateTime.now().add(const Duration(days: 7));
      case NudgeContext.goalSetting:
        return DateTime.now().add(const Duration(days: 30));
      case NudgeContext.budgetAlert:
        return DateTime.now().add(const Duration(hours: 6));
      case NudgeContext.monthEnd:
        return DateTime.now().add(const Duration(days: 3));
      case NudgeContext.emergency:
        return DateTime.now().add(const Duration(hours: 1));
    }
  }

  Future<void> _updatePersonalizedEffectiveness(
      String userId, NudgeEffectivenessResult result) async {
    // Extract nudge type from metadata
    final nudgeTypeString = result.metadata['nudgeType']?.toString();
    if (nudgeTypeString == null) return;

    // Convert string back to enum (simplified approach)
    NudgeType? nudgeType;
    for (final type in NudgeType.values) {
      if (type.toString() == nudgeTypeString) {
        nudgeType = type;
        break;
      }
    }

    if (nudgeType == null) return;

    // Update the personalized effectiveness score using exponential smoothing
    final currentScore =
        _personalizedEffectiveness[userId]?[nudgeType] ?? _getBaselineEffectiveness(nudgeType);
    const learningRate = 0.3; // How quickly to adapt to new data

    final newScore = currentScore * (1 - learningRate) + result.effectiveness * learningRate;

    _personalizedEffectiveness.putIfAbsent(userId, () => {})[nudgeType] = newScore.clamp(0.0, 1.0);
  }

  double _getBaselineEffectiveness(NudgeType nudgeType) {
    // Based on behavioral economics research
    switch (nudgeType) {
      case NudgeType.lossAversion:
        return 0.75; // Very effective
      case NudgeType.socialProof:
        return 0.70; // Highly effective
      case NudgeType.anchoring:
        return 0.65; // Moderately effective
      case NudgeType.mentalAccounting:
        return 0.60; // Moderately effective
      case NudgeType.commitmentDevice:
        return 0.80; // Very effective
      case NudgeType.scarcity:
        return 0.55; // Somewhat effective
      case NudgeType.progressCelebration:
        return 0.68; // Effective for motivation
      case NudgeType.impactFraming:
        return 0.62; // Moderately effective
      case NudgeType.freshStart:
        return 0.58; // Moderately effective
      case NudgeType.implementation:
        return 0.72; // Highly effective
    }
  }

  double _getContextMultiplier(NudgeType nudgeType, NudgeContext context) {
    // Different nudge types work better in different contexts
    switch (nudgeType) {
      case NudgeType.lossAversion:
        return context == NudgeContext.beforePurchase ? 1.2 : 1.0;
      case NudgeType.socialProof:
        return context == NudgeContext.dailyCheckin ? 1.15 : 1.0;
      case NudgeType.commitmentDevice:
        return context == NudgeContext.goalSetting ? 1.3 : 1.0;
      case NudgeType.progressCelebration:
        return context == NudgeContext.weeklyReview ? 1.25 : 1.0;
      default:
        return 1.0;
    }
  }

  NudgeType _getDefaultNudgeTypeForContext(NudgeContext context) {
    switch (context) {
      case NudgeContext.beforePurchase:
        return NudgeType.lossAversion;
      case NudgeContext.afterPurchase:
        return NudgeType.mentalAccounting;
      case NudgeContext.dailyCheckin:
        return NudgeType.socialProof;
      case NudgeContext.weeklyReview:
        return NudgeType.progressCelebration;
      case NudgeContext.goalSetting:
        return NudgeType.commitmentDevice;
      case NudgeContext.budgetAlert:
        return NudgeType.lossAversion;
      case NudgeContext.monthEnd:
        return NudgeType.freshStart;
      case NudgeContext.emergency:
        return NudgeType.implementation;
    }
  }

  List<Map<String, String>> _getNudgeTemplates(NudgeType nudgeType, NudgeContext context) {
    switch (nudgeType) {
      case NudgeType.lossAversion:
        return [
          {
            'message':
                'You could lose \${amount} from your {goal} if you continue this spending pattern',
            'action': 'Protect My Goal',
            'factors': 'loss_framing,goal_threat',
          },
          {
            'message': 'This purchase could set you back {days} days on your savings goal',
            'action': 'Reconsider Purchase',
            'factors': 'time_loss,progress_threat',
          },
        ];
      case NudgeType.socialProof:
        return [
          {
            'message': '{percentage}% of users in your income tier save more than you this month',
            'action': 'See How to Improve',
            'factors': 'peer_comparison,social_norm',
          },
          {
            'message': 'Users like you typically spend 20% less on {category}',
            'action': 'Learn Their Strategies',
            'factors': 'peer_behavior,category_specific',
          },
        ];
      case NudgeType.commitmentDevice:
        return [
          {
            'message':
                'You committed to saving \${amount} this month. You\'re {percentage}% there!',
            'action': 'Stay Committed',
            'factors': 'commitment_reminder,progress_update',
          },
        ];
      case NudgeType.progressCelebration:
        return [
          {
            'message': 'Amazing! You\'ve stayed under budget for {days} days straight! 🎉',
            'action': 'Keep It Up',
            'factors': 'achievement_recognition,momentum_building',
          },
        ];
      default:
        return [
          {
            'message': 'Consider your budget before making this decision',
            'action': 'Review Budget',
            'factors': 'general_awareness',
          },
        ];
    }
  }

  String _personalizeMessage(String template, Map<String, dynamic> contextData) {
    var message = template;

    // Replace common placeholders
    final replacements = {
      '{amount}': '\$${(contextData['amount'] ?? 50).toString()}',
      '{goal}': contextData['goal']?.toString() ?? 'savings goal',
      '{days}': (contextData['days'] ?? 5).toString(),
      '{percentage}': (contextData['percentage'] ?? 75).toString(),
      '{category}': contextData['category']?.toString() ?? 'this category',
    };

    for (final entry in replacements.entries) {
      message = message.replaceAll(entry.key, entry.value);
    }

    return message;
  }

  Map<String, double> _calculateContextEffectiveness(List<NudgeEffectivenessResult> history) {
    final contextResults = <String, List<double>>{};

    for (final result in history) {
      final context = result.metadata['context']?.toString() ?? 'unknown';
      contextResults.putIfAbsent(context, () => []).add(result.effectiveness);
    }

    final contextEffectiveness = <String, double>{};
    for (final entry in contextResults.entries) {
      contextEffectiveness[entry.key] = entry.value.reduce((a, b) => a + b) / entry.value.length;
    }

    return contextEffectiveness;
  }
}

// Import models first
import '../models/budget_intelligence_models.dart';

// Import enhanced services
import 'enhanced_master_budget_engine.dart';
import 'enhanced_income_service.dart';
import 'advanced_habit_recognition_service.dart';
import 'contextual_nudge_service.dart';
import 'social_comparison_service.dart';
import 'predictive_budget_service.dart';
import 'category_intelligence_service.dart';
import 'explanation_engine_service.dart';

// Import legacy services for compatibility
import 'onboarding_state.dart';
import 'logging_service.dart';

/// Enhanced daily budget calculation result compatible with existing system
class EnhancedDailyBudgetCalculation {
  // Legacy compatibility fields
  final double totalDailyBudget;
  final double baseAmount;
  final double redistributionBuffer;
  final double fixedCommitments;
  final double savingsTarget;
  final double confidence;
  final String methodology;

  // Enhanced intelligence fields
  final EnhancedBudgetResult enhancedResult;
  final List<String> intelligentInsights;
  final Map<String, double> categoryBreakdown;
  final PersonalizedNudge? contextualNudge;
  final BudgetForecast? tomorrowForecast;
  final BudgetExplanation explanation;
  final double riskAssessment;
  final Map<String, dynamic> advancedMetrics;

  EnhancedDailyBudgetCalculation({
    required this.totalDailyBudget,
    required this.baseAmount,
    required this.redistributionBuffer,
    required this.fixedCommitments,
    required this.savingsTarget,
    required this.confidence,
    required this.methodology,
    required this.enhancedResult,
    required this.intelligentInsights,
    required this.categoryBreakdown,
    this.contextualNudge,
    this.tomorrowForecast,
    required this.explanation,
    required this.riskAssessment,
    required this.advancedMetrics,
  });

  /// Legacy compatibility method
  Map<String, dynamic> toLegacyFormat() {
    return {
      'totalDailyBudget': totalDailyBudget,
      'baseAmount': baseAmount,
      'redistributionBuffer': redistributionBuffer,
      'fixedCommitments': fixedCommitments,
      'savingsTarget': savingsTarget,
      'confidence': confidence,
      'methodology': methodology,
    };
  }

  /// Enhanced format with all intelligence data
  Map<String, dynamic> toEnhancedFormat() {
    return {
      ...toLegacyFormat(),
      'enhancedResult': enhancedResult,
      'intelligentInsights': intelligentInsights,
      'categoryBreakdown': categoryBreakdown,
      'contextualNudge': contextualNudge,
      'tomorrowForecast': tomorrowForecast,
      'explanation': explanation,
      'riskAssessment': riskAssessment,
      'advancedMetrics': advancedMetrics,
    };
  }
}

/// Enhanced production budget engine integrating all intelligence services
/// Backward compatible with existing MITA infrastructure
class EnhancedProductionBudgetEngine {
  static final EnhancedProductionBudgetEngine _instance =
      EnhancedProductionBudgetEngine._internal();
  factory EnhancedProductionBudgetEngine() => _instance;
  EnhancedProductionBudgetEngine._internal();

  // Master engine instance
  final EnhancedMasterBudgetEngine _masterEngine = EnhancedMasterBudgetEngine();

  // Individual service instances for direct access
  final EnhancedIncomeService _incomeService = EnhancedIncomeService();
  final AdvancedHabitRecognitionService _habitService = AdvancedHabitRecognitionService();
  final ContextualNudgeService _nudgeService = ContextualNudgeService();
  final SocialComparisonService _socialService = SocialComparisonService();
  final PredictiveBudgetService _predictiveService = PredictiveBudgetService();
  final CategoryIntelligenceService _categoryService = CategoryIntelligenceService();
  final ExplanationEngineService _explanationService = ExplanationEngineService();

  /// Main enhanced budget calculation method
  Future<EnhancedDailyBudgetCalculation> calculateDailyBudget({
    required OnboardingState onboardingData,
    DateTime? targetDate,
    String? userId,
    List<Map<String, dynamic>>? transactionHistory,
    Map<String, dynamic>? additionalContext,
    bool useEnhancedFeatures = true,
  }) async {
    try {
      logInfo('Calculating enhanced daily budget with full intelligence integration',
          tag: 'ENHANCED_BUDGET_ENGINE');

      final actualTargetDate = targetDate ?? DateTime.now();
      final actualUserId = userId ?? 'anonymous_${DateTime.now().millisecondsSinceEpoch}';
      final actualTransactionHistory = transactionHistory ?? <Map<String, dynamic>>[];

      // Convert onboarding data to enhanced user profile
      final userProfile = _convertOnboardingToProfile(onboardingData, additionalContext);

      if (useEnhancedFeatures && actualTransactionHistory.isNotEmpty) {
        // Use full enhanced intelligence system
        return await _calculateEnhancedBudget(
          userId: actualUserId,
          userProfile: userProfile,
          transactionHistory: actualTransactionHistory,
          targetDate: actualTargetDate,
          onboardingData: onboardingData,
        );
      } else {
        // Use legacy calculation with some enhancements for backward compatibility
        return await _calculateLegacyCompatibleBudget(
          onboardingData: onboardingData,
          targetDate: actualTargetDate,
          userId: actualUserId,
          userProfile: userProfile,
        );
      }
    } catch (e) {
      logError('Error in enhanced budget calculation: $e', tag: 'ENHANCED_BUDGET_ENGINE');

      // Fallback to legacy calculation
      return await _calculateLegacyCompatibleBudget(
        onboardingData: onboardingData,
        targetDate: targetDate ?? DateTime.now(),
        userId: userId ?? 'fallback_user',
        userProfile: _convertOnboardingToProfile(onboardingData, additionalContext),
      );
    }
  }

  /// Full enhanced budget calculation with all intelligence services
  Future<EnhancedDailyBudgetCalculation> _calculateEnhancedBudget({
    required String userId,
    required Map<String, dynamic> userProfile,
    required List<Map<String, dynamic>> transactionHistory,
    required DateTime targetDate,
    required OnboardingState onboardingData,
  }) async {
    // Calculate enhanced budget using master engine
    final enhancedResult = await _masterEngine.calculateEnhancedDailyBudget(
      userId: userId,
      userProfile: userProfile,
      transactionHistory: transactionHistory,
      targetDate: targetDate,
    );

    // Extract legacy-compatible values
    final totalDailyBudget = enhancedResult.dailyBudget;
    final confidence = enhancedResult.confidence;

    // Calculate legacy format values for backward compatibility
    final monthlyIncome = (userProfile['monthlyIncome'] as num?)?.toDouble() ?? 0.0;
    const fixedCommitmentRatio = 0.55; // Default, would be calculated by enhanced system
    const savingsTargetRatio = 0.15; // Default, would be calculated by enhanced system

    final fixedCommitments = monthlyIncome * fixedCommitmentRatio;
    final savingsTarget = monthlyIncome * savingsTargetRatio;
    final baseAmount = (monthlyIncome - fixedCommitments - savingsTarget) / 30;
    final redistributionBuffer = totalDailyBudget * 0.15;

    // Generate intelligent insights summary
    final intelligentInsights = <String>[];
    intelligentInsights.addAll(enhancedResult.personalizedInsights.take(3));
    intelligentInsights.addAll(enhancedResult.recommendations.take(2));

    return EnhancedDailyBudgetCalculation(
      // Legacy compatibility fields
      totalDailyBudget: totalDailyBudget,
      baseAmount: baseAmount,
      redistributionBuffer: redistributionBuffer,
      fixedCommitments: fixedCommitments,
      savingsTarget: savingsTarget,
      confidence: confidence,
      methodology: 'enhanced_intelligence_v2',

      // Enhanced intelligence fields
      enhancedResult: enhancedResult,
      intelligentInsights: intelligentInsights,
      categoryBreakdown: enhancedResult.categoryAllocations,
      contextualNudge: enhancedResult.suggestedNudge,
      tomorrowForecast: enhancedResult.tomorrowForecast,
      explanation: enhancedResult.explanation,
      riskAssessment: enhancedResult.riskScore,
      advancedMetrics: enhancedResult.metadata,
    );
  }

  /// Legacy-compatible calculation with some enhancements
  Future<EnhancedDailyBudgetCalculation> _calculateLegacyCompatibleBudget({
    required OnboardingState onboardingData,
    required DateTime targetDate,
    required String userId,
    required Map<String, dynamic> userProfile,
  }) async {
    // Use enhanced income classification even in legacy mode
    final incomeClassification = await _incomeService.classifyIncomeEnhanced(
      onboardingData.income ?? 0.0,
      countryCode: userProfile['countryCode']?.toString(),
      stateCode: userProfile['stateCode']?.toString(),
    );

    // Get budget parameters from enhanced classification
    final budgetParams = _incomeService.calculateBlendedBudgetParameters(incomeClassification);

    final monthlyIncome = onboardingData.income ?? 0.0;
    final fixedCommitments = monthlyIncome * budgetParams['fixedCommitmentRatio']!;
    final savingsTarget = monthlyIncome * budgetParams['savingsTargetRatio']!;
    final availableSpending = monthlyIncome - fixedCommitments - savingsTarget;
    final baseDailyBudget = availableSpending / 30;

    // Apply basic temporal adjustment
    var temporalMultiplier = 1.0;

    // Weekend adjustment
    if (targetDate.weekday >= 6) {
      temporalMultiplier *= 1.15; // 15% increase for weekends
    }

    // Month-end adjustment
    if (targetDate.day > 25) {
      temporalMultiplier *= 0.85; // 15% decrease for month-end conservation
    }

    final totalDailyBudget = baseDailyBudget * temporalMultiplier;
    final redistributionBuffer = totalDailyBudget * budgetParams['redistributionBuffer']!;

    // Generate basic explanation
    final explanation = await _explanationService.explainBudgetCalculation(
      inputData: {
        'monthlyIncome': monthlyIncome,
        'incomeTier': incomeClassification.primaryTier.toString(),
        'targetDate': targetDate.toIso8601String(),
      },
      calculationResults: {
        'finalDailyBudget': totalDailyBudget,
        'adjustedIncome': monthlyIncome,
        'fixedCommitments': fixedCommitments,
        'savingsTarget': savingsTarget,
        'availableSpending': availableSpending,
        'confidence': incomeClassification.isInTransition ? 0.7 : 0.85,
      },
      context: ExplanationContext(
        userId: userId,
        userLevel: 'intermediate',
        userInterests: <String>[],
        preferVisualExplanations: false,
        preferDetailedMath: false,
        communicationStyle: 'simple',
      ),
    );

    // Generate basic insights
    final insights = <String>[];
    insights.add(_incomeService.generateTierExplanation(incomeClassification));

    if (temporalMultiplier != 1.0) {
      insights.add(
          'Budget adjusted for ${temporalMultiplier > 1.0 ? 'weekend' : 'month-end'} spending patterns');
    }

    // Create mock enhanced result for compatibility
    final mockEnhancedResult = EnhancedBudgetResult(
      dailyBudget: totalDailyBudget,
      confidence: incomeClassification.isInTransition ? 0.7 : 0.85,
      calculationBreakdown: <String, dynamic>{'legacy_mode': true},
      personalizedInsights: insights,
      recommendations: <String>['Track spending to enable enhanced features'],
      categoryAllocations: <String, double>{},
      riskScore: 0.3, // Low risk in legacy mode
      metadata: <String, dynamic>{'mode': 'legacy_compatible'},
    );

    return EnhancedDailyBudgetCalculation(
      // Legacy compatibility fields
      totalDailyBudget: totalDailyBudget,
      baseAmount: baseDailyBudget,
      redistributionBuffer: redistributionBuffer,
      fixedCommitments: fixedCommitments,
      savingsTarget: savingsTarget,
      confidence: incomeClassification.isInTransition ? 0.7 : 0.85,
      methodology: 'enhanced_income_classification',

      // Enhanced intelligence fields (basic versions)
      enhancedResult: mockEnhancedResult,
      intelligentInsights: insights,
      categoryBreakdown: <String, double>{},
      explanation: explanation,
      riskAssessment: 0.3,
      advancedMetrics: <String, dynamic>{'legacy_mode': true},
    );
  }

  /// Convert onboarding state to enhanced user profile
  Map<String, dynamic> _convertOnboardingToProfile(
    OnboardingState onboardingData,
    Map<String, dynamic>? additionalContext,
  ) {
    return {
      'monthlyIncome': onboardingData.income ?? 0.0,
      'incomeTier': onboardingData.incomeTier?.toString() ?? 'middle',
      'countryCode': onboardingData.countryCode ?? 'US',
      'stateCode': onboardingData.stateCode,
      'location': '${onboardingData.countryCode ?? 'US'}-${onboardingData.stateCode ?? 'CA'}',
      'goals': onboardingData.goals,
      'habits': onboardingData.habits,
      'habitsComment': onboardingData.habitsComment,
      'expenses': onboardingData.expenses,
      'experienceLevel': 'intermediate',
      'interests': <String>[],
      'preferVisuals': false,
      'preferMath': false,
      'communicationStyle': 'conversational',
      'spendingPersonality': <String, dynamic>{'primaryTrait': 'balanced'},
      ...?additionalContext,
    };
  }

  /// Generate comprehensive budget intelligence analysis
  Future<BudgetIntelligenceResult> generateBudgetIntelligence({
    required String userId,
    required OnboardingState onboardingData,
    required List<Map<String, dynamic>> transactionHistory,
    DateTime? targetDate,
    Map<String, dynamic>? additionalContext,
  }) async {
    final userProfile = _convertOnboardingToProfile(onboardingData, additionalContext);

    return await _masterEngine.generateBudgetIntelligence(
      userId: userId,
      userProfile: userProfile,
      transactionHistory: transactionHistory,
      targetDate: targetDate ?? DateTime.now(),
    );
  }

  /// Get personalized nudge for current context
  Future<PersonalizedNudge?> getPersonalizedNudge({
    required String userId,
    required NudgeContext context,
    required Map<String, dynamic> contextData,
  }) async {
    return await _nudgeService.generatePersonalizedNudge(
      userId: userId,
      context: context,
      contextData: contextData,
    );
  }

  /// Get social comparison insights
  Future<List<SocialComparisonInsight>> getSocialInsights({
    required String userId,
    required OnboardingState onboardingData,
    required Map<String, dynamic> userMetrics,
  }) async {
    final userProfile = UserDemographicProfile(
      userId: userId,
      incomeTier: (onboardingData.incomeTier != null)
          ? IncomeTier.values.firstWhere(
              (e) => e.toString() == onboardingData.incomeTier.toString(),
              orElse: () => IncomeTier.middle)
          : IncomeTier.middle,
      interests: onboardingData.goals ?? <String>[],
      spendingPersonality: <String, dynamic>{},
    );

    return await _socialService.generateSocialInsights(userId, userProfile, userMetrics);
  }

  /// Analyze spending habits
  Future<HabitAnalysisResult> analyzeSpendingHabits({
    required List<Map<String, dynamic>> transactionHistory,
  }) async {
    return _habitService.analyzeSpendingHabits(transactionHistory);
  }

  /// Get budget forecast
  Future<PredictiveBudgetAnalysis> getBudgetForecast({
    required List<Map<String, dynamic>> historicalData,
    required Map<String, dynamic> currentFinancialState,
    int forecastDays = 30,
  }) async {
    return await _predictiveService.generateBudgetPredictions(
      historicalData: historicalData,
      currentFinancialState: currentFinancialState,
      externalFactors: <Map<String, dynamic>>[],
      forecastDays: forecastDays,
    );
  }

  /// Detect life events affecting budget
  Future<List<LifeEventDetection>> detectLifeEvents({
    required List<Map<String, dynamic>> spendingHistory,
  }) async {
    return await _categoryService.detectLifeEvents(spendingHistory);
  }

  /// Get explanation for any budget calculation
  Future<BudgetExplanation> explainBudgetCalculation({
    required Map<String, dynamic> inputData,
    required Map<String, dynamic> calculationResults,
    required String userId,
    String userLevel = 'intermediate',
  }) async {
    return await _explanationService.explainBudgetCalculation(
      inputData: inputData,
      calculationResults: calculationResults,
      context: ExplanationContext(
        userId: userId,
        userLevel: userLevel,
        userInterests: <String>[],
        preferVisualExplanations: false,
        preferDetailedMath: false,
        communicationStyle: 'conversational',
      ),
    );
  }

  /// Check system health and capabilities
  Map<String, dynamic> getSystemCapabilities() {
    return {
      'enhanced_features_available': true,
      'services_integrated': [
        'enhanced_income_classification',
        'temporal_intelligence',
        'spending_velocity_analysis',
        'habit_recognition',
        'contextual_nudges',
        'social_comparison',
        'predictive_forecasting',
        'category_intelligence',
        'explanation_engine',
      ],
      'backward_compatibility': true,
      'version': '2.0.0',
      'algorithm_sophistication': 'high',
      'personalization_level': 'advanced',
      'explanation_quality': 'detailed',
      'learning_capability': 'continuous',
    };
  }
}

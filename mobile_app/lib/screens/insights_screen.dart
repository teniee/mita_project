import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:provider/provider.dart';
import '../providers/budget_provider.dart';
import '../providers/transaction_provider.dart';
import '../providers/user_provider.dart';
import '../services/api_service.dart';
import '../services/income_service.dart';
import '../services/cohort_service.dart';
import '../widgets/income_tier_widgets.dart';
import '../widgets/peer_comparison_widgets.dart';
import '../theme/income_theme.dart';
import '../utils/string_extensions.dart';
import '../services/logging_service.dart';

class InsightsScreen extends StatefulWidget {
  const InsightsScreen({super.key});

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> with TickerProviderStateMixin {
  // Keep services not covered by providers
  final ApiService _apiService = ApiService();
  final IncomeService _incomeService = IncomeService();
  final CohortService _cohortService = CohortService();

  bool _isAILoading = true;
  late TabController _tabController;

  // Income-related data (computed from UserProvider)
  double _monthlyIncome = 0.0;
  IncomeTier? _incomeTier;

  // Traditional Analytics Data - computed from providers
  List<Map<String, dynamic>> dailyTotals = [];

  // AI Insights Data (not covered by providers)
  Map<String, dynamic>? aiSnapshot;
  Map<String, dynamic>? aiProfile;
  Map<String, dynamic>? spendingPatterns;
  Map<String, dynamic>? personalizedFeedback;
  Map<String, dynamic>? financialHealthScore;
  List<Map<String, dynamic>> spendingAnomalies = [];
  Map<String, dynamic>? savingsOptimization;
  Map<String, dynamic>? weeklyInsights;
  Map<String, dynamic>? aiMonthlyReport;
  Map<String, dynamic>? aiBudgetOptimization;
  Map<String, dynamic>? aiGoalAnalysis;

  // Income-based insights
  Map<String, dynamic>? _peerComparison;
  List<String> _incomeBasedTips = [];
  Map<String, dynamic>? _budgetOptimization;
  Map<String, dynamic>? _incomeClassification;
  List<Map<String, dynamic>> _incomeBasedGoals = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);

    // Initialize providers after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final userProvider = context.read<UserProvider>();
      final budgetProvider = context.read<BudgetProvider>();
      final transactionProvider = context.read<TransactionProvider>();

      // Initialize UserProvider if needed
      if (userProvider.state == UserState.initial) {
        userProvider.initialize();
      }

      if (budgetProvider.state == BudgetState.initial) {
        budgetProvider.initialize();
      }
      if (transactionProvider.state == TransactionState.initial) {
        transactionProvider.initialize();
      }

      // Load monthly transactions for analytics
      final now = DateTime.now();
      transactionProvider.loadMonthlyTransactions(
        year: now.year,
        month: now.month,
      );

      // Fetch AI insights and income-based data
      fetchAIInsights();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> fetchAIInsights() async {
    try {
      // First, get user profile for income data
      await _fetchUserProfile();

      // Fetch AI insights in parallel
      await Future.wait([
        _createAndFetchAISnapshot(),
        _fetchAIProfile(),
        _fetchSpendingPatterns(),
        _fetchPersonalizedFeedback(),
        _fetchFinancialHealthScore(),
        _fetchSpendingAnomalies(),
        _fetchSavingsOptimization(),
        _fetchWeeklyInsights(),
        _fetchAIMonthlyReport(),
        _fetchAIBudgetOptimization(),
        _fetchAIGoalAnalysis(),
        _fetchIncomeBasedInsights(),
      ]);

      if (mounted) {
        setState(() => _isAILoading = false);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isAILoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading insights: $e')),
        );
      }
    }
  }

  Future<void> _fetchUserProfile() async {
    try {
      // Use UserProvider for user profile data
      final userProvider = context.read<UserProvider>();

      // Ensure user data is loaded
      if (userProvider.state == UserState.initial || userProvider.state == UserState.loading) {
        await userProvider.initialize();
      }

      // Get income from UserProvider
      final incomeValue = userProvider.userIncome;
      if (incomeValue <= 0) {
        throw Exception('Income data required for insights. Please complete onboarding.');
      }
      _monthlyIncome = incomeValue;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
    } catch (e) {
      logError('Error fetching user profile: $e');
      throw Exception('Income data required for insights. Please complete onboarding.');
    }
  }

  Future<void> _fetchIncomeBasedInsights() async {
    try {
      final futures = await Future.wait([
        _apiService.getPeerComparison(),
        _apiService.getCohortInsights(),
        _apiService.getIncomeBasedTips(_monthlyIncome),
        _apiService.getIncomeClassification(),
        _apiService.getIncomeBasedGoals(_monthlyIncome),
      ]);

      _peerComparison = futures[0] as Map<String, dynamic>;
      _incomeBasedTips = List<String>.from(futures[2] as List);
      _incomeClassification = futures[3] as Map<String, dynamic>;
      _incomeBasedGoals = List<Map<String, dynamic>>.from(futures[4] as List? ?? []);

      // Generate budget optimization insights using provider data
      final transactionProvider = context.read<TransactionProvider>();
      final categoryTotals = transactionProvider.spendingByCategory;
      if (categoryTotals.isNotEmpty) {
        _budgetOptimization =
            _cohortService.getCohortBudgetOptimization(_monthlyIncome, categoryTotals);
      }
    } catch (e) {
      logError('Error fetching income-based insights: $e');
      _incomeBasedTips = _incomeService.getFinancialTips(_incomeTier ?? IncomeTier.middle);
    }
  }

  void _computeDailyTotals(List<dynamic> transactions) {
    final now = DateTime.now();
    final Map<String, double> daily = {};

    for (final e in transactions) {
      final date = e.spentAt;
      if (date.month == now.month && date.year == now.year) {
        final day = DateFormat('yyyy-MM-dd').format(date);
        daily[day] = (daily[day] ?? 0) + e.amount;
      }
    }

    dailyTotals = daily.entries.map((e) => {'date': e.key, 'amount': e.value}).toList()
      ..sort((a, b) => (a['date'] as String).compareTo(b['date'] as String));
  }

  void _generateSampleAnalyticsData() {
    final dailyBudget = _monthlyIncome / 30;
    final now = DateTime.now();

    // Generate sample daily spending for past 2 weeks
    dailyTotals = List.generate(14, (index) {
      final date = now.subtract(Duration(days: 13 - index));
      final isWeekend = date.weekday == 6 || date.weekday == 7;
      final spendingMultiplier = isWeekend ? 1.3 : 0.8;
      final amount = (dailyBudget * spendingMultiplier * (0.7 + (index % 3) * 0.2));

      return {
        'date': DateFormat('yyyy-MM-dd').format(date),
        'amount': amount,
      };
    });
  }

  /// Create a fresh AI snapshot and fetch it
  Future<void> _createAndFetchAISnapshot() async {
    try {
      final now = DateTime.now();
      await _apiService.createAISnapshot(year: now.year, month: now.month);
      aiSnapshot = await _apiService.getLatestAISnapshot();
    } catch (e) {
      logError('Error creating/fetching AI snapshot: $e');
      aiSnapshot = {
        'rating': 'B+',
        'risk': 'moderate',
        'summary':
            'Your spending patterns show good discipline with occasional room for improvement. You\'re doing well with food budgeting but could optimize transportation costs.',
      };
    }
  }

  Future<void> _fetchAIMonthlyReport() async {
    try {
      final now = DateTime.now();
      aiMonthlyReport = await _apiService.getAIMonthlyReport(year: now.year, month: now.month);
    } catch (e) {
      logError('Error fetching AI monthly report: $e');
    }
  }

  Future<void> _fetchAIProfile() async {
    try {
      aiProfile = await _apiService.getAIFinancialProfile();
    } catch (e) {
      logError('Error fetching AI profile: $e');
    }
  }

  Future<void> _fetchSpendingPatterns() async {
    try {
      spendingPatterns = await _apiService.getSpendingPatterns();
    } catch (e) {
      logError('Error fetching spending patterns: $e');
    }
  }

  Future<void> _fetchPersonalizedFeedback() async {
    try {
      personalizedFeedback = await _apiService.getAIPersonalizedFeedback();
    } catch (e) {
      logError('Error fetching personalized feedback: $e');
    }
  }

  Future<void> _fetchFinancialHealthScore() async {
    try {
      financialHealthScore = await _apiService.getAIFinancialHealthScore();
    } catch (e) {
      logError('Error fetching financial health score: $e');
    }
  }

  Future<void> _fetchSpendingAnomalies() async {
    try {
      spendingAnomalies = await _apiService.getSpendingAnomalies();
    } catch (e) {
      logError('Error fetching spending anomalies: $e');
    }
  }

  Future<void> _fetchSavingsOptimization() async {
    try {
      savingsOptimization = await _apiService.getAISavingsOptimization();
    } catch (e) {
      logError('Error fetching savings optimization: $e');
    }
  }

  Future<void> _fetchWeeklyInsights() async {
    try {
      weeklyInsights = await _apiService.getAIWeeklyInsights();
    } catch (e) {
      logError('Error fetching weekly insights: $e');
    }
  }

  Future<void> _fetchAIBudgetOptimization() async {
    try {
      aiBudgetOptimization = await _apiService.getAIBudgetOptimization();
    } catch (e) {
      logError('Error fetching AI budget optimization: $e');
    }
  }

  Future<void> _fetchAIGoalAnalysis() async {
    try {
      aiGoalAnalysis = await _apiService.getAIGoalAnalysis();
    } catch (e) {
      logError('Error fetching AI goal analysis: $e');
    }
  }

  /// Convert enhanced confidence to letter grade
  String _getGradeFromConfidence(double confidence) {
    if (confidence >= 0.9) return 'A+';
    if (confidence >= 0.85) return 'A';
    if (confidence >= 0.8) return 'A-';
    if (confidence >= 0.75) return 'B+';
    if (confidence >= 0.7) return 'B';
    if (confidence >= 0.65) return 'B-';
    if (confidence >= 0.6) return 'C+';
    if (confidence >= 0.55) return 'C';
    if (confidence >= 0.5) return 'C-';
    return 'D';
  }

  @override
  Widget build(BuildContext context) {
    final userProvider = context.watch<UserProvider>();
    final budgetProvider = context.watch<BudgetProvider>();
    final transactionProvider = context.watch<TransactionProvider>();

    // Update local income data from UserProvider for reactive updates
    if (userProvider.userIncome > 0 && _monthlyIncome != userProvider.userIncome) {
      _monthlyIncome = userProvider.userIncome;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
    }

    // Combined loading state from providers and local AI loading
    final isLoading = _isAILoading ||
        userProvider.state == UserState.loading ||
        budgetProvider.state == BudgetState.loading ||
        transactionProvider.state == TransactionState.loading;

    // Compute daily totals from transaction provider data
    if (transactionProvider.transactions.isNotEmpty) {
      _computeDailyTotals(transactionProvider.transactions);
    } else if (_monthlyIncome > 0 && dailyTotals.isEmpty) {
      _generateSampleAnalyticsData();
    }

    // Use enhanced budget insights from provider if available
    if (budgetProvider.budgetSuggestions.isNotEmpty &&
        budgetProvider.budgetSuggestions['confidence'] != null) {
      final confidence = budgetProvider.budgetSuggestions['confidence'];
      financialHealthScore ??= {
        'score': (confidence * 100).round(),
        'grade': _getGradeFromConfidence(confidence),
        'improvements': budgetProvider.budgetSuggestions['intelligent_insights']
                ?.map((insight) => insight['message'] ?? insight.toString())
                .toList() ??
            [],
      };

      if (budgetProvider.budgetSuggestions['intelligent_insights'] != null) {
        personalizedFeedback ??= {
          'feedback':
              'Based on your spending patterns and financial goals, here are personalized insights from our enhanced budget intelligence system.',
          'tips': budgetProvider.budgetSuggestions['intelligent_insights']
              .map((insight) => insight['message'] ?? insight.toString())
              .toList(),
        };
      }

      if (budgetProvider.budgetSuggestions['category_insights'] != null) {
        final categoryInsights = budgetProvider.budgetSuggestions['category_insights'] as List;
        spendingPatterns ??= {
          'patterns': categoryInsights
              .map((insight) => insight['message'] ?? 'Smart category optimization detected')
              .toList(),
        };
      }
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: _incomeTier != null
          ? IncomeTheme.createTierAppBar(
              tier: _incomeTier!,
              title: 'Financial Insights',
            )
          : AppBar(
              title: const Text(
                'Financial Insights',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              backgroundColor: AppColors.background,
              elevation: 0,
              iconTheme: const IconThemeData(color: AppColors.textPrimary),
              centerTitle: true,
            ),
      body:
          isLoading ? _buildLoadingState() : _buildTabContent(budgetProvider, transactionProvider),
    );
  }

  Widget _buildLoadingState() {
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : AppColors.textPrimary;

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: primaryColor),
          const SizedBox(height: 16),
          Text(
            'Analyzing your financial data...',
            style: TextStyle(
              fontFamily: AppTypography.fontBody,
              color: primaryColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabContent(BudgetProvider budgetProvider, TransactionProvider transactionProvider) {
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : AppColors.textPrimary;

    return Column(
      children: [
        // Income tier header
        if (_incomeTier != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            child: IncomeTierCard(
              monthlyIncome: _monthlyIncome,
              showDetails: false,
            ),
          ),

        // Tab bar
        TabBar(
          controller: _tabController,
          labelColor: primaryColor,
          unselectedLabelColor: Colors.grey,
          indicatorColor: primaryColor,
          isScrollable: true,
          tabs: const [
            Tab(text: 'AI Overview'),
            Tab(text: 'Analytics'),
            Tab(text: 'Peer Insights'),
            Tab(text: 'Recommendations'),
          ],
        ),

        // Tab content
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildAIOverviewTab(),
              _buildAnalyticsTab(transactionProvider),
              _buildPeerInsightsTab(transactionProvider),
              _buildRecommendationsTab(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPeerInsightsTab(TransactionProvider transactionProvider) {
    final categoryTotals = transactionProvider.spendingByCategory;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Peer comparison
          if (_peerComparison != null && _incomeTier != null)
            PeerComparisonCard(
              comparisonData: _peerComparison!,
              monthlyIncome: _monthlyIncome,
            ),

          const SizedBox(height: 20),

          // Cohort insights
          if (_incomeTier != null) CohortInsightsWidget(monthlyIncome: _monthlyIncome),

          const SizedBox(height: 20),

          // Spending trends comparison
          if (categoryTotals.isNotEmpty)
            SpendingTrendsComparisonWidget(
              userSpending: categoryTotals,
              monthlyIncome: _monthlyIncome,
              peerData: _peerComparison,
            ),

          const SizedBox(height: 20),

          // Income-based tips
          if (_incomeBasedTips.isNotEmpty)
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.lightbulb_rounded,
                          color: _incomeTier != null
                              ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
                              : Colors.amber,
                          size: 24,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'Tips for Your Income Level',
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                            color: _incomeTier != null
                                ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
                                : AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    ..._incomeBasedTips.map(
                      (tip) => Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.blue.shade200),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.check_circle_rounded,
                              color: Colors.blue.shade600,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                tip,
                                style: const TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  fontSize: 14,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildAIOverviewTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // AI Financial Health Score
          _buildFinancialHealthCard(),
          const SizedBox(height: 20),

          // AI Snapshot
          _buildAISnapshotCard(),
          const SizedBox(height: 20),

          // AI Monthly Report
          _buildAIMonthlyReportCard(),
          const SizedBox(height: 20),

          // Spending Patterns
          _buildSpendingPatternsCard(),
          const SizedBox(height: 20),

          // Weekly Insights
          _buildWeeklyInsightsCard(),
          const SizedBox(height: 20),

          // Anomalies Detection
          _buildAnomaliesCard(),
        ],
      ),
    );
  }

  Widget _buildAnalyticsTab(TransactionProvider transactionProvider) {
    final totalSpending = transactionProvider.totalSpending;
    final categoryTotals = transactionProvider.spendingByCategory;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Total Spending This Month: \$${totalSpending.toStringAsFixed(2)}',
            style: const TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontWeight: FontWeight.bold,
              fontSize: 18,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 20),
          if (categoryTotals.isNotEmpty) ...[
            const Text(
              'Spending by Category',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 10),
            Container(
              height: 250,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.grey.withValues(alpha: 0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: PieChart(
                PieChartData(
                  sections: categoryTotals.entries.map((e) {
                    final value = e.value;
                    return PieChartSectionData(
                      title: '\$${value.toStringAsFixed(0)}',
                      value: value,
                      titleStyle: const TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                      radius: 80,
                      color: _getCategoryColor(e.key),
                    );
                  }).toList(),
                ),
              ),
            ),
          ],
          const SizedBox(height: 30),
          if (dailyTotals.isNotEmpty) ...[
            const Text(
              'Daily Spending Trend',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 10),
            Container(
              height: 250,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.grey.withValues(alpha: 0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: BarChart(
                BarChartData(
                  borderData: FlBorderData(show: false),
                  gridData: const FlGridData(show: false),
                  backgroundColor: Colors.transparent,
                  titlesData: FlTitlesData(
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 32,
                        getTitlesWidget: (value, meta) {
                          final index = value.toInt();
                          if (index < 0 || index >= dailyTotals.length) return Container();
                          final label = DateFormat('MM/dd')
                              .format(DateTime.parse(dailyTotals[index]['date']));
                          return Text(
                            label,
                            style: const TextStyle(
                              fontSize: 10,
                              fontFamily: AppTypography.fontBody,
                              color: AppColors.textPrimary,
                            ),
                          );
                        },
                        interval: 1,
                      ),
                    ),
                    leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  ),
                  barGroups: List.generate(dailyTotals.length, (i) {
                    return BarChartGroupData(
                      x: i,
                      barRods: [
                        BarChartRodData(
                          toY: dailyTotals[i]['amount'],
                          width: 14,
                          borderRadius: BorderRadius.circular(6),
                          gradient: LinearGradient(
                            colors: [
                              AppColors.textPrimary.withValues(alpha: 0.7),
                              AppColors.textPrimary
                            ],
                            begin: Alignment.bottomCenter,
                            end: Alignment.topCenter,
                          ),
                        ),
                      ],
                    );
                  }),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildRecommendationsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Income-based budget optimization
          if (_budgetOptimization != null) _buildBudgetOptimizationCard(),

          if (_budgetOptimization != null) const SizedBox(height: 20),

          // Cohort-based habit recommendations
          if (_incomeTier != null) _buildCohortHabitRecommendationsCard(),

          if (_incomeTier != null) const SizedBox(height: 20),

          // Personalized Feedback
          _buildPersonalizedFeedbackCard(),
          const SizedBox(height: 20),

          // Savings Optimization
          _buildSavingsOptimizationCard(),
          const SizedBox(height: 20),

          // Income-level specific goal suggestions
          if (_incomeTier != null) _buildIncomeGoalSuggestionsCard(),
        ],
      ),
    );
  }

  Widget _buildFinancialHealthCard() {
    if (financialHealthScore == null) return Container();

    final score = financialHealthScore!['score'] ?? 75;
    final grade = financialHealthScore!['grade'] ?? 'B+';
    final improvements = List<String>.from(financialHealthScore!['improvements'] ?? []);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.textPrimary,
            AppColors.textPrimary.withValues(alpha: 0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(
                Icons.health_and_safety,
                color: Colors.white,
                size: 24,
              ),
              SizedBox(width: 12),
              Text(
                'Financial Health Score',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                  color: Colors.white,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Text(
                '$score',
                style: const TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 48,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '/ 100',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 18,
                  color: Colors.white.withValues(alpha: 0.7),
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Grade: $grade',
                  style: const TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          if (improvements.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Key Improvements:',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            ...improvements.take(3).map((improvement) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Icon(
                        Icons.arrow_right,
                        color: Colors.white.withValues(alpha: 0.7),
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          improvement,
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white.withValues(alpha: 0.9),
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _buildAISnapshotCard() {
    if (aiSnapshot == null) return Container();

    final rating = aiSnapshot!['rating'] ?? 'B';
    final risk = aiSnapshot!['risk'] ?? 'moderate';
    final summary = aiSnapshot!['summary'] ?? 'No summary available';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.psychology,
                  color: AppColors.textPrimary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'AI Financial Analysis',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildScoreChip('Rating', rating, _getRatingColor(rating)),
              const SizedBox(width: 12),
              _buildScoreChip('Risk', risk, _getRiskColor(risk)),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            summary,
            style: const TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSpendingPatternsCard() {
    if (spendingPatterns == null) return Container();

    final patterns = List<String>.from(spendingPatterns!['patterns'] ?? []);

    if (patterns.isEmpty) return Container();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.trending_up,
                  color: AppColors.textPrimary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Spending Patterns',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: patterns
                .map((pattern) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.textPrimary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        _formatPatternName(pattern),
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildWeeklyInsightsCard() {
    if (weeklyInsights == null) return Container();

    final insights = weeklyInsights!['insights'] ?? 'No insights available this week.';
    final trend = weeklyInsights!['trend'] ?? 'stable';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.calendar_view_week,
                  color: AppColors.textPrimary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Weekly Insights',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
              const Spacer(),
              _buildTrendIndicator(trend),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            insights,
            style: const TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnomaliesCard() {
    if (spendingAnomalies.isEmpty) return Container();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.orange.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.warning_amber,
                  color: Colors.orange,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Spending Anomalies',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Colors.orange,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...spendingAnomalies.take(3).map((anomaly) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  children: [
                    const Icon(
                      Icons.error_outline,
                      color: Colors.orange,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        anomaly['description'] ?? 'Unusual spending detected',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 14,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildPersonalizedFeedbackCard() {
    if (personalizedFeedback == null) return Container();

    final feedback = personalizedFeedback!['feedback'] ?? 'No feedback available';
    final tips = List<String>.from(personalizedFeedback!['tips'] ?? []);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.lightbulb_outline,
                  color: AppColors.textPrimary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Personalized Recommendations',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            feedback,
            style: const TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          if (tips.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Action Items:',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            ...tips.map((tip) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        margin: const EdgeInsets.only(top: 6),
                        decoration: const BoxDecoration(
                          color: AppColors.textPrimary,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          tip,
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 14,
                            color: AppColors.textSecondary,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _buildSavingsOptimizationCard() {
    if (savingsOptimization == null) return Container();

    final potentialSavings = savingsOptimization!['potential_savings'] ?? 0.0;
    final suggestions = List<String>.from(savingsOptimization!['suggestions'] ?? []);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.green.withValues(alpha: 0.1),
            Colors.green.withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.savings,
                  color: Colors.green,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Savings Optimization',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Colors.green,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            'Potential Monthly Savings: \$${potentialSavings.toStringAsFixed(2)}',
            style: const TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontWeight: FontWeight.w600,
              fontSize: 18,
              color: Colors.green,
            ),
          ),
          if (suggestions.isNotEmpty) ...[
            const SizedBox(height: 16),
            ...suggestions.map((suggestion) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.eco,
                        color: Colors.green,
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          suggestion,
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 14,
                            color: AppColors.textSecondary,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _buildScoreChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            value.toUpperCase(),
            style: TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrendIndicator(String trend) {
    IconData icon;
    Color color;

    switch (trend.toLowerCase()) {
      case 'improving':
        icon = Icons.trending_up;
        color = Colors.green;
        break;
      case 'declining':
        icon = Icons.trending_down;
        color = Colors.red;
        break;
      default:
        icon = Icons.trending_flat;
        color = Colors.orange;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 4),
          Text(
            trend.capitalize(),
            style: TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Color _getRatingColor(String rating) {
    switch (rating.toUpperCase()) {
      case 'A':
      case 'A+':
        return Colors.green;
      case 'B':
      case 'B+':
        return Colors.blue;
      case 'C':
      case 'C+':
        return Colors.orange;
      default:
        return Colors.red;
    }
  }

  Color _getRiskColor(String risk) {
    switch (risk.toLowerCase()) {
      case 'low':
        return Colors.green;
      case 'moderate':
        return Colors.orange;
      case 'high':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  Color _getCategoryColor(String category) {
    final colors = [
      AppColors.textPrimary,
      AppColors.info,
      AppColors.chart7,
      AppColors.accent,
      AppColors.categoryEntertainment,
    ];
    return colors[category.hashCode % colors.length];
  }

  String _formatPatternName(String pattern) {
    return pattern.replaceAll('_', ' ').split(' ').map((word) => word.capitalize()).join(' ');
  }

  Widget _buildBudgetOptimizationCard() {
    if (_budgetOptimization == null) return Container();

    final suggestions = List<String>.from(_budgetOptimization!['suggestions'] ?? []);
    final overallScore = _budgetOptimization!['overall_score'] ?? 100.0;
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : AppColors.textPrimary;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: primaryColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.tune_rounded,
                  color: primaryColor,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'Budget Optimization',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                  color: primaryColor,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: _getScoreColor(overallScore.toInt()).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  '${overallScore.toStringAsFixed(0)}%',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.bold,
                    color: _getScoreColor(overallScore.toInt()),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (suggestions.isNotEmpty) ...[
            Text(
              'Optimization Suggestions:',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: primaryColor,
              ),
            ),
            const SizedBox(height: 12),
            ...suggestions.take(3).map(
                  (suggestion) => Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: primaryColor.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: primaryColor.withValues(alpha: 0.2)),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.auto_fix_high_rounded,
                          color: primaryColor,
                          size: 16,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            suggestion,
                            style: const TextStyle(
                              fontFamily: AppTypography.fontBody,
                              fontSize: 14,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ],
      ),
    );
  }

  Widget _buildCohortHabitRecommendationsCard() {
    final habits = _cohortService.getCohortHabitRecommendations(_monthlyIncome);
    final primaryColor = _incomeService.getIncomeTierPrimaryColor(_incomeTier!);
    final tierName = _incomeService.getIncomeTierName(_incomeTier!);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: primaryColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.fitness_center_rounded,
                  color: primaryColor,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Recommended Habits',
                      style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                        color: primaryColor,
                      ),
                    ),
                    Text(
                      'Based on successful $tierName patterns',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          ...habits.map(
            (habit) => Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: habit['color'].withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: habit['color'].withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          habit['icon'],
                          color: habit['color'],
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              habit['title'],
                              style: TextStyle(
                                fontFamily: AppTypography.fontHeading,
                                fontWeight: FontWeight.w600,
                                fontSize: 16,
                                color: habit['color'],
                              ),
                            ),
                            Text(
                              habit['frequency'].toString().toUpperCase(),
                              style: TextStyle(
                                fontFamily: AppTypography.fontBody,
                                fontSize: 11,
                                color: Colors.grey.shade600,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.green.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          '${habit['peer_adoption']} adopt',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 10,
                            color: Colors.green,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    habit['description'],
                    style: const TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(
                        Icons.trending_up,
                        size: 14,
                        color: habit['impact'] == 'high' ? Colors.green : Colors.blue,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '${habit['impact'].toString().toUpperCase()} IMPACT',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 10,
                          color: habit['impact'] == 'high' ? Colors.green : Colors.blue,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIncomeGoalSuggestionsCard() {
    final goalSuggestions = _cohortService.getCohortGoalSuggestions(_monthlyIncome);
    if (goalSuggestions.isEmpty) return Container();

    final primaryColor = _incomeService.getIncomeTierPrimaryColor(_incomeTier!);
    final tierName = _incomeService.getIncomeTierName(_incomeTier!);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: primaryColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.flag_rounded,
                  color: primaryColor,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Suggested Goals',
                      style: TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                        color: primaryColor,
                      ),
                    ),
                    Text(
                      'Popular goals among $tierName users',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          ...goalSuggestions.take(3).map(
                (goal) => Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        primaryColor.withValues(alpha: 0.05),
                        primaryColor.withValues(alpha: 0.02),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: primaryColor.withValues(alpha: 0.2)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              goal['title'],
                              style: TextStyle(
                                fontFamily: AppTypography.fontHeading,
                                fontWeight: FontWeight.w600,
                                fontSize: 16,
                                color: primaryColor,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.blue.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              '${(goal['peer_adoption'] * 100).toStringAsFixed(0)}% adopt',
                              style: const TextStyle(
                                fontFamily: AppTypography.fontBody,
                                fontSize: 10,
                                color: Colors.blue,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        goal['description'],
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 14,
                          height: 1.4,
                        ),
                      ),
                      if (goal['target_amount'] != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Target: \$${goal['target_amount'].toStringAsFixed(0)}',
                          style: TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontWeight: FontWeight.bold,
                            color: primaryColor,
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.7),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.info_outline,
                              size: 16,
                              color: Colors.blue.shade600,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                goal['cohort_context'],
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  fontSize: 12,
                                  color: Colors.blue.shade700,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }

  Color _getScoreColor(int score) {
    if (score >= 80) return Colors.green;
    if (score >= 60) return Colors.orange;
    return Colors.red;
  }

  /// Build AI Monthly Report Card
  Widget _buildAIMonthlyReportCard() {
    if (aiMonthlyReport == null) return Container();

    final summary = aiMonthlyReport!['summary'] ?? 'No monthly summary available';
    final highlights = List<String>.from(aiMonthlyReport!['highlights'] ?? []);
    final recommendations = List<String>.from(aiMonthlyReport!['recommendations'] ?? []);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.accent.withValues(alpha: 0.1),
            AppColors.accent.withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.accent.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.accent.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.summarize,
                  color: AppColors.accent,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'AI Monthly Report',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                  color: AppColors.accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            summary,
            style: const TextStyle(
              fontFamily: AppTypography.fontBody,
              fontSize: 14,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          if (highlights.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Key Highlights:',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            ...highlights.map((highlight) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.star,
                        color: AppColors.secondary,
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          highlight,
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 14,
                            color: AppColors.textSecondary,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
          if (recommendations.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Recommendations:',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            ...recommendations.map((rec) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.arrow_forward,
                        color: AppColors.accent,
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          rec,
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 14,
                            color: AppColors.textSecondary,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }
}


import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import '../services/api_service.dart';

class InsightsScreen extends StatefulWidget {
  const InsightsScreen({Key? key}) : super(key: key);

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  late TabController _tabController;
  
  // Traditional Analytics Data
  double totalSpending = 0;
  Map<String, double> categoryTotals = {};
  List<Map<String, dynamic>> dailyTotals = [];
  
  // AI Insights Data
  Map<String, dynamic>? aiSnapshot;
  Map<String, dynamic>? aiProfile;
  Map<String, dynamic>? spendingPatterns;
  Map<String, dynamic>? personalizedFeedback;
  Map<String, dynamic>? financialHealthScore;
  List<Map<String, dynamic>> spendingAnomalies = [];
  Map<String, dynamic>? savingsOptimization;
  Map<String, dynamic>? weeklyInsights;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    fetchInsights();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> fetchInsights() async {
    try {
      // Fetch traditional analytics
      await _fetchTraditionalAnalytics();
      
      // Fetch AI insights in parallel
      await Future.wait([
        _fetchAISnapshot(),
        _fetchAIProfile(),
        _fetchSpendingPatterns(),
        _fetchPersonalizedFeedback(),
        _fetchFinancialHealthScore(),
        _fetchSpendingAnomalies(),
        _fetchSavingsOptimization(),
        _fetchWeeklyInsights(),
      ]);

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading insights: $e')),
        );
      }
    }
  }

  Future<void> _fetchTraditionalAnalytics() async {
    final analytics = await _apiService.getMonthlyAnalytics();
    final expenses = await _apiService.getExpenses();
    final now = DateTime.now();
    final monthExpenses = expenses.where((e) {
      final date = DateTime.parse(e['date']);
      return date.month == now.month && date.year == now.year;
    });

    double sum = 0;
    final Map<String, double> catSums =
        Map<String, double>.from(analytics['categories'] as Map);
    final Map<String, double> daily = {};

    for (final e in monthExpenses) {
      sum += e['amount'];
      final day = DateFormat('yyyy-MM-dd').format(DateTime.parse(e['date']));
      daily[day] = (daily[day] ?? 0) + e['amount'];
    }

    totalSpending = sum;
    categoryTotals = catSums;
    dailyTotals = daily.entries
        .map((e) => {'date': e.key, 'amount': e.value})
        .toList()
      ..sort((a, b) => (a['date'] as String).compareTo(b['date'] as String));
  }

  Future<void> _fetchAISnapshot() async {
    try {
      aiSnapshot = await _apiService.getLatestAISnapshot();
    } catch (e) {
      print('Error fetching AI snapshot: $e');
    }
  }

  Future<void> _fetchAIProfile() async {
    try {
      aiProfile = await _apiService.getAIFinancialProfile();
    } catch (e) {
      print('Error fetching AI profile: $e');
    }
  }

  Future<void> _fetchSpendingPatterns() async {
    try {
      spendingPatterns = await _apiService.getSpendingPatterns();
    } catch (e) {
      print('Error fetching spending patterns: $e');
    }
  }

  Future<void> _fetchPersonalizedFeedback() async {
    try {
      personalizedFeedback = await _apiService.getAIPersonalizedFeedback();
    } catch (e) {
      print('Error fetching personalized feedback: $e');
    }
  }

  Future<void> _fetchFinancialHealthScore() async {
    try {
      financialHealthScore = await _apiService.getAIFinancialHealthScore();
    } catch (e) {
      print('Error fetching financial health score: $e');
    }
  }

  Future<void> _fetchSpendingAnomalies() async {
    try {
      spendingAnomalies = await _apiService.getSpendingAnomalies();
    } catch (e) {
      print('Error fetching spending anomalies: $e');
    }
  }

  Future<void> _fetchSavingsOptimization() async {
    try {
      savingsOptimization = await _apiService.getAISavingsOptimization();
    } catch (e) {
      print('Error fetching savings optimization: $e');
    }
  }

  Future<void> _fetchWeeklyInsights() async {
    try {
      weeklyInsights = await _apiService.getAIWeeklyInsights();
    } catch (e) {
      print('Error fetching weekly insights: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'AI Insights',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
          ),
        ),
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
        bottom: _isLoading ? null : TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF193C57),
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFF193C57),
          tabs: const [
            Tab(text: 'AI Overview'),
            Tab(text: 'Analytics'),
            Tab(text: 'Recommendations'),
          ],
        ),
      ),
      body: _isLoading 
        ? const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(color: Color(0xFF193C57)),
                SizedBox(height: 16),
                Text(
                  'Analyzing your financial data...',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
          )
        : TabBarView(
            controller: _tabController,
            children: [
              _buildAIOverviewTab(),
              _buildAnalyticsTab(),
              _buildRecommendationsTab(),
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

  Widget _buildAnalyticsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Total Spending This Month: \$${totalSpending.toStringAsFixed(2)}',
            style: const TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              fontSize: 18,
              color: Color(0xFF193C57),
            ),
          ),
          const SizedBox(height: 20),
          
          if (categoryTotals.isNotEmpty) ...[
            const Text(
              'Spending by Category',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: Color(0xFF193C57),
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
                    color: Colors.grey.withOpacity(0.1),
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
                        fontFamily: 'Manrope',
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
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: Color(0xFF193C57),
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
                    color: Colors.grey.withOpacity(0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: BarChart(
                BarChartData(
                  borderData: FlBorderData(show: false),
                  gridData: FlGridData(show: false),
                  backgroundColor: Colors.transparent,
                  titlesData: FlTitlesData(
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 32,
                        getTitlesWidget: (value, meta) {
                          final index = value.toInt();
                          if (index < 0 || index >= dailyTotals.length) return Container();
                          final label = DateFormat('MM/dd').format(DateTime.parse(dailyTotals[index]['date']));
                          return Text(
                            label, 
                            style: const TextStyle(
                              fontSize: 10,
                              fontFamily: 'Manrope',
                              color: Color(0xFF193C57),
                            ),
                          );
                        },
                        interval: 1,
                      ),
                    ),
                    leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
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
                              const Color(0xFF193C57).withOpacity(0.7),
                              const Color(0xFF193C57)
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
          // Personalized Feedback
          _buildPersonalizedFeedbackCard(),
          const SizedBox(height: 20),
          
          // Savings Optimization
          _buildSavingsOptimizationCard(),
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
            const Color(0xFF193C57),
            const Color(0xFF193C57).withOpacity(0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.health_and_safety,
                color: Colors.white,
                size: 24,
              ),
              const SizedBox(width: 12),
              const Text(
                'Financial Health Score',
                style: TextStyle(
                  fontFamily: 'Sora',
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
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 48,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '/ 100',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 18,
                  color: Colors.white.withOpacity(0.7),
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  'Grade: $grade',
                  style: const TextStyle(
                    fontFamily: 'Sora',
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
                fontFamily: 'Sora',
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
                    color: Colors.white.withOpacity(0.7),
                    size: 16,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      improvement,
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        color: Colors.white.withOpacity(0.9),
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
            color: Colors.grey.withOpacity(0.1),
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
                  color: const Color(0xFF193C57).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.psychology,
                  color: Color(0xFF193C57),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'AI Financial Analysis',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Color(0xFF193C57),
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
              fontFamily: 'Manrope',
              fontSize: 14,
              color: Color(0xFF666666),
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
            color: Colors.grey.withOpacity(0.1),
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
                  color: const Color(0xFF193C57).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.trending_up,
                  color: Color(0xFF193C57),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Spending Patterns',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Color(0xFF193C57),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: patterns.map((pattern) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFF193C57).withOpacity(0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                _formatPatternName(pattern),
                style: const TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 12,
                  color: Color(0xFF193C57),
                  fontWeight: FontWeight.w500,
                ),
              ),
            )).toList(),
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
            color: Colors.grey.withOpacity(0.1),
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
                  color: const Color(0xFF193C57).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.calendar_view_week,
                  color: Color(0xFF193C57),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Weekly Insights',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Color(0xFF193C57),
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
              fontFamily: 'Manrope',
              fontSize: 14,
              color: Color(0xFF666666),
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
        border: Border.all(color: Colors.orange.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.grey.withOpacity(0.1),
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
                  color: Colors.orange.withOpacity(0.1),
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
                  fontFamily: 'Sora',
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
                      fontFamily: 'Manrope',
                      fontSize: 14,
                      color: Color(0xFF666666),
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
            color: Colors.grey.withOpacity(0.1),
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
                  color: const Color(0xFF193C57).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.lightbulb_outline,
                  color: Color(0xFF193C57),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Personalized Recommendations',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Color(0xFF193C57),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            feedback,
            style: const TextStyle(
              fontFamily: 'Manrope',
              fontSize: 14,
              color: Color(0xFF666666),
              height: 1.5,
            ),
          ),
          if (tips.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Action Items:',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: Color(0xFF193C57),
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
                      color: Color(0xFF193C57),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tip,
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 14,
                        color: Color(0xFF666666),
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
            Colors.green.withOpacity(0.1),
            Colors.green.withOpacity(0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.green.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.2),
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
                  fontFamily: 'Sora',
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
              fontFamily: 'Sora',
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
                        fontFamily: 'Manrope',
                        fontSize: 14,
                        color: Color(0xFF666666),
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
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontFamily: 'Manrope',
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            value.toUpperCase(),
            style: TextStyle(
              fontFamily: 'Sora',
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
        color: color.withOpacity(0.1),
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
              fontFamily: 'Manrope',
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
      const Color(0xFF193C57),
      const Color(0xFF2E5984),
      const Color(0xFF4A7BA7),
      const Color(0xFF6D8DD4),
      const Color(0xFF9BB5FF),
    ];
    return colors[category.hashCode % colors.length];
  }

  String _formatPatternName(String pattern) {
    return pattern
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.capitalize())
        .join(' ');
  }
}

extension StringExtension on String {
  String capitalize() {
    if (isEmpty) return this;
    return '${this[0].toUpperCase()}${substring(1).toLowerCase()}';
  }
}


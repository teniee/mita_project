import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class BehavioralInsightsScreen extends StatefulWidget {
  const BehavioralInsightsScreen({super.key});

  @override
  State<BehavioralInsightsScreen> createState() => _BehavioralInsightsScreenState();
}

class _BehavioralInsightsScreenState extends State<BehavioralInsightsScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  late TabController _tabController;
  
  bool _isLoading = true;
  Map<String, dynamic> _patterns = {};
  Map<String, dynamic> _predictions = {};
  List<dynamic> _anomalies = [];
  Map<String, dynamic> _insights = {};
  Map<String, dynamic> _behavioralPredictions = {};
  Map<String, dynamic> _adaptiveRecommendations = {};
  Map<String, dynamic> _behavioralCluster = {};
  Map<String, dynamic> _behavioralProgress = {};
  Map<String, dynamic> _behavioralAnomalies = {};
  Map<String, dynamic> _spendingTriggers = {};
  Map<String, dynamic> _behavioralWarnings = {};
  Map<String, dynamic> _behavioralPreferences = {};
  Map<String, dynamic> _behavioralCalendar = {};
  List<Map<String, dynamic>> _behavioralExpenseSuggestions = [];
  Map<String, dynamic> _behavioralNotificationSettings = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 6, vsync: this);
    _loadBehavioralData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadBehavioralData() async {
    setState(() => _isLoading = true);

    try {
      final results = await Future.wait([
        _apiService.getSpendingPatterns(),
        _apiService.getBehaviorPredictions(),
        _apiService.getBehaviorAnomalies(),
        _apiService.getBehaviorInsights(),
        _apiService.getBehavioralPredictions(),
        _apiService.getAdaptiveBehaviorRecommendations(),
        _apiService.getBehavioralCluster(),
        _apiService.getBehavioralProgress(months: 6),
        _apiService.getBehavioralAnomalies(),
        _apiService.getSpendingTriggers(),
        _apiService.getBehavioralWarnings(),
        _apiService.getBehavioralPreferences(),
        _apiService.getBehaviorCalendar(),
        _apiService.getBehavioralExpenseSuggestions(categoryPreferences: {}),
        _apiService.getBehavioralNotificationSettings(),
      ]);

      if (!mounted) return;
      setState(() {
        _patterns = Map<String, dynamic>.from(results[0] as Map);
        _predictions = Map<String, dynamic>.from(results[1] as Map);
        _anomalies = List<dynamic>.from(results[2] as List);
        _insights = Map<String, dynamic>.from(results[3] as Map);
        _behavioralPredictions = Map<String, dynamic>.from(results[4] as Map);
        _adaptiveRecommendations = Map<String, dynamic>.from(results[5] as Map);
        _behavioralCluster = Map<String, dynamic>.from(results[6] as Map);
        _behavioralProgress = Map<String, dynamic>.from(results[7] as Map);
        _behavioralAnomalies = Map<String, dynamic>.from(results[8] as Map);
        _spendingTriggers = Map<String, dynamic>.from(results[9] as Map);
        _behavioralWarnings = Map<String, dynamic>.from(results[10] as Map);
        _behavioralPreferences = Map<String, dynamic>.from(results[11] as Map);
        _behavioralCalendar = Map<String, dynamic>.from(results[12] as Map);
        _behavioralExpenseSuggestions = List<Map<String, dynamic>>.from(results[13] as List? ?? []);
        _behavioralNotificationSettings = Map<String, dynamic>.from(results[14] as Map);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load behavioral data: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Behavioral Insights',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        backgroundColor: const AppColors.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: const AppColors.textPrimary,
          unselectedLabelColor: Colors.grey,
          indicatorColor: const AppColors.secondary,
          labelStyle: const TextStyle(
            fontFamily: AppTypography.fontBody,
            fontWeight: FontWeight.w600,
            fontSize: 12,
          ),
          tabs: const [
            Tab(text: 'Patterns'),
            Tab(text: 'Predictions'),
            Tab(text: 'Anomalies'),
            Tab(text: 'Insights'),
            Tab(text: 'Progress'),
            Tab(text: 'Cluster'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildPatternsTab(),
                _buildPredictionsTab(),
                _buildAnomaliesTab(),
                _buildInsightsTab(),
                _buildProgressTab(),
                _buildClusterTab(),
              ],
            ),
    );
  }

  Widget _buildPatternsTab() {
    final patterns = _patterns['patterns'] as List<dynamic>? ?? [];
    final analysis = _patterns['analysis'] as Map<String, dynamic>? ?? {};

    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader('Your Spending Patterns', Icons.psychology),
            const SizedBox(height: 16),
            
            // Pattern Tags
            if (patterns.isNotEmpty) ...[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: patterns.map<Widget>((pattern) {
                  return _buildPatternTag(pattern.toString());
                }).toList(),
              ),
              const SizedBox(height: 24),
            ],

            // Analysis Details
            if (analysis.isNotEmpty) ...[
              _buildAnalysisCard('Weekend Spending', 
                '${((analysis['weekend_spending_ratio'] ?? 0.0) * 100).toInt()}%',
                'of your spending happens on weekends',
                Icons.weekend,
                const AppColors.categoryEntertainment),
              const SizedBox(height: 12),
              
              _buildAnalysisCard('Food Focused', 
                '${((analysis['food_spending_ratio'] ?? 0.0) * 100).toInt()}%',
                'of your budget goes to food',
                Icons.restaurant,
                const AppColors.success),
              const SizedBox(height: 24),
            ],

            // Peak Times
            if (analysis['peak_spending_times'] != null) ...[
              _buildSectionHeader('Peak Spending Times', Icons.schedule),
              const SizedBox(height: 12),
              ...(analysis['peak_spending_times'] as List).map((time) =>
                  _buildInfoTile(time.toString(), Icons.access_time)),
              const SizedBox(height: 24),
            ],

            // Recommendations
            if (analysis['recommendations'] != null) ...[
              _buildSectionHeader('Recommendations', Icons.lightbulb),
              const SizedBox(height: 12),
              ...(analysis['recommendations'] as List).map((rec) =>
                  _buildRecommendationTile(rec.toString())),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildPredictionsTab() {
    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader('Next Month Prediction', Icons.trending_up),
            const SizedBox(height: 16),
            
            // Prediction Card
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 3,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: const LinearGradient(
                    colors: [AppColors.info, Color(0xFF42A5F5)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Predicted Spending',
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white,
                            fontSize: 16,
                          ),
                        ),
                        Text(
                          '${((_predictions['confidence'] ?? 0.0) * 100).toInt()}% confident',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '\$${(_predictions['next_month_spending'] ?? 0.0).toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        color: Colors.white,
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Recommended Budget',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  color: Colors.white70,
                                  fontSize: 12,
                                ),
                              ),
                              Text(
                                '\$${(_predictions['recommended_budget'] ?? 0.0).toStringAsFixed(2)}',
                                style: const TextStyle(
                                  fontFamily: AppTypography.fontHeading,
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Savings Potential',
                                style: TextStyle(
                                  fontFamily: AppTypography.fontBody,
                                  color: Colors.white70,
                                  fontSize: 12,
                                ),
                              ),
                              Text(
                                '+\$${(_predictions['savings_potential'] ?? 0.0).toStringAsFixed(2)}',
                                style: const TextStyle(
                                  fontFamily: AppTypography.fontHeading,
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Risk Factors
            if (_predictions['risk_factors'] != null) ...[
              _buildSectionHeader('Risk Factors', Icons.warning),
              const SizedBox(height: 12),
              ...(_predictions['risk_factors'] as List).map((risk) =>
                  _buildRiskFactorTile(risk)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAnomaliesTab() {
    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: _anomalies.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.check_circle, size: 64, color: AppColors.success),
                  SizedBox(height: 16),
                  Text(
                    'No anomalies detected',
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Your spending patterns look normal',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _anomalies.length,
              itemBuilder: (context, index) {
                final anomaly = _anomalies[index];
                return _buildAnomalyCard(anomaly);
              },
            ),
    );
  }

  Widget _buildInsightsTab() {
    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Personality Card
            Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 3,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: const LinearGradient(
                    colors: [AppColors.categoryEntertainment, Color(0xFFBA68C8)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Your Spending Personality',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        color: Colors.white,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _insights['spending_personality'] ?? 'Analyzing...',
                      style: const TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 24),
            
            // Key Traits
            if (_insights['key_traits'] != null) ...[
              _buildSectionHeader('Key Traits', Icons.psychology),
              const SizedBox(height: 12),
              ...(_insights['key_traits'] as List).map((trait) =>
                  _buildInfoTile(trait.toString(), Icons.check_circle, const AppColors.success)),
              const SizedBox(height: 24),
            ],
            
            // Strengths
            if (_insights['strengths'] != null) ...[
              _buildSectionHeader('Your Strengths', Icons.star),
              const SizedBox(height: 12),
              ...(_insights['strengths'] as List).map((strength) =>
                  _buildInfoTile(strength.toString(), Icons.star, const AppColors.secondary)),
              const SizedBox(height: 24),
            ],
            
            // Improvement Areas
            if (_insights['improvement_areas'] != null) ...[
              _buildSectionHeader('Areas for Improvement', Icons.trending_up),
              const SizedBox(height: 12),
              ...(_insights['improvement_areas'] as List).map((area) =>
                  _buildInfoTile(area.toString(), Icons.trending_up, const AppColors.warning)),
              const SizedBox(height: 24),
            ],
            
            // Strategies
            if (_insights['recommended_strategies'] != null) ...[
              _buildSectionHeader('Recommended Strategies', Icons.lightbulb),
              const SizedBox(height: 12),
              ...(_insights['recommended_strategies'] as List).map((strategy) =>
                  _buildRecommendationTile(strategy.toString())),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: const AppColors.textPrimary, size: 24),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildPatternTag(String pattern) {
    Color tagColor;
    String displayText;
    
    switch (pattern) {
      case 'weekend_spender':
        tagColor = const AppColors.categoryEntertainment;
        displayText = 'Weekend Spender';
        break;
      case 'food_dominated':
        tagColor = const AppColors.success;
        displayText = 'Food Focused';
        break;
      case 'emotional_spending':
        tagColor = const AppColors.warningDark;
        displayText = 'Emotional Spender';
        break;
      default:
        tagColor = const AppColors.categoryUtilities;
        displayText = pattern.replaceAll('_', ' ').toUpperCase();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: tagColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tagColor.withValues(alpha: 0.3)),
      ),
      child: Text(
        displayText,
        style: TextStyle(
          fontFamily: AppTypography.fontBody,
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: tagColor,
        ),
      ),
    );
  }

  Widget _buildAnalysisCard(String title, String value, String description, 
      IconData icon, Color color) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Text(
                        value,
                        style: TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: color,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          description,
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoTile(String text, IconData icon, [Color? color]) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(
            icon,
            size: 20,
            color: color ?? const AppColors.textPrimary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationTile(String recommendation) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(
              Icons.lightbulb,
              color: AppColors.secondary,
              size: 20,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                recommendation,
                style: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRiskFactorTile(Map<String, dynamic> risk) {
    Color impactColor;
    switch (risk['impact']) {
      case 'high':
        impactColor = const AppColors.warningDark;
        break;
      case 'medium':
        impactColor = const AppColors.warning;
        break;
      default:
        impactColor = const AppColors.success;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 40,
              decoration: BoxDecoration(
                color: impactColor,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    risk['factor'] ?? '',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${risk['impact']?.toString().toUpperCase()} IMPACT',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: impactColor,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnomalyCard(Map<String, dynamic> anomaly) {
    final date = DateTime.parse(anomaly['date']);
    final anomalyScore = (anomaly['anomaly_score'] ?? 0.0) as double;
    
    Color severityColor;
    if (anomalyScore >= 0.8) {
      severityColor = const AppColors.warningDark;
    } else if (anomalyScore >= 0.6) {
      severityColor = const AppColors.warning;
    } else {
      severityColor = const AppColors.secondary;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  DateFormat('MMM d').format(date),
                  style: const TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: AppColors.textPrimary,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: severityColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${(anomalyScore * 100).toInt()}% anomaly',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: severityColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            
            Text(
              anomaly['description'] ?? '',
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
            
            const SizedBox(height: 12),
            
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Category',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                      Text(
                        anomaly['category'] ?? '',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Amount',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                      Text(
                        '\$${(anomaly['amount'] ?? 0.0).toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Expected',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                      Text(
                        '\$${(anomaly['expected_amount'] ?? 0.0).toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            
            if (anomaly['possible_causes'] != null) ...[
              const SizedBox(height: 12),
              Text(
                'Possible causes:',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey[700],
                ),
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 8,
                children: (anomaly['possible_causes'] as List).map<Widget>((cause) =>
                    Chip(
                      label: Text(
                        cause.toString(),
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 10,
                        ),
                      ),
                      backgroundColor: Colors.grey[100],
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    )).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildProgressTab() {
    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader('Behavioral Progress', Icons.trending_up),
            const SizedBox(height: 16),

            // Progress overview card
            if (_behavioralProgress.isNotEmpty) ...[
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                elevation: 3,
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    gradient: const LinearGradient(
                      colors: [AppColors.success, Color(0xFF66BB6A)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Your Progress Score',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          color: Colors.white,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_behavioralProgress['overall_score'] ?? 0}/100',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          color: Colors.white,
                          fontSize: 48,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _behavioralProgress['progress_message'] ?? 'Keep up the great work!',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          color: Colors.white,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Progress metrics
            if (_behavioralProgress['metrics'] != null) ...[
              _buildSectionHeader('Monthly Metrics', Icons.assessment),
              const SizedBox(height: 12),
              ...(_behavioralProgress['metrics'] as List).map((metric) =>
                  _buildMetricCard(metric)),
              const SizedBox(height: 24),
            ],

            // Improvements
            if (_behavioralProgress['improvements'] != null) ...[
              _buildSectionHeader('Improvements', Icons.star),
              const SizedBox(height: 12),
              ...(_behavioralProgress['improvements'] as List).map((improvement) =>
                  _buildInfoTile(improvement.toString(), Icons.check_circle, const AppColors.success)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildClusterTab() {
    return RefreshIndicator(
      onRefresh: _loadBehavioralData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader('Your Behavioral Cluster', Icons.group),
            const SizedBox(height: 16),

            // Cluster info card
            if (_behavioralCluster.isNotEmpty) ...[
              Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                elevation: 3,
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    gradient: const LinearGradient(
                      colors: [AppColors.categoryEducation, Color(0xFF9575CD)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Your Spending Cluster',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          color: Colors.white,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _behavioralCluster['cluster_name'] ?? 'Unknown',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          color: Colors.white,
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _behavioralCluster['description'] ?? '',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          color: Colors.white,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Cluster characteristics
            if (_behavioralCluster['characteristics'] != null) ...[
              _buildSectionHeader('Cluster Characteristics', Icons.psychology),
              const SizedBox(height: 12),
              ...(_behavioralCluster['characteristics'] as List).map((char) =>
                  _buildInfoTile(char.toString(), Icons.check_circle)),
              const SizedBox(height: 24),
            ],

            // Adaptive recommendations
            if (_adaptiveRecommendations.isNotEmpty) ...[
              _buildSectionHeader('Personalized Recommendations', Icons.lightbulb),
              const SizedBox(height: 12),
              if (_adaptiveRecommendations['recommendations'] != null)
                ...(_adaptiveRecommendations['recommendations'] as List).map((rec) =>
                    _buildRecommendationTile(rec.toString())),
              const SizedBox(height: 24),
            ],

            // Spending triggers
            if (_spendingTriggers.isNotEmpty) ...[
              _buildSectionHeader('Your Spending Triggers', Icons.warning_amber),
              const SizedBox(height: 12),
              if (_spendingTriggers['triggers'] != null)
                ...(_spendingTriggers['triggers'] as List).map((trigger) =>
                    _buildTriggerCard(trigger)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(Map<String, dynamic> metric) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: const AppColors.success.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.analytics, color: AppColors.success, size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    metric['name'] ?? '',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${metric['value'] ?? 0}',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                      color: AppColors.success,
                    ),
                  ),
                ],
              ),
            ),
            if (metric['trend'] != null)
              Icon(
                metric['trend'] == 'up' ? Icons.trending_up : Icons.trending_down,
                color: metric['trend'] == 'up' ? Colors.green : Colors.red,
                size: 24,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTriggerCard(Map<String, dynamic> trigger) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
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
                  child: const Icon(Icons.flag, color: Colors.orange, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    trigger['trigger_name'] ?? '',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              trigger['description'] ?? '',
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            if (trigger['frequency'] != null) ...[
              const SizedBox(height: 8),
              Text(
                'Frequency: ${trigger['frequency']}',
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
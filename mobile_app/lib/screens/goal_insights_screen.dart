/// MODULE 5: Goal Insights Screen
/// AI-powered insights, health analysis, and recommendations for goals

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/goal.dart';
import '../providers/goals_provider.dart';

class GoalInsightsScreen extends StatefulWidget {
  final Goal goal;

  const GoalInsightsScreen({super.key, required this.goal});

  @override
  State<GoalInsightsScreen> createState() => _GoalInsightsScreenState();
}

class _GoalInsightsScreenState extends State<GoalInsightsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // Load health data via provider after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<GoalsProvider>().loadGoalHealthData(widget.goal.id);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _loadHealthData() {
    context.read<GoalsProvider>().loadGoalHealthData(widget.goal.id);
  }

  @override
  Widget build(BuildContext context) {
    // Watch the provider for reactive updates
    final goalsProvider = context.watch<GoalsProvider>();
    final isLoading = goalsProvider.isHealthDataLoading(widget.goal.id);
    final healthData = goalsProvider.getGoalHealthData(widget.goal.id);

    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Goal Insights',
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
          tabs: const [
            Tab(text: 'Health', icon: Icon(Icons.favorite)),
            Tab(text: 'Insights', icon: Icon(Icons.lightbulb)),
            Tab(text: 'Tips', icon: Icon(Icons.tips_and_updates)),
          ],
        ),
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : healthData == null
              ? _buildErrorState()
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildHealthTab(healthData),
                    _buildInsightsTab(healthData),
                    _buildRecommendationsTab(healthData),
                  ],
                ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          const Text('Failed to load insights'),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _loadHealthData,
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildHealthTab(Map<String, dynamic> healthData) {
    final healthScore = healthData['health_score'] ?? 0;
    final isOnTrack = healthData['on_track'] ?? false;
    final predictedDate = healthData['predicted_completion_date'];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Health Score Card
          _buildHealthScoreCard(healthScore, isOnTrack),
          const SizedBox(height: 24),

          // Goal Overview
          _buildSectionTitle('Goal Overview'),
          const SizedBox(height: 12),
          _buildGoalOverviewCard(),
          const SizedBox(height: 24),

          // Predicted Completion
          if (predictedDate != null) ...[
            _buildSectionTitle('Predicted Completion'),
            const SizedBox(height: 12),
            _buildPredictedCompletionCard(predictedDate),
            const SizedBox(height: 24),
          ],

          // Progress Visualization
          _buildSectionTitle('Progress Visualization'),
          const SizedBox(height: 12),
          _buildProgressVisualization(),
        ],
      ),
    );
  }

  Widget _buildInsightsTab(Map<String, dynamic> healthData) {
    final insights = healthData['insights'] as List? ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('Key Insights'),
        const SizedBox(height: 12),
        if (insights.isEmpty)
          _buildEmptyInsights()
        else
          ...insights.map((insight) => _buildInsightCard(insight.toString())),
      ],
    );
  }

  Widget _buildRecommendationsTab(Map<String, dynamic> healthData) {
    final recommendations = healthData['recommendations'] as List? ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionTitle('AI Recommendations'),
        const SizedBox(height: 12),
        if (recommendations.isEmpty)
          _buildEmptyRecommendations()
        else
          ...recommendations.map((rec) => _buildRecommendationCard(rec.toString())),
      ],
    );
  }

  Widget _buildHealthScoreCard(int score, bool isOnTrack) {
    Color scoreColor;
    String scoreLabel;
    IconData scoreIcon;

    if (score >= 80) {
      scoreColor = Colors.green;
      scoreLabel = 'Excellent';
      scoreIcon = Icons.trending_up;
    } else if (score >= 60) {
      scoreColor = const AppColors.secondary;
      scoreLabel = 'Good';
      scoreIcon = Icons.trending_flat;
    } else if (score >= 40) {
      scoreColor = Colors.orange;
      scoreLabel = 'Fair';
      scoreIcon = Icons.trending_down;
    } else {
      scoreColor = Colors.red;
      scoreLabel = 'Needs Attention';
      scoreIcon = Icons.warning;
    }

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [scoreColor.withValues(alpha: 0.8), scoreColor],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: scoreColor.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Health Score',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 16,
                      color: Colors.white.withValues(alpha: 0.9),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '$score/100',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 40,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    scoreLabel,
                    style: const TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              Icon(scoreIcon, size: 64, color: Colors.white.withValues(alpha: 0.7)),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(
                  isOnTrack ? Icons.check_circle : Icons.warning,
                  color: Colors.white,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  isOnTrack ? 'On Track' : 'Behind Schedule',
                  style: const TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGoalOverviewCard() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            _buildOverviewRow('Title', widget.goal.title, Icons.flag),
            const Divider(height: 24),
            _buildOverviewRow('Target', widget.goal.formattedTargetAmount, Icons.savings),
            const Divider(height: 24),
            _buildOverviewRow('Saved', widget.goal.formattedSavedAmount, Icons.account_balance_wallet),
            const Divider(height: 24),
            _buildOverviewRow('Progress', widget.goal.progressPercentage, Icons.show_chart),
            if (widget.goal.targetDate != null) ...[
              const Divider(height: 24),
              _buildOverviewRow(
                'Deadline',
                DateFormat('MMM dd, yyyy').format(widget.goal.targetDate!),
                Icons.calendar_today,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildOverviewRow(String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: const AppColors.textPrimary, size: 20),
        const SizedBox(width: 12),
        Text(
          label,
          style: const TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 14,
            color: Colors.grey,
          ),
        ),
        const Spacer(),
        Text(
          value,
          style: const TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
      ],
    );
  }

  Widget _buildPredictedCompletionCard(String predictedDate) {
    final predicted = DateTime.parse(predictedDate);
    final target = widget.goal.targetDate;
    final isLate = target != null && predicted.isAfter(target);

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: isLate ? Colors.red.shade50 : Colors.green.shade50,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Icon(
              isLate ? Icons.warning : Icons.check_circle,
              color: isLate ? Colors.red.shade700 : Colors.green.shade700,
              size: 32,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Predicted Completion',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 12,
                      color: isLate ? Colors.red.shade700 : Colors.green.shade700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    DateFormat('MMM dd, yyyy').format(predicted),
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: isLate ? Colors.red.shade800 : Colors.green.shade800,
                    ),
                  ),
                  if (isLate && target != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      '${predicted.difference(target).inDays} days late',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 12,
                        color: Colors.red.shade600,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressVisualization() {
    final progress = widget.goal.progress / 100;
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Current Progress',
                  style: const TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
                Text(
                  widget.goal.progressPercentage,
                  style: const TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: LinearProgressIndicator(
                value: progress.clamp(0.0, 1.0),
                backgroundColor: Colors.grey.shade200,
                valueColor: AlwaysStoppedAnimation(_getProgressColor(widget.goal.progress)),
                minHeight: 24,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildProgressMilestone('0%', progress >= 0),
                _buildProgressMilestone('25%', progress >= 0.25),
                _buildProgressMilestone('50%', progress >= 0.50),
                _buildProgressMilestone('75%', progress >= 0.75),
                _buildProgressMilestone('100%', progress >= 1.0),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressMilestone(String label, bool reached) {
    return Column(
      children: [
        Icon(
          reached ? Icons.check_circle : Icons.circle_outlined,
          color: reached ? Colors.green : Colors.grey.shade400,
          size: 20,
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 10,
            color: reached ? Colors.green : Colors.grey,
          ),
        ),
      ],
    );
  }

  Widget _buildInsightCard(String insight) {
    // Parse emoji from insight
    final hasEmoji = insight.contains(RegExp(r'[\u{1F300}-\u{1F9FF}]', unicode: true));

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const AppColors.secondary.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.lightbulb, color: AppColors.textPrimary, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                insight,
                style: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  height: 1.5,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecommendationCard(String recommendation) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.tips_and_updates, color: Colors.green, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                recommendation,
                style: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  height: 1.5,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyInsights() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.insights, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(
              'No insights yet',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Keep tracking your progress to unlock AI-powered insights',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: Colors.grey.shade500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyRecommendations() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.stars, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(
              'You\'re doing great!',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'No recommendations at this time. Keep up the good work!',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: Colors.grey.shade500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontFamily: AppTypography.fontHeading,
        fontSize: 18,
        fontWeight: FontWeight.bold,
        color: AppColors.textPrimary,
      ),
    );
  }

  Color _getProgressColor(double progress) {
    if (progress >= 100) return Colors.green;
    if (progress >= 70) return const AppColors.secondary;
    return const AppColors.textPrimary;
  }
}

/// MODULE 5: Smart Goal Recommendations Screen
/// AI-powered personalized goal recommendations based on user behavior

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class SmartGoalRecommendationsScreen extends StatefulWidget {
  const SmartGoalRecommendationsScreen({super.key});

  @override
  State<SmartGoalRecommendationsScreen> createState() => _SmartGoalRecommendationsScreenState();
}

class _SmartGoalRecommendationsScreenState extends State<SmartGoalRecommendationsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<Map<String, dynamic>> _recommendations = [];
  List<Map<String, dynamic>> _opportunities = [];
  List<Map<String, dynamic>> _adjustments = [];

  @override
  void initState() {
    super.initState();
    _loadAllRecommendations();
  }

  Future<void> _loadAllRecommendations() async {
    setState(() => _isLoading = true);
    try {
      final recommendationsData = await _apiService.getSmartGoalRecommendations();
      final opportunitiesData = await _apiService.detectGoalOpportunities();
      final adjustmentsData = await _apiService.getGoalAdjustmentSuggestions();

      setState(() {
        _recommendations = List<Map<String, dynamic>>.from(
          recommendationsData['recommendations'] ?? []
        );
        _opportunities = List<Map<String, dynamic>>.from(
          opportunitiesData['opportunities'] ?? []
        );
        _adjustments = List<Map<String, dynamic>>.from(
          adjustmentsData['adjustments'] ?? []
        );
        _isLoading = false;
      });
    } catch (e) {
      logError('Error loading recommendations: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _createGoalFromRecommendation(Map<String, dynamic> recommendation) async {
    final data = {
      'title': recommendation['title'],
      'description': recommendation['description'] ?? recommendation['reasoning'],
      'category': recommendation['category'],
      'target_amount': recommendation['target_amount'],
      'saved_amount': 0,
      'monthly_contribution': recommendation['monthly_contribution'],
      'priority': recommendation['priority'],
      'target_date': recommendation['suggested_deadline'],
    };

    try {
      await _apiService.createGoal(data);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Goal "${recommendation['title']}" created successfully!'),
          backgroundColor: Colors.green,
        ),
      );
      Navigator.pop(context, true);  // Return to goals screen
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Smart Recommendations',
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
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAllRecommendations,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAllRecommendations,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header
                    _buildHeader(),
                    const SizedBox(height: 24),

                    // AI Recommendations
                    if (_recommendations.isNotEmpty) ...[
                      _buildSectionTitle('✨ AI Recommendations for You'),
                      const SizedBox(height: 12),
                      ..._recommendations.map((rec) => _buildRecommendationCard(rec)),
                      const SizedBox(height: 24),
                    ],

                    // Opportunities
                    if (_opportunities.isNotEmpty) ...[
                      _buildSectionTitle('💡 Opportunities Detected'),
                      const SizedBox(height: 12),
                      ..._opportunities.map((opp) => _buildOpportunityCard(opp)),
                      const SizedBox(height: 24),
                    ],

                    // Adjustments
                    if (_adjustments.isNotEmpty) ...[
                      _buildSectionTitle('🔧 Goal Adjustments Suggested'),
                      const SizedBox(height: 12),
                      ..._adjustments.map((adj) => _buildAdjustmentCard(adj)),
                      const SizedBox(height: 24),
                    ],

                    // Empty state
                    if (_recommendations.isEmpty && _opportunities.isEmpty && _adjustments.isEmpty)
                      _buildEmptyState(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildHeader() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [AppColors.textPrimary, AppColors.textPrimary.withValues(alpha: 0.7)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const AppColors.secondary,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.auto_awesome, color: AppColors.textPrimary, size: 32),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Powered by AI',
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Personalized recommendations based on your spending patterns',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      fontSize: 13,
                      color: Colors.white.withValues(alpha: 0.8),
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

  Widget _buildRecommendationCard(Map<String, dynamic> rec) {
    final priority = rec['priority'] ?? 'medium';
    final priorityColor = _getPriorityColor(priority);

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: () => _showRecommendationDetails(rec),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: [Colors.white, priorityColor.withValues(alpha: 0.05)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          rec['title'] ?? 'Goal',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontHeading,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          rec['category'] ?? 'General',
                          style: TextStyle(
                            fontFamily: AppTypography.fontBody,
                            fontSize: 13,
                            color: Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: priorityColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      priority.toUpperCase(),
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: priorityColor,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                rec['description'] ?? rec['reasoning'] ?? '',
                style: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 14,
                  height: 1.5,
                  color: Colors.black87,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: _buildInfoChip(
                      'Target',
                      '\$${(rec['target_amount'] ?? 0).toStringAsFixed(0)}',
                      Icons.flag,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildInfoChip(
                      'Monthly',
                      '\$${(rec['monthly_contribution'] ?? 0).toStringAsFixed(0)}',
                      Icons.calendar_month,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => _createGoalFromRecommendation(rec),
                  icon: const Icon(Icons.add_circle),
                  label: const Text('Create This Goal'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: priorityColor,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOpportunityCard(Map<String, dynamic> opp) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: Colors.amber.shade50,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.amber,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.lightbulb, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    opp['suggested_goal'] ?? 'Opportunity',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              opp['reason'] ?? '',
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                height: 1.5,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildInfoChip(
                  'Amount',
                  '\$${(opp['target_amount'] ?? 0).toStringAsFixed(0)}',
                  Icons.attach_money,
                ),
                _buildInfoChip(
                  'Monthly',
                  '\$${(opp['monthly_contribution'] ?? 0).toStringAsFixed(0)}',
                  Icons.trending_up,
                ),
                if (opp['category'] != null)
                  _buildInfoChip('Category', opp['category'], Icons.category),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAdjustmentCard(Map<String, dynamic> adj) {
    final currentMonthly = adj['current_monthly'] ?? 0;
    final suggestedMonthly = adj['suggested_monthly'] ?? 0;
    final increase = suggestedMonthly - currentMonthly;

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      color: Colors.blue.shade50,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.tune, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    adj['goal_title'] ?? 'Goal Adjustment',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              adj['reason'] ?? 'Adjustment suggested',
              style: const TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                height: 1.5,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  Column(
                    children: [
                      const Text(
                        'Current',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '\$${currentMonthly.toStringAsFixed(0)}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  Icon(Icons.arrow_forward, color: Colors.blue.shade400),
                  Column(
                    children: [
                      const Text(
                        'Suggested',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '\$${suggestedMonthly.toStringAsFixed(0)}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (increase > 0) ...[
              const SizedBox(height: 8),
              Text(
                '+ \$${increase.toStringAsFixed(0)}/month increase',
                style: const TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Colors.green,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildInfoChip(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.grey.shade700),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontFamily: AppTypography.fontBody,
                  fontSize: 10,
                  color: Colors.grey.shade600,
                ),
              ),
              Text(
                value,
                style: const TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          children: [
            Icon(Icons.check_circle, size: 64, color: Colors.green.shade400),
            const SizedBox(height: 16),
            const Text(
              'All Caught Up!',
              style: TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'No new recommendations at this time.\nKeep tracking your spending to unlock personalized insights!',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
                fontSize: 14,
                color: Colors.grey.shade600,
                height: 1.5,
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

  Color _getPriorityColor(String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
        return Colors.red;
      case 'medium':
        return Colors.orange;
      case 'low':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  void _showRecommendationDetails(Map<String, dynamic> rec) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        height: MediaQuery.of(context).size.height * 0.7,
        decoration: const BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              rec['title'] ?? 'Goal Details',
              style: const TextStyle(
                fontFamily: AppTypography.fontHeading,
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildDetailRow('Description', rec['description'] ?? rec['reasoning'] ?? 'No description'),
                    const SizedBox(height: 16),
                    _buildDetailRow('Category', rec['category'] ?? 'General'),
                    const SizedBox(height: 16),
                    _buildDetailRow('Target Amount', '\$${(rec['target_amount'] ?? 0).toStringAsFixed(2)}'),
                    const SizedBox(height: 16),
                    _buildDetailRow('Monthly Contribution', '\$${(rec['monthly_contribution'] ?? 0).toStringAsFixed(2)}'),
                    const SizedBox(height: 16),
                    _buildDetailRow('Priority', rec['priority'] ?? 'medium'),
                    if (rec['suggested_deadline'] != null) ...[
                      const SizedBox(height: 16),
                      _buildDetailRow('Suggested Deadline', rec['suggested_deadline']),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  Navigator.pop(context);
                  _createGoalFromRecommendation(rec);
                },
                icon: const Icon(Icons.add_circle),
                label: const Text('Create This Goal'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const AppColors.secondary,
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 13,
            color: Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: 4),
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
}

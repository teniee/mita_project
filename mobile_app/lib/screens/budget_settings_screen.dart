import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../providers/budget_provider.dart';
import '../providers/user_provider.dart';
import '../services/logging_service.dart';
import '../services/income_service.dart';
import '../widgets/income_tier_widgets.dart';
import '../theme/income_theme.dart';

class BudgetSettingsScreen extends StatefulWidget {
  const BudgetSettingsScreen({super.key});

  @override
  State<BudgetSettingsScreen> createState() => _BudgetSettingsScreenState();
}

class _BudgetSettingsScreenState extends State<BudgetSettingsScreen> {
  final IncomeService _incomeService = IncomeService();

  // Income-related data
  double _monthlyIncome = 0.0;
  IncomeTier? _incomeTier;

  final List<Map<String, dynamic>> _budgetModes = [
    {
      'id': 'default',
      'name': 'Standard Budget',
      'description': 'Traditional budget tracking with basic redistribution',
      'icon': Icons.account_balance_wallet,
      'color': Colors.grey,
      'features': ['Basic tracking', 'Manual redistribution', 'Standard alerts'],
    },
    {
      'id': 'flexible',
      'name': 'Flexible Budget',
      'description': 'Adaptive budget that adjusts to your spending patterns',
      'icon': Icons.auto_fix_high,
      'color': AppColors.successLight,
      'features': ['Auto-adjustment', 'Smart redistribution', 'Flexible limits'],
    },
    {
      'id': 'strict',
      'name': 'Strict Budget',
      'description': 'Rigid budget control with firm spending limits',
      'icon': Icons.lock,
      'color': AppColors.danger,
      'features': ['Hard limits', 'Strict alerts', 'No overspending'],
    },
    {
      'id': 'behavioral',
      'name': 'Behavioral Adaptive',
      'description': 'AI-powered budget that learns from your behavior',
      'icon': Icons.psychology,
      'color': AppColors.accent,
      'features': ['AI learning', 'Behavioral insights', 'Predictive adjustments'],
    },
    {
      'id': 'goal',
      'name': 'Goal-Oriented',
      'description': 'Budget optimized for achieving your savings goals',
      'icon': Icons.flag,
      'color': AppColors.secondary,
      'features': ['Goal tracking', 'Savings priority', 'Target optimization'],
    },
  ];

  @override
  void initState() {
    super.initState();
    // Initialize providers after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeProviders();
    });
  }

  Future<void> _initializeProviders() async {
    final userProvider = context.read<UserProvider>();
    final budgetProvider = context.read<BudgetProvider>();

    // Get user income from UserProvider
    final income = userProvider.userIncome;

    if (income <= 0) {
      logError('Income data required for budget settings. Please complete onboarding.',
          tag: 'BUDGET_SETTINGS');
      return;
    }

    setState(() {
      _monthlyIncome = income;
      _incomeTier = _incomeService.classifyIncome(_monthlyIncome);
    });

    // Load budget settings data
    await budgetProvider.loadBudgetSettingsData(
      _monthlyIncome,
      incomeTier: _incomeTier?.toString(),
    );
  }

  Future<void> _refreshSettings() async {
    final budgetProvider = context.read<BudgetProvider>();
    await budgetProvider.loadBudgetSettingsData(
      _monthlyIncome,
      incomeTier: _incomeTier?.toString(),
    );
  }

  Future<void> _updateBudgetMode(String newMode) async {
    final budgetProvider = context.read<BudgetProvider>();

    final success = await budgetProvider.setBudgetMode(newMode);

    if (mounted) {
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white),
                const SizedBox(width: 8),
                Text('Budget mode updated to ${_getBudgetModeByIdName(newMode)}'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.primary,
            behavior: SnackBarBehavior.floating,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.error, color: Colors.white),
                SizedBox(width: 8),
                Text('Failed to update budget mode'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  Future<void> _updateAutomationSettings(Map<String, dynamic> newSettings) async {
    final budgetProvider = context.read<BudgetProvider>();

    final success = await budgetProvider.updateAutomationSettings(newSettings);

    if (mounted && success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white),
              SizedBox(width: 8),
              Text('Automation settings updated'),
            ],
          ),
          backgroundColor: Theme.of(context).colorScheme.primary,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  String _getBudgetModeByIdName(String id) {
    final mode = _budgetModes.firstWhere(
      (mode) => mode['id'] == id,
      orElse: () => _budgetModes[0],
    );
    return mode['name'];
  }

  Map<String, dynamic> _getBudgetModeById(String id) {
    return _budgetModes.firstWhere(
      (mode) => mode['id'] == id,
      orElse: () => _budgetModes[0],
    );
  }

  Widget _buildBudgetModeCard(
      Map<String, dynamic> mode, String currentBudgetMode, bool isUpdating) {
    final isSelected = mode['id'] == currentBudgetMode;
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      elevation: isSelected ? 6 : 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: isSelected ? BorderSide(color: mode['color'], width: 2) : BorderSide.none,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: isUpdating ? null : () => _updateBudgetMode(mode['id']),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: mode['color'].withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      mode['icon'],
                      color: mode['color'],
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              mode['name'],
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: colorScheme.onSurface,
                                fontFamily: AppTypography.fontHeading,
                              ),
                            ),
                            if (isSelected) ...[
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: mode['color'],
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Text(
                                  'ACTIVE',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          mode['description'],
                          style: TextStyle(
                            fontSize: 14,
                            color: colorScheme.onSurface.withValues(alpha: 0.7),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (isUpdating && isSelected)
                    const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else if (isSelected)
                    Icon(
                      Icons.check_circle,
                      color: mode['color'],
                      size: 24,
                    ),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: (mode['features'] as List<String>)
                    .map<Widget>(
                      (feature) => Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: colorScheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: mode['color'].withValues(alpha: 0.3)),
                        ),
                        child: Text(
                          feature,
                          style: TextStyle(
                            fontSize: 12,
                            color: mode['color'],
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBudgetRemainingCard(Map<String, dynamic>? budgetRemaining) {
    if (budgetRemaining == null) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : colorScheme.primary;

    final totalBudget = (budgetRemaining['total_budget'] as num?)?.toDouble() ?? 0.0;
    final totalSpent = (budgetRemaining['total_spent'] as num?)?.toDouble() ?? 0.0;
    final remaining = (budgetRemaining['remaining'] as num?)?.toDouble() ?? 0.0;
    final percentageUsed = totalBudget > 0 ? (totalSpent / totalBudget * 100) : 0.0;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.account_balance_wallet, color: primaryColor),
                const SizedBox(width: 12),
                Text(
                  'Budget Status This Month',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: percentageUsed / 100,
                minHeight: 12,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  percentageUsed > 90
                      ? Colors.red
                      : percentageUsed > 70
                          ? Colors.orange
                          : primaryColor,
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Budget stats
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Total Budget',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${totalBudget.toStringAsFixed(0)}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Text(
                      'Spent',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${totalSpent.toStringAsFixed(0)}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                        color: percentageUsed > 90 ? Colors.red : null,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'Remaining',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                    Text(
                      '\$${remaining.toStringAsFixed(0)}',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        fontFamily: AppTypography.fontHeading,
                        color: remaining < 0 ? Colors.red : Colors.green,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAutomationSettings(Map<String, dynamic> automationSettings) {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.settings_suggest, color: colorScheme.primary),
                const SizedBox(width: 12),
                Text(
                  'Automation Settings',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                    fontFamily: AppTypography.fontHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Auto Redistribution
            SwitchListTile(
              title: const Text(
                'Auto Redistribution',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Automatically redistribute budget when overspending occurs',
                style: TextStyle(fontSize: 12),
              ),
              value: automationSettings['auto_redistribution'] ?? false,
              onChanged: (bool value) {
                _updateAutomationSettings({'auto_redistribution': value});
              },
              activeColor: colorScheme.primary,
            ),

            // Smart Suggestions
            SwitchListTile(
              title: const Text(
                'Smart Suggestions',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Receive AI-powered budget recommendations',
                style: TextStyle(fontSize: 12),
              ),
              value: automationSettings['smart_suggestions'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'smart_suggestions': value});
              },
              activeColor: colorScheme.primary,
            ),

            // Behavioral Learning
            SwitchListTile(
              title: const Text(
                'Behavioral Learning',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Allow AI to learn from your spending patterns',
                style: TextStyle(fontSize: 12),
              ),
              value: automationSettings['behavioral_learning'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'behavioral_learning': value});
              },
              activeColor: colorScheme.primary,
            ),

            // Real-time Alerts
            SwitchListTile(
              title: const Text(
                'Real-time Alerts',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              subtitle: const Text(
                'Get instant notifications for budget changes',
                style: TextStyle(fontSize: 12),
              ),
              value: automationSettings['realtime_alerts'] ?? true,
              onChanged: (bool value) {
                _updateAutomationSettings({'realtime_alerts': value});
              },
              activeColor: colorScheme.primary,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final primaryColor = _incomeTier != null
        ? _incomeService.getIncomeTierPrimaryColor(_incomeTier!)
        : colorScheme.primary;

    // Watch BudgetProvider for reactive updates
    final budgetProvider = context.watch<BudgetProvider>();

    final isLoading = budgetProvider.isLoading;
    final currentBudgetMode = budgetProvider.budgetMode;
    final automationSettings = budgetProvider.automationSettings;
    final budgetRecommendations = budgetProvider.budgetRecommendations;
    final budgetRemaining = budgetProvider.budgetRemaining;
    final behavioralAllocation = budgetProvider.behavioralAllocation;
    final isUpdating = budgetProvider.isUpdatingMode;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: _incomeTier != null
          ? IncomeTheme.createTierAppBar(
              tier: _incomeTier!,
              title: 'Budget Settings',
            )
          : AppBar(
              title: const Text(
                'Budget Settings',
                style: TextStyle(
                  fontFamily: AppTypography.fontHeading,
                  fontWeight: FontWeight.bold,
                ),
              ),
              backgroundColor: colorScheme.surface,
              elevation: 0,
              centerTitle: true,
              iconTheme: IconThemeData(color: colorScheme.onSurface),
            ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshSettings,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Income Context Card
                    if (_incomeTier != null)
                      IncomeTierCard(
                        monthlyIncome: _monthlyIncome,
                        showDetails: false,
                      ),

                    if (_incomeTier != null) const SizedBox(height: 16),

                    // Budget Remaining Status
                    _buildBudgetRemainingCard(budgetRemaining),

                    // Income-based Budget Recommendations
                    if (budgetRecommendations != null)
                      Card(
                        elevation: 2,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    Icons.recommend_rounded,
                                    color: primaryColor,
                                    size: 24,
                                  ),
                                  const SizedBox(width: 12),
                                  Text(
                                    'Income-Based Recommendations',
                                    style: TextStyle(
                                      fontFamily: AppTypography.fontHeading,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 18,
                                      color: primaryColor,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              ...(budgetRecommendations['allocations'] as Map<String, dynamic>?)
                                      ?.entries
                                      .map((entry) {
                                    final category = entry.key;
                                    final amount = entry.value as double;
                                    final percentage =
                                        _incomeService.getIncomePercentage(amount, _monthlyIncome);

                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 8),
                                      child: Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Text(
                                            category.toUpperCase(),
                                            style: const TextStyle(
                                              fontFamily: AppTypography.fontHeading,
                                              fontWeight: FontWeight.w600,
                                              fontSize: 14,
                                            ),
                                          ),
                                          Column(
                                            crossAxisAlignment: CrossAxisAlignment.end,
                                            children: [
                                              Text(
                                                '\$${amount.toStringAsFixed(0)}',
                                                style: TextStyle(
                                                  fontFamily: AppTypography.fontHeading,
                                                  fontWeight: FontWeight.bold,
                                                  color: primaryColor,
                                                ),
                                              ),
                                              Text(
                                                '${percentage.toStringAsFixed(1)}% of income',
                                                style: TextStyle(
                                                  fontFamily: AppTypography.fontBody,
                                                  fontSize: 11,
                                                  color: Colors.grey[600],
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList() ??
                                  [],
                            ],
                          ),
                        ),
                      ),

                    if (budgetRecommendations != null) const SizedBox(height: 16),

                    // Behavioral Budget Allocation (AI-powered)
                    if (behavioralAllocation != null && behavioralAllocation['allocations'] != null)
                      Card(
                        elevation: 2,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    Icons.psychology,
                                    color: AppColors.accent,
                                    size: 24,
                                  ),
                                  const SizedBox(width: 12),
                                  Text(
                                    'AI Behavioral Allocation',
                                    style: TextStyle(
                                      fontFamily: AppTypography.fontHeading,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 18,
                                      color: colorScheme.onSurface,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Budget allocation based on your behavioral patterns',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                                ),
                              ),
                              const SizedBox(height: 16),
                              ...(behavioralAllocation['allocations'] as Map<String, dynamic>?)
                                      ?.entries
                                      .map((entry) {
                                    final category = entry.key;
                                    final data = entry.value as Map<String, dynamic>;
                                    final amount = (data['amount'] as num?)?.toDouble() ?? 0.0;
                                    final confidence =
                                        (data['confidence'] as num?)?.toDouble() ?? 0.0;

                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 12),
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                            children: [
                                              Text(
                                                category.toUpperCase(),
                                                style: const TextStyle(
                                                  fontFamily: AppTypography.fontHeading,
                                                  fontWeight: FontWeight.w600,
                                                  fontSize: 13,
                                                ),
                                              ),
                                              Text(
                                                '\$${amount.toStringAsFixed(0)}',
                                                style: const TextStyle(
                                                  fontFamily: AppTypography.fontHeading,
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 15,
                                                ),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 4),
                                          Row(
                                            children: [
                                              Expanded(
                                                child: ClipRRect(
                                                  borderRadius: BorderRadius.circular(4),
                                                  child: LinearProgressIndicator(
                                                    value: confidence / 100,
                                                    minHeight: 6,
                                                    backgroundColor: Colors.grey[200],
                                                    valueColor: AlwaysStoppedAnimation<Color>(
                                                      AppColors.accent,
                                                    ),
                                                  ),
                                                ),
                                              ),
                                              const SizedBox(width: 8),
                                              Text(
                                                '${confidence.toStringAsFixed(0)}% confidence',
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  color: Colors.grey[600],
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList() ??
                                  [],
                            ],
                          ),
                        ),
                      ),

                    if (behavioralAllocation != null) const SizedBox(height: 24),

                    // Current Mode Display
                    Card(
                      elevation: 4,
                      margin: const EdgeInsets.only(bottom: 24),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      child: Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          gradient: LinearGradient(
                            colors: [
                              _getBudgetModeById(currentBudgetMode)['color'],
                              _getBudgetModeById(currentBudgetMode)['color'].withValues(alpha: 0.8),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              _getBudgetModeById(currentBudgetMode)['icon'],
                              color: Colors.white,
                              size: 32,
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Current Budget Mode',
                                    style: TextStyle(
                                      color: Colors.white70,
                                      fontSize: 14,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    _getBudgetModeById(currentBudgetMode)['name'],
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      fontFamily: AppTypography.fontHeading,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Budget Modes Section
                    Text(
                      'Choose Your Budget Mode',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Select the budget management approach that best fits your financial goals and spending habits.',
                      style: TextStyle(
                        fontSize: 14,
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Budget mode cards
                    ..._budgetModes
                        .map((mode) => _buildBudgetModeCard(mode, currentBudgetMode, isUpdating)),

                    const SizedBox(height: 24),

                    // Automation Settings
                    Text(
                      'Automation Preferences',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Customize how MITA automatically manages your budget and provides intelligent recommendations.',
                      style: TextStyle(
                        fontSize: 14,
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(height: 20),

                    _buildAutomationSettings(automationSettings),

                    const SizedBox(height: 24),

                    // Additional Info
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.info_outline, color: colorScheme.primary),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Changes to your budget mode will take effect immediately and may trigger automatic redistribution of your current budget.',
                              style: TextStyle(
                                fontSize: 13,
                                color: colorScheme.primary,
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
    );
  }
}

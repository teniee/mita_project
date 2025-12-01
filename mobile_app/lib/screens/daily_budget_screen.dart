import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../services/accessibility_service.dart';
import 'package:intl/intl.dart';
import '../services/logging_service.dart';
import '../core/enhanced_error_handling.dart';
import '../core/app_error_handler.dart';
import '../core/error_handling.dart';
import '../providers/budget_provider.dart';

class DailyBudgetScreen extends StatefulWidget {
  const DailyBudgetScreen({super.key});

  @override
  State<DailyBudgetScreen> createState() => _DailyBudgetScreenState();
}

class _DailyBudgetScreenState extends State<DailyBudgetScreen>
    with RobustErrorHandlingMixin {
  final AccessibilityService _accessibilityService =
      AccessibilityService.instance;

  @override
  void initState() {
    super.initState();
    _accessibilityService.initialize().then((_) {
      _accessibilityService.announceNavigation(
        'Daily Budget Dashboard',
        description: 'Smart budget tracking and financial insights',
      );
    });

    // Initialize BudgetProvider for centralized state management
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final budgetProvider = context.read<BudgetProvider>();
      if (budgetProvider.state == BudgetState.initial) {
        budgetProvider.initialize();
      }
    });
  }

  Future<void> _triggerBudgetRedistribution() async {
    final budgetProvider = context.read<BudgetProvider>();
    if (budgetProvider.isRedistributing) return;

    _accessibilityService.announceToScreenReader(
      'Starting budget redistribution',
      financialContext: 'Budget Management',
      isImportant: true,
    );

    final success = await budgetProvider.redistributeBudget();

    if (mounted) {
      if (success) {
        _accessibilityService.announceToScreenReader(
          'Budget successfully redistributed. Budget amounts have been updated.',
          financialContext: 'Budget Management',
          isImportant: true,
        );

        context.showSuccessSnack('Budget successfully redistributed!');
      } else {
        _accessibilityService.announceToScreenReader(
          'Failed to redistribute budget. Please try again.',
          financialContext: 'Budget Management Error',
          isImportant: true,
        );

        showEnhancedErrorDialog(
          'Budget Redistribution Failed',
          budgetProvider.errorMessage ??
              'Unable to redistribute your budget at this time.',
          onRetry: _triggerBudgetRedistribution,
          canRetry: true,
        );
      }
    }
  }

  Future<void> _triggerAutoBudgetAdaptation() async {
    final budgetProvider = context.read<BudgetProvider>();

    _accessibilityService.announceToScreenReader(
      'Starting automatic budget adaptation',
      financialContext: 'Budget Management',
      isImportant: true,
    );

    final success = await budgetProvider.triggerAutoAdaptation();

    if (mounted) {
      if (success) {
        _accessibilityService.announceToScreenReader(
          'Budget adapted based on your spending patterns. Budget amounts have been updated.',
          financialContext: 'Budget Management',
          isImportant: true,
        );

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Semantics(
              liveRegion: true,
              label: 'Success: Budget adapted based on spending patterns',
              child:
                  const Text('Budget adapted based on your spending patterns!'),
            ),
            duration: const Duration(seconds: 3),
            backgroundColor: AppColors.successLight,
          ),
        );
      } else {
        _accessibilityService.announceToScreenReader(
          'Failed to adapt budget automatically. Please try again.',
          financialContext: 'Budget Management Error',
          isImportant: true,
        );
      }
    }
  }

  Color getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return AppColors.successLight;
      case 'warning':
        return AppColors.secondary;
      case 'exceeded':
      case 'over':
        return AppColors.danger;
      default:
        return Colors.grey;
    }
  }

  IconData getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'exceeded':
      case 'over':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  String _getBudgetModeDisplayName(String mode) {
    switch (mode) {
      case 'strict':
        return 'Strict Budget';
      case 'flexible':
        return 'Flexible Budget';
      case 'behavioral':
        return 'Behavioral Adaptive';
      case 'goal':
        return 'Goal-Oriented';
      default:
        return 'Standard Budget';
    }
  }

  Widget _buildLiveBudgetCard(BudgetProvider budgetProvider) {
    final liveBudgetStatus = budgetProvider.liveBudgetStatus;
    if (liveBudgetStatus.isEmpty) return const SizedBox.shrink();

    final totalBudget = liveBudgetStatus['total_budget']?.toDouble() ?? 0.0;
    final totalSpent = liveBudgetStatus['total_spent']?.toDouble() ?? 0.0;
    final remaining = totalBudget - totalSpent;
    final percentage = totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;

    String statusDescription;
    if (percentage > 0.8) {
      statusDescription = 'Warning: Over 80% of budget used';
    } else if (percentage > 0.6) {
      statusDescription = 'Caution: Over 60% of budget used';
    } else {
      statusDescription = 'Good: Budget within safe limits';
    }

    return Semantics(
      label: _accessibilityService.createProgressSemanticLabel(
        category: 'Total Budget',
        spent: totalSpent,
        limit: totalBudget,
        status: statusDescription,
      ),
      child: Card(
        margin: const EdgeInsets.only(bottom: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 4,
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: percentage > 0.8
                  ? [AppColors.danger, AppColors.warning]
                  : percentage > 0.6
                      ? [
                          AppColors.secondary,
                          AppColors.secondary.withValues(alpha: 0.7)
                        ]
                      : [
                          AppColors.successLight,
                          AppColors.success.withValues(alpha: 0.5)
                        ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Semantics(
                    header: true,
                    label: 'Live Budget Status',
                    child: const Text(
                      'Live Budget Status',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        fontFamily: AppTypography.fontHeading,
                      ),
                    ),
                  ),
                  Semantics(
                    label:
                        'Budget Mode: ${_getBudgetModeDisplayName(budgetProvider.budgetMode)}',
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _getBudgetModeDisplayName(budgetProvider.budgetMode),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w500,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Semantics(
                    label: _accessibilityService.createFinancialSemanticLabel(
                      label: 'Total Budget',
                      amount: totalBudget,
                      isBalance: true,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Total Budget',
                          style: TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                        Text(
                          '\$${totalBudget.toStringAsFixed(2)}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Semantics(
                    label: _accessibilityService.createFinancialSemanticLabel(
                      label: 'Total Spent',
                      amount: totalSpent,
                      isBalance: false,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Spent',
                          style: TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                        Text(
                          '\$${totalSpent.toStringAsFixed(2)}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Semantics(
                    label: _accessibilityService.createFinancialSemanticLabel(
                      label: 'Remaining Budget',
                      amount: remaining,
                      status: remaining >= 0 ? 'Available' : 'Over budget',
                      isBalance: true,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Remaining',
                          style: TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                        Text(
                          '\$${remaining.toStringAsFixed(2)}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Semantics(
                label:
                    'Budget progress bar. ${(percentage * 100).toStringAsFixed(1)} percent of budget used',
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: percentage.clamp(0.0, 1.0),
                    backgroundColor: Colors.white.withValues(alpha: 0.3),
                    valueColor:
                        const AlwaysStoppedAnimation<Color>(Colors.white),
                    minHeight: 8,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${(percentage * 100).toStringAsFixed(1)}% of budget used',
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionButtons(BudgetProvider budgetProvider) {
    final isRedistributing = budgetProvider.isRedistributing;

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: const Text(
                'Smart Budget Actions',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  fontFamily: AppTypography.fontHeading,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Semantics(
                    label: _accessibilityService.createButtonSemanticLabel(
                      action: isRedistributing
                          ? 'Redistributing budget'
                          : 'Redistribute Budget',
                      context: isRedistributing
                          ? 'Budget redistribution in progress, please wait'
                          : 'Reallocate budget between days based on spending patterns',
                      isDisabled: isRedistributing,
                    ),
                    button: true,
                    child: ElevatedButton.icon(
                      onPressed: isRedistributing
                          ? null
                          : _triggerBudgetRedistribution,
                      icon: isRedistributing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.balance, size: 18),
                      label: Text(isRedistributing
                          ? 'Redistributing...'
                          : 'Redistribute'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ).withMinimumTouchTarget(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Semantics(
                    label: _accessibilityService.createButtonSemanticLabel(
                      action: 'Auto Adapt Budget',
                      context:
                          'Automatically adjust budget based on your spending patterns and behavior',
                    ),
                    button: true,
                    child: ElevatedButton.icon(
                      onPressed: _triggerAutoBudgetAdaptation,
                      icon: const Icon(Icons.auto_fix_high, size: 18),
                      label: const Text('Auto Adapt'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.successLight,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ).withMinimumTouchTarget(),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionsCard(BudgetProvider budgetProvider) {
    final budgetSuggestions = budgetProvider.budgetSuggestions;
    if (budgetSuggestions.isEmpty) return const SizedBox.shrink();

    final suggestions =
        budgetSuggestions['suggestions'] as List<dynamic>? ?? [];
    if (suggestions.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.lightbulb, color: AppColors.secondary),
                SizedBox(width: 8),
                Text(
                  'AI Budget Suggestions',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: AppTypography.fontHeading,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...suggestions.take(3).map<Widget>(
                  (suggestion) => Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.secondary, width: 1),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.arrow_forward,
                            size: 16, color: AppColors.secondary),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            suggestion['message'] ?? suggestion.toString(),
                            style: const TextStyle(
                                fontSize: 14, color: AppColors.textPrimary),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ),
      ),
    );
  }

  Widget _buildRedistributionHistory(BudgetProvider budgetProvider) {
    final redistributionHistory = budgetProvider.redistributionHistory;
    if (redistributionHistory.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.history, color: AppColors.accent),
                SizedBox(width: 8),
                Text(
                  'Recent Redistribution',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: AppTypography.fontHeading,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...redistributionHistory.take(3).map<Widget>(
                  (transfer) => Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.infoLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Day ${transfer['from']} → Day ${transfer['to']}',
                          style: const TextStyle(
                              fontSize: 14, fontWeight: FontWeight.w500),
                        ),
                        Text(
                          '\$${(transfer['amount'] ?? 0).toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppColors.accent,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Use BudgetProvider for centralized state
    final budgetProvider = context.watch<BudgetProvider>();
    final isLoading = budgetProvider.isLoading;
    final budgets = budgetProvider.dailyBudgets;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Semantics(
          header: true,
          label: 'Smart Daily Budget Dashboard',
          child: const Text(
            'Smart Daily Budget',
            style: TextStyle(
              fontFamily: AppTypography.fontHeading,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        actions: [
          Semantics(
            label: _accessibilityService.createButtonSemanticLabel(
              action: 'Budget Settings',
              context: 'Configure budget modes and preferences',
            ),
            button: true,
            child: IconButton(
              icon: const Icon(Icons.settings),
              onPressed: () {
                Navigator.pushNamed(context, '/budget_settings');
                _accessibilityService.announceNavigation(
                  'Budget Settings',
                  description: 'Configure your budget preferences',
                );
              },
            ).withMinimumTouchTarget(),
          ),
        ],
      ),
      body: isLoading
          ? Semantics(
              label: 'Loading budget data. Please wait.',
              liveRegion: true,
              child: const Center(child: CircularProgressIndicator()),
            )
          : RefreshIndicator(
              onRefresh: () =>
                  context.read<BudgetProvider>().loadAllBudgetData(),
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    _buildLiveBudgetCard(budgetProvider),
                    _buildActionButtons(budgetProvider),
                    _buildSuggestionsCard(budgetProvider),
                    _buildRedistributionHistory(budgetProvider),

                    // Original budget list
                    if (budgets.isEmpty)
                      Semantics(
                        label:
                            'No budget data available. Your intelligent budget tracking will appear here when data is loaded.',
                        child: Card(
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16)),
                          elevation: 3,
                          child: const Padding(
                            padding: EdgeInsets.all(32),
                            child: Column(
                              children: [
                                Icon(Icons.account_balance_wallet,
                                    size: 64, color: Colors.grey),
                                SizedBox(height: 16),
                                Text(
                                  'No budget data available',
                                  style: TextStyle(
                                    fontSize: 18,
                                    color: Colors.grey,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                SizedBox(height: 8),
                                Text(
                                  'Your intelligent budget tracking will appear here',
                                  style: TextStyle(color: Colors.grey),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ),
                          ),
                        ),
                      )
                    else
                      ...(budgets.map<Widget>((budget) {
                        final date = DateFormat('MMMM d, yyyy')
                            .format(DateTime.parse(budget['date']));
                        final status = budget['status'] ?? 'unknown';
                        final spent = (budget['spent'] ?? 0).toDouble();
                        final limit = (budget['limit'] ?? 1).toDouble();
                        final percentage = ((spent / limit) * 100).round();

                        return Semantics(
                          label:
                              _accessibilityService.createProgressSemanticLabel(
                            category: 'Budget for $date',
                            spent: spent,
                            limit: limit,
                            status: status,
                          ),
                          child: Card(
                            margin: const EdgeInsets.only(bottom: 16),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14)),
                            elevation: 3,
                            child: ListTile(
                              contentPadding: const EdgeInsets.all(16),
                              leading: Semantics(
                                label: 'Status icon: $status',
                                child: Icon(getStatusIcon(status),
                                    color: getStatusColor(status), size: 32),
                              ),
                              title: Semantics(
                                label: 'Date: $date',
                                child: Text(
                                  date,
                                  style: const TextStyle(
                                    fontFamily: AppTypography.fontHeading,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const SizedBox(height: 4),
                                  Semantics(
                                    label: _accessibilityService
                                        .createFinancialSemanticLabel(
                                      label: 'Spending summary',
                                      amount: spent,
                                      category:
                                          'out of ${_accessibilityService.formatCurrency(limit)} limit',
                                    ),
                                    child: Text(
                                      'Spent: \$${budget['spent']} / Limit: \$${budget['limit']}',
                                      style: const TextStyle(
                                          fontFamily: AppTypography.fontBody),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Semantics(
                                    label:
                                        'Progress indicator: $percentage percent of budget used',
                                    child: LinearProgressIndicator(
                                      value: ((budget['spent'] ?? 0) /
                                              (budget['limit'] ?? 1))
                                          .clamp(0.0, 1.0),
                                      backgroundColor: Colors.grey[300],
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                          getStatusColor(status)),
                                    ),
                                  ),
                                ],
                              ),
                              trailing: Semantics(
                                label: 'Budget status: $status',
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: getStatusColor(status)
                                        .withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    status.toUpperCase(),
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: getStatusColor(status),
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        );
                      }).toList()),
                  ],
                ),
              ),
            ),
    );
  }
}

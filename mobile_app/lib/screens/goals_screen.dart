/// MODULE 5: Budgeting Goals - Enhanced Goals Screen
/// Complete UI for goal management with statistics and filtering

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/goal.dart';
import '../providers/goals_provider.dart';
import '../services/logging_service.dart';
import 'goal_insights_screen.dart';
import 'smart_goal_recommendations_screen.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({super.key});

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(_onTabChanged);

    // Initialize GoalsProvider for centralized state management
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final goalsProvider = context.read<GoalsProvider>();
      if (goalsProvider.state == GoalsState.initial) {
        goalsProvider.initialize();
      }
    });
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) {
      final goalsProvider = context.read<GoalsProvider>();
      String? status;
      switch (_tabController.index) {
        case 0:
          status = null;
          break;
        case 1:
          status = 'active';
          break;
        case 2:
          status = 'completed';
          break;
        case 3:
          status = 'paused';
          break;
      }
      goalsProvider.setStatusFilter(status);
    }
  }

  Future<void> _showGoalForm({Goal? goal}) async {
    final titleController = TextEditingController(text: goal?.title);
    final descriptionController = TextEditingController(text: goal?.description);
    final amountController = TextEditingController(
      text: goal?.targetAmount.toStringAsFixed(0) ?? '',
    );
    final savedController = TextEditingController(
      text: goal?.savedAmount.toStringAsFixed(0) ?? '',
    );
    final monthlyController = TextEditingController(
      text: goal?.monthlyContribution?.toStringAsFixed(0) ?? '',
    );

    String selectedCategory = goal?.category ?? GoalCategories.savings;
    String selectedPriority = goal?.priority ?? 'medium';
    DateTime? selectedDate = goal?.targetDate;

    final result = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(goal == null ? 'Create New Goal' : 'Edit Goal'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Title
                TextField(
                  controller: titleController,
                  decoration: const InputDecoration(
                    labelText: 'Goal Title *',
                    hintText: 'e.g., Emergency Fund',
                  ),
                ),
                const SizedBox(height: 16),

                // Description
                TextField(
                  controller: descriptionController,
                  decoration: const InputDecoration(
                    labelText: 'Description',
                    hintText: 'What is this goal for?',
                  ),
                  maxLines: 2,
                ),
                const SizedBox(height: 16),

                // Category Dropdown
                DropdownButtonFormField<String>(
                  value: selectedCategory,
                  decoration: const InputDecoration(labelText: 'Category'),
                  items: GoalCategories.all.map((cat) {
                    return DropdownMenuItem(value: cat, child: Text(cat));
                  }).toList(),
                  onChanged: (value) {
                    setDialogState(() => selectedCategory = value!);
                  },
                ),
                const SizedBox(height: 16),

                // Target Amount
                TextField(
                  controller: amountController,
                  decoration: const InputDecoration(
                    labelText: 'Target Amount *',
                    prefixText: '\$',
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 16),

                // Saved Amount
                TextField(
                  controller: savedController,
                  decoration: const InputDecoration(
                    labelText: 'Already Saved',
                    prefixText: '\$',
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 16),

                // Monthly Contribution
                TextField(
                  controller: monthlyController,
                  decoration: const InputDecoration(
                    labelText: 'Monthly Contribution (Optional)',
                    prefixText: '\$',
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 16),

                // Priority
                DropdownButtonFormField<String>(
                  value: selectedPriority,
                  decoration: const InputDecoration(labelText: 'Priority'),
                  items: GoalPriorities.all.map((priority) {
                    return DropdownMenuItem(
                      value: priority,
                      child: Text(priority[0].toUpperCase() + priority.substring(1)),
                    );
                  }).toList(),
                  onChanged: (value) {
                    setDialogState(() => selectedPriority = value!);
                  },
                ),
                const SizedBox(height: 16),

                // Target Date
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Target Date (Optional)'),
                  subtitle: Text(
                    selectedDate != null
                        ? DateFormat('MMM dd, yyyy').format(selectedDate!)
                        : 'Not set',
                  ),
                  trailing: const Icon(Icons.calendar_today),
                  onTap: () async {
                    final date = await showDatePicker(
                      context: context,
                      initialDate: selectedDate ?? DateTime.now().add(const Duration(days: 90)),
                      firstDate: DateTime.now(),
                      lastDate: DateTime.now().add(const Duration(days: 3650)),
                    );
                    if (date != null) {
                      setDialogState(() => selectedDate = date);
                    }
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                final title = titleController.text.trim();
                final amount = double.tryParse(amountController.text.trim()) ?? 0;

                if (title.isEmpty || amount <= 0) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Please fill in required fields')),
                  );
                  return;
                }

                final data = {
                  'title': title,
                  'description': descriptionController.text.trim(),
                  'category': selectedCategory,
                  'target_amount': amount,
                  'saved_amount': double.tryParse(savedController.text.trim()) ?? 0,
                  'monthly_contribution': monthlyController.text.isNotEmpty
                      ? double.tryParse(monthlyController.text.trim())
                      : null,
                  'priority': selectedPriority,
                  'target_date': selectedDate?.toIso8601String().split('T')[0],
                };

                try {
                  final goalsProvider = context.read<GoalsProvider>();
                  bool success;
                  if (goal == null) {
                    success = await goalsProvider.createGoal(data);
                  } else {
                    success = await goalsProvider.updateGoal(goal.id, data);
                  }
                  if (!context.mounted) return;
                  if (success) {
                    Navigator.pop(context, true);
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Error: ${goalsProvider.errorMessage}')),
                    );
                  }
                } catch (e) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: $e')),
                  );
                }
              },
              child: Text(goal == null ? 'Create' : 'Save'),
            ),
          ],
        ),
      ),
    );

    // GoalsProvider auto-refreshes on successful operations
  }

  Future<void> _deleteGoal(Goal goal) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Goal'),
        content: Text('Are you sure you want to delete "${goal.title}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      final goalsProvider = context.read<GoalsProvider>();
      final success = await goalsProvider.deleteGoal(goal.id);
      if (!success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${goalsProvider.errorMessage}')),
        );
      }
    }
  }

  Future<void> _addSavings(Goal goal) async {
    final controller = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Savings'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Amount to Add',
            prefixText: '\$',
          ),
          keyboardType: TextInputType.number,
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              final amount = double.tryParse(controller.text.trim()) ?? 0;
              if (amount <= 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Please enter a valid amount')),
                );
                return;
              }

              try {
                final goalsProvider = context.read<GoalsProvider>();
                final success = await goalsProvider.addSavings(goal.id, amount);
                if (!context.mounted) return;
                if (success) {
                  Navigator.pop(context, true);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: ${goalsProvider.errorMessage}')),
                  );
                }
              } catch (e) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Error: $e')),
                );
              }
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );

    // GoalsProvider auto-refreshes on successful operations
  }

  Future<void> _toggleGoalStatus(Goal goal) async {
    final goalsProvider = context.read<GoalsProvider>();
    final success = await goalsProvider.toggleGoalStatus(goal);
    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${goalsProvider.errorMessage}')),
      );
    }
  }

  void _showGoalInsights(Goal goal) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => GoalInsightsScreen(goal: goal),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Use GoalsProvider for centralized state
    final goalsProvider = context.watch<GoalsProvider>();
    final isLoading = goalsProvider.isLoading;
    final goals = goalsProvider.goals;
    final hasStatistics = goalsProvider.hasStatistics;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Goals',
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
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.textPrimary,
          unselectedLabelColor: Colors.grey,
          indicatorColor: AppColors.secondary,
          tabs: const [
            Tab(text: 'All'),
            Tab(text: 'Active'),
            Tab(text: 'Completed'),
            Tab(text: 'Paused'),
          ],
        ),
      ),
      floatingActionButton: Column(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          FloatingActionButton.extended(
            heroTag: "smart_recommendations_fab",
            onPressed: () async {
              final result = await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const SmartGoalRecommendationsScreen(),
                ),
              );
              if (result == true) {
                context.read<GoalsProvider>().refresh();
              }
            },
            backgroundColor: AppColors.textPrimary,
            label: const Text('AI Suggestions', style: TextStyle(color: Colors.white)),
            icon: const Icon(Icons.auto_awesome, color: AppColors.secondary),
          ),
          const SizedBox(height: 12),
          FloatingActionButton(
            heroTag: "goals_fab",
            onPressed: () => _showGoalForm(),
            backgroundColor: AppColors.secondary,
            child: const Icon(Icons.add, color: Colors.black),
          ),
        ],
      ),
      body: Column(
        children: [
          // Statistics Card
          if (hasStatistics) _buildStatisticsCard(goalsProvider),

          // Goals List
          Expanded(
            child: isLoading
                ? const Center(child: CircularProgressIndicator())
                : goals.isEmpty
                    ? _buildEmptyState()
                    : _buildGoalsList(goals),
          ),
        ],
      ),
    );
  }

  Widget _buildStatisticsCard(GoalsProvider goalsProvider) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.textPrimary, AppColors.textPrimary.withValues(alpha: 0.7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildStatItem('Total', goalsProvider.totalGoals.toString(), Icons.flag),
              _buildStatItem('Active', goalsProvider.activeGoals.toString(), Icons.play_arrow),
              _buildStatItem('Done', goalsProvider.completedGoals.toString(), Icons.check_circle),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildStatItem(
                'Completion',
                '${goalsProvider.completionRate.toStringAsFixed(0)}%',
                Icons.pie_chart,
              ),
              _buildStatItem(
                'Avg Progress',
                '${goalsProvider.averageProgress.toStringAsFixed(0)}%',
                Icons.trending_up,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: AppColors.secondary, size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 12,
            color: Colors.white70,
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.flag, size: 64, color: Colors.grey),
          const SizedBox(height: 16),
          const Text(
            'No goals yet',
            style: TextStyle(fontSize: 18, color: Colors.grey, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          const Text(
            'Tap the + button to create your first goal',
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Widget _buildGoalsList(List<Goal> goals) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: goals.length,
      itemBuilder: (context, index) => _buildGoalCard(goals[index]),
    );
  }

  Widget _buildGoalCard(Goal goal) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 4,
      shadowColor: Colors.black.withValues(alpha: 0.1),
      child: InkWell(
        onTap: () => _showGoalForm(goal: goal),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              colors: [
                Colors.white,
                AppColors.background.withValues(alpha: 0.3),
              ],
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            goal.title,
                            style: const TextStyle(
                              fontFamily: AppTypography.fontHeading,
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          if (goal.description != null && goal.description!.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              goal.description!,
                              style: const TextStyle(fontSize: 14, color: Colors.grey),
                            ),
                          ],
                        ],
                      ),
                    ),
                    PopupMenuButton<String>(
                      onSelected: (value) {
                        switch (value) {
                          case 'insights':
                            _showGoalInsights(goal);
                            break;
                          case 'edit':
                            _showGoalForm(goal: goal);
                            break;
                          case 'add_savings':
                            _addSavings(goal);
                            break;
                          case 'toggle_status':
                            _toggleGoalStatus(goal);
                            break;
                          case 'delete':
                            _deleteGoal(goal);
                            break;
                        }
                      },
                      itemBuilder: (context) => [
                        const PopupMenuItem(
                          value: 'insights',
                          child: Row(children: [
                            Icon(Icons.insights, size: 20),
                            SizedBox(width: 8),
                            Text('AI Insights')
                          ]),
                        ),
                        const PopupMenuItem(
                          value: 'edit',
                          child: Row(children: [
                            Icon(Icons.edit, size: 20),
                            SizedBox(width: 8),
                            Text('Edit')
                          ]),
                        ),
                        const PopupMenuItem(
                          value: 'add_savings',
                          child: Row(children: [
                            Icon(Icons.add_circle, size: 20),
                            SizedBox(width: 8),
                            Text('Add Savings')
                          ]),
                        ),
                        PopupMenuItem(
                          value: 'toggle_status',
                          child: Row(
                            children: [
                              Icon(goal.status == 'active' ? Icons.pause : Icons.play_arrow,
                                  size: 20),
                              const SizedBox(width: 8),
                              Text(goal.status == 'active' ? 'Pause' : 'Resume'),
                            ],
                          ),
                        ),
                        const PopupMenuItem(
                          value: 'delete',
                          child: Row(
                            children: [
                              Icon(Icons.delete, size: 20, color: Colors.red),
                              SizedBox(width: 8),
                              Text('Delete', style: TextStyle(color: Colors.red)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),

                // Category & Priority
                const SizedBox(height: 12),
                Row(
                  children: [
                    if (goal.category != null) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.secondary.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          goal.category!,
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                      const SizedBox(width: 8),
                    ],
                    if (goal.priority != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: _getPriorityColor(goal.priority!).withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          goal.priority![0].toUpperCase() + goal.priority!.substring(1),
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: _getPriorityColor(goal.priority!),
                          ),
                        ),
                      ),
                  ],
                ),

                const SizedBox(height: 16),

                // Progress
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      goal.formattedSavedAmount,
                      style: const TextStyle(
                        fontFamily: AppTypography.fontHeading,
                        fontWeight: FontWeight.bold,
                        fontSize: 20,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Text(
                      'of ${goal.formattedTargetAmount}',
                      style: const TextStyle(fontSize: 16, color: Colors.grey),
                    ),
                  ],
                ),

                const SizedBox(height: 8),

                LinearProgressIndicator(
                  value: (goal.progress / 100).clamp(0.0, 1.0),
                  backgroundColor: Colors.grey.shade200,
                  valueColor: AlwaysStoppedAnimation(_getProgressColor(goal.progress)),
                  minHeight: 8,
                ),

                const SizedBox(height: 8),

                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      goal.progressPercentage,
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                    Text(
                      '${goal.formattedRemainingAmount} remaining',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),

                // Target Date
                if (goal.targetDate != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: goal.isOverdue ? Colors.red.shade50 : Colors.blue.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: goal.isOverdue ? Colors.red.shade200 : Colors.blue.shade200,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.calendar_today,
                          size: 16,
                          color: goal.isOverdue ? Colors.red.shade700 : Colors.blue.shade700,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          goal.isOverdue
                              ? 'Overdue: ${DateFormat('MMM dd, yyyy').format(goal.targetDate!)}'
                              : 'Target: ${DateFormat('MMM dd, yyyy').format(goal.targetDate!)}',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: goal.isOverdue ? Colors.red.shade700 : Colors.blue.shade700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Color _getProgressColor(double progress) {
    if (progress >= 100) return Colors.green;
    if (progress >= 70) return AppColors.secondary;
    return AppColors.textPrimary;
  }

  Color _getPriorityColor(String priority) {
    switch (priority) {
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
}

/// MODULE 5: Budgeting Goals - Enhanced Goals Screen
/// Complete UI for goal management with statistics and filtering

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/goal.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import 'goal_insights_screen.dart';
import 'smart_goal_recommendations_screen.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({super.key});

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<Goal> _goals = [];
  Map<String, dynamic>? _statistics;
  String? _selectedStatus;
  String? _selectedCategory;

  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(_onTabChanged);
    fetchGoals();
    fetchStatistics();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) {
      setState(() {
        switch (_tabController.index) {
          case 0:
            _selectedStatus = null;
            break;
          case 1:
            _selectedStatus = 'active';
            break;
          case 2:
            _selectedStatus = 'completed';
            break;
          case 3:
            _selectedStatus = 'paused';
            break;
        }
      });
      fetchGoals();
    }
  }

  Future<void> fetchGoals() async {
    setState(() => _isLoading = true);
    try {
      final data = await _apiService.getGoals(
        status: _selectedStatus,
        category: _selectedCategory,
      );
      setState(() {
        _goals = data.map((json) => Goal.fromJson(json)).toList();
        _isLoading = false;
      });
    } catch (e) {
      logError('Error loading goals: $e');
      if (!mounted) return;
      setState(() {
        _goals = _getSampleGoals();
        _isLoading = false;
      });
    }
  }

  Future<void> fetchStatistics() async {
    try {
      final stats = await _apiService.getGoalStatistics();
      setState(() => _statistics = stats);
    } catch (e) {
      logError('Error loading goal statistics: $e');
    }
  }

  List<Goal> _getSampleGoals() {
    return [
      Goal(
        id: '1',
        title: 'Emergency Fund',
        description: 'Build a 3-month emergency fund',
        category: 'Emergency',
        targetAmount: 5000,
        savedAmount: 1250,
        status: 'active',
        progress: 25.0,
        createdAt: DateTime.now().subtract(const Duration(days: 30)),
        lastUpdated: DateTime.now(),
        priority: 'high',
      ),
    ];
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
                  if (goal == null) {
                    await _apiService.createGoal(data);
                  } else {
                    await _apiService.updateGoal(goal.id, data);
                  }
                  if (!context.mounted) return;
                  Navigator.pop(context, true);
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

    if (result == true) {
      fetchGoals();
      fetchStatistics();
    }
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
      try {
        await _apiService.deleteGoal(goal.id);
        fetchGoals();
        fetchStatistics();
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
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
                await _apiService.addSavingsToGoal(goal.id, amount);
                if (!context.mounted) return;
                Navigator.pop(context, true);
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

    if (result == true) {
      fetchGoals();
      fetchStatistics();
    }
  }

  Future<void> _toggleGoalStatus(Goal goal) async {
    try {
      if (goal.status == 'active') {
        await _apiService.pauseGoal(goal.id);
      } else if (goal.status == 'paused') {
        await _apiService.resumeGoal(goal.id);
      }
      fetchGoals();
      fetchStatistics();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
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
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Goals',
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
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF193C57),
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFFFFD25F),
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
                fetchGoals();
                fetchStatistics();
              }
            },
            backgroundColor: const Color(0xFF193C57),
            label: const Text('AI Suggestions', style: TextStyle(color: Colors.white)),
            icon: const Icon(Icons.auto_awesome, color: Color(0xFFFFD25F)),
          ),
          const SizedBox(height: 12),
          FloatingActionButton(
            heroTag: "goals_fab",
            onPressed: () => _showGoalForm(),
            backgroundColor: const Color(0xFFFFD25F),
            child: const Icon(Icons.add, color: Colors.black),
          ),
        ],
      ),
      body: Column(
        children: [
          // Statistics Card
          if (_statistics != null) _buildStatisticsCard(),

          // Goals List
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _goals.isEmpty
                    ? _buildEmptyState()
                    : _buildGoalsList(),
          ),
        ],
      ),
    );
  }

  Widget _buildStatisticsCard() {
    final stats = _statistics!;
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF193C57), Color(0xFF2B5876)],
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
              _buildStatItem('Total', stats['total_goals'].toString(), Icons.flag),
              _buildStatItem('Active', stats['active_goals'].toString(), Icons.play_arrow),
              _buildStatItem('Done', stats['completed_goals'].toString(), Icons.check_circle),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildStatItem(
                'Completion',
                '${stats['completion_rate'].toStringAsFixed(0)}%',
                Icons.pie_chart,
              ),
              _buildStatItem(
                'Avg Progress',
                '${stats['average_progress'].toStringAsFixed(0)}%',
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
        Icon(icon, color: const Color(0xFFFFD25F), size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontFamily: 'Sora',
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            fontFamily: 'Manrope',
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

  Widget _buildGoalsList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _goals.length,
      itemBuilder: (context, index) => _buildGoalCard(_goals[index]),
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
                const Color(0xFFFFF9F0).withValues(alpha: 0.3),
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
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.bold,
                              fontSize: 18,
                              color: Color(0xFF193C57),
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
                          child: Row(children: [Icon(Icons.insights, size: 20), SizedBox(width: 8), Text('AI Insights')]),
                        ),
                        const PopupMenuItem(
                          value: 'edit',
                          child: Row(children: [Icon(Icons.edit, size: 20), SizedBox(width: 8), Text('Edit')]),
                        ),
                        const PopupMenuItem(
                          value: 'add_savings',
                          child: Row(children: [Icon(Icons.add_circle, size: 20), SizedBox(width: 8), Text('Add Savings')]),
                        ),
                        PopupMenuItem(
                          value: 'toggle_status',
                          child: Row(
                            children: [
                              Icon(goal.status == 'active' ? Icons.pause : Icons.play_arrow, size: 20),
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
                          color: const Color(0xFFFFD25F).withValues(alpha: 0.2),
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
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.bold,
                        fontSize: 20,
                        color: Color(0xFF193C57),
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
    if (progress >= 70) return const Color(0xFFFFD25F);
    return const Color(0xFF193C57);
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

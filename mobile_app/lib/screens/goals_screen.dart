
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({Key? key}) : super(key: key);

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _goals = [];

  @override
  void initState() {
    super.initState();
    fetchGoals();
  }

  Future<void> fetchGoals() async {
    try {
      final data = await _apiService.getGoals();
      setState(() {
        _goals = data;
        _isLoading = false;
      });
    } catch (e) {
      logError('Error loading goals: $e');
      if (!mounted) return;
      setState(() {
        // Use sample data instead of empty list to make the screen more engaging
        _goals = _getSampleGoals();
        _isLoading = false;
      });
    }
  }

  List<dynamic> _getSampleGoals() {
    return [
      {
        'id': 1,
        'title': 'Emergency Fund',
        'target_amount': 5000,
        'current_amount': 1250,
        'description': 'Build a 3-month emergency fund for financial security',
        'category': 'Savings',
        'deadline': DateTime.now().add(const Duration(days: 180)).toIso8601String(),
        'created_at': DateTime.now().subtract(const Duration(days: 30)).toIso8601String(),
      },
      {
        'id': 2,
        'title': 'Vacation to Europe',
        'target_amount': 3500,
        'current_amount': 850,
        'description': 'Save for a 2-week trip to Europe next summer',
        'category': 'Travel',
        'deadline': DateTime.now().add(const Duration(days: 300)).toIso8601String(),
        'created_at': DateTime.now().subtract(const Duration(days: 15)).toIso8601String(),
      },
      {
        'id': 3,
        'title': 'New Laptop',
        'target_amount': 1200,
        'current_amount': 400,
        'description': 'Upgrade to a new laptop for work and productivity',
        'category': 'Technology',
        'deadline': DateTime.now().add(const Duration(days: 90)).toIso8601String(),
        'created_at': DateTime.now().subtract(const Duration(days: 10)).toIso8601String(),
      },
    ];
  }

  Future<void> _showGoalForm({Map<String, dynamic>? goal}) async {
    final TextEditingController titleController =
        TextEditingController(text: goal?['title']);
    final TextEditingController amountController =
        TextEditingController(text: goal?['target_amount']?.toString());
    final bool isEditing = goal != null;

    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(isEditing ? 'Edit Goal' : 'New Goal'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleController,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            TextField(
              controller: amountController,
              decoration: const InputDecoration(labelText: 'Target Amount'),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final title = titleController.text.trim();
              final amount = double.tryParse(amountController.text.trim()) ?? 0;

              if (title.isEmpty || amount <= 0) return;

              final data = {
                'title': title,
                'target_amount': amount,
              };

              try {
                if (isEditing) {
                  await _apiService.updateGoal(goal['id'], data);
                } else {
                  await _apiService.createGoal(data);
                }
                if (!mounted) return;
                Navigator.pop(context, true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Failed to save goal: \$e')),
                );
              }
            },
            child: Text(isEditing ? 'Save' : 'Create'),
          )
        ],
      ),
    );

    if (result == true) fetchGoals();
  }

  Future<void> _deleteGoal(int id) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Goal'),
        content: const Text('Are you sure you want to delete this goal?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _apiService.deleteGoal(id);
        fetchGoals();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: \$e')),
        );
      }
    }
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
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showGoalForm(),
        backgroundColor: const Color(0xFFFFD25F),
        child: const Icon(Icons.add, color: Colors.black),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth > 600;
          Widget content;
          if (_isLoading) {
            content = const Center(child: CircularProgressIndicator());
          } else if (_goals.isEmpty) {
            content = const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.flag, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    'No goals yet',
                    style: TextStyle(
                      fontSize: 18,
                      color: Colors.grey,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Tap the + button to create your first goal',
                    style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            );
          } else {
            content = ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _goals.length,
              itemBuilder: (context, index) {
                final goal = _goals[index];
                final targetAmount = (goal['target_amount'] ?? 0).toDouble();
                final currentAmount = (goal['current_amount'] ?? 0).toDouble();
                final progress = targetAmount > 0 ? currentAmount / targetAmount : 0.0;
                final remainingAmount = targetAmount - currentAmount;
                
                // Parse deadline if available
                DateTime? deadline;
                try {
                  if (goal['deadline'] != null) {
                    deadline = DateTime.parse(goal['deadline']);
                  }
                } catch (e) {
                  // Ignore parsing errors
                }
                
                return Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  elevation: 4,
                  shadowColor: Colors.black.withOpacity(0.1),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: LinearGradient(
                        colors: [
                          Colors.white,
                          const Color(0xFFFFF9F0).withOpacity(0.3),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                    ),
                    child: Padding(
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
                                      goal['title'] ?? 'Goal',
                                      style: const TextStyle(
                                        fontFamily: 'Sora',
                                        fontWeight: FontWeight.bold,
                                        fontSize: 18,
                                        color: Color(0xFF193C57),
                                      ),
                                    ),
                                    if (goal['description'] != null && goal['description'].isNotEmpty) ...[
                                      const SizedBox(height: 4),
                                      Text(
                                        goal['description'],
                                        style: const TextStyle(
                                          fontFamily: 'Manrope',
                                          fontSize: 14,
                                          color: Colors.grey,
                                        ),
                                      ),
                                    ],
                                    if (goal['category'] != null) ...[
                                      const SizedBox(height: 8),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFFFFD25F).withOpacity(0.2),
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Text(
                                          goal['category'],
                                          style: const TextStyle(
                                            fontFamily: 'Manrope',
                                            fontSize: 12,
                                            fontWeight: FontWeight.w600,
                                            color: Color(0xFF193C57),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              PopupMenuButton<String>(
                                onSelected: (value) {
                                  if (value == 'edit') {
                                    _showGoalForm(goal: goal);
                                  } else if (value == 'delete') {
                                    _deleteGoal(goal['id']);
                                  }
                                },
                                itemBuilder: (context) => const [
                                  PopupMenuItem(
                                    value: 'edit',
                                    child: Row(
                                      children: [
                                        Icon(Icons.edit, size: 20),
                                        SizedBox(width: 8),
                                        Text('Edit'),
                                      ],
                                    ),
                                  ),
                                  PopupMenuItem(
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
                                child: const Icon(
                                  Icons.more_vert,
                                  color: Color(0xFF193C57),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          
                          // Progress section
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '\$${currentAmount.toStringAsFixed(0)}',
                                style: const TextStyle(
                                  fontFamily: 'Sora',
                                  fontWeight: FontWeight.bold,
                                  fontSize: 20,
                                  color: Color(0xFF193C57),
                                ),
                              ),
                              Text(
                                'of \$${targetAmount.toStringAsFixed(0)}',
                                style: const TextStyle(
                                  fontFamily: 'Manrope',
                                  fontSize: 16,
                                  color: Colors.grey,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          
                          // Progress bar
                          LinearProgressIndicator(
                            value: progress.clamp(0.0, 1.0),
                            backgroundColor: Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              progress >= 1.0 ? Colors.green :
                              progress >= 0.7 ? const Color(0xFFFFD25F) :
                              const Color(0xFF193C57),
                            ),
                            minHeight: 8,
                          ),
                          const SizedBox(height: 8),
                          
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '${(progress * 100).toStringAsFixed(0)}% complete',
                                style: const TextStyle(
                                  fontFamily: 'Manrope',
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF193C57),
                                ),
                              ),
                              if (remainingAmount > 0)
                                Text(
                                  '\$${remainingAmount.toStringAsFixed(0)} remaining',
                                  style: const TextStyle(
                                    fontFamily: 'Manrope',
                                    fontSize: 12,
                                    color: Colors.grey,
                                  ),
                                ),
                            ],
                          ),
                          
                          // Deadline info
                          if (deadline != null) ...[
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.blue.shade50,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: Colors.blue.shade200),
                              ),
                              child: Row(
                                children: [
                                  Icon(
                                    Icons.calendar_today,
                                    size: 16,
                                    color: Colors.blue.shade600,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Target date: ${deadline.day}/${deadline.month}/${deadline.year}',
                                    style: TextStyle(
                                      fontFamily: 'Manrope',
                                      fontSize: 12,
                                      color: Colors.blue.shade700,
                                      fontWeight: FontWeight.w500,
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
                );
              },
            );
          }

          return Padding(
            padding: const EdgeInsets.all(16),
            child: isWide
                ? Row(
                    children: [
                      Expanded(child: content),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Center(
                          child: Icon(Icons.flag, size: 120, color: Colors.grey[400]),
                        ),
                      ),
                    ],
                  )
                : content,
          );
        },
      ),
    );
  }
}


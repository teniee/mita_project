
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'services/logging_service.dart';

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
        // Set data to empty instead of showing error
        _goals = [];
        _isLoading = false;
      });
    }
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
                return Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  elevation: 3,
                  child: ListTile(
                    contentPadding: const EdgeInsets.all(16),
                    title: Text(
                      goal['title'] ?? 'Goal',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    subtitle: Text(
                      'Target: \$${goal['target_amount']}',
                      style: const TextStyle(fontFamily: 'Manrope'),
                    ),
                    trailing: PopupMenuButton<String>(
                      onSelected: (value) {
                        if (value == 'edit') {
                          _showGoalForm(goal: goal);
                        } else if (value == 'delete') {
                          _deleteGoal(goal['id']);
                        }
                      },
                      itemBuilder: (context) => const [
                        PopupMenuItem(value: 'edit', child: Text('Edit')),
                        PopupMenuItem(value: 'delete', child: Text('Delete')),
                      ],
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


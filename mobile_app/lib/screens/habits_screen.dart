import 'package:flutter/material.dart';
import '../services/api_service.dart';

// Habit data model for better type safety and data management
class Habit {
  final int id;
  final String title;
  final String description;
  final String targetFrequency;
  final DateTime createdAt;
  final List<DateTime> completedDates;
  final int currentStreak;
  final int longestStreak;
  final double completionRate;

  Habit({
    required this.id,
    required this.title,
    required this.description,
    required this.targetFrequency,
    required this.createdAt,
    required this.completedDates,
    required this.currentStreak,
    required this.longestStreak,
    required this.completionRate,
  });

  factory Habit.fromJson(Map<String, dynamic> json) {
    return Habit(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      description: json['description'] ?? '',
      targetFrequency: json['target_frequency'] ?? 'daily',
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      completedDates: (json['completed_dates'] as List<dynamic>? ?? [])
          .map((date) => DateTime.tryParse(date.toString()) ?? DateTime.now())
          .toList(),
      currentStreak: json['current_streak'] ?? 0,
      longestStreak: json['longest_streak'] ?? 0,
      completionRate: (json['completion_rate'] ?? 0.0).toDouble(),
    );
  }

  bool get isCompletedToday {
    final today = DateTime.now();
    return completedDates.any((date) => 
        date.year == today.year && 
        date.month == today.month && 
        date.day == today.day);
  }
}

class HabitsScreen extends StatefulWidget {
  const HabitsScreen({Key? key}) : super(key: key);

  @override
  State<HabitsScreen> createState() => _HabitsScreenState();
}

class _HabitsScreenState extends State<HabitsScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<Habit> _habits = [];
  String? _errorMessage;
  late AnimationController _animationController;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _fetchHabits();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Future<void> _fetchHabits() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final data = await _apiService.getHabits();
      setState(() {
        _habits = data.map((json) => Habit.fromJson(json)).toList();
        _isLoading = false;
      });
      _animationController.forward();
    } catch (e) {
      print('Error loading habits: $e');
      if (!mounted) return;
      setState(() {
        _habits = [];
        _isLoading = false;
        _errorMessage = 'Failed to load habits. Please try again.';
      });
    }
  }

  Future<void> _toggleHabitCompletion(Habit habit) async {
    final today = DateTime.now().toIso8601String().split('T')[0];
    
    try {
      if (habit.isCompletedToday) {
        await _apiService.uncompleteHabit(habit.id, today);
      } else {
        await _apiService.completeHabit(habit.id, today);
      }
      
      // Show success feedback
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            habit.isCompletedToday 
                ? 'Habit unmarked for today' 
                : 'Great job! Habit completed for today',
          ),
          backgroundColor: habit.isCompletedToday 
              ? Colors.orange 
              : Colors.green,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
      
      // Refresh the habits list to get updated data
      _fetchHabits();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to update habit: $e'),
          backgroundColor: Colors.red,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    }
  }

  Future<void> _showHabitForm({Habit? habit}) async {
    final titleController = TextEditingController(text: habit?.title ?? '');
    final descController = TextEditingController(text: habit?.description ?? '');
    String selectedFrequency = habit?.targetFrequency ?? 'daily';
    final isEditing = habit != null;

    final result = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFFFFF9F0),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: Text(
            isEditing ? 'Edit Habit' : 'Create New Habit',
            style: const TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              color: Color(0xFF193C57),
            ),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: titleController,
                  style: const TextStyle(fontFamily: 'Manrope'),
                  decoration: InputDecoration(
                    labelText: 'Habit Title',
                    labelStyle: const TextStyle(color: Color(0xFF193C57)),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F), width: 2),
                    ),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: descController,
                  maxLines: 3,
                  style: const TextStyle(fontFamily: 'Manrope'),
                  decoration: InputDecoration(
                    labelText: 'Description (optional)',
                    labelStyle: const TextStyle(color: Color(0xFF193C57)),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F), width: 2),
                    ),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: selectedFrequency,
                  style: const TextStyle(fontFamily: 'Manrope', color: Color(0xFF193C57)),
                  decoration: InputDecoration(
                    labelText: 'Target Frequency',
                    labelStyle: const TextStyle(color: Color(0xFF193C57)),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Color(0xFFFFD25F), width: 2),
                    ),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                  items: const [
                    DropdownMenuItem(value: 'daily', child: Text('Daily')),
                    DropdownMenuItem(value: 'weekly', child: Text('Weekly')),
                    DropdownMenuItem(value: 'monthly', child: Text('Monthly')),
                  ],
                  onChanged: (value) {
                    setDialogState(() {
                      selectedFrequency = value!;
                    });
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text(
                'Cancel',
                style: TextStyle(color: Colors.grey, fontFamily: 'Manrope'),
              ),
            ),
            ElevatedButton(
              onPressed: () async {
                final title = titleController.text.trim();
                if (title.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Please enter a habit title'),
                      backgroundColor: Colors.orange,
                    ),
                  );
                  return;
                }

                final data = {
                  'title': title,
                  'description': descController.text.trim(),
                  'target_frequency': selectedFrequency,
                };

                try {
                  if (isEditing) {
                    await _apiService.updateHabit(habit!.id, data);
                  } else {
                    await _apiService.createHabit(data);
                  }
                  if (!mounted) return;
                  Navigator.pop(context, true);
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Failed to save habit: $e'),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFFD25F),
                foregroundColor: Colors.black,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: Text(
                isEditing ? 'Update' : 'Create',
                style: const TextStyle(fontFamily: 'Sora', fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );

    if (result == true) _fetchHabits();
  }

  Future<void> _deleteHabit(Habit habit) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFFFFF9F0),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text(
          'Delete Habit',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
          ),
        ),
        content: Text(
          'Are you sure you want to delete "${habit.title}"? This action cannot be undone.',
          style: const TextStyle(fontFamily: 'Manrope'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text(
              'Cancel',
              style: TextStyle(color: Colors.grey, fontFamily: 'Manrope'),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text(
              'Delete',
              style: TextStyle(fontFamily: 'Sora', fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _apiService.deleteHabit(habit.id);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('"${habit.title}" deleted successfully'),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
        _fetchHabits();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to delete habit: $e'),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    }
  }

  Widget _buildHabitCard(Habit habit) {
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
                          habit.title,
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                            color: Color(0xFF193C57),
                          ),
                        ),
                        if (habit.description.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            habit.description,
                            style: const TextStyle(
                              fontFamily: 'Manrope',
                              fontSize: 14,
                              color: Colors.grey,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') {
                        _showHabitForm(habit: habit);
                      } else if (value == 'delete') {
                        _deleteHabit(habit);
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'edit',
                        child: Row(
                          children: [
                            Icon(Icons.edit, size: 20),
                            SizedBox(width: 8),
                            Text('Edit'),
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
                    child: const Icon(
                      Icons.more_vert,
                      color: Color(0xFF193C57),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  // Today's completion checkbox
                  InkWell(
                    onTap: () => _toggleHabitCompletion(habit),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: habit.isCompletedToday 
                            ? const Color(0xFFFFD25F) 
                            : Colors.grey.shade200,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: habit.isCompletedToday 
                              ? const Color(0xFFFFD25F) 
                              : Colors.grey.shade300,
                          width: 2,
                        ),
                      ),
                      child: Icon(
                        habit.isCompletedToday 
                            ? Icons.check_rounded 
                            : Icons.add,
                        color: habit.isCompletedToday 
                            ? Colors.black 
                            : Colors.grey.shade600,
                        size: 20,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    habit.isCompletedToday ? 'Completed today!' : 'Mark as done',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      color: habit.isCompletedToday 
                          ? const Color(0xFF193C57) 
                          : Colors.grey.shade600,
                    ),
                  ),
                  const Spacer(),
                  // Streak counter
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: habit.currentStreak > 0 
                          ? Colors.orange.shade100 
                          : Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.local_fire_department,
                          size: 16,
                          color: habit.currentStreak > 0 
                              ? Colors.orange.shade700 
                              : Colors.grey.shade600,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '${habit.currentStreak}',
                          style: TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                            color: habit.currentStreak > 0 
                                ? Colors.orange.shade700 
                                : Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Progress indicators
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Completion Rate',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 12,
                            color: Colors.grey.shade600,
                          ),
                        ),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(
                          value: habit.completionRate / 100,
                          backgroundColor: Colors.grey.shade200,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            habit.completionRate >= 80 ? Colors.green :
                            habit.completionRate >= 50 ? Colors.orange :
                            Colors.red,
                          ),
                          minHeight: 6,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${habit.completionRate.toInt()}%',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 20),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Best Streak',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${habit.longestStreak} days',
                        style: const TextStyle(
                          fontFamily: 'Sora',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF193C57),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: const Color(0xFFFFD25F).withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.psychology,
              size: 64,
              color: Color(0xFFFFD25F),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'Start Building Better Habits',
            style: TextStyle(
              fontSize: 24,
              fontFamily: 'Sora',
              fontWeight: FontWeight.bold,
              color: Color(0xFF193C57),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Create your first habit and start tracking\nyour progress towards a better you',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              fontFamily: 'Manrope',
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 32),
          ElevatedButton.icon(
            onPressed: () => _showHabitForm(),
            icon: const Icon(Icons.add, color: Colors.black),
            label: const Text(
              'Create Your First Habit',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.bold,
                color: Colors.black,
              ),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFFD25F),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.red,
          ),
          const SizedBox(height: 16),
          Text(
            _errorMessage ?? 'Something went wrong',
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 16,
              fontFamily: 'Manrope',
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _fetchHabits,
            icon: const Icon(Icons.refresh, color: Colors.black),
            label: const Text(
              'Try Again',
              style: TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.bold,
                color: Colors.black,
              ),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFFD25F),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Habits',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
            fontSize: 24,
          ),
        ),
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
        actions: [
          if (_habits.isNotEmpty)
            IconButton(
              onPressed: _fetchHabits,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
            ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showHabitForm(),
        backgroundColor: const Color(0xFFFFD25F),
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text(
          'New Habit',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _fetchHabits,
        color: const Color(0xFFFFD25F),
        child: _isLoading
            ? const Center(
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Color(0xFFFFD25F)),
                ),
              )
            : _errorMessage != null
                ? _buildErrorState()
                : _habits.isEmpty
                    ? _buildEmptyState()
                    : AnimatedBuilder(
                        animation: _animationController,
                        builder: (context, child) {
                          return FadeTransition(
                            opacity: _animationController,
                            child: ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _habits.length,
                              itemBuilder: (context, index) {
                                return SlideTransition(
                                  position: Tween<Offset>(
                                    begin: const Offset(0, 0.3),
                                    end: Offset.zero,
                                  ).animate(CurvedAnimation(
                                    parent: _animationController,
                                    curve: Interval(
                                      index * 0.1,
                                      1.0,
                                      curve: Curves.easeOutBack,
                                    ),
                                  )),
                                  child: _buildHabitCard(_habits[index]),
                                );
                              },
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
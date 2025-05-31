
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HabitsScreen extends StatefulWidget {
  const HabitsScreen({Key? key}) : super(key: key);

  @override
  State<HabitsScreen> createState() => _HabitsScreenState();
}

class _HabitsScreenState extends State<HabitsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _habits = [];

  @override
  void initState() {
    super.initState();
    fetchHabits();
  }

  Future<void> fetchHabits() async {
    try {
      final data = await _apiService.getHabits();
      setState(() {
        _habits = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load habits: \$e')),
      );
    }
  }

  Future<void> _showHabitForm({Map<String, dynamic>? habit}) async {
    final titleController = TextEditingController(text: habit?['title']);
    final descController = TextEditingController(text: habit?['description']);
    final isEditing = habit != null;

    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(isEditing ? 'Edit Habit' : 'New Habit'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleController,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final title = titleController.text.trim();
              final desc = descController.text.trim();
              if (title.isEmpty) return;

              final data = {
                'title': title,
                'description': desc,
              };

              try {
                if (isEditing) {
                  await _apiService.updateHabit(habit!['id'], data);
                } else {
                  await _apiService.createHabit(data);
                }
                if (!mounted) return;
                Navigator.pop(context, true);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Failed to save habit: \$e')),
                );
              }
            },
            child: Text(isEditing ? 'Save' : 'Create'),
          ),
        ],
      ),
    );

    if (result == true) fetchHabits();
  }

  Future<void> _deleteHabit(int id) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Habit'),
        content: const Text('Are you sure you want to delete this habit?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _apiService.deleteHabit(id);
        fetchHabits();
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
          'Habits',
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
        onPressed: () => _showHabitForm(),
        backgroundColor: const Color(0xFFFFD25F),
        child: const Icon(Icons.add, color: Colors.black),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _habits.isEmpty
              ? const Center(child: Text('No habits added yet'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _habits.length,
                  itemBuilder: (context, index) {
                    final habit = _habits[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      elevation: 3,
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(16),
                        title: Text(
                          habit['title'] ?? 'Habit',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        subtitle: Text(
                          habit['description'] ?? '',
                          style: const TextStyle(fontFamily: 'Manrope'),
                        ),
                        trailing: PopupMenuButton<String>(
                          onSelected: (value) {
                            if (value == 'edit') {
                              _showHabitForm(habit: habit);
                            } else if (value == 'delete') {
                              _deleteHabit(habit['id']);
                            }
                          },
                          itemBuilder: (context) => [
                            const PopupMenuItem(value: 'edit', child: Text('Edit')),
                            const PopupMenuItem(value: 'delete', child: Text('Delete')),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}

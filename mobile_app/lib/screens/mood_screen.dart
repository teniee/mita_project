import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/reminder_service.dart';

class MoodScreen extends StatefulWidget {
  const MoodScreen({Key? key}) : super(key: key);

  @override
  State<MoodScreen> createState() => _MoodScreenState();
}

class _MoodScreenState extends State<MoodScreen> {
  final ApiService _apiService = ApiService();
  double _mood = 3;

  @override
  void initState() {
    super.initState();
    ReminderService.scheduleDailyReminder();
  }

  Future<void> _submit() async {
    try {
      await _apiService.logMood(_mood.round());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Mood saved')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed: \$e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Mood'),
        backgroundColor: const Color(0xFFFFF9F0),
        foregroundColor: const Color(0xFF193C57),
        elevation: 0,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Slider(
              value: _mood,
              min: 1,
              max: 5,
              divisions: 4,
              label: _mood.round().toString(),
              onChanged: (v) => setState(() => _mood = v),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _submit,
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }
}

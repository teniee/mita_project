import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class AdviceHistoryScreen extends StatefulWidget {
  const AdviceHistoryScreen({super.key});

  @override
  State<AdviceHistoryScreen> createState() => _AdviceHistoryScreenState();
}

class _AdviceHistoryScreenState extends State<AdviceHistoryScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  List<dynamic> _items = [];

  @override
  void initState() {
    super.initState();
    fetchHistory();
  }

  Future<void> fetchHistory() async {
    try {
      final data = await _apiService.getAdviceHistory();
      setState(() {
        _items = data;
        _loading = false;
      });
    } catch (e) {
      logError('Error loading advice history: $e');
      if (!mounted) return;
      setState(() {
        // Set data to empty instead of showing error
        _items = [];
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Advice History'),
        backgroundColor: const Color(0xFFFFF9F0),
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
        elevation: 0,
      ),
      backgroundColor: const Color(0xFFFFF9F0),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.history, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No advice history yet',
                        style: const TextStyle(
                          fontSize: 18,
                          color: Colors.grey,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Your advice history will appear here',
                        style: const TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (_, i) {
                    final item = _items[i] as Map<String, dynamic>;
                    final date = DateFormat.yMMMd().format(DateTime.parse(item['date'] as String));
                    return ListTile(
                      title: Text(item['text'] as String),
                      subtitle: Text(date),
                    );
                  },
                ),
    );
  }
}

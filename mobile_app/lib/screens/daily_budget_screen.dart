
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'package:intl/intl.dart';

class DailyBudgetScreen extends StatefulWidget {
  const DailyBudgetScreen({Key? key}) : super(key: key);

  @override
  State<DailyBudgetScreen> createState() => _DailyBudgetScreenState();
}

class _DailyBudgetScreenState extends State<DailyBudgetScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  List<dynamic> _budgets = [];

  @override
  void initState() {
    super.initState();
    fetchBudgets();
  }

  Future<void> fetchBudgets() async {
    try {
      final data = await _apiService.getDailyBudgets();
      setState(() {
        _budgets = data;
        _isLoading = false;
      });
    } catch (e) {
      print('Error loading daily budgets: $e');
      if (!mounted) return;
      setState(() {
        // Set data to empty instead of showing error
        _budgets = [];
        _isLoading = false;
      });
    }
  }

  Color getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
        return const Color(0xFF84FAA1);
      case 'warning':
        return const Color(0xFFFFD25F);
      case 'exceeded':
        return const Color(0xFFFF5C5C);
      default:
        return Colors.grey;
    }
  }

  IconData getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'exceeded':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Daily Budget',
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
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _budgets.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.account_balance_wallet, size: 64, color: Colors.grey),
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
                        'Your daily budget tracking will appear here',
                        style: TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _budgets.length,
                  itemBuilder: (context, index) {
                    final budget = _budgets[index];
                    final date = DateFormat('MMMM d, yyyy').format(DateTime.parse(budget['date']));
                    final status = budget['status'] ?? 'unknown';
                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      elevation: 3,
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(16),
                        leading: Icon(getStatusIcon(status), color: getStatusColor(status)),
                        title: Text(
                          date,
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        subtitle: Text(
                          'Spent: \$${budget['spent']} / Limit: \$${budget['limit']}',
                          style: const TextStyle(fontFamily: 'Manrope'),
                        ),
                        trailing: Text(
                          status.toUpperCase(),
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: getStatusColor(status),
                          ),
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}

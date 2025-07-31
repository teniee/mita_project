import 'edit_expense_screen.dart';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({Key? key}) : super(key: key);

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _expenses = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    fetchExpenses();
  }

  Future<void> fetchExpenses() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await _apiService.getExpenses();
      if (!mounted) return;
      setState(() {
        _expenses = data;
        _isLoading = false;
      });
    } catch (e) {
      logError('Error loading transactions: $e');
      if (!mounted) return;
      setState(() {
        // Show demo data if backend is not available
        _expenses = _getDemoTransactions();
        _isLoading = false;
        _error = null;
      });
    }
  }

  List<Map<String, dynamic>> _getDemoTransactions() {
    return [
      {
        'id': '1',
        'action': 'Coffee Shop',
        'category': 'Food & Dining',
        'amount': '4.50',
        'date': DateTime.now().subtract(const Duration(hours: 2)).toIso8601String(),
        'description': 'Morning coffee',
      },
      {
        'id': '2',
        'action': 'Metro Card',
        'category': 'Transportation',
        'amount': '15.00',
        'date': DateTime.now().subtract(const Duration(hours: 5)).toIso8601String(),
        'description': 'Weekly metro pass',
      },
      {
        'id': '3',
        'action': 'Grocery Store',
        'category': 'Food & Dining',
        'amount': '67.85',
        'date': DateTime.now().subtract(const Duration(days: 1)).toIso8601String(),
        'description': 'Weekly groceries',
      },
      {
        'id': '4',
        'action': 'Netflix',
        'category': 'Entertainment',
        'amount': '15.99',
        'date': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
        'description': 'Monthly subscription',
      },
      {
        'id': '5',
        'action': 'Gas Station',
        'category': 'Transportation',
        'amount': '45.20',
        'date': DateTime.now().subtract(const Duration(days: 3)).toIso8601String(),
        'description': 'Fuel',
      },
    ];
  }

  Color _getCategoryColor(String category) {
    switch (category.toLowerCase()) {
      case 'food & dining':
      case 'food':
        return const Color(0xFF4CAF50);
      case 'transportation':
      case 'transport':
        return const Color(0xFF2196F3);
      case 'entertainment':
        return const Color(0xFF9C27B0);
      case 'shopping':
        return const Color(0xFFFF9800);
      case 'health':
      case 'healthcare':
        return const Color(0xFFF44336);
      case 'utilities':
        return const Color(0xFF607D8B);
      case 'education':
        return const Color(0xFF3F51B5);
      default:
        return const Color(0xFF795548);
    }
  }

  IconData _getCategoryIcon(String category) {
    switch (category.toLowerCase()) {
      case 'food & dining':
      case 'food':
        return Icons.restaurant;
      case 'transportation':
      case 'transport':
        return Icons.directions_car;
      case 'entertainment':
        return Icons.movie;
      case 'shopping':
        return Icons.shopping_bag;
      case 'health':
      case 'healthcare':
        return Icons.local_hospital;
      case 'utilities':
        return Icons.flash_on;
      case 'education':
        return Icons.school;
      default:
        return Icons.account_balance_wallet;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Transactions',
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
          : _expenses.isEmpty
                  ? RefreshIndicator(
                      onRefresh: fetchExpenses,
                      child: SingleChildScrollView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        child: SizedBox(
                          height: MediaQuery.of(context).size.height - 200,
                          child: const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.receipt_long,
                                  size: 64,
                                  color: Color(0xFF193C57),
                                ),
                                SizedBox(height: 16),
                                Text(
                                  'No transactions yet',
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontFamily: 'Sora',
                                    fontWeight: FontWeight.w600,
                                    color: Color(0xFF193C57),
                                  ),
                                ),
                                SizedBox(height: 8),
                                Text(
                                  'Pull down to refresh or add your first expense',
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontFamily: 'Manrope',
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: fetchExpenses,
                      child: ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _expenses.length,
                  itemBuilder: (context, index) {
                    final item = _expenses[index];
                    return GestureDetector(
                      onTap: () async {
                        final result = await Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) =>
                                EditExpenseScreen(expense: item),
                          ),
                        );
                        if (result == true) fetchExpenses();
                      },
                      child: Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        elevation: 2,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            children: [
                              Container(
                                width: 48,
                                height: 48,
                                decoration: BoxDecoration(
                                  color: _getCategoryColor(item['category'] ?? ''),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Icon(
                                  _getCategoryIcon(item['category'] ?? ''),
                                  color: Colors.white,
                                  size: 24,
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item['action'] ?? item['description'] ?? 'Transaction',
                                      style: const TextStyle(
                                        fontFamily: 'Sora',
                                        fontWeight: FontWeight.w600,
                                        fontSize: 16,
                                        color: Color(0xFF193C57),
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      item['category'] ?? 'Other',
                                      style: TextStyle(
                                        fontFamily: 'Manrope',
                                        fontSize: 14,
                                        color: Colors.grey[600],
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      DateFormat('MMM d, yyyy • h:mm a').format(
                                        DateTime.parse(item['date']),
                                      ),
                                      style: TextStyle(
                                        fontFamily: 'Manrope',
                                        fontSize: 12,
                                        color: Colors.grey[500],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '-\$${item['amount']}',
                                    style: const TextStyle(
                                      fontFamily: 'Sora',
                                      fontWeight: FontWeight.bold,
                                      fontSize: 16,
                                      color: Color(0xFFFF5C5C),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: _getCategoryColor(item['category'] ?? '').withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      'Expense',
                                      style: TextStyle(
                                        fontFamily: 'Manrope',
                                        fontSize: 10,
                                        fontWeight: FontWeight.w600,
                                        color: _getCategoryColor(item['category'] ?? ''),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                      ),
                    ),
    );
  }
}


import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'package:intl/intl.dart';
import '../services/logging_service.dart';

class InstallmentsScreen extends StatefulWidget {
  const InstallmentsScreen({super.key});

  @override
  State<InstallmentsScreen> createState() => _InstallmentsScreenState();
}

class _InstallmentsScreenState extends State<InstallmentsScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> installments = [];
  bool isLoading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    fetchInstallments();
  }

  Future<void> fetchInstallments() async {
    try {
      final data = await _apiService.getInstallments();
      if (!mounted) return;
      setState(() {
        installments = data;
        isLoading = false;
      });
    } catch (e) {
      logError('Error loading installments: $e');
      if (!mounted) return;
      setState(() {
        // Set data to empty instead of showing error
        installments = [];
        isLoading = false;
        error = null;
      });
    }
  }

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'active':
        return const Color(0xFFFFD25F);
      case 'completed':
        return const Color(0xFF84FAA1);
      case 'overdue':
        return const Color(0xFFFF5C5C);
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Installments',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
          ),
        ),
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        centerTitle: true,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : installments.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.payment, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No installments found',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.grey,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Your installment tracking will appear here',
                        style: TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: installments.length,
                  itemBuilder: (context, index) {
                    final item = installments[index];
                    final progress = (item['paid_amount'] / item['total_amount']).clamp(0.0, 1.0);

                    return Container(
                      margin: const EdgeInsets.only(bottom: 20),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.05),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item['title'],
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              fontFamily: 'Sora',
                            ),
                          ),
                          const SizedBox(height: 8),
                          LinearProgressIndicator(
                            value: progress,
                            backgroundColor: const Color(0xFFE0E0E0),
                            color: _statusColor(item['status']),
                            minHeight: 8,
                          ),
                          const SizedBox(height: 8),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '\$${item['paid_amount']} / \$${item['total_amount']}',
                                style: const TextStyle(fontFamily: 'Manrope'),
                              ),
                              Text(
                                'Due: ${DateFormat.yMMMd().format(DateTime.parse(item['due_date']))}',
                                style: const TextStyle(
                                  fontFamily: 'Manrope',
                                  fontStyle: FontStyle.italic,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Status: ${item['status']}',
                            style: TextStyle(
                              fontFamily: 'Manrope',
                              color: _statusColor(item['status']),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
    );
  }
}


import 'package:flutter/material.dart';
import '../services/api_service.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({Key? key}) : super(key: key);

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final ApiService _apiService = ApiService();
  Map<String, dynamic>? dashboardData;
  bool isLoading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    fetchDashboardData();
  }

  Future<void> fetchDashboardData() async {
    try {
      final data = await _apiService.getDashboard();
      if (!mounted) return;
      setState(() {
        dashboardData = data;
        isLoading = false;
      });
    } catch (e) {
      setState(() {
        error = 'Failed to load data: \$e';
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: isLoading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? Center(child: Text(error!))
                : Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Hello!',
                          style: TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                            fontSize: 24,
                            color: Color(0xFF193C57),
                          ),
                        ),
                        const SizedBox(height: 20),
                        _buildBalanceCard(),
                        const SizedBox(height: 20),
                        _buildBudgetTargets(),
                        const SizedBox(height: 20),
                        _buildMiniCalendar(),
                        const SizedBox(height: 20),
                        _buildRecentTransactions(),
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _buildBalanceCard() {
    final balance = dashboardData?['balance'] ?? 0;
    final spent = dashboardData?['spent'] ?? 0;

    return Card(
      color: const Color(0xFFFFD25F),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Current Balance', style: TextStyle(fontFamily: 'Manrope', fontSize: 16)),
            const SizedBox(height: 6),
            Text(
              '\$\$balance',
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text('Spent: \$\$spent', style: const TextStyle(fontFamily: 'Manrope')),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetTargets() {
    final targets = dashboardData?['daily_targets'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Today's Budget Targets',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 12),
        ...targets.map<Widget>((target) {
          return Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: ListTile(
              title: Text(target['category'], style: const TextStyle(fontFamily: 'Manrope')),
              trailing: Text('\$${target['limit']}', style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          );
        }).toList()
      ],
    );
  }

  Widget _buildMiniCalendar() {
    final week = dashboardData?['week'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'This Week',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: week.map<Widget>((day) {
            Color color;
            switch (day['status']) {
              case 'over': color = const Color(0xFFFF5C5C); break;
              case 'warning': color = const Color(0xFFFFD25F); break;
              default: color = const Color(0xFF84FAA1);
            }

            return Container(
              width: 42,
              height: 50,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Text(day['day'], style: const TextStyle(fontWeight: FontWeight.bold)),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildRecentTransactions() {
    final transactions = dashboardData?['transactions'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Recent Transactions',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 12),
        ...transactions.map<Widget>((tx) {
          return ListTile(
            leading: const Icon(Icons.attach_money),
            title: Text(tx['category']),
            subtitle: Text(tx['date']),
            trailing: Text('-\$${tx['amount']}', style: const TextStyle(fontWeight: FontWeight.bold)),
          );
        }).toList()
      ],
    );
  }
}

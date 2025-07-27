
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'advice_history_screen.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({Key? key}) : super(key: key);

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  final ApiService _apiService = ApiService();
  Map<String, dynamic>? dashboardData;
  Map<String, dynamic>? latestAdvice;
  bool isLoading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    fetchDashboardData();
  }

  Future<void> fetchDashboardData() async {
    try {
      // Try to fetch dashboard data
      Map<String, dynamic>? data;
      Map<String, dynamic>? advice;
      
      try {
        data = await _apiService.getDashboard();
      } catch (e) {
        print('Dashboard endpoint not available: $e');
        // Provide default dashboard data for users without onboarding
        data = {
          'total_budget': 0,
          'spent_today': 0,
          'remaining_budget': 0,
          'message': 'Complete onboarding to see your dashboard'
        };
      }
      
      try {
        advice = await _apiService.getLatestAdvice();
      } catch (e) {
        print('Advice endpoint not available: $e');
        // Provide default advice for new users
        advice = {
          'title': 'Welcome to MITA!',
          'content': 'Complete your onboarding to get personalized financial advice.'
        };
      }
      
      if (!mounted) return;
      setState(() {
        dashboardData = data;
        latestAdvice = advice;
        isLoading = false;
      });
    } catch (e) {
      print('General error in fetchDashboardData: $e');
      setState(() {
        error = 'Unable to load data. Please check your connection.';
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
                : LayoutBuilder(
                    builder: (context, constraints) {
                      final isWide = constraints.maxWidth > 600;
                      final leftColumn = <Widget>[
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
                      ];
                      final rightColumn = <Widget>[
                        _buildMiniCalendar(),
                        const SizedBox(height: 20),
                        _buildInsightsCard(),
                        const SizedBox(height: 20),
                        _buildRecentTransactions(),
                      ];
                      return Padding(
                        padding: const EdgeInsets.all(20),
                        child: isWide
                            ? Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: leftColumn,
                                    ),
                                  ),
                                  const SizedBox(width: 20),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: rightColumn,
                                    ),
                                  ),
                                ],
                              )
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [...leftColumn, const SizedBox(height: 20), ...rightColumn],
                              ),
                      );
                    },
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
              '\$${balance}',
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text('Spent: \$${spent}', style: const TextStyle(fontFamily: 'Manrope')),
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
          "Today's Budget Targets",
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

  Widget _buildInsightsCard() {
    final text = latestAdvice?['text'] ?? 'No advice yet';
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const AdviceHistoryScreen()),
        );
      },
      child: Card(
        color: const Color(0xFFE8F0FE),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            text,
            style: const TextStyle(fontFamily: 'Manrope'),
          ),
        ),
      ),
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
            title: Text(tx['action']),
            subtitle: Text(tx['date']),
            trailing: Text('-\$${tx['amount']}', style: const TextStyle(fontWeight: FontWeight.bold)),
          );
        }).toList()
      ],
    );
  }
}

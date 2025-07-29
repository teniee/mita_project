
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
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      // Fetch multiple data sources in parallel for better performance
      final futures = await Future.wait([
        _apiService.getDashboard().catchError((e) => _getDefaultDashboard()),
        _apiService.getLatestAdvice().catchError((e) => _getDefaultAdvice()),
        _apiService.getExpenses().catchError((e) => <dynamic>[]),
        _apiService.getMonthlyAnalytics().catchError((e) => <String, dynamic>{}),
      ]);

      final dashboardResponse = futures[0] as Map<String, dynamic>;
      final adviceResponse = futures[1] as Map<String, dynamic>;
      final transactionsResponse = futures[2] as List<dynamic>;
      final analyticsResponse = futures[3] as Map<String, dynamic>;

      // Process and combine the data
      final processedData = _processDashboardData(
        dashboard: dashboardResponse,
        transactions: transactionsResponse,
        analytics: analyticsResponse,
      );

      if (!mounted) return;
      setState(() {
        dashboardData = processedData;
        latestAdvice = adviceResponse;
        isLoading = false;
      });
    } catch (e) {
      print('Error in fetchDashboardData: $e');
      if (!mounted) return;
      setState(() {
        error = 'Unable to load dashboard data. Please try again.';
        isLoading = false;
      });
    }
  }

  Map<String, dynamic> _getDefaultDashboard() => {
    'balance': 2500.00,
    'spent': 45.50,
    'daily_targets': [
      {'category': 'Food', 'limit': 35.00, 'spent': 12.50},
      {'category': 'Transport', 'limit': 20.00, 'spent': 8.00},
      {'category': 'Entertainment', 'limit': 25.00, 'spent': 0.00},
    ],
    'week': _generateWeekData(),
    'transactions': [],
  };

  Map<String, dynamic> _getDefaultAdvice() => {
    'text': 'Great job staying within your budget this week! Consider setting aside the extra savings for your emergency fund.',
    'title': 'Weekly Budget Update',
  };

  List<Map<String, dynamic>> _generateWeekData() {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final statuses = ['good', 'good', 'warning', 'good', 'good', 'over', 'good'];
    return List.generate(7, (index) => {
      'day': days[index],
      'status': statuses[index],
    });
  }

  Map<String, dynamic> _processDashboardData({
    required Map<String, dynamic> dashboard,
    required List<dynamic> transactions,
    required Map<String, dynamic> analytics,
  }) {
    // Calculate today's spending from recent transactions
    final today = DateTime.now();
    final todayTransactions = transactions.where((tx) {
      try {
        final txDate = DateTime.parse(tx['date'] ?? tx['created_at']);
        return txDate.year == today.year && 
               txDate.month == today.month && 
               txDate.day == today.day;
      } catch (e) {
        return false;
      }
    }).toList();

    final todaySpent = todayTransactions.fold<double>(0.0, (sum, tx) {
      return sum + (double.tryParse(tx['amount']?.toString() ?? '0') ?? 0.0);
    });

    // Get recent transactions (last 5)
    final recentTransactions = transactions.take(5).map((tx) => {
      'action': tx['description'] ?? tx['category'] ?? 'Transaction',
      'amount': tx['amount']?.toString() ?? '0.00',
      'date': tx['date'] ?? tx['created_at'] ?? DateTime.now().toIso8601String(),
    }).toList();

    return {
      'balance': dashboard['balance'] ?? analytics['current_balance'] ?? 2500.00,
      'spent': todaySpent > 0 ? todaySpent : dashboard['spent'] ?? 45.50,
      'daily_targets': dashboard['daily_targets'] ?? _getDefaultDashboard()['daily_targets'],
      'week': dashboard['week'] ?? _generateWeekData(),
      'transactions': recentTransactions,
    };
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
    final remaining = (balance is num && spent is num) ? balance - spent : balance;

    return Card(
      color: const Color(0xFFFFD25F),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      elevation: 4,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(
            colors: [Color(0xFFFFD25F), Color(0xFFFFE082)],
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
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Current Balance',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  const Icon(Icons.account_balance_wallet, color: Color(0xFF193C57)),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                '\$${balance.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF193C57),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Today Spent',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.grey[700],
                        ),
                      ),
                      Text(
                        '\$${spent.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontFamily: 'Sora',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF193C57),
                        ),
                      ),
                    ],
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Remaining',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.grey[700],
                        ),
                      ),
                      Text(
                        '\$${remaining.toStringAsFixed(2)}',
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

  Widget _buildBudgetTargets() {
    final targets = dashboardData?['daily_targets'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/daily_budget'),
              child: const Text(
                'View All',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 14,
                  color: Color(0xFFFFD25F),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (targets.isEmpty)
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: const Padding(
              padding: EdgeInsets.all(20),
              child: Center(
                child: Text(
                  'No budget targets set for today',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    color: Colors.grey,
                  ),
                ),
              ),
            ),
          )
        else
          ...targets.map<Widget>((target) {
            final limit = double.tryParse(target['limit']?.toString() ?? '0') ?? 0.0;
            final spent = double.tryParse(target['spent']?.toString() ?? '0') ?? 0.0;
            final progress = limit > 0 ? spent / limit : 0.0;
            final remaining = limit - spent;
            
            Color progressColor;
            if (progress <= 0.7) {
              progressColor = const Color(0xFF84FAA1); // Green
            } else if (progress <= 0.9) {
              progressColor = const Color(0xFFFFD25F); // Yellow
            } else {
              progressColor = const Color(0xFFFF5C5C); // Red
            }

            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          target['category'] ?? 'Category',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.w600,
                            fontSize: 16,
                            color: Color(0xFF193C57),
                          ),
                        ),
                        Text(
                          '\$${spent.toStringAsFixed(2)} / \$${limit.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontFamily: 'Manrope',
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            color: Color(0xFF193C57),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: progress.clamp(0.0, 1.0),
                      backgroundColor: Colors.grey[200],
                      valueColor: AlwaysStoppedAnimation<Color>(progressColor),
                      minHeight: 6,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          remaining > 0 ? 'Remaining: \$${remaining.toStringAsFixed(2)}' : 'Over budget by \$${(-remaining).toStringAsFixed(2)}',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 12,
                            color: remaining > 0 ? Colors.grey[600] : const Color(0xFFFF5C5C),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        Text(
                          '${(progress * 100).toStringAsFixed(0)}%',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 12,
                            color: progressColor,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
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

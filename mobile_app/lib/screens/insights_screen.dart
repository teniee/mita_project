
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import '../services/api_service.dart';

class InsightsScreen extends StatefulWidget {
  const InsightsScreen({Key? key}) : super(key: key);

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  double totalSpending = 0;
  Map<String, double> categoryTotals = {};
  List<Map<String, dynamic>> dailyTotals = [];
  List<Map<String, dynamic>> monthlyTrend = [];

  @override
  void initState() {
    super.initState();
    fetchInsights();
  }

  Future<void> fetchInsights() async {
    try {
      final analytics = await _apiService.getMonthlyAnalytics();
      final trend = await _apiService.getMonthlyTrend();
      final expenses = await _apiService.getExpenses();
      final now = DateTime.now();
      final monthExpenses = expenses.where((e) {
        final date = DateTime.parse(e['date']);
        return date.month == now.month && date.year == now.year;
      });

      double sum = 0;
      final Map<String, double> catSums =
          Map<String, double>.from(analytics['categories'] as Map);
      final Map<String, double> daily = {};

      for (final e in monthExpenses) {
        sum += e['amount'];
        final day = DateFormat('yyyy-MM-dd').format(DateTime.parse(e['date']));
        daily[day] = (daily[day] ?? 0) + e['amount'];
      }

      setState(() {
        totalSpending = sum;
        categoryTotals = catSums;
        dailyTotals = daily.entries
            .map((e) => {'date': e.key, 'amount': e.value})
            .toList()
          ..sort((a, b) => (a['date'] as String).compareTo(b['date'] as String));
        monthlyTrend = trend
            .map((e) => {
                  'label': e['month'] ?? e['day'],
                  'amount': e['total'] as num? ?? 0,
                })
            .toList();
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading insights: \$e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Insights',
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
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth > 600;
          Widget content;
          if (_isLoading) {
            content = const Center(child: CircularProgressIndicator());
          } else {
            content = ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  'Total Spending This Month: \$${totalSpending.toStringAsFixed(2)}',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                  ),
                ),
                const SizedBox(height: 20),
                if (categoryTotals.isNotEmpty) ...[
                  const Text(
                    'Spending by Category',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  SizedBox(
                    height: 200,
                    child: PieChart(
                      PieChartData(
                        sections: categoryTotals.entries.map((e) {
                          final value = e.value;
                          return PieChartSectionData(
                            title: '\$${value.toStringAsFixed(0)}',
                            value: value,
                            titleStyle: const TextStyle(
                              fontFamily: 'Manrope',
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                            radius: 60,
                          );
                        }).toList(),
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 30),
                if (dailyTotals.isNotEmpty) ...[
                  const Text(
                    'Spending by Day',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 200,
                    child: BarChart(
                      BarChartData(
                        borderData: FlBorderData(show: false),
                        titlesData: FlTitlesData(
                          bottomTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              reservedSize: 32,
                              getTitlesWidget: (value, meta) {
                                final index = value.toInt();
                                if (index < 0 || index >= dailyTotals.length) return Container();
                                final label = DateFormat('MM/dd').format(DateTime.parse(dailyTotals[index]['date']));
                                return Text(label, style: const TextStyle(fontSize: 10));
                              },
                              interval: 1,
                            ),
                          ),
                          leftTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                          rightTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                          topTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                        ),
                        barGroups: List.generate(dailyTotals.length, (i) {
                          return BarChartGroupData(
                            x: i,
                            barRods: [
                              BarChartRodData(
                                toY: dailyTotals[i]['amount'],
                                width: 14,
                                borderRadius: BorderRadius.circular(6),
                                color: const Color(0xFF193C57),
                              ),
                            ],
                          );
                        }),
                      ),
                    ),
                  ),
                ],
                if (monthlyTrend.isNotEmpty) ...[
                  const SizedBox(height: 30),
                  const Text(
                    'Monthly Trend',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 200,
                    child: LineChart(
                      LineChartData(
                        borderData: FlBorderData(show: false),
                        titlesData: FlTitlesData(
                          bottomTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              reservedSize: 32,
                              interval: 1,
                              getTitlesWidget: (value, meta) {
                                final index = value.toInt();
                                if (index < 0 || index >= monthlyTrend.length) {
                                  return Container();
                                }
                                return Text(
                                  monthlyTrend[index]['label'],
                                  style: const TextStyle(fontSize: 10),
                                );
                              },
                            ),
                          ),
                          leftTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                          rightTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                          topTitles: AxisTitles(
                            sideTitles: SideTitles(showTitles: false),
                          ),
                        ),
                        lineBarsData: [
                          LineChartBarData(
                            color: const Color(0xFF193C57),
                            spots: List.generate(
                              monthlyTrend.length,
                              (i) => FlSpot(
                                i.toDouble(),
                                (monthlyTrend[i]['amount'] as num).toDouble(),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ]
              ],
            );
          }

          return Padding(
            padding: const EdgeInsets.all(20),
            child: isWide
                ? Row(
                    children: [
                      Expanded(child: content),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Center(
                          child: Icon(Icons.insights,
                              size: 120, color: Colors.grey),
                        ),
                      ),
                    ],
                  )
                : content,
          );
        },
      ),
    );
  }
}


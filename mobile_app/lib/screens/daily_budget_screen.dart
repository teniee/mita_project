
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'package:intl/intl.dart';
import 'dart:async';
import '../services/logging_service.dart';

class DailyBudgetScreen extends StatefulWidget {
  const DailyBudgetScreen({super.key});

  @override
  State<DailyBudgetScreen> createState() => _DailyBudgetScreenState();
}

class _DailyBudgetScreenState extends State<DailyBudgetScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  bool _isRedistributing = false;
  List<dynamic> _budgets = [];
  Map<String, dynamic> _liveBudgetStatus = {};
  Map<String, dynamic> _budgetSuggestions = {};
  List<dynamic> _redistributionHistory = [];
  String _budgetMode = 'default';
  Timer? _liveUpdateTimer;

  @override
  void initState() {
    super.initState();
    _initializeData();
    _startLiveUpdates();
  }

  @override
  void dispose() {
    _liveUpdateTimer?.cancel();
    super.dispose();
  }

  Future<void> _initializeData() async {
    await fetchBudgets();
    await _fetchLiveBudgetStatus();
    await _fetchBudgetSuggestions();
    await _fetchBudgetMode();
    await _fetchRedistributionHistory();
  }

  void _startLiveUpdates() {
    // Temporarily disabled live updates to prevent recurring server errors
    print('Daily budget live updates disabled due to backend server errors');
    
    // TODO: Re-enable when backend is stable:
    // _liveUpdateTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
    //   if (mounted) {
    //     _fetchLiveBudgetStatus();
    //   }
    // });
  }

  Future<void> fetchBudgets() async {
    try {
      final data = await _apiService.getDailyBudgets();
      setState(() {
        _budgets = data;
        _isLoading = false;
      });
    } catch (e) {
      logError('Error loading daily budgets: $e');
      if (!mounted) return;
      setState(() {
        // Set data to empty instead of showing error
        _budgets = [];
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchLiveBudgetStatus() async {
    try {
      final status = await _apiService.getLiveBudgetStatus();
      if (mounted) {
        setState(() {
          _liveBudgetStatus = status;
        });
      }
    } catch (e) {
      logError('Error loading live budget status: $e');
    }
  }

  Future<void> _fetchBudgetSuggestions() async {
    try {
      final suggestions = await _apiService.getBudgetSuggestions();
      if (mounted) {
        setState(() {
          _budgetSuggestions = suggestions;
        });
      }
    } catch (e) {
      logError('Error loading budget suggestions: $e');
    }
  }

  Future<void> _fetchBudgetMode() async {
    try {
      final mode = await _apiService.getBudgetMode();
      if (mounted) {
        setState(() {
          _budgetMode = mode;
        });
      }
    } catch (e) {
      logError('Error loading budget mode: $e');
    }
  }

  Future<void> _fetchRedistributionHistory() async {
    try {
      final history = await _apiService.getBudgetRedistributionHistory();
      if (mounted) {
        setState(() {
          _redistributionHistory = history;
        });
      }
    } catch (e) {
      logError('Error loading redistribution history: $e');
    }
  }

  Future<void> _triggerBudgetRedistribution() async {
    setState(() {
      _isRedistributing = true;
    });

    try {
      // Get current calendar data for redistribution
      final calendarData = await _apiService.getCalendar();
      
      // Convert to the format expected by redistribution algorithm
      Map<String, Map<String, dynamic>> calendarDict = {};
      for (var day in calendarData) {
        final dayNum = day['day'].toString();
        calendarDict[dayNum] = {
          'total': (day['spent'] ?? 0).toDouble(),
          'limit': (day['limit'] ?? 0).toDouble(),
        };
      }

      // Trigger redistribution
      final result = await _apiService.redistributeCalendarBudget(calendarDict);
      
      // Refresh all data after redistribution
      await _initializeData();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Budget successfully redistributed!'),
            duration: Duration(seconds: 3),
            backgroundColor: Color(0xFF84FAA1),
          ),
        );
      }
    } catch (e) {
      logError('Error during budget redistribution: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Failed to redistribute budget. Please try again.'),
            duration: Duration(seconds: 3),
            backgroundColor: Color(0xFFFF5C5C),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRedistributing = false;
        });
      }
    }
  }

  Future<void> _triggerAutoBudgetAdaptation() async {
    try {
      await _apiService.triggerBudgetAdaptation();
      await _initializeData();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Budget adapted based on your spending patterns!'),
            duration: Duration(seconds: 3),
            backgroundColor: Color(0xFF84FAA1),
          ),
        );
      }
    } catch (e) {
      logError('Error during auto adaptation: $e');
    }
  }

  Color getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return const Color(0xFF84FAA1);
      case 'warning':
        return const Color(0xFFFFD25F);
      case 'exceeded':
      case 'over':
        return const Color(0xFFFF5C5C);
      default:
        return Colors.grey;
    }
  }

  IconData getStatusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'normal':
      case 'good':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'exceeded':
      case 'over':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  String _getBudgetModeDisplayName(String mode) {
    switch (mode) {
      case 'strict':
        return 'Strict Budget';
      case 'flexible':
        return 'Flexible Budget';
      case 'behavioral':
        return 'Behavioral Adaptive';
      case 'goal':
        return 'Goal-Oriented';
      default:
        return 'Standard Budget';
    }
  }

  Color _getBudgetModeColor(String mode) {
    switch (mode) {
      case 'strict':
        return const Color(0xFFFF5C5C);
      case 'flexible':
        return const Color(0xFF84FAA1);
      case 'behavioral':
        return const Color(0xFF6B73FF);
      case 'goal':
        return const Color(0xFFFFD25F);
      default:
        return Colors.grey;
    }
  }

  Widget _buildLiveBudgetCard() {
    if (_liveBudgetStatus.isEmpty) return const SizedBox.shrink();
    
    final totalBudget = _liveBudgetStatus['total_budget']?.toDouble() ?? 0.0;
    final totalSpent = _liveBudgetStatus['total_spent']?.toDouble() ?? 0.0;
    final remaining = totalBudget - totalSpent;
    final percentage = totalBudget > 0 ? (totalSpent / totalBudget) : 0.0;
    
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 4,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            colors: percentage > 0.8 
              ? [const Color(0xFFFF5C5C), const Color(0xFFFF8A65)]
              : percentage > 0.6 
                ? [const Color(0xFFFFD25F), const Color(0xFFFFE082)]
                : [const Color(0xFF84FAA1), const Color(0xFFA8E6A0)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Live Budget Status',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    fontFamily: 'Sora',
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _getBudgetModeDisplayName(_budgetMode),
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w500,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Total Budget',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    Text(
                      '\$${totalBudget.toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Spent',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    Text(
                      '\$${totalSpent.toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Remaining',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    Text(
                      '\$${remaining.toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: percentage.clamp(0.0, 1.0),
                backgroundColor: Colors.white.withValues(alpha: 0.3),
                valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                minHeight: 8,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${(percentage * 100).toStringAsFixed(1)}% of budget used',
              style: const TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Smart Budget Actions',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                fontFamily: 'Sora',
                color: Color(0xFF193C57),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isRedistributing ? null : _triggerBudgetRedistribution,
                    icon: _isRedistributing 
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.balance, size: 18),
                    label: Text(_isRedistributing ? 'Redistributing...' : 'Redistribute'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF6B73FF),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _triggerAutoBudgetAdaptation,
                    icon: const Icon(Icons.auto_fix_high, size: 18),
                    label: const Text('Auto Adapt'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF84FAA1),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionsCard() {
    if (_budgetSuggestions.isEmpty) return const SizedBox.shrink();

    final suggestions = _budgetSuggestions['suggestions'] as List<dynamic>? ?? [];
    if (suggestions.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.lightbulb, color: Color(0xFFFFD25F)),
                const SizedBox(width: 8),
                const Text(
                  'AI Budget Suggestions',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'Sora',
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...suggestions.take(3).map<Widget>((suggestion) => 
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF9F0),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFFD25F), width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.arrow_forward, size: 16, color: Color(0xFFFFD25F)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        suggestion['message'] ?? suggestion.toString(),
                        style: const TextStyle(fontSize: 14, color: Color(0xFF193C57)),
                      ),
                    ),
                  ],
                ),
              ),
            ).toList(),
          ],
        ),
      ),
    );
  }

  Widget _buildRedistributionHistory() {
    if (_redistributionHistory.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.history, color: Color(0xFF6B73FF)),
                const SizedBox(width: 8),
                const Text(
                  'Recent Redistribution',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'Sora',
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ..._redistributionHistory.take(3).map<Widget>((transfer) =>
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0F4FF),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Day ${transfer['from']} → Day ${transfer['to']}',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                    ),
                    Text(
                      '\$${(transfer['amount'] ?? 0).toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF6B73FF),
                      ),
                    ),
                  ],
                ),
              ),
            ).toList(),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Smart Daily Budget',
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
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              // Navigate to budget settings/mode selection
              Navigator.pushNamed(context, '/budget_settings');
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _initializeData,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    _buildLiveBudgetCard(),
                    _buildActionButtons(),
                    _buildSuggestionsCard(),
                    _buildRedistributionHistory(),
                    
                    // Original budget list
                    if (_budgets.isEmpty)
                      Card(
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        elevation: 3,
                        child: const Padding(
                          padding: EdgeInsets.all(32),
                          child: Column(
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
                                'Your intelligent budget tracking will appear here',
                                style: TextStyle(color: Colors.grey),
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        ),
                      )
                    else
                      ...(_budgets.map<Widget>((budget) {
                        final date = DateFormat('MMMM d, yyyy').format(DateTime.parse(budget['date']));
                        final status = budget['status'] ?? 'unknown';
                        return Card(
                          margin: const EdgeInsets.only(bottom: 16),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                          elevation: 3,
                          child: ListTile(
                            contentPadding: const EdgeInsets.all(16),
                            leading: Icon(getStatusIcon(status), color: getStatusColor(status), size: 32),
                            title: Text(
                              date,
                              style: const TextStyle(
                                fontFamily: 'Sora',
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const SizedBox(height: 4),
                                Text(
                                  'Spent: \$${budget['spent']} / Limit: \$${budget['limit']}',
                                  style: const TextStyle(fontFamily: 'Manrope'),
                                ),
                                const SizedBox(height: 4),
                                LinearProgressIndicator(
                                  value: ((budget['spent'] ?? 0) / (budget['limit'] ?? 1)).clamp(0.0, 1.0),
                                  backgroundColor: Colors.grey[300],
                                  valueColor: AlwaysStoppedAnimation<Color>(getStatusColor(status)),
                                ),
                              ],
                            ),
                            trailing: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: getStatusColor(status).withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                status.toUpperCase(),
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: getStatusColor(status),
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ),
                        );
                      }).toList()),
                  ],
                ),
              ),
            ),
    );
  }
}

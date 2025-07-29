import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({Key? key}) : super(key: key);

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> calendarData = [];
  bool isLoading = true;
  String? error;
  DateTime currentMonth = DateTime.now();

  @override
  void initState() {
    super.initState();
    fetchCalendarData();
  }

  Future<void> fetchCalendarData() async {
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      final data = await _apiService.getCalendar();
      if (!mounted) return;
      setState(() {
        calendarData = data;
        isLoading = false;
      });
    } catch (e) {
      print('Error loading calendar: $e');
      if (!mounted) return;
      setState(() {
        calendarData = [];
        isLoading = false;
        error = e.toString();
      });
    }
  }

  Color _getDayColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.error;
      case 'warning':
        return colorScheme.tertiary;
      case 'good':
      default:
        return colorScheme.primary;
    }
  }

  Color _getOnDayColor(String status) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (status.toLowerCase()) {
      case 'over':
        return colorScheme.onError;
      case 'warning':
        return colorScheme.onTertiary;
      case 'good':
      default:
        return colorScheme.onPrimary;
    }
  }

  String _getMonthName(int month) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[month - 1];
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: Text(
          '${_getMonthName(currentMonth.month)} ${currentMonth.year}',
          style: textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurface,
          ),
        ),
        backgroundColor: colorScheme.surface,
        elevation: 0,
        centerTitle: true,
        iconTheme: IconThemeData(color: colorScheme.onSurface),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: fetchCalendarData,
            tooltip: 'Refresh Calendar',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: fetchCalendarData,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Month header with spending summary
                Card(
                  elevation: 2,
                  margin: const EdgeInsets.only(bottom: 24),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Monthly Overview',
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _buildStatusIndicator('Good', colorScheme.primary, colorScheme.onPrimary),
                            _buildStatusIndicator('Warning', colorScheme.tertiary, colorScheme.onTertiary),
                            _buildStatusIndicator('Over Budget', colorScheme.error, colorScheme.onError),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),

                // Calendar grid
                if (isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(32.0),
                      child: CircularProgressIndicator(),
                    ),
                  )
                else if (error != null)
                  Card(
                    elevation: 1,
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          Icon(
                            Icons.error_outline_rounded,
                            size: 48,
                            color: colorScheme.error,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Unable to load calendar',
                            style: textTheme.titleMedium?.copyWith(
                              color: colorScheme.onSurface,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Please check your connection and try again',
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withValues(alpha: 0.7),
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          FilledButton.icon(
                            onPressed: fetchCalendarData,
                            icon: const Icon(Icons.refresh_rounded),
                            label: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (calendarData.isEmpty)
                  Card(
                    elevation: 1,
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          Icon(
                            Icons.calendar_month_outlined,
                            size: 48,
                            color: colorScheme.primary,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'No calendar data available',
                            style: textTheme.titleMedium?.copyWith(
                              color: colorScheme.onSurface,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Complete your budget setup to see your spending calendar',
                            style: textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withValues(alpha: 0.7),
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: calendarData.length,
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 7, // 7 days in a week
                      crossAxisSpacing: 8,
                      mainAxisSpacing: 8,
                      childAspectRatio: 0.8,
                    ),
                    itemBuilder: (context, index) {
                      final day = calendarData[index];
                      final dayNumber = day['day'] as int;
                      final status = day['status'] as String;
                      final limit = day['limit'] as int;
                      final spent = day['spent'] as int? ?? 0;

                      return Material(
                        elevation: 2,
                        borderRadius: BorderRadius.circular(12),
                        color: _getDayColor(status),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: () => Navigator.pushNamed(
                            context, 
                            '/daily_budget',
                            arguments: {'day': dayNumber, 'month': currentMonth.month, 'year': currentMonth.year},
                          ),
                          child: Container(
                            padding: const EdgeInsets.all(8.0),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  dayNumber.toString(),
                                  style: textTheme.titleLarge?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: _getOnDayColor(status),
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '\$$limit',
                                  style: textTheme.bodySmall?.copyWith(
                                    color: _getOnDayColor(status).withValues(alpha: 0.8),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                if (spent > 0) ...[
                                  const SizedBox(height: 2),
                                  Text(
                                    'Spent: \$$spent',
                                    style: textTheme.bodySmall?.copyWith(
                                      color: _getOnDayColor(status).withValues(alpha: 0.7),
                                      fontSize: 10,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.pushNamed(context, '/daily_budget'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add Expense'),
        tooltip: 'Add new expense',
      ),
    );
  }

  Widget _buildStatusIndicator(String label, Color color, Color onColor) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ],
    );
  }
}

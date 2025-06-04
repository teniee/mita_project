import 'daily_budget_screen.dart';

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

  @override
  void initState() {
    super.initState();
    fetchCalendarData();
  }

  Future<void> fetchCalendarData() async {
    try {
      final data = await _apiService.getCalendar();
      if (!mounted) return;
      setState(() {
        calendarData = data;
        isLoading = false;
      });
    } catch (e) {
      setState(() {
        error = 'Failed to load calendar: \$e';
        isLoading = false;
      });
    }
  }

  void _showDayDetails(Map<String, dynamic> day) {
    final spent = day['spent'];
    final limit = day['limit'];
    final status = day['status'];

    showModalBottomSheet(
      context: context,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      backgroundColor: Colors.white,
      builder: (_) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Day: ${day['date']}',
              style: const TextStyle(fontFamily: 'Sora', fontWeight: FontWeight.bold, fontSize: 20),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Spent', style: TextStyle(fontFamily: 'Manrope')),
                Text('\$${spent}', style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Daily Limit', style: TextStyle(fontFamily: 'Manrope')),
                Text('\$${limit}', style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const Divider(height: 24),
            const Text(
              'By Categories',
              style: TextStyle(fontFamily: 'Sora', fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 10),
            ...day['categories'].map<Widget>((cat) {
              double catSpent = cat['spent'] ?? 0;
              double catLimit = cat['limit'] ?? 0;
              Color color = catSpent > catLimit
                  ? const Color(0xFFFF5C5C)
                  : (catSpent > 0.8 * catLimit
                      ? const Color(0xFFFFD25F)
                      : const Color(0xFF84FAA1));

              return Container(
                margin: const EdgeInsets.symmetric(vertical: 4),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(cat['category'], style: const TextStyle(fontFamily: 'Manrope')),
                    Text(
                      '\$${cat['spent']} / \$${cat['limit']}',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              );
            }).toList()
          ],
        ),
      ),
    );
  }

  Color _getDayColor(String status) {
    switch (status) {
      case 'over':
        return const Color(0xFFFF5C5C);
      case 'warning':
        return const Color(0xFFFFD25F);
      default:
        return const Color(0xFF84FAA1);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Calendar',
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
          : error != null
              ? Center(child: Text(error!))
              : Padding(
                  padding: const EdgeInsets.all(20),
                  child: GridView.builder(
                    itemCount: calendarData.length,
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 4,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                      childAspectRatio: 1,
                    ),
                    itemBuilder: (context, index) {
                      final day = calendarData[index];
                      return GestureDetector(
                        onTap: () => Navigator.pushNamed(context, '/daily_budget'),
                        child: Container(
                          decoration: BoxDecoration(
                            color: _getDayColor(day['status']),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          alignment: Alignment.center,
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                day['day'].toString(),
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 18,
                                  color: Colors.white,
                                ),
                              ),
                              Text(
                                '\$${day['limit']}',
                                style: const TextStyle(color: Colors.white70),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}

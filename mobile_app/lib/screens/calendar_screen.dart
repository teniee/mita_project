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
      print('Error loading calendar: $e');
      // For missing endpoints, show empty state instead of error
      if (!mounted) return;
      setState(() {
        calendarData = []; // Show empty calendar instead of error
        isLoading = false;
        error = null; // Don't show error message
      });
    }
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

import 'habits_screen.dart';

import 'package:flutter/material.dart';
import 'home_screen.dart';
import 'calendar_screen.dart';
import 'goals_screen.dart';
import 'insights_screen.dart';

class BottomNavigation extends StatefulWidget {
  const BottomNavigation({Key? key}) : super(key: key);

  @override
  State<BottomNavigation> createState() => _BottomNavigationState();
}

class _BottomNavigationState extends State<BottomNavigation> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    HomeScreen(),
    CalendarScreen(),
    GoalsScreen(),
    InsightsScreen(),
    HabitsScreen(),
  ];

  final List<BottomNavigationBarItem> _items = const [
    BottomNavigationBarItem(
      icon: Icon(Icons.home),
      label: 'Home',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.calendar_today),
      label: 'Calendar',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.flag),
      label: 'Goals',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.bar_chart),
      label: 'Insights',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.check_circle),
      label: 'Habits',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        selectedItemColor: const Color(0xFF193C57),
        unselectedItemColor: Colors.grey,
        backgroundColor: const Color(0xFFFFF9F0),
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontFamily: 'Manrope',
          fontWeight: FontWeight.w400,
        ),
        items: _items,
      ),
    );
  }
}

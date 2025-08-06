import 'package:flutter/material.dart';
import 'main_screen.dart';
import 'calendar_screen.dart';
import 'goals_screen.dart';
import 'insights_screen.dart';
import 'habits_screen.dart';
import 'mood_screen.dart';

class BottomNavigation extends StatefulWidget {
  const BottomNavigation({Key? key}) : super(key: key);

  @override
  State<BottomNavigation> createState() => _BottomNavigationState();
}

class _BottomNavigationState extends State<BottomNavigation> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    MainScreen(),
    CalendarScreen(),
    GoalsScreen(),
    InsightsScreen(),
    HabitsScreen(),
    MoodScreen(),
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
    BottomNavigationBarItem(
      icon: Icon(Icons.mood),
      label: 'Mood',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: colorScheme.surface,
          boxShadow: [
            BoxShadow(
              color: colorScheme.shadow.withValues(alpha: 0.1),
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          child: BottomNavigationBar(
            currentIndex: _currentIndex,
            onTap: (index) => setState(() => _currentIndex = index),
            selectedItemColor: colorScheme.primary,
            unselectedItemColor: colorScheme.onSurfaceVariant,
            backgroundColor: Colors.transparent,
            elevation: 0,
            type: BottomNavigationBarType.fixed,
            enableFeedback: true,
            selectedLabelStyle: TextStyle(
              fontFamily: 'Sora',
              fontWeight: FontWeight.w600,
              fontSize: 11,
              color: colorScheme.primary,
            ),
            unselectedLabelStyle: TextStyle(
              fontFamily: 'Manrope',
              fontWeight: FontWeight.w400,
              fontSize: 10,
              color: colorScheme.onSurfaceVariant,
            ),
            selectedIconTheme: IconThemeData(
              color: colorScheme.primary,
              size: 24,
            ),
            unselectedIconTheme: IconThemeData(
              color: colorScheme.onSurfaceVariant,
              size: 22,
            ),
            items: _items.map((item) {
              final index = _items.indexOf(item);
              return BottomNavigationBarItem(
                icon: Container(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Icon(
                    (item.icon as Icon).icon,
                    size: _currentIndex == index ? 24 : 22,
                  ),
                ),
                label: item.label,
                tooltip: item.label,
              );
            }).toList(),
          ),
        ),
      ),
    );
  }
}

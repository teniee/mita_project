import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:mita/providers/budget_provider.dart';
import 'package:mita/providers/user_provider.dart';
import 'package:mita/screens/user_profile_screen.dart';
import 'package:mita/theme/mita_theme.dart';

class _ProfileUserProvider extends UserProvider {
  @override
  UserState get state => UserState.authenticated;

  @override
  bool get isLoading => false;

  @override
  Map<String, dynamic> get userProfile => const {
        'name': 'Beta User',
        'email': 'beta@example.com',
        'income': 6000.0,
        'currency': 'BGN',
        'region': 'Bulgaria',
        'goals': <dynamic>[],
      };

  @override
  Map<String, dynamic> get financialContext => const {
        'active_goals': 0,
      };

  @override
  String get userName => 'Beta User';

  @override
  String get userEmail => 'beta@example.com';

  @override
  double get userIncome => 6000.0;

  @override
  String get userCurrency => 'BGN';

  @override
  String get userRegion => 'Bulgaria';

  @override
  List<dynamic> get userGoals => const [];

  @override
  Future<void> loadFinancialContext({int? sessionGeneration}) async {}
}

class _ProfileBudgetProvider extends BudgetProvider {
  _ProfileBudgetProvider({required this.transactionCount});

  final int? transactionCount;

  @override
  Map<String, dynamic> get liveBudgetStatus => transactionCount == null
      ? const {}
      : const {
          'monthly_spent': 0.0,
          'on_track': true,
        };

  @override
  double get totalSpent => 0.0;

  @override
  int? get monthlyTransactionCount => transactionCount;
}

void main() {
  testWidgets(
      'profile fits API 36 phone metrics and shows the real transaction count',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<UserProvider>.value(
          value: _ProfileUserProvider(),
        ),
        ChangeNotifierProvider<BudgetProvider>.value(
          value: _ProfileBudgetProvider(transactionCount: 7),
        ),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        home: const UserProfileScreen(),
      ),
    ));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('7 this month'), findsOneWidget);
    expect(find.textContaining('156'), findsNothing);
  });

  testWidgets('profile marks missing transaction stats unavailable',
      (tester) async {
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<UserProvider>.value(
          value: _ProfileUserProvider(),
        ),
        ChangeNotifierProvider<BudgetProvider>.value(
          value: _ProfileBudgetProvider(transactionCount: null),
        ),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        home: const UserProfileScreen(),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Unavailable'), findsOneWidget);
    expect(find.textContaining('156'), findsNothing);
  });
}

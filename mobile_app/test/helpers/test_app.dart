// Shared test harness.
//
// The app builds its widget tree under a MultiProvider (see lib/main.dart);
// screens read state via context.watch/read. Widget tests must therefore
// wrap screens in the same provider set or every build throws
// ProviderNotFoundException.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/providers.dart';
import 'package:provider/provider.dart';
import 'package:provider/single_child_widget.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Mirror of the production provider tree (lib/main.dart).
List<SingleChildWidget> buildTestProviders() {
  return [
    ChangeNotifierProvider<SettingsProvider>(create: (_) => SettingsProvider()),
    ChangeNotifierProvider<BudgetProvider>(create: (_) => BudgetProvider()),
    ChangeNotifierProvider<TransactionProvider>(
        create: (_) => TransactionProvider()),
    ChangeNotifierProvider<GoalsProvider>(create: (_) => GoalsProvider()),
    ChangeNotifierProvider<ChallengesProvider>(
        create: (_) => ChallengesProvider()),
    ChangeNotifierProvider<HabitsProvider>(create: (_) => HabitsProvider()),
    ChangeNotifierProvider<BehavioralProvider>(
        create: (_) => BehavioralProvider()),
    ChangeNotifierProvider<MoodProvider>(create: (_) => MoodProvider()),
    ChangeNotifierProvider<NotificationsProvider>(
        create: (_) => NotificationsProvider()),
    ChangeNotifierProvider<AdviceProvider>(create: (_) => AdviceProvider()),
    ChangeNotifierProvider<InstallmentsProvider>(
        create: (_) => InstallmentsProvider()),
    ChangeNotifierProvider<LoadingProvider>(create: (_) => LoadingProvider()),
    ChangeNotifierProvider<UserProvider>(
      create: (context) => UserProvider(
        onSessionBoundary: () {
          context.read<BudgetProvider>().resetSession();
          context.read<TransactionProvider>().resetSession();
          context.read<GoalsProvider>().resetSession();
          context.read<ChallengesProvider>().resetSession();
          context.read<HabitsProvider>().resetSession();
          context.read<BehavioralProvider>().resetSession();
          context.read<MoodProvider>().resetSession();
          context.read<NotificationsProvider>().resetSession();
          context.read<AdviceProvider>().resetSession();
          context.read<InstallmentsProvider>().resetSession();
          context.read<LoadingProvider>().reset();
        },
        onAccountTransition: () {
          context.read<SettingsProvider>().resetSession();
        },
      ),
    ),
  ];
}

/// Wrap [home] exactly the way the real app does: providers + MaterialApp.
Widget wrapWithProviders(
  Widget home, {
  Map<String, WidgetBuilder>? routes,
}) {
  return MultiProvider(
    providers: buildTestProviders(),
    child: MaterialApp(
      home: home,
      routes: routes ?? const <String, WidgetBuilder>{},
    ),
  );
}

/// Common test bootstrap: binding + mocked platform channels that screens
/// touch during initState (shared_preferences).
void initTestEnvironment() {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues(<String, Object>{});
}

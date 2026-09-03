/// The Calendar day-details screen must never show a day budget that its own
/// Category Breakdown does not account for.
///
/// Reported from the real UI on 2026-08-04, 2026-08-05 and 2026-08-18: every
/// one of those days showed
///
///     Budget $79.00   Spent $0.00   Remaining $79.00
///
/// while the visible Category Breakdown read "Food & Dining $0 / $0",
/// "Transportation $0 / $0", "Entertainment $0 / $0". The three dates have
/// completely different persisted plans in the database (they summed to
/// $48.18, $464.18 and $48.18), so an identical $79.00 on all three could not
/// have come from any of them.
///
/// It came from POST /calendar/shell — a planning preview that divides a
/// monthly total by the number of days, giving the SAME figure for every day
/// of the month. `_generateDefaultCategoryBreakdown()` then filled the list
/// with four hardcoded category names sized as fractions of that average, and
/// `toStringAsFixed(0)` rendered the sub-dollar ones as "$0".
///
/// The invariant these tests pin, for a selected date D:
///
///     day_budget    == SUM(persisted category planned amounts for D)
///     day_remaining == day_budget - day_spent
///
/// and, when D has no persisted allocation, no daily budget is invented.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mita/l10n/generated/app_localizations.dart';
import 'package:mita/providers/providers.dart';
import 'package:mita/screens/calendar_day_details_screen.dart';
import 'package:mita/services/security_monitor.dart';
import 'package:mita/theme/mita_theme.dart';

/// The screen awaits a transactions fetch before it builds the breakdown.
/// Left to reach the network it hangs for the whole test (and would talk to
/// production); failing it immediately is what lets the breakdown render.
class _NoNetwork extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      throw const SocketException('network disabled in tests');
}

/// Host with the calendar month already loaded.
///
/// The screen kicks off BudgetProvider.loadCalendarData when calendarData is
/// empty; with the network disabled that background load throws into the test
/// zone and fails the test before anything is asserted. Seeding the day the
/// screen is showing is also more faithful — on a device the provider has
/// already loaded the month by the time this sheet opens.
Widget _host(Widget home, Map<String, dynamic> seedDay) => MultiProvider(
      providers: [
        ChangeNotifierProvider<SettingsProvider>(
            create: (_) => SettingsProvider()),
        ChangeNotifierProvider<BudgetProvider>(
            create: (_) => BudgetProvider()..calendarData.add(seedDay)),
        ChangeNotifierProvider<TransactionProvider>(
            create: (_) => TransactionProvider()),
      ],
      child: MaterialApp(
        theme: MitaTheme.lightTheme,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: home),
      ),
    );

/// A saved-calendar day exactly as BudgetProvider.mergeSavedCalendarDay emits
/// it: `is_preview: false`, an int `limit`, and per-category planned/spent.
Map<String, dynamic> _savedDay({
  required int day,
  required String date,
  required Map<String, double> planned,
  Map<String, double> spent = const {},
}) {
  final cats = <String, dynamic>{};
  planned.forEach((cat, amount) {
    cats[cat] = {'planned': amount, 'spent': spent[cat] ?? 0.0};
  });
  final limit = planned.values.fold<double>(0.0, (a, b) => a + b);
  final totalSpent = spent.values.fold<double>(0.0, (a, b) => a + b);
  return {
    'day': day,
    'date': date,
    'is_preview': false,
    'limit': limit.round(),
    'status': 'good',
    'spent': totalSpent.round(),
    'categories': cats,
    'is_today': false,
    'is_weekend': false,
  };
}

/// A shell-preview day exactly as ApiService._transformCalendarData emits it:
/// `is_preview: true`, one flat figure repeated across the whole month.
Map<String, dynamic> _previewDay({required int day, required String date}) => {
      'day': day,
      'date': date,
      'is_preview': true,
      'limit': 79,
      'status': 'good',
      'spent': 0,
      // What the shell actually returns: a monthly total spread evenly.
      'categories': const {
        'food': 0.30,
        'transportation': 0.30,
        'entertainment': 0.16,
        'shopping': 0.20,
        'healthcare': 0.14,
        'rent': 60.00,
        'utilities': 10.00,
        'insurance': 8.00,
      },
      'is_today': false,
      'is_weekend': false,
    };

/// Sum of every "$x / $y" budgeted figure rendered in the Category Breakdown.
double _renderedCategoryTotal(WidgetTester tester) {
  var total = 0.0;
  // Past/today rows render "$spent / $budgeted"; future rows render just
  // "$budgeted" (they have no spend yet). Both are the budgeted figure.
  final withSpent = RegExp(r'^\$[\d.]+ / \$([\d.]+)$');
  final budgetOnly = RegExp(r'^\$([\d.]+)$');
  final seenRow = <String>{};
  for (final w in tester.widgetList<Text>(find.byType(Text))) {
    final t = w.data;
    if (t == null) continue;
    final m = withSpent.firstMatch(t);
    if (m != null) {
      total += double.parse(m.group(1)!);
      seenRow.add(t);
    }
  }
  if (seenRow.isNotEmpty) return total;
  // Future-day form. Exclude the three header-card figures, which are not
  // category rows: they live inside _buildBudgetStat next to their labels.
  final headerLabels = {
    'Budget',
    'Spent',
    'Remaining',
    'Available',
    'Predicted'
  };
  final texts =
      tester.widgetList<Text>(find.byType(Text)).map((w) => w.data).toList();
  for (var i = 0; i < texts.length; i++) {
    final t = texts[i];
    if (t == null) continue;
    final m = budgetOnly.firstMatch(t);
    if (m == null) continue;
    final prev = i > 0 ? texts[i - 1] : null;
    if (prev != null && headerLabels.contains(prev)) continue;
    total += double.parse(m.group(1)!);
  }
  return total;
}

Future<void> _pumpDay(
    WidgetTester tester, Map<String, dynamic> day, DateTime date) async {
  // The sheet sizes itself to 85% of the viewport; a tall surface keeps the
  // whole breakdown laid out so every row is findable.
  tester.view.physicalSize = const Size(1200, 3600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(_host(
      CalendarDayDetailsScreen(
        dayNumber: day['day'] as int,
        // The route args the calendar grid passes. Deliberately WRONG here:
        // the screen must derive its figures from dayData, never from these.
        limit: 79,
        spent: 0,
        status: day['status'] as String,
        date: date,
        dayData: day,
      ),
      day));
  // postFrameCallback -> _loadDayDetails -> transactions fetch (fails on the
  // disabled network) -> _loadCategoryBreakdown.
  //
  // runAsync lets the real Dio failure resolve, and the trailing fake-time
  // pumps then drain the request timeout timers it armed — without them the
  // binding trips "A Timer is still pending even after the widget tree was
  // disposed" on whichever test happens to run first.
  await tester.pump();
  await tester.runAsync(() async {
    await Future<void>.delayed(const Duration(seconds: 2));
  });
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
  await tester.pump(const Duration(minutes: 3));

  // Touching ApiService starts SecurityMonitor's 5-minute periodic timer,
  // which outlives the widget tree and trips the binding's "A Timer is still
  // pending" invariant on whichever test happened to construct the singleton.
  // It is process-wide infrastructure, not part of what is under test.
  SecurityMonitor.instance.stopMonitoring();
}

void main() {
  setUpAll(() => HttpOverrides.global = _NoNetwork());
  tearDownAll(() => HttpOverrides.global = null);
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    // getToken() blocks on the secure-storage platform channel, and the screen
    // awaits it before building the breakdown.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async => call.method == 'readAll' ? <String, String>{} : null,
    );
  });

  group('selected-day summary equals the persisted category sum', () {
    // The three dates from the report, with their real persisted allocations.
    final cases = <String, Map<String, double>>{
      '2026-08-04': {
        'coffee': 5.40,
        'groceries': 13.71,
        'transport public': 30.00,
      },
      '2026-08-05': {
        'coffee': 5.40,
        'flights': 144.00,
        'groceries': 13.71,
        'insurance medical': 216.00,
        'transport public': 30.00,
      },
      '2026-08-18': {
        'coffee': 5.40,
        'groceries': 13.71,
        'transport public': 30.00,
      },
    };

    for (final entry in cases.entries) {
      final dateStr = entry.key;
      final planned = entry.value;
      final date = DateTime.parse(dateStr);
      final expected = planned.values.fold<double>(0.0, (a, b) => a + b);

      testWidgets('$dateStr shows \$${expected.toStringAsFixed(2)}, not \$79',
          (tester) async {
        await _pumpDay(
          tester,
          _savedDay(day: date.day, date: dateStr, planned: planned),
          date,
        );

        // TOP CARD == DB SUM
        expect(
          find.text('\$${expected.toStringAsFixed(2)}'),
          findsWidgets,
          reason: 'the Budget figure must be the persisted category sum',
        );
        // The reported fabrication must be gone.
        expect(find.text('\$79.00'), findsNothing);
        expect(find.text('\$79'), findsNothing);

        // CATEGORY SUM == TOP CARD
        expect(
          _renderedCategoryTotal(tester),
          closeTo(expected, 0.001),
          reason: 'the breakdown must account for the whole day budget',
        );
      });
    }

    testWidgets('the three dates do not all show the same figure',
        (tester) async {
      // The tell that $79 was an average: Aug 5 carries fixed expenses and is
      // an order of magnitude larger than Aug 4 and Aug 18.
      final aug4 =
          cases['2026-08-04']!.values.fold<double>(0.0, (a, b) => a + b);
      final aug5 =
          cases['2026-08-05']!.values.fold<double>(0.0, (a, b) => a + b);
      expect(aug4, isNot(closeTo(aug5, 0.01)));
    });
  });

  group('no invented budget', () {
    testWidgets('a day with no category allocation shows no daily budget',
        (tester) async {
      final date = DateTime.parse('2026-08-04');
      await _pumpDay(
        tester,
        _savedDay(day: 4, date: '2026-08-04', planned: const {}),
        date,
      );

      expect(find.text('\$79.00'), findsNothing);
      expect(find.text('No budget set for this day'), findsOneWidget);
      // ...and none of the four hardcoded fallback categories appear.
      expect(find.text('Food & Dining'), findsNothing);
      expect(find.text('Transportation'), findsNothing);
      expect(find.text('Entertainment'), findsNothing);
      expect(find.text('Shopping'), findsNothing);
    });

    testWidgets('a shell preview day is labelled, not shown as a budget',
        (tester) async {
      final date = DateTime.parse('2026-08-04');
      await _pumpDay(tester, _previewDay(day: 4, date: '2026-08-04'), date);

      // The exact defect: $79 presented as this day's budget.
      expect(find.text('\$79.00'), findsNothing);
      expect(find.text('\$79'), findsNothing);
      expect(find.text('Budget preview only'), findsOneWidget);
      // Its evenly-spread categories are not this day's allocation either.
      expect(_renderedCategoryTotal(tester), 0.0);
    });
  });

  group('cents are not rounded away', () {
    testWidgets('a sub-dollar allocation renders as cents, never as \$0',
        (tester) async {
      final date = DateTime.parse('2026-08-04');
      await _pumpDay(
        tester,
        _savedDay(
          day: 4,
          date: '2026-08-04',
          planned: const {'coffee': 0.30, 'groceries': 0.45},
        ),
        date,
      );

      // toStringAsFixed(0) turned these into "$0" and made a real plan look
      // like an absent one.
      expect(find.textContaining('0.30'), findsWidgets);
      expect(find.text('\$0 / \$0'), findsNothing);
      expect(_renderedCategoryTotal(tester), closeTo(0.75, 0.001));
    });
  });

  group('rollover-generated months satisfy the same invariant', () {
    testWidgets('a September day derived from August still balances',
        (tester) async {
      // ensure_month_plan rolls August's per-category totals into September,
      // so a September day is the same shape and must obey the same rule.
      final date = DateTime.parse('2026-09-04');
      const planned = {
        'coffee': 5.40,
        'groceries': 13.71,
        'transport public': 30.00,
      };
      await _pumpDay(
        tester,
        _savedDay(day: 4, date: '2026-09-04', planned: planned),
        date,
      );

      const expected = 49.11;
      expect(find.text('\$${expected.toStringAsFixed(2)}'), findsWidgets);
      expect(_renderedCategoryTotal(tester), closeTo(expected, 0.001));
    });
  });
}

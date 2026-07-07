/// Regression tests for the saved-calendar merge in BudgetProvider.
///
/// Bug context: /calendar/saved/{year}/{month} returned "limit": 0.0 for
/// every day (backend never wrote daily_budget), which silently disabled
/// the calendar traffic-light — `limit > 0 && spent > limit` can never
/// flag an overspent day when limit is 0. These tests pin the merge
/// contract against the real backend day shape.
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/budget_provider.dart';

void main() {
  final today = DateTime(2026, 7, 6);

  Map<String, dynamic> backendDay({
    String date = '2026-07-06',
    int day = 6,
    double limit = 69.33,
    Map<String, dynamic>? plannedBudget,
  }) {
    // Exact shape of one element of data.calendar from
    // GET /api/calendar/saved/{year}/{month}.
    return {
      'date': date,
      'day': day,
      'planned_budget': plannedBudget ??
          {
            'food': {'planned': 23.76, 'spent': 23.75, 'status': 'pending'},
            'coffee': {'planned': 5.62, 'spent': 0.0, 'status': 'pending'},
          },
      'limit': limit,
      'total': 69.33,
      'spent': 23.75,
      'status': 'active',
    };
  }

  group('mergeSavedCalendarDay', () {
    test('propagates the backend day limit', () {
      final merged = mergeSavedCalendarDay(
        backendDay(),
        today: today,
        spentByDay: {6: 23.75},
        spentByDayCategory: {
          6: {'food': 23.75},
        },
      );

      expect(merged['limit'], 69, reason: 'limit must survive the merge');
      expect(merged['day'], 6);
      expect(merged['date'], '2026-07-06');
      expect(merged['is_today'], isTrue);
      expect(merged['spent'], 24); // 23.75 rounded
    });

    test('flags an overspent day against a non-zero limit', () {
      final merged = mergeSavedCalendarDay(
        backendDay(limit: 50.0),
        today: today,
        spentByDay: {6: 80.0},
        spentByDayCategory: {
          6: {'food': 80.0},
        },
      );
      expect(merged['status'], 'over');
    });

    test('warns when spending approaches the limit', () {
      final merged = mergeSavedCalendarDay(
        backendDay(limit: 100.0),
        today: today,
        spentByDay: {6: 90.0},
        spentByDayCategory: {
          6: {'food': 90.0},
        },
      );
      expect(merged['status'], 'warning');
    });

    test(
        'REGRESSION: a zero limit disables overspend detection — '
        'this is why the backend must emit real limits', () {
      final merged = mergeSavedCalendarDay(
        backendDay(limit: 0.0),
        today: today,
        spentByDay: {6: 500.0},
        spentByDayCategory: {
          6: {'food': 500.0},
        },
      );
      // Massively overspent day still reads 'good' when limit is 0.
      // The backend-side regression tests (test_calendar_limits.py)
      // guarantee limits are never 0 for planned days.
      expect(merged['status'], 'good');
      expect(merged['limit'], 0);
    });

    test('future days stay planned with no spending attributed', () {
      final merged = mergeSavedCalendarDay(
        backendDay(date: '2026-07-20', day: 20),
        today: today,
        spentByDay: {20: 10.0},
        spentByDayCategory: {
          20: {'food': 10.0},
        },
      );
      expect(merged['status'], 'planned');
      final cats = merged['categories'] as Map<String, dynamic>;
      expect((cats['food'] as Map)['spent'], 0.0,
          reason: 'future days must not show spending');
    });

    test('merges unplanned-category transactions into the day', () {
      final merged = mergeSavedCalendarDay(
        backendDay(),
        today: today,
        spentByDay: {6: 12.0},
        spentByDayCategory: {
          6: {'gadgets': 12.0},
        },
      );
      final cats = merged['categories'] as Map<String, dynamic>;
      expect(cats, contains('gadgets'));
      expect((cats['gadgets'] as Map)['planned'], 0.0);
      expect((cats['gadgets'] as Map)['spent'], 12.0);
    });

    test('parses plain YYYY-MM-DD day keys from the backend', () {
      final merged = mergeSavedCalendarDay(
        backendDay(date: '2026-07-05', day: 5),
        today: today,
        spentByDay: {},
        spentByDayCategory: {},
      );
      expect(merged['is_today'], isFalse);
      expect(merged['status'], 'good', reason: 'past day, nothing spent');
      expect(merged['is_weekend'], isTrue, reason: '2026-07-05 is a Sunday');
    });

    test('handles category values that are plain numbers', () {
      final merged = mergeSavedCalendarDay(
        backendDay(plannedBudget: {'food': 30.0}),
        today: today,
        spentByDay: {},
        spentByDayCategory: {},
      );
      final cats = merged['categories'] as Map<String, dynamic>;
      expect((cats['food'] as Map)['planned'], 30.0);
    });
  });
}

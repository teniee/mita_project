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
    double spent = 23.75,
    Map<String, dynamic>? plannedBudget,
  }) {
    // Exact shape of one element of data.calendar from
    // GET /api/calendar/saved/{year}/{month}.
    return {
      'date': date,
      'day': day,
      'planned_budget': plannedBudget ??
          {
            'food': {'planned': 23.76, 'spent': spent, 'status': 'pending'},
            'coffee': {'planned': 5.62, 'spent': 0.0, 'status': 'pending'},
          },
      'limit': limit,
      'total': 69.33,
      'spent': spent,
      'status': 'active',
    };
  }

  // A shell/preview day (POST /calendar/shell) carries NO backend spent —
  // the transaction overlay is the only spent source on this path.
  Map<String, dynamic> shellDay({
    String date = '2026-07-06',
    int day = 6,
    double limit = 69.33,
    Map<String, dynamic>? plannedBudget,
  }) {
    return {
      'date': date,
      'day': day,
      'planned_budget': plannedBudget ?? {'food': 23.76, 'coffee': 5.62},
      'limit': limit,
      'total': 69.33,
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
        backendDay(limit: 50.0, spent: 80.0),
        today: today,
        spentByDay: const {},
        spentByDayCategory: const {},
      );
      expect(merged['status'], 'over');
    });

    test('warns when spending approaches the limit', () {
      final merged = mergeSavedCalendarDay(
        backendDay(limit: 100.0, spent: 90.0),
        today: today,
        spentByDay: const {},
        spentByDayCategory: const {},
      );
      expect(merged['status'], 'warning');
    });

    test(
        'REGRESSION: a zero limit disables overspend detection — '
        'this is why the backend must emit real limits', () {
      final merged = mergeSavedCalendarDay(
        backendDay(limit: 0.0, spent: 500.0),
        today: today,
        spentByDay: const {},
        spentByDayCategory: const {},
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

    test('merges unplanned-category transactions on the shell path', () {
      // Only the shell/preview path (no backend spent) uses the overlay for
      // unplanned categories; the saved path already carries them as plan
      // rows.
      final merged = mergeSavedCalendarDay(
        shellDay(),
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

    test(
        'REGRESSION: trusts backend spent even when the transaction overlay '
        'is empty', () {
      // The device bug: the saved-calendar payload carried the correct
      // spent (23.75), but the merge recomputed from a /transactions/ fetch
      // whose date filter missed the row, so the calendar rendered $0. With
      // empty overlay maps the merge must still surface the backend spent.
      final merged = mergeSavedCalendarDay(
        backendDay(),
        today: today,
        spentByDay: const {},
        spentByDayCategory: const {},
      );

      expect(merged['spent'], 24, reason: 'backend day spent 23.75 -> 24');
      final cats = merged['categories'] as Map<String, dynamic>;
      expect((cats['food'] as Map)['spent'], 23.75,
          reason: 'backend per-category spent must survive with no overlay');
      expect((cats['coffee'] as Map)['spent'], 0.0);
    });

    test('backend per-category spent overrides a stale overlay value', () {
      final merged = mergeSavedCalendarDay(
        backendDay(),
        today: today,
        // Overlay disagrees (e.g. an inconsistent /transactions/ page) —
        // the backend value wins.
        spentByDay: const {6: 999.0},
        spentByDayCategory: const {
          6: {'food': 999.0},
        },
      );
      final cats = merged['categories'] as Map<String, dynamic>;
      expect((cats['food'] as Map)['spent'], 23.75);
      expect(merged['spent'], 24);
    });
  });
}

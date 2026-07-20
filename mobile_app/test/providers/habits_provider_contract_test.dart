// Regression tests for the habit id contract (Phase-4 sweep, session 7).
//
// The backend returns UUID string ids for habits. The old model coerced
// them through int.tryParse → every habit got id 0, so edit/delete/
// complete all hit /habits/0 and 422'd. The id must stay the opaque
// backend string, and the PATCH/DELETE paths must not carry a trailing
// slash (FastAPI 307s, and dart:io only follows redirects for GET/HEAD).

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/habits_provider.dart';

void main() {
  group('Habit.fromJson id contract', () {
    test('preserves a backend UUID id verbatim', () {
      final habit = Habit.fromJson({
        'id': '9c27f3d9-d9a7-4e2a-b165-f1017df72577',
        'title': 'Morning budget check',
      });
      expect(habit.id, '9c27f3d9-d9a7-4e2a-b165-f1017df72577');
    });

    test('does not collapse distinct UUID ids into one value', () {
      final a = Habit.fromJson({'id': '11111111-1111-1111-1111-111111111111'});
      final b = Habit.fromJson({'id': '22222222-2222-2222-2222-222222222222'});
      expect(a.id, isNot(b.id));
    });

    test('tolerates a numeric id by stringifying it', () {
      expect(Habit.fromJson({'id': 7}).id, '7');
    });

    test('missing id becomes empty string, not a fake 0', () {
      expect(Habit.fromJson({'title': 'x'}).id, '');
    });
  });
}

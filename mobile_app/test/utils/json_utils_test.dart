import 'package:flutter_test/flutter_test.dart';
import 'package:mita/utils/json_utils.dart';

void main() {
  group('asStringOrNull / asString', () {
    test('passes strings through', () {
      expect(asStringOrNull('abc'), 'abc');
      expect(asString('abc'), 'abc');
    });

    test('rejects non-strings instead of throwing', () {
      expect(asStringOrNull(42), isNull);
      expect(asStringOrNull(null), isNull);
      expect(asStringOrNull({'a': 1}), isNull);
      expect(asString(42, fallback: 'x'), 'x');
    });
  });

  group('numeric coercion (flat number vs string shapes)', () {
    test('int, double, and numeric-string all normalize to double', () {
      expect(asDouble(7), 7.0);
      expect(asDouble(7.5), 7.5);
      expect(asDouble('7.5'), 7.5);
    });

    test('nested-map value degrades to fallback, not a TypeError', () {
      // Regression: backend switched budget fields between flat numbers and
      // nested maps; parsing must degrade instead of crashing the dashboard.
      expect(asDouble({'amount': 7.5}), 0.0);
      expect(asDoubleOrNull({'amount': 7.5}), isNull);
    });

    test('int coercion', () {
      expect(asInt('12'), 12);
      expect(asInt(12.9), 12);
      expect(asIntOrNull('not a number'), isNull);
      expect(asInt(null, fallback: -1), -1);
    });
  });

  group('asBool', () {
    test('accepts bool, num, and common string spellings', () {
      expect(asBool(true), isTrue);
      expect(asBool(1), isTrue);
      expect(asBool(0), isFalse);
      expect(asBool('true'), isTrue);
      expect(asBool('FALSE'), isFalse);
      expect(asBool('yes'), isTrue);
    });

    test('unknown shapes use the fallback', () {
      expect(asBool('maybe'), isFalse);
      expect(asBool(null, fallback: true), isTrue);
      expect(asBool([1, 2]), isFalse);
    });
  });

  group('asStringKeyedMap', () {
    test('passes string-keyed maps through and normalizes other keys', () {
      expect(asStringKeyedMap({'a': 1}), {'a': 1});
      expect(asStringKeyedMap(<dynamic, dynamic>{1: 'x'}), {'1': 'x'});
    });

    test('non-map input yields an empty map / null', () {
      expect(asStringKeyedMap('nope'), isEmpty);
      expect(asStringKeyedMap(null), isEmpty);
      expect(asStringKeyedMapOrNull(3.14), isNull);
    });
  });

  group('asMapList / asList / asStringList', () {
    test('list of objects normalizes and drops non-map entries', () {
      final result = asMapList([
        {'a': 1},
        'junk',
        42,
        {2: 'b'},
      ]);
      expect(result, [
        {'a': 1},
        {'2': 'b'},
      ]);
    });

    test('non-list input yields empty list', () {
      expect(asMapList({'a': 1}), isEmpty);
      expect(asList('x'), isEmpty);
      expect(asStringList(null), isEmpty);
    });

    test('string list stringifies non-null scalars', () {
      expect(asStringList(['a', 1, null, true]), ['a', '1', 'true']);
    });
  });

  group('asDateTimeOrNull', () {
    test('parses ISO strings and passes DateTime through', () {
      expect(asDateTimeOrNull('2026-07-12T00:00:00Z'),
          DateTime.utc(2026, 7, 12));
      final now = DateTime(2026, 1, 1);
      expect(asDateTimeOrNull(now), now);
    });

    test('garbage yields null', () {
      expect(asDateTimeOrNull('not a date'), isNull);
      expect(asDateTimeOrNull(123), isNull);
    });
  });
}

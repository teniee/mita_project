/// The Financial Health Score card must show a number only when the server
/// measured one.
///
/// `/api/ai/financial-health-score` answered a brand-new account — no
/// transactions at all — with the income tier's expectation threshold as that
/// person's score: $9,000/month got `score: 73, grade: "C"`, the same figure
/// copied into four components, and `trend: "stable"`. The card rendered it as
/// a real assessment, because its only guard was "score and grade are not
/// null" and the server always filled them in.
///
/// The backend now suppresses the verdict (`status: "insufficient_data"`,
/// null score/grade/trend, empty components). These cases pin the client half:
/// no assessment, no card.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/utils/health_score_data.dart';

void main() {
  group('hasFinancialHealthScore', () {
    test('false for a missing payload', () {
      expect(hasFinancialHealthScore(null), isFalse);
      expect(hasFinancialHealthScore(<String, dynamic>{}), isFalse);
    });

    test('false when the server says it has not enough data', () {
      expect(
        hasFinancialHealthScore(const {
          'score': null,
          'grade': null,
          'components': <String, dynamic>{},
          'trend': null,
          'status': 'insufficient_data',
          'data_points': 0,
        }),
        isFalse,
      );
    });

    test('the insufficient-data verdict wins over any figure beside it', () {
      // Defence in depth: if a score ever ships alongside that status, the
      // status is the statement about whether it means anything.
      expect(
        hasFinancialHealthScore(const {
          'score': 73,
          'grade': 'C',
          'status': 'insufficient_data',
        }),
        isFalse,
      );
    });

    test('false when the analysis failed (degraded envelope)', () {
      expect(
        hasFinancialHealthScore(const {
          'score': null,
          'grade': null,
          'components': <String, dynamic>{},
          'improvements': <String>[],
          'trend': null,
          'error': 'Financial health score is currently unavailable',
        }),
        isFalse,
      );
    });

    test('false when either half of the assessment is missing', () {
      expect(
          hasFinancialHealthScore(const {'score': 73, 'grade': null}), isFalse);
      expect(hasFinancialHealthScore(const {'score': null, 'grade': 'C'}),
          isFalse);
    });

    test('true for a measured score', () {
      expect(
        hasFinancialHealthScore(const {
          'score': 51,
          'grade': 'F',
          'components': {
            'budgeting': 0,
            'spending_efficiency': 80,
            'saving_potential': 29,
            'consistency': 100,
          },
          'improvements': <String>[],
          'trend': 'stable',
        }),
        isTrue,
      );
    });

    test('a score of 0 is a measurement, not a missing value', () {
      expect(
        hasFinancialHealthScore(const {'score': 0, 'grade': 'F'}),
        isTrue,
      );
    });
  });
}

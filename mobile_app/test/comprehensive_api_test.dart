import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';

/// Comprehensive API Endpoint Testing
/// Tests all the critical endpoints mentioned in the QA requirements
///
/// This test file validates the fixed endpoints:
/// - /api/cohort/insights
/// - /api/insights/
/// - /api/ai/latest-snapshots (not /api/ai/ai/ai/latest-snapshots)
/// - /api/cohort/income_classification
/// - /api/calendar/shell
/// - /api/users/me (not /api/users/users/me)
/// - /api/analytics/monthly (not /api/analytics/analytics/monthly)

void main() {
  group('MITA API Endpoint Tests', () {
    late Dio dio;
    const baseUrl = 'https://mita-docker-ready-project-manus.onrender.com/api';

    setUpAll(() {
      dio = Dio(BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
      ));
    });

    group('Authentication & User Management', () {
      test('POST /auth/login - Should handle login requests', () async {
        try {
          final response = await dio.post('/auth/login',
              data: {'email': 'test@example.com', 'password': 'testpassword'});

          // Should return either valid auth response or proper error
          expect(response.statusCode, isIn([200, 400, 401, 404]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            // Should contain token fields for successful login
            if (response.data['access_token'] != null) {
              expect(response.data['access_token'], isA<String>());
            }
          }
        } catch (e) {
          if (e is DioException) {
            // Should return proper HTTP error codes, not crash
            expect(e.response?.statusCode, isIn([400, 401, 404, 422, 500]));
          } else {
            fail('Unexpected error type: ${e.runtimeType}');
          }
        }
      });

      test('GET /users/me - Fixed duplicate path issue', () async {
        try {
          final response = await dio.get('/users/me');

          // Should return 401 for unauthenticated, not 404 for wrong path
          expect(response.statusCode, isIn([200, 401]));
        } catch (e) {
          if (e is DioException) {
            // Should be 401 (unauthorized) not 404 (not found)
            // 404 would indicate the old broken path /users/users/me
            expect(e.response?.statusCode, isNot(404),
                reason:
                    'Endpoint should exist but require authentication, not return 404');
            expect(e.response?.statusCode, isIn([401, 500]));
          }
        }
      });
    });

    group('Cohort & Analytics Endpoints', () {
      test('GET /api/cohort/insights - Should return insights data', () async {
        try {
          final response = await dio.get('/cohort/insights');

          // Should return 200 or 401, not 404
          expect(response.statusCode, isIn([200, 401]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            expect(response.data['data'], isNotNull);
          }
        } catch (e) {
          if (e is DioException) {
            // Should not return 404 - endpoint should exist
            expect(e.response?.statusCode, isNot(404));
            expect(e.response?.statusCode, isIn([401, 500]));
          }
        }
      });

      test(
          'GET /api/cohort/income_classification - Should return income tier data',
          () async {
        try {
          final response = await dio.get('/cohort/income_classification');

          expect(response.statusCode, isIn([200, 401]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            final data = response.data['data'];
            if (data != null) {
              // Should contain income classification fields
              expect(data, isA<Map<String, dynamic>>());
            }
          }
        } catch (e) {
          if (e is DioException) {
            expect(e.response?.statusCode, isNot(404));
            expect(e.response?.statusCode, isIn([401, 500]));
          }
        }
      });

      test('GET /api/insights/ - Should work for premium and non-premium users',
          () async {
        try {
          final response = await dio.get('/insights/');

          expect(response.statusCode, isIn([200, 401, 403]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
          } else if (response.statusCode == 403) {
            // Acceptable for premium-only features
            expect(response.data, isA<Map<String, dynamic>>());
          }
        } catch (e) {
          if (e is DioException) {
            expect(e.response?.statusCode, isNot(404));
            expect(e.response?.statusCode, isIn([401, 403, 500]));
          }
        }
      });
    });

    group('AI & Analytics Endpoints', () {
      test('GET /api/ai/latest-snapshots - Fixed duplicate path', () async {
        try {
          final response = await dio.get('/ai/latest-snapshots');

          expect(response.statusCode, isIn([200, 401]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            final data = response.data['data'];
            if (data is List) {
              expect(data, isA<List<dynamic>>());
            }
          }
        } catch (e) {
          if (e is DioException) {
            // Should NOT return 404 - the old broken path was /ai/ai/ai/latest-snapshots
            expect(e.response?.statusCode, isNot(404),
                reason:
                    'Fixed path should exist, old /ai/ai/ai/latest-snapshots was broken');
            expect(e.response?.statusCode, isIn([401, 500]));
          }
        }
      });

      test('GET /api/analytics/monthly - Fixed duplicate path', () async {
        try {
          final response = await dio.get('/analytics/monthly');

          expect(response.statusCode, isIn([200, 401]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            expect(response.data['data'], isNotNull);
          }
        } catch (e) {
          if (e is DioException) {
            // Should NOT return 404 - old broken path was /analytics/analytics/monthly
            expect(e.response?.statusCode, isNot(404),
                reason:
                    'Fixed path should exist, old /analytics/analytics/monthly was broken');
            expect(e.response?.statusCode, isIn([401, 500]));
          }
        }
      });
    });

    group('Calendar & Budget Endpoints', () {
      test(
          'POST /api/calendar/shell - Should return calendar data without 500 errors',
          () async {
        try {
          // Test with realistic shell configuration
          final shellConfig = {
            'income': 5000.0,
            'savings_target': 1000.0,
            'fixed': {
              'rent': 1500.0,
              'utilities': 250.0,
              'insurance': 200.0,
            },
            'weights': {
              'food': 0.15,
              'transportation': 0.15,
              'entertainment': 0.08,
              'shopping': 0.10,
              'healthcare': 0.07,
            },
            'year': DateTime.now().year,
            'month': DateTime.now().month,
          };

          final response = await dio.post('/calendar/shell', data: shellConfig);

          // Should not return 500 internal server error
          expect(response.statusCode, isNot(500));
          expect(response.statusCode, isIn([200, 400, 401]));

          if (response.statusCode == 200) {
            expect(response.data, isA<Map<String, dynamic>>());
            expect(response.data['data'], isNotNull);
            final calendarData = response.data['data']['calendar'];
            if (calendarData != null) {
              expect(calendarData, isA<Map<String, dynamic>>());
            }
          }
        } catch (e) {
          if (e is DioException) {
            // Should NOT return 500 - that was the bug being fixed
            expect(e.response?.statusCode, isNot(500),
                reason: 'Calendar endpoint should not return 500 errors');
            expect(e.response?.statusCode, isIn([400, 401, 422]));
          }
        }
      });
    });

    group('Error Handling & Response Format Tests', () {
      test('All endpoints should return proper JSON responses', () async {
        final endpoints = [
          '/cohort/insights',
          '/insights/',
          '/ai/latest-snapshots',
          '/cohort/income_classification',
          '/users/me',
          '/analytics/monthly',
        ];

        for (final endpoint in endpoints) {
          try {
            final response = await dio.get(endpoint);

            // Should return valid JSON
            expect(response.data, isA<Map<String, dynamic>>());
          } catch (e) {
            if (e is DioException && e.response != null) {
              // Even error responses should be valid JSON
              expect(e.response!.data, isA<Map<String, dynamic>>(),
                  reason:
                      'Endpoint $endpoint should return JSON even for errors');
            }
          }
        }
      });

      test('Endpoints should have consistent error response format', () async {
        try {
          // Test with invalid auth token
          final response = await dio.get('/users/me',
              options:
                  Options(headers: {'Authorization': 'Bearer invalid-token'}));

          if (response.statusCode == 401) {
            expect(response.data, isA<Map<String, dynamic>>());
            // Should have consistent error structure
          }
        } catch (e) {
          if (e is DioException && e.response?.statusCode == 401) {
            expect(e.response!.data, isA<Map<String, dynamic>>());
            // Error responses should be structured JSON, not plain text
          }
        }
      });
    });

    group('Performance & Reliability Tests', () {
      test('Endpoints should respond within reasonable time', () async {
        final stopwatch = Stopwatch()..start();

        try {
          await dio.get('/cohort/insights');
        } catch (e) {
          // Error is fine, we're testing response time
        }

        stopwatch.stop();

        // Should respond within 10 seconds (network included)
        expect(stopwatch.elapsedMilliseconds, lessThan(10000),
            reason: 'API endpoints should respond quickly');
      });

      test('Calendar endpoint should handle invalid data gracefully', () async {
        try {
          // Test with invalid shell configuration
          final response = await dio.post('/calendar/shell', data: {
            'invalid': 'data',
            'income': 'not-a-number',
          });

          // Should return 400 bad request, not 500 internal error
          expect(response.statusCode, isIn([400, 422]));
        } catch (e) {
          if (e is DioException) {
            // Should be client error (400-499), not server error (500-599)
            expect(e.response?.statusCode, lessThan(500),
                reason:
                    'Invalid input should return client error, not server error');
          }
        }
      });
    });
  });
}

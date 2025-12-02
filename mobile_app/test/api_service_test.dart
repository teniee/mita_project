import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';

void main() {
  test('ApiService returns same instance', () {
    final a = ApiService();
    final b = ApiService();
    expect(identical(a, b), isTrue);
  });
}

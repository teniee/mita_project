import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/user_data_manager.dart';
import 'package:mocktail/mocktail.dart';

class _MockApiService extends Mock implements ApiService {}

Map<String, dynamic> _profile(String id, double income) => {
      'success': true,
      'data': {
        'id': id,
        'email': '$id@example.test',
        'income': income,
        'currency': 'EUR',
      },
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockApiService api;
  late Map<String, String> secureStore;
  late String owner;
  late Future<Map<String, dynamic>> Function() profileResponse;

  setUp(() {
    api = _MockApiService();
    secureStore = <String, String>{};
    owner = 'account-a';
    profileResponse = () async => _profile(owner, 1000);

    when(() => api.getUserId()).thenAnswer((_) async => owner);
    when(() => api.getUserProfile(forceRefresh: any(named: 'forceRefresh')))
        .thenAnswer((_) => profileResponse());
    when(() => api.hasCompletedOnboarding()).thenAnswer((_) async => true);

    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final args = (call.arguments as Map?) ?? const {};
        final key = args['key'] as String?;
        switch (call.method) {
          case 'write':
            secureStore[key!] = args['value'] as String;
            return null;
          case 'read':
            return secureStore[key];
          case 'delete':
            secureStore.remove(key);
            return null;
          case 'readAll':
            return Map<String, String>.from(secureStore);
          case 'deleteAll':
            secureStore.clear();
            return null;
          case 'containsKey':
            return secureStore.containsKey(key);
          default:
            return null;
        }
      },
    );
  });

  UserDataManager manager() => UserDataManager.forTesting(
        secureStorage: const FlutterSecureStorage(),
        apiService: api,
      );

  String keyFor(String account, String field) =>
      'user_cache_${UserDataManager.cacheNamespaceForOwner(account)}_$field';

  test('cache is owner-namespaced and same-account offline restart can use it',
      () async {
    final first = manager();
    await first.initialize();

    expect(
      (jsonDecode(secureStore[keyFor('account-a', 'profile')]!)
          as Map<String, dynamic>)['id'],
      'account-a',
    );
    expect(secureStore[keyFor('account-a', 'owner')], 'account-a');

    // A new manager represents a process restart. Network profile refresh
    // fails, but the exact same owner can still use its fresh durable cache.
    profileResponse = () async => throw StateError('offline');
    final restarted = manager();
    await restarted.initialize();

    final offlineProfile = await restarted.getUserProfile();
    expect(offlineProfile['id'], 'account-a');
    expect(offlineProfile['income'], 1000);
  });

  test('account B never loads account A cache', () async {
    final current = manager();
    await current.initialize();

    current.beginSessionBoundary();
    owner = 'account-b';
    profileResponse = () async => _profile('account-b', 2000);
    await current.initialize();

    final profile = await current.getUserProfile();
    expect(profile['id'], 'account-b');
    expect(profile['income'], 2000);
    expect(secureStore[keyFor('account-a', 'owner')], 'account-a');
    expect(secureStore[keyFor('account-b', 'owner')], 'account-b');
  });

  test('old account-A refresh cannot write memory or storage after boundary',
      () async {
    final current = manager();
    await current.initialize();

    final staleResponse = Completer<Map<String, dynamic>>();
    final staleStarted = Completer<void>();
    profileResponse = () {
      if (!staleStarted.isCompleted) staleStarted.complete();
      return staleResponse.future;
    };

    final staleRefresh = current.refreshUserData();
    await staleStarted.future;

    current.beginSessionBoundary();
    owner = 'account-b';
    profileResponse = () async => _profile('account-b', 2000);
    await current.initialize();

    staleResponse.complete(_profile('account-a-late', 9999));
    await staleRefresh;

    final profile = await current.getUserProfile();
    expect(profile['id'], 'account-b');
    expect(
      (jsonDecode(secureStore[keyFor('account-b', 'profile')]!)
          as Map<String, dynamic>)['id'],
      'account-b',
    );
    expect(
      (jsonDecode(secureStore[keyFor('account-a', 'profile')]!)
          as Map<String, dynamic>)['id'],
      'account-a',
      reason: 'the stale response must not overwrite account A durable cache',
    );
  });

  test('logout clears memory synchronously before secure-storage awaits',
      () async {
    final current = manager();
    await current.initialize();
    expect((await current.getUserProfile())['id'], 'account-a');

    final clearFuture = current.clearUserData();

    expect(current.getCachedOnboardingData(), isNull);
    // A concurrent profile read cannot return the old in-memory account.
    profileResponse = () async => <String, dynamic>{};
    final afterBoundary = await current.getUserProfile();
    expect(afterBoundary['id'], isNot('account-a'));

    await clearFuture;
    expect(secureStore[keyFor('account-a', 'owner')], isNull);
    expect(secureStore[keyFor('account-a', 'profile')], isNull);
  });
}

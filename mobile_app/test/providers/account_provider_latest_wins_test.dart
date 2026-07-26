import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/installment_models.dart';
import 'package:mita/models/notification_model.dart';
import 'package:mita/providers/advice_provider.dart';
import 'package:mita/providers/behavioral_provider.dart';
import 'package:mita/providers/challenges_provider.dart';
import 'package:mita/providers/goals_provider.dart';
import 'package:mita/providers/habits_provider.dart';
import 'package:mita/providers/installments_provider.dart';
import 'package:mita/providers/notifications_provider.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/installment_service.dart';
import 'package:mocktail/mocktail.dart';

class _MockApiService extends Mock implements ApiService {}

class _MockInstallmentService extends Mock implements InstallmentService {}

Map<String, dynamic> _goalJson(String id) => {
      'id': id,
      'title': 'Goal $id',
      'target_amount': 100,
      'saved_amount': 10,
      'status': 'active',
      'progress': 10,
      'created_at': '2026-07-25T00:00:00Z',
      'last_updated': '2026-07-25T00:00:00Z',
    };

Map<String, dynamic> _habitJson(String id) => {
      'id': id,
      'title': 'Habit $id',
      'description': '',
      'target_frequency': 'daily',
      'created_at': '2026-07-25T00:00:00Z',
      'completed_dates': <String>[],
      'current_streak': 0,
      'longest_streak': 0,
      'completion_rate': 0,
    };

NotificationModel _notification(String id) {
  final timestamp = DateTime.utc(2026, 7, 25);
  return NotificationModel(
    id: id,
    userId: 'account',
    title: id,
    message: 'Message $id',
    type: 'info',
    priority: 'medium',
    status: 'delivered',
    isRead: false,
    createdAt: timestamp,
    updatedAt: timestamp,
  );
}

Map<String, dynamic> _notificationResponse(String id, {int unread = 1}) => {
      'notifications': [_notification(id).toJson()],
      'unread_count': unread,
      'total': 1,
      'has_more': false,
    };

InstallmentsSummary _summary(String owner) => InstallmentsSummary(
      totalActive: 0,
      totalCompleted: 0,
      totalMonthlyPayment: 0,
      installments: const [],
      currentInstallmentLoad: 0,
      loadMessage: owner,
    );

void main() {
  test('GoalsProvider keeps the newest same-session list response', () async {
    final api = _MockApiService();
    final first = Completer<List<dynamic>>();
    final second = Completer<List<dynamic>>();
    var calls = 0;
    when(
      () => api.getGoals(
        status: any(named: 'status'),
        category: any(named: 'category'),
      ),
    ).thenAnswer((_) => (++calls == 1 ? first : second).future);

    final provider = GoalsProvider(apiService: api);
    final oldLoad = provider.loadGoals();
    final newLoad = provider.loadGoals();

    second.complete([_goalJson('new')]);
    await newLoad;
    first.complete([_goalJson('old')]);
    await oldLoad;

    expect(provider.goals.single.id, 'new');
    expect(provider.isLoading, isFalse);
  });

  test('GoalsProvider invalidates a list before a pending mutation', () async {
    final api = _MockApiService();
    final staleList = Completer<List<dynamic>>();
    final delete = Completer<void>();
    var listCalls = 0;
    when(
      () => api.getGoals(
        status: any(named: 'status'),
        category: any(named: 'category'),
      ),
    ).thenAnswer((_) {
      listCalls += 1;
      if (listCalls == 1) return Future.value([_goalJson('kept')]);
      if (listCalls == 2) return staleList.future;
      return Future.value(<dynamic>[]);
    });
    when(api.getGoalStatistics).thenAnswer((_) async => <String, dynamic>{});
    when(() => api.deleteGoal('kept')).thenAnswer((_) => delete.future);

    final provider = GoalsProvider(apiService: api);
    await provider.loadGoals();
    final oldLoad = provider.loadGoals();
    final mutation = provider.deleteGoal('kept');

    staleList.complete([_goalJson('stale')]);
    await oldLoad;
    expect(provider.goals.single.id, 'kept');

    delete.complete();
    expect(await mutation, isTrue);
    expect(provider.goals, isEmpty);
  });

  test('ChallengesProvider keeps newest aggregate and per-item progress',
      () async {
    final api = _MockApiService();
    final firstList = Completer<List<dynamic>>();
    final secondList = Completer<List<dynamic>>();
    final firstProgress = Completer<Map<String, dynamic>>();
    final secondProgress = Completer<Map<String, dynamic>>();
    var listCalls = 0;
    var progressCalls = 0;

    when(api.getChallenges)
        .thenAnswer((_) => (++listCalls == 1 ? firstList : secondList).future);
    when(api.getAvailableChallenges).thenAnswer((_) async => <dynamic>[]);
    when(api.getGameificationStats)
        .thenAnswer((_) async => <String, dynamic>{});
    when(
      () => api.getLeaderboard(period: any(named: 'period')),
    ).thenAnswer((_) async => <dynamic>[]);
    when(() => api.getChallengeProgress('shared')).thenAnswer(
      (_) => (++progressCalls == 1 ? firstProgress : secondProgress).future,
    );

    final provider = ChallengesProvider(apiService: api);
    final oldLoad = provider.loadChallengeData();
    final newLoad = provider.loadChallengeData();
    secondList.complete([
      {'id': 'new'}
    ]);
    await newLoad;
    firstList.complete([
      {'id': 'old'}
    ]);
    await oldLoad;
    expect(provider.activeChallenges.single['id'], 'new');

    final oldProgressLoad = provider.loadChallengeProgress('shared');
    final newProgressLoad = provider.loadChallengeProgress('shared');
    secondProgress.complete({'value': 'new'});
    await newProgressLoad;
    firstProgress.complete({'value': 'old'});
    await oldProgressLoad;
    expect(provider.challengeProgress['shared']?['value'], 'new');
  });

  test('HabitsProvider keeps newest list and progress responses', () async {
    final api = _MockApiService();
    final firstList = Completer<List<dynamic>>();
    final secondList = Completer<List<dynamic>>();
    final firstProgress = Completer<Map<String, dynamic>>();
    final secondProgress = Completer<Map<String, dynamic>>();
    var listCalls = 0;
    var progressCalls = 0;
    when(api.getHabits).thenAnswer((_) {
      listCalls += 1;
      if (listCalls == 1) return firstList.future;
      if (listCalls == 2) return secondList.future;
      return Future.value([_habitJson('shared')]);
    });
    when(() => api.getHabitProgress('shared')).thenAnswer(
      (_) => (++progressCalls == 1 ? firstProgress : secondProgress).future,
    );

    final provider = HabitsProvider(apiService: api);
    final oldLoad = provider.loadHabits();
    final newLoad = provider.loadHabits();
    secondList.complete([_habitJson('shared')]);
    await newLoad;
    firstList.complete([_habitJson('old')]);
    await oldLoad;
    expect(provider.habits.single.id, 'shared');

    await provider.loadHabits();
    secondProgress.complete({'owner': 'new'});
    await pumpEventQueue();
    firstProgress.complete({'owner': 'old'});
    await pumpEventQueue();
    expect(provider.habitProgress['shared']?['owner'], 'new');
  });

  test('HabitsProvider invalidates a list before delete completes', () async {
    final api = _MockApiService();
    final staleList = Completer<List<dynamic>>();
    final delete = Completer<void>();
    var listCalls = 0;
    when(api.getHabits).thenAnswer((_) {
      listCalls += 1;
      if (listCalls == 1) return Future.value([_habitJson('kept')]);
      return staleList.future;
    });
    when(() => api.getHabitProgress(any()))
        .thenAnswer((_) async => <String, dynamic>{});
    when(() => api.deleteHabit('kept')).thenAnswer((_) => delete.future);

    final provider = HabitsProvider(apiService: api);
    await provider.loadHabits();
    final oldLoad = provider.loadHabits();
    final mutation = provider.deleteHabit('kept');

    staleList.complete([_habitJson('stale')]);
    await oldLoad;
    expect(provider.habits.single.id, 'kept');

    delete.complete();
    expect(await mutation, isTrue);
    expect(provider.habits, isEmpty);
  });

  test('AdviceProvider keeps the newest aggregate response', () async {
    final api = _MockApiService();
    final first = Completer<List<dynamic>>();
    final second = Completer<List<dynamic>>();
    var historyCalls = 0;
    var latestCalls = 0;
    when(api.getAdviceHistory)
        .thenAnswer((_) => (++historyCalls == 1 ? first : second).future);
    when(api.getLatestAdvice).thenAnswer(
      (_) async => {'owner': ++latestCalls == 1 ? 'old' : 'new'},
    );

    final provider = AdviceProvider(apiService: api);
    final oldLoad = provider.loadAdviceData();
    final newLoad = provider.loadAdviceData();
    second.complete([
      {'owner': 'new'}
    ]);
    await newLoad;
    first.complete([
      {'owner': 'old'}
    ]);
    await oldLoad;

    expect(
      (provider.adviceHistory.single as Map<String, dynamic>)['owner'],
      'new',
    );
    expect(provider.latestAdvice?['owner'], 'new');
    expect(provider.state, AdviceState.loaded);
  });

  test('BehavioralProvider keeps newest same-resource response', () async {
    final api = _MockApiService();
    final first = Completer<Map<String, dynamic>>();
    final second = Completer<Map<String, dynamic>>();
    var calls = 0;
    when(
      () => api.getSpendingPatterns(
        year: any(named: 'year'),
        month: any(named: 'month'),
      ),
    ).thenAnswer((_) => (++calls == 1 ? first : second).future);

    final provider = BehavioralProvider(apiService: api);
    final oldLoad = provider.loadSpendingPatterns(year: 2026, month: 6);
    final newLoad = provider.loadSpendingPatterns(year: 2026, month: 7);
    second.complete({'owner': 'new'});
    await newLoad;
    first.complete({'owner': 'old'});
    await oldLoad;

    expect(provider.patterns['owner'], 'new');
  });

  test('NotificationsProvider keeps newest list and unread-count responses',
      () async {
    final api = _MockApiService();
    final firstList = Completer<Map<String, dynamic>>();
    final secondList = Completer<Map<String, dynamic>>();
    final firstCount = Completer<int>();
    final secondCount = Completer<int>();
    var listCalls = 0;
    var countCalls = 0;
    when(
      () => api.getNotifications(
        unreadOnly: any(named: 'unreadOnly'),
        type: any(named: 'type'),
        priority: any(named: 'priority'),
        limit: any(named: 'limit'),
      ),
    ).thenAnswer(
      (_) => (++listCalls == 1 ? firstList : secondList).future,
    );
    when(api.getUnreadNotificationCount).thenAnswer(
      (_) => (++countCalls == 1 ? firstCount : secondCount).future,
    );

    final provider = NotificationsProvider(apiService: api);
    final oldLoad = provider.loadNotifications(refresh: true);
    final newLoad = provider.loadNotifications(refresh: true);
    secondList.complete(_notificationResponse('new', unread: 2));
    await newLoad;
    firstList.complete(_notificationResponse('old', unread: 1));
    await oldLoad;
    expect(provider.notifications.single.id, 'new');
    expect(provider.unreadCount, 2);

    final oldCountLoad = provider.fetchUnreadCount();
    final newCountLoad = provider.fetchUnreadCount();
    secondCount.complete(4);
    await newCountLoad;
    firstCount.complete(3);
    await oldCountLoad;
    expect(provider.unreadCount, 4);
  });

  test(
      'NotificationsProvider rejects a list already running when delete starts',
      () async {
    final api = _MockApiService();
    final staleList = Completer<Map<String, dynamic>>();
    final delete = Completer<bool>();
    var listCalls = 0;
    when(
      () => api.getNotifications(
        unreadOnly: any(named: 'unreadOnly'),
        type: any(named: 'type'),
        priority: any(named: 'priority'),
        limit: any(named: 'limit'),
      ),
    ).thenAnswer((_) {
      listCalls += 1;
      return listCalls == 1
          ? Future.value(_notificationResponse('kept'))
          : staleList.future;
    });
    when(() => api.deleteNotification('kept')).thenAnswer((_) => delete.future);

    final provider = NotificationsProvider(apiService: api);
    await provider.loadNotifications();
    final oldLoad = provider.loadNotifications(refresh: true);
    final mutation = provider.deleteNotification(provider.notifications.single);

    staleList.complete(_notificationResponse('stale'));
    await oldLoad;
    expect(provider.notifications.single.id, 'kept');

    delete.complete(true);
    expect(await mutation, isTrue);
    expect(provider.notifications, isEmpty);
  });

  test('InstallmentsProvider keeps newest filtered response', () async {
    final service = _MockInstallmentService();
    final first = Completer<InstallmentsSummary>();
    final second = Completer<InstallmentsSummary>();
    var calls = 0;
    when(
      () => service.getInstallments(
        status: any(named: 'status'),
      ),
    ).thenAnswer((_) => (++calls == 1 ? first : second).future);

    final provider = InstallmentsProvider(service: service);
    final oldLoad = provider.loadInstallments(status: InstallmentStatus.active);
    final newLoad =
        provider.loadInstallments(status: InstallmentStatus.completed);
    second.complete(_summary('new'));
    await newLoad;
    first.complete(_summary('old'));
    await oldLoad;

    expect(provider.summary?.loadMessage, 'new');
    expect(provider.state, InstallmentsState.loaded);
    expect(provider.isLoading, isFalse);
  });
}

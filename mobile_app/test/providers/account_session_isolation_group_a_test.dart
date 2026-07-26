import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/providers/advice_provider.dart';
import 'package:mita/providers/challenges_provider.dart';
import 'package:mita/providers/goals_provider.dart';
import 'package:mita/providers/habits_provider.dart';
import 'package:mita/services/api_service.dart';
import 'package:mocktail/mocktail.dart';

class _MockApiService extends Mock implements ApiService {}

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

void main() {
  test('GoalsProvider reset rejects old load and can initialize new session',
      () async {
    final api = _MockApiService();
    final accountA = Completer<List<dynamic>>();
    var goalRequest = 0;

    when(
      () => api.getGoals(
        status: any(named: 'status'),
        category: any(named: 'category'),
      ),
    ).thenAnswer((_) {
      goalRequest += 1;
      return goalRequest == 1
          ? accountA.future
          : Future<List<dynamic>>.value([_goalJson('account-b')]);
    });
    when(api.getGoalStatistics).thenAnswer(
      (_) async => {'total_goals': 1},
    );

    final provider = GoalsProvider(apiService: api);
    final oldLoad = provider.loadGoals();
    expect(provider.isLoading, isTrue);

    var notifications = 0;
    provider.addListener(() => notifications += 1);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, GoalsState.initial);
    expect(provider.goals, isEmpty);
    expect(provider.statistics, isEmpty);
    expect(provider.selectedStatus, isNull);
    expect(provider.selectedCategory, isNull);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);
    expect(provider.recommendations, isEmpty);
    expect(provider.opportunities, isEmpty);
    expect(provider.adjustments, isEmpty);
    expect(provider.isLoadingRecommendations, isFalse);

    accountA.complete([_goalJson('account-a')]);
    await oldLoad;

    expect(notifications, 1);
    expect(provider.goals, isEmpty);
    expect(provider.state, GoalsState.initial);

    await provider.initialize();
    expect(provider.state, GoalsState.loaded);
    expect(provider.goals.single.id, 'account-b');
    expect(provider.totalGoals, 1);
  });

  test('ChallengesProvider reset rejects old aggregate and progress loads',
      () async {
    final api = _MockApiService();
    final oldChallenges = Completer<List<dynamic>>();
    final oldProgress = Completer<Map<String, dynamic>>();
    var challengeRequest = 0;

    when(api.getChallenges).thenAnswer((_) {
      challengeRequest += 1;
      return challengeRequest == 1
          ? oldChallenges.future
          : Future<List<dynamic>>.value([
              {'id': 'account-b', 'title': 'B'}
            ]);
    });
    when(api.getAvailableChallenges).thenAnswer((_) async => <dynamic>[]);
    when(api.getGameificationStats).thenAnswer(
      (_) async => {'total_points': 20},
    );
    when(
      () => api.getLeaderboard(period: any(named: 'period')),
    ).thenAnswer((_) async => <dynamic>[]);
    when(() => api.getChallengeProgress('account-a'))
        .thenAnswer((_) => oldProgress.future);
    when(() => api.getChallengeProgress('account-b')).thenAnswer(
      (_) async => {'current_progress': 2},
    );

    final provider = ChallengesProvider(apiService: api);
    final oldLoad = provider.loadChallengeData();
    final oldProgressLoad = provider.loadChallengeProgress('account-a');

    var notifications = 0;
    provider.addListener(() => notifications += 1);
    provider.resetSession();
    expect(notifications, 1);
    expect(provider.state, ChallengesState.initial);
    expect(provider.activeChallenges, isEmpty);
    expect(provider.availableChallenges, isEmpty);
    expect(provider.gamificationStats, isEmpty);
    expect(provider.leaderboard, isEmpty);
    expect(provider.challengeProgress, isEmpty);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);

    oldChallenges.complete([
      {'id': 'account-a', 'title': 'A'}
    ]);
    await oldLoad;
    oldProgress.complete({'current_progress': 99});
    await oldProgressLoad;

    expect(notifications, 1);
    expect(provider.activeChallenges, isEmpty);
    expect(provider.challengeProgress, isEmpty);

    await provider.initialize();
    await Future<void>.delayed(Duration.zero);
    expect(provider.state, ChallengesState.loaded);
    expect(provider.activeChallenges.single['id'], 'account-b');
    expect(provider.totalPoints, 20);
    expect(provider.challengeProgress['account-b']?['current_progress'], 2);
  });

  test('HabitsProvider reset rejects old load and stale delete completion',
      () async {
    final api = _MockApiService();
    final accountA = Completer<List<dynamic>>();
    final staleDelete = Completer<void>();
    var habitRequest = 0;

    when(api.getHabits).thenAnswer((_) {
      habitRequest += 1;
      return habitRequest == 1
          ? accountA.future
          : Future<List<dynamic>>.value([_habitJson('account-b')]);
    });
    when(() => api.getHabitProgress(any())).thenAnswer(
      (_) async => {'completion_percentage': 10},
    );
    when(() => api.deleteHabit('account-a'))
        .thenAnswer((_) => staleDelete.future);

    final provider = HabitsProvider(apiService: api);
    final oldLoad = provider.loadHabits();

    var notifications = 0;
    provider.addListener(() => notifications += 1);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, HabitsState.initial);
    expect(provider.habits, isEmpty);
    expect(provider.habitProgress, isEmpty);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);

    accountA.complete([_habitJson('account-a')]);
    await oldLoad;
    expect(notifications, 1);
    expect(provider.habits, isEmpty);

    await provider.initialize();
    await Future<void>.delayed(Duration.zero);
    expect(provider.habits.single.id, 'account-b');

    final staleDeleteResult = provider.deleteHabit('account-a');
    provider.resetSession();
    await provider.initialize();
    staleDelete.complete();

    expect(await staleDeleteResult, isFalse);
    expect(provider.habits.single.id, 'account-b');
  });

  test('AdviceProvider reset rejects old advice and restores initial state',
      () async {
    final api = _MockApiService();
    final accountA = Completer<List<dynamic>>();
    var historyRequest = 0;

    when(api.getAdviceHistory).thenAnswer((_) {
      historyRequest += 1;
      return historyRequest == 1
          ? accountA.future
          : Future<List<dynamic>>.value([
              {'id': 'account-b'}
            ]);
    });
    when(api.getLatestAdvice).thenAnswer(
      (_) async => {'id': 'latest-b'},
    );

    final provider = AdviceProvider(apiService: api);
    final oldLoad = provider.loadAdviceData();

    var notifications = 0;
    provider.addListener(() => notifications += 1);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, AdviceState.initial);
    expect(provider.adviceHistory, isEmpty);
    expect(provider.latestAdvice, isNull);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);

    accountA.complete([
      {'id': 'account-a'}
    ]);
    await oldLoad;

    expect(notifications, 1);
    expect(provider.adviceHistory, isEmpty);
    expect(provider.latestAdvice, isNull);

    await provider.initialize();
    expect(provider.state, AdviceState.loaded);
    expect(
      (provider.adviceHistory.single as Map<String, dynamic>)['id'],
      'account-b',
    );
    expect(provider.latestAdvice?['id'], 'latest-b');
  });
}

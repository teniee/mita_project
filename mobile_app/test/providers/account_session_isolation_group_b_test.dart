import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mita/models/installment_models.dart';
import 'package:mita/models/notification_model.dart';
import 'package:mita/providers/behavioral_provider.dart';
import 'package:mita/providers/installments_provider.dart';
import 'package:mita/providers/mood_provider.dart';
import 'package:mita/providers/notifications_provider.dart';
import 'package:mita/services/api_service.dart';
import 'package:mita/services/installment_service.dart';
import 'package:mocktail/mocktail.dart';

class _MockApiService extends Mock implements ApiService {}

class _MockInstallmentService extends Mock implements InstallmentService {}

InstallmentsSummary _installmentsSummary() {
  return const InstallmentsSummary(
    totalActive: 1,
    totalCompleted: 0,
    totalMonthlyPayment: 25,
    installments: [],
    currentInstallmentLoad: 5,
    loadMessage: 'Account A',
  );
}

Installment _installment() {
  final date = DateTime.utc(2026, 7, 25);
  return Installment(
    id: 'installment-a',
    userId: 'account-a',
    itemName: 'Phone',
    category: InstallmentCategory.electronics,
    totalAmount: 100,
    paymentAmount: 25,
    interestRate: 0,
    totalPayments: 4,
    paymentsMade: 1,
    paymentFrequency: 'monthly',
    firstPaymentDate: date,
    nextPaymentDate: date,
    finalPaymentDate: date,
    status: InstallmentStatus.active,
    createdAt: date,
    updatedAt: date,
  );
}

NotificationModel _notification() {
  final date = DateTime.utc(2026, 7, 25);
  return NotificationModel(
    id: 'notification-a',
    userId: 'account-a',
    title: 'Account A',
    message: 'Private message',
    type: 'info',
    priority: 'medium',
    status: 'delivered',
    isRead: false,
    createdAt: date,
    updatedAt: date,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('behavioral reset rejects an old account response and notifies once',
      () async {
    final api = _MockApiService();
    final response = Completer<Map<String, dynamic>>();
    when(
      () => api.getSpendingPatterns(year: 2026, month: 7),
    ).thenAnswer((_) => response.future);

    final provider = BehavioralProvider(apiService: api);
    final oldLoad = provider.loadSpendingPatterns(year: 2026, month: 7);
    expect(provider.isLoading, isTrue);

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, BehavioralState.initial);
    expect(provider.isLoading, isFalse);
    expect(provider.errorMessage, isNull);
    expect(provider.patterns, isEmpty);
    expect(provider.predictions, isEmpty);
    expect(provider.anomalies, isEmpty);
    expect(provider.insights, isEmpty);
    expect(provider.behavioralPredictions, isEmpty);
    expect(provider.adaptiveRecommendations, isEmpty);
    expect(provider.behavioralCluster, isEmpty);
    expect(provider.behavioralProgress, isEmpty);
    expect(provider.behavioralAnomalies, isEmpty);
    expect(provider.spendingTriggers, isEmpty);
    expect(provider.behavioralWarnings, isEmpty);
    expect(provider.behavioralPreferences, isEmpty);
    expect(provider.behavioralCalendar, isEmpty);
    expect(provider.behavioralExpenseSuggestions, isEmpty);
    expect(provider.behavioralNotificationSettings, isEmpty);

    response.complete({'owner': 'account-a'});
    await oldLoad;

    expect(notifications, 1);
    expect(provider.state, BehavioralState.initial);
    expect(provider.patterns, isEmpty);
  });

  test('mood reset rejects an old submission and restores initial state',
      () async {
    final api = _MockApiService();
    final response = Completer<void>();
    when(() => api.logMood(5)).thenAnswer((_) => response.future);

    final provider = MoodProvider(apiService: api);
    provider.setSelectedMood(4.6);
    final oldSubmission = provider.logMood();
    expect(provider.state, MoodState.submitting);
    expect(provider.isLoading, isTrue);

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, MoodState.initial);
    expect(provider.isLoading, isFalse);
    expect(provider.errorMessage, isNull);
    expect(provider.selectedMood, 3);
    expect(provider.hasSubmittedToday, isFalse);
    expect(provider.moodHistory, isEmpty);
    expect(provider.lastSubmissionDate, isNull);

    response.complete();
    expect(await oldSubmission, isFalse);

    expect(notifications, 1);
    expect(provider.state, MoodState.initial);
    expect(provider.hasSubmittedToday, isFalse);
  });

  test('notifications reset clears filters and rejects an old list response',
      () async {
    final api = _MockApiService();
    final response = Completer<Map<String, dynamic>>();
    when(
      () => api.getNotifications(
        unreadOnly: true,
        type: null,
        priority: null,
        limit: 100,
      ),
    ).thenAnswer((_) => response.future);

    final provider = NotificationsProvider(apiService: api);
    provider.setShowUnreadOnly(true);
    expect(provider.showUnreadOnly, isTrue);
    expect(provider.isLoading, isTrue);

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, NotificationState.initial);
    expect(provider.notifications, isEmpty);
    expect(provider.unreadCount, 0);
    expect(provider.total, 0);
    expect(provider.hasMore, isFalse);
    expect(provider.errorMessage, isNull);
    expect(provider.isLoading, isFalse);
    expect(provider.showUnreadOnly, isFalse);
    expect(provider.filterType, isNull);
    expect(provider.filterPriority, isNull);

    response.complete({
      'notifications': <Map<String, dynamic>>[],
      'unread_count': 9,
      'total': 9,
      'has_more': true,
    });
    await pumpEventQueue();

    expect(notifications, 1);
    expect(provider.state, NotificationState.initial);
    expect(provider.unreadCount, 0);
    expect(provider.total, 0);
    expect(provider.hasMore, isFalse);
  });

  test('notification mutation cannot update state after a session reset',
      () async {
    final api = _MockApiService();
    final notification = _notification();
    final response = Completer<bool>();
    when(
      () => api.getNotifications(
        unreadOnly: false,
        type: null,
        priority: null,
        limit: 100,
      ),
    ).thenAnswer(
      (_) async => {
        'notifications': [notification.toJson()],
        'unread_count': 1,
        'total': 1,
        'has_more': false,
      },
    );
    when(
      () => api.markNotificationRead(notification.id),
    ).thenAnswer((_) => response.future);

    final provider = NotificationsProvider(apiService: api);
    await provider.loadNotifications();
    final oldMutation = provider.markAsRead(notification);

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();
    response.complete(true);

    expect(await oldMutation, isFalse);
    expect(notifications, 1);
    expect(provider.state, NotificationState.initial);
    expect(provider.notifications, isEmpty);
    expect(provider.unreadCount, 0);
  });

  test('installments reset clears filter and rejects an old summary', () async {
    final service = _MockInstallmentService();
    final response = Completer<InstallmentsSummary>();
    when(
      () => service.getInstallments(status: InstallmentStatus.active),
    ).thenAnswer((_) => response.future);

    final provider = InstallmentsProvider(service: service);
    final oldLoad = provider.setFilter(InstallmentStatus.active);
    expect(provider.selectedFilter, InstallmentStatus.active);
    expect(provider.isLoading, isTrue);

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();

    expect(notifications, 1);
    expect(provider.state, InstallmentsState.initial);
    expect(provider.isLoading, isFalse);
    expect(provider.errorMessage, isNull);
    expect(provider.successMessage, isNull);
    expect(provider.summary, isNull);
    expect(provider.installments, isEmpty);
    expect(provider.selectedFilter, isNull);

    response.complete(_installmentsSummary());
    await oldLoad;

    expect(notifications, 1);
    expect(provider.state, InstallmentsState.initial);
    expect(provider.summary, isNull);
    expect(provider.selectedFilter, isNull);
  });

  test('installment mutation cannot set messages after a session reset',
      () async {
    final service = _MockInstallmentService();
    final response = Completer<Installment>();
    when(
      () => service.markPaymentMade('installment-a'),
    ).thenAnswer((_) => response.future);

    final provider = InstallmentsProvider(service: service);
    final oldMutation = provider.markPaymentMade('installment-a');

    var notifications = 0;
    provider.addListener(() => notifications++);
    provider.resetSession();
    response.complete(_installment());

    expect(await oldMutation, isFalse);
    expect(notifications, 1);
    expect(provider.state, InstallmentsState.initial);
    expect(provider.summary, isNull);
    expect(provider.errorMessage, isNull);
    expect(provider.successMessage, isNull);
  });
}

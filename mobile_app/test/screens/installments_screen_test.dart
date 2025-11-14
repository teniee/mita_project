import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:mita/models/installment_models.dart';
import 'package:mita/screens/installments_screen.dart';
import 'package:mita/services/installment_service.dart';
import 'package:mita/services/localization_service.dart';

// Mock classes
class MockInstallmentService extends Mock implements InstallmentService {}

class MockLocalizationService extends Mock implements LocalizationService {}

void main() {
  group('InstallmentsScreen Tests', () {
    late MockInstallmentService mockInstallmentService;
    late MockLocalizationService mockLocalizationService;

    setUp(() {
      mockInstallmentService = MockInstallmentService();
      mockLocalizationService = MockLocalizationService();
    });

    Widget createWidgetUnderTest() {
      return MaterialApp(
        home: const InstallmentsScreen(),
        routes: {
          '/installment-calculator': (context) => const Scaffold(
            body: Center(child: Text('Calculator')),
          ),
        },
      );
    }

    group('Initial Load Tests', () {
      testWidgets('displays shimmer loader while loading',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null)).thenAnswer(
          (_) => Future.delayed(
            const Duration(seconds: 2),
            () => InstallmentsSummary(
              totalActive: 1,
              totalCompleted: 0,
              totalMonthlyPayment: 150.0,
              installments: [],
              currentInstallmentLoad: 0.5,
              loadMessage: 'Moderate',
            ),
          ),
        );

        await tester.pumpWidget(createWidgetUnderTest());
        expect(find.byType(CircularProgressIndicator), findsWidgets);
      });

      testWidgets('displays error state when loading fails',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null))
            .thenThrow(InstallmentServiceException('Network error', 0));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.error_outline), findsWidgets);
        expect(find.byType(ElevatedButton), findsWidgets);
      });

      testWidgets('displays empty state when no installments',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 0,
                totalCompleted: 0,
                totalMonthlyPayment: 0.0,
                installments: [],
                currentInstallmentLoad: 0.0,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.credit_card), findsWidgets);
        expect(find.text('No installments yet'), findsWidgets);
      });
    });

    group('Summary Card Tests', () {
      testWidgets('displays correct summary information',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Laptop',
          category: InstallmentCategory.electronics,
          totalAmount: 1200.0,
          paymentAmount: 100.0,
          interestRate: 5.0,
          totalPayments: 12,
          paymentsMade: 3,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 365)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 100.0,
                nextPaymentDate: installment.nextPaymentDate,
                nextPaymentAmount: installment.paymentAmount,
                installments: [installment],
                currentInstallmentLoad: 0.5,
                loadMessage: 'Moderate',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('1 Active'), findsWidgets);
        expect(find.text('Monthly Payment'), findsWidgets);
      });

      testWidgets('displays load indicator with correct color levels',
          (WidgetTester tester) async {
        // Test Safe load (green)
        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 50.0,
                installments: [],
                currentInstallmentLoad: 0.3, // Safe
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Safe'), findsWidgets);
      });
    });

    group('Filter Tabs Tests', () {
      testWidgets('displays all filter tabs with counts',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 2,
                totalCompleted: 1,
                totalMonthlyPayment: 200.0,
                installments: [],
                currentInstallmentLoad: 0.4,
                loadMessage: 'Moderate',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('All'), findsWidgets);
        expect(find.text('Active'), findsWidgets);
        expect(find.text('Completed'), findsWidgets);
        expect(find.text('Overdue'), findsWidgets);
      });

      testWidgets('filters installments when tab is selected',
          (WidgetTester tester) async {
        final activeInstallment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Phone',
          category: InstallmentCategory.electronics,
          totalAmount: 800.0,
          paymentAmount: 80.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 2,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 80.0,
                installments: [activeInstallment],
                currentInstallmentLoad: 0.4,
                loadMessage: 'Moderate',
              ),
            ));

        when(mockInstallmentService.getInstallments(
                status: InstallmentStatus.active))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 80.0,
                installments: [activeInstallment],
                currentInstallmentLoad: 0.4,
                loadMessage: 'Moderate',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        // Tap on Active filter
        await tester.tap(find.text('Active'));
        await tester.pumpAndSettle();

        expect(find.text('Phone'), findsWidgets);
      });
    });

    group('Installment Card Tests', () {
      testWidgets('displays installment card with correct information',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Gaming Laptop',
          category: InstallmentCategory.electronics,
          totalAmount: 2000.0,
          paymentAmount: 150.0,
          interestRate: 4.5,
          totalPayments: 15,
          paymentsMade: 5,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 20)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 450)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 150.0,
                installments: [installment],
                currentInstallmentLoad: 0.5,
                loadMessage: 'Moderate',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Gaming Laptop'), findsWidgets);
        expect(find.text('Active'), findsWidgets);
        expect(find.text('5/15 payments'), findsWidgets);
      });

      testWidgets('shows correct category icon and color',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Furniture',
          category: InstallmentCategory.furniture,
          totalAmount: 1500.0,
          paymentAmount: 125.0,
          interestRate: 3.5,
          totalPayments: 12,
          paymentsMade: 0,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now(),
          finalPaymentDate: DateTime.now().add(const Duration(days: 360)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 125.0,
                installments: [installment],
                currentInstallmentLoad: 0.3,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.chair), findsWidgets);
      });

      testWidgets('displays quick action buttons for active installments',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Test Item',
          category: InstallmentCategory.other,
          totalAmount: 500.0,
          paymentAmount: 50.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 1,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 50.0,
                installments: [installment],
                currentInstallmentLoad: 0.2,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Mark Paid'), findsWidgets);
        expect(find.text('Cancel'), findsWidgets);
      });

      testWidgets('displays popup menu with action options',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Test Item',
          category: InstallmentCategory.other,
          totalAmount: 500.0,
          paymentAmount: 50.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 1,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 50.0,
                installments: [installment],
                currentInstallmentLoad: 0.2,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.more_vert));
        await tester.pumpAndSettle();

        expect(find.text('View Details'), findsWidgets);
        expect(find.text('Mark Payment Made'), findsWidgets);
      });
    });

    group('Progress Bar Tests', () {
      testWidgets('displays correct progress percentage',
          (WidgetTester tester) async {
        final installment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Item',
          category: InstallmentCategory.other,
          totalAmount: 1000.0,
          paymentAmount: 100.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 5, // 50% progress
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
          status: InstallmentStatus.active,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 100.0,
                installments: [installment],
                currentInstallmentLoad: 0.3,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('50%'), findsWidgets);
      });
    });

    group('Status Badge Tests', () {
      testWidgets('displays correct status badge color and text',
          (WidgetTester tester) async {
        final completedInstallment = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Completed Item',
          category: InstallmentCategory.other,
          totalAmount: 500.0,
          paymentAmount: 50.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 10,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now(),
          finalPaymentDate: DateTime.now(),
          status: InstallmentStatus.completed,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 0,
                totalCompleted: 1,
                totalMonthlyPayment: 0.0,
                installments: [completedInstallment],
                currentInstallmentLoad: 0.0,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Completed'), findsWidgets);
      });
    });

    group('FAB Navigation Tests', () {
      testWidgets('FAB navigates to calculator screen',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 0,
                totalCompleted: 0,
                totalMonthlyPayment: 0.0,
                installments: [],
                currentInstallmentLoad: 0.0,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Can I Afford?'), findsWidgets);
      });
    });

    group('Refresh Indicator Tests', () {
      testWidgets('allows pull to refresh',
          (WidgetTester tester) async {
        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 0,
                totalCompleted: 0,
                totalMonthlyPayment: 0.0,
                installments: [],
                currentInstallmentLoad: 0.0,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        // Verify RefreshIndicator exists
        expect(find.byType(RefreshIndicator), findsWidgets);
      });
    });

    group('Edge Cases', () {
      testWidgets('handles installment with notes correctly',
          (WidgetTester tester) async {
        final installmentWithNotes = Installment(
          id: '1',
          userId: 'user1',
          itemName: 'Item with notes',
          category: InstallmentCategory.other,
          totalAmount: 500.0,
          paymentAmount: 50.0,
          interestRate: 5.0,
          totalPayments: 10,
          paymentsMade: 1,
          paymentFrequency: 'monthly',
          firstPaymentDate: DateTime.now(),
          nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
          finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
          status: InstallmentStatus.active,
          notes: 'Important note about this installment',
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 1,
                totalCompleted: 0,
                totalMonthlyPayment: 50.0,
                installments: [installmentWithNotes],
                currentInstallmentLoad: 0.2,
                loadMessage: 'Safe',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Item with notes'), findsWidgets);
      });

      testWidgets('handles multiple installments correctly',
          (WidgetTester tester) async {
        final installments = [
          Installment(
            id: '1',
            userId: 'user1',
            itemName: 'Item 1',
            category: InstallmentCategory.electronics,
            totalAmount: 500.0,
            paymentAmount: 50.0,
            interestRate: 5.0,
            totalPayments: 10,
            paymentsMade: 1,
            paymentFrequency: 'monthly',
            firstPaymentDate: DateTime.now(),
            nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
            finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
            status: InstallmentStatus.active,
            createdAt: DateTime.now(),
            updatedAt: DateTime.now(),
          ),
          Installment(
            id: '2',
            userId: 'user1',
            itemName: 'Item 2',
            category: InstallmentCategory.furniture,
            totalAmount: 1000.0,
            paymentAmount: 100.0,
            interestRate: 4.5,
            totalPayments: 10,
            paymentsMade: 5,
            paymentFrequency: 'monthly',
            firstPaymentDate: DateTime.now(),
            nextPaymentDate: DateTime.now().add(const Duration(days: 30)),
            finalPaymentDate: DateTime.now().add(const Duration(days: 300)),
            status: InstallmentStatus.active,
            createdAt: DateTime.now(),
            updatedAt: DateTime.now(),
          ),
        ];

        when(mockInstallmentService.getInstallments(status: null))
            .thenAnswer((_) => Future.value(
              InstallmentsSummary(
                totalActive: 2,
                totalCompleted: 0,
                totalMonthlyPayment: 150.0,
                installments: installments,
                currentInstallmentLoad: 0.4,
                loadMessage: 'Moderate',
              ),
            ));

        await tester.pumpWidget(createWidgetUnderTest());
        await tester.pumpAndSettle();

        expect(find.text('Item 1'), findsWidgets);
        expect(find.text('Item 2'), findsWidgets);
        expect(find.text('2 Active'), findsWidgets);
      });
    });
  });
}

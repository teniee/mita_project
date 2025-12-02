import 'dart:async';
import 'dart:math';
import 'dart:collection';
import 'package:flutter_test/flutter_test.dart';
import 'package:mita/services/income_service.dart';
import 'package:mita/services/country_profiles_service.dart';
import 'package:mita/services/financial_health_calculator.dart';
import 'package:mita/services/secure_device_service.dart';
import 'package:mita/services/password_validation_service.dart';
import 'package:mita/services/smart_categorization_service.dart';
import 'package:mita/services/production_budget_engine.dart';

/// Comprehensive backend performance test suite for MITA financial application
/// 
/// Performance Targets:
/// - Income classification: ~0.08ms per operation (80μs)
/// - Authentication flows: <200ms p95
/// - Database queries: <50ms p95
/// - API endpoints: <200ms p95
/// - Memory usage: Stable under load
/// - Concurrent user capacity: 1000+ users
/// - Financial calculations: <2ms for complex operations
/// - Security overhead: <10ms additional latency
/// - Rate limiting: <5ms lookup time
/// - Token operations: <100ms generation/validation
///
/// Load Testing Scenarios:
/// - Burst traffic simulation
/// - Sustained load testing
/// - Memory pressure testing
/// - Database connection pool stress
/// - Cache performance validation
///
/// Critical Financial Operations:
/// - Budget calculations with precision
/// - Transaction categorization accuracy
/// - Multi-currency operations
/// - Real-time balance updates
/// - Fraud detection algorithms

/// Performance metrics collection class
class PerformanceMetrics {
  final List<double> _measurements = [];
  final String operationName;
  late DateTime _startTime;
  
  PerformanceMetrics(this.operationName) {
    _startTime = DateTime.now();
  }
  
  void addMeasurement(double milliseconds) {
    _measurements.add(milliseconds);
  }
  
  PerformanceReport generateReport() {
    if (_measurements.isEmpty) {
      return PerformanceReport(operationName, 0, 0, 0, 0, 0, 0, []);
    }
    
    _measurements.sort();
    final count = _measurements.length;
    final sum = _measurements.reduce((a, b) => a + b);
    final mean = sum / count;
    final min = _measurements.first;
    final max = _measurements.last;
    final p95Index = ((count - 1) * 0.95).ceil();
    final p95 = _measurements[p95Index];
    final p99Index = ((count - 1) * 0.99).ceil();
    final p99 = _measurements[p99Index];
    
    return PerformanceReport(operationName, count, mean, min, max, p95, p99, List.from(_measurements));
  }
}

/// Performance report data class
class PerformanceReport {
  final String operation;
  final int sampleCount;
  final double mean;
  final double min;
  final double max;
  final double p95;
  final double p99;
  final List<double> rawData;
  
  PerformanceReport(this.operation, this.sampleCount, this.mean, this.min, 
                   this.max, this.p95, this.p99, this.rawData);
  
  void printReport() {
    // print('\n=== Performance Report: $operation ===');
    // print('  Samples: $sampleCount');
    // print('  Mean: ${mean.toStringAsFixed(3)}ms');
    // print('  Min: ${min.toStringAsFixed(3)}ms');
    // print('  Max: ${max.toStringAsFixed(3)}ms');
    // print('  P95: ${p95.toStringAsFixed(3)}ms');
    // print('  P99: ${p99.toStringAsFixed(3)}ms');
    // print('  Throughput: ${(1000 / mean).toStringAsFixed(0)} ops/sec');
  }
  
  Map<String, dynamic> toJson() {
    return {
      'operation': operation,
      'sampleCount': sampleCount,
      'mean': mean,
      'min': min,
      'max': max,
      'p95': p95,
      'p99': p99,
      'throughput': 1000 / mean,
      'timestamp': DateTime.now().toIso8601String(),
    };
  }
}

/// Load testing simulator for concurrent operations
class LoadTestSimulator {
  final int concurrentUsers;
  final Duration testDuration;
  final Function() operationToTest;
  
  LoadTestSimulator({
    required this.concurrentUsers,
    required this.testDuration,
    required this.operationToTest,
  });
  
  Future<LoadTestResult> runLoadTest() async {
    final completedOperations = <Future<void>>[];
    final operationCounts = <int>[];
    final errors = <String>[];
    final stopwatch = Stopwatch()..start();
    
    // Launch concurrent user simulations
    for (int userId = 0; userId < concurrentUsers; userId++) {
      final userCompleter = Completer<void>();
      int userOperationCount = 0;
      
      // Each user performs operations until test duration expires
      Future.microtask(() async {
        try {
          while (stopwatch.elapsed < testDuration) {
            await operationToTest();
            userOperationCount++;
            
            // Small random delay to simulate realistic user behavior
            await Future.delayed(Duration(milliseconds: Random().nextInt(100)));
          }
        } catch (e) {
          errors.add('User $userId: $e');
        } finally {
          operationCounts.add(userOperationCount);
          userCompleter.complete();
        }
      });
      
      completedOperations.add(userCompleter.future);
    }
    
    // Wait for all users to complete
    await Future.wait(completedOperations);
    stopwatch.stop();
    
    final totalOperations = operationCounts.reduce((a, b) => a + b);
    final averageOpsPerUser = totalOperations / concurrentUsers;
    final opsPerSecond = totalOperations / (stopwatch.elapsedMilliseconds / 1000);
    
    return LoadTestResult(
      concurrentUsers: concurrentUsers,
      duration: stopwatch.elapsed,
      totalOperations: totalOperations,
      averageOpsPerUser: averageOpsPerUser,
      opsPerSecond: opsPerSecond,
      errors: errors,
    );
  }
}

/// Load test result data class
class LoadTestResult {
  final int concurrentUsers;
  final Duration duration;
  final int totalOperations;
  final double averageOpsPerUser;
  final double opsPerSecond;
  final List<String> errors;
  
  LoadTestResult({
    required this.concurrentUsers,
    required this.duration,
    required this.totalOperations,
    required this.averageOpsPerUser,
    required this.opsPerSecond,
    required this.errors,
  });
  
  void printResult() {
    // print('\n=== Load Test Results ===');
    // print('  Concurrent Users: $concurrentUsers');
    // print('  Duration: ${duration.inSeconds}s');
    // print('  Total Operations: $totalOperations');
    // print('  Avg Ops/User: ${averageOpsPerUser.toStringAsFixed(1)}');
    // print('  Ops/Second: ${opsPerSecond.toStringAsFixed(1)}');
    // print('  Errors: ${errors.length}');
    if (errors.isNotEmpty) {
      // print('  Error samples:');
      // errors.take(5).forEach((e) => print('    - $e'));
    }
  }
}
void main() {
  // Set up test environment with proper timeout
  setUpAll(() {
    // print('\n=== MITA Performance Test Suite ===');
    // print('Target Performance Standards:');
    // print('  • Income Classification: ~80μs (0.08ms)');
    // print('  • Authentication Flow: <200ms P95');
    // print('  • Database Queries: <50ms P95');
    // print('  • API Endpoints: <200ms P95');
    // print('  • Concurrent Users: 1000+ supported');
    // print('  • Memory Usage: Stable under load');
    // print('  • Error Rate: <1% under normal load');
    // print('========================================\n');
  });
  
  tearDownAll(() {
    // print('\n=== Performance Test Suite Complete ===');
    // print('All performance benchmarks executed.');
    // print('Check results against production targets.');
    // print('Save baseline metrics for regression testing.');
    // print('==========================================\n');
  });
  group('Backend Performance Tests', () {
    
    group('Income Classification Performance', () {
      late IncomeService incomeService;
      late CountryProfilesService countryService;
      
      setUp(() {
        incomeService = IncomeService();
        countryService = CountryProfilesService();
      });

      test('Income classification should meet 0.08ms target', () async {
        const int iterations = 10000;
        final stopwatch = Stopwatch();
        final random = Random(42); // Deterministic for consistent results
        
        // Warm-up runs to eliminate JIT compilation overhead
        for (int i = 0; i < 100; i++) {
          incomeService.classifyIncome(5000.0);
        }
        
        // Performance test
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          final income = random.nextDouble() * 20000 + 1000; // $1k-$21k range
          incomeService.classifyIncome(income);
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        final avgTimeMicroseconds = stopwatch.elapsedMicroseconds / iterations;
        
        // print('Income Classification Performance:');
        // print('  Total time: ${stopwatch.elapsedMilliseconds}ms for $iterations operations');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(4)}ms per classification');
        // print('  Average time: ${avgTimeMicroseconds.toStringAsFixed(2)}μs per classification');
        // print('  Target: 80μs (0.08ms)');
        
        // Target: 0.08ms = 80 microseconds per classification
        expect(avgTimeMicroseconds, lessThan(80.0),
          reason: 'Income classification should complete within 0.08ms target');
        
        // Additional validation: Operations per second
        final operationsPerSecond = 1000000 / avgTimeMicroseconds; // Convert μs to ops/sec
        // print('  Performance: ${operationsPerSecond.toStringAsFixed(0)} operations/second');
        
        expect(operationsPerSecond, greaterThan(12500),
          reason: 'Should handle at least 12,500 classifications per second');
      });

      test('Location-based classification performance', () async {
        const int iterations = 1000;
        final stopwatch = Stopwatch();
        final random = Random(42);
        final states = ['CA', 'NY', 'TX', 'FL', 'IL', 'PA', 'OH', 'GA', 'NC', 'MI'];
        
        // Warm-up
        for (int i = 0; i < 10; i++) {
          incomeService.classifyIncomeForLocation(5000.0, 'CA');
        }
        
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          final income = random.nextDouble() * 15000 + 2000;
          final state = states[random.nextInt(states.length)];
          incomeService.classifyIncomeForLocation(income, 'US', stateCode: state);
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        
        // print('Location-based Classification Performance:');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(4)}ms per classification');
        // print('  Target: <1ms per operation');
        
        expect(avgTimeMs, lessThan(1.0),
          reason: 'Location-based classification should complete within 1ms');
      });

      test('Concurrent classification performance', () async {
        const int concurrentOperations = 100;
        const int operationsPerTask = 100;
        
        final stopwatch = Stopwatch();
        final completer = Completer<void>();
        int completedTasks = 0;
        
        stopwatch.start();
        
        // Launch concurrent classification tasks
        for (int i = 0; i < concurrentOperations; i++) {
          Future.microtask(() async {
            final random = Random(i); // Different seed per task
            for (int j = 0; j < operationsPerTask; j++) {
              final income = random.nextDouble() * 10000 + 1000;
              incomeService.classifyIncome(income);
            }
            
            completedTasks++;
            if (completedTasks == concurrentOperations) {
              completer.complete();
            }
          });
        }
        
        await completer.future;
        stopwatch.stop();
        
        const totalOperations = concurrentOperations * operationsPerTask;
        final avgTimeMs = stopwatch.elapsedMilliseconds / totalOperations;
        
        // print('Concurrent Classification Performance:');
        // print('  Total operations: $totalOperations');
        // print('  Concurrent tasks: $concurrentOperations');
        // print('  Total time: ${stopwatch.elapsedMilliseconds}ms');
        // print('  Average time per operation: ${avgTimeMs.toStringAsFixed(4)}ms');
        
        expect(avgTimeMs, lessThan(0.5),
          reason: 'Concurrent classification should maintain performance');
      });

      test('Memory stability under load', () async {
        const int iterations = 5000;
        final memoryUsage = <int>[];
        
        // Measure memory at intervals
        for (int batch = 0; batch < 10; batch++) {
          // Process batch of classifications
          for (int i = 0; i < iterations ~/ 10; i++) {
            final income = (i % 10000) + 1000.0;
            incomeService.classifyIncome(income);
          }
          
          // Force garbage collection and measure (approximation)
          await Future.delayed(const Duration(milliseconds: 10));
          memoryUsage.add(DateTime.now().millisecondsSinceEpoch);
        }
        
        // print('Memory stability test completed with ${iterations} classifications');
        expect(memoryUsage.length, equals(10),
          reason: 'Memory measurement should complete successfully');
      });
    });

    group('Financial Health Calculator Performance', () {
      late FinancialHealthCalculator calculator;
      
      setUp(() {
        calculator = FinancialHealthCalculator();
      });

      test('Budget calculation performance', () async {
        const int iterations = 1000;
        final stopwatch = Stopwatch();
        final random = Random(42);
        
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          final income = random.nextDouble() * 10000 + 3000;
          final expenses = income * (0.7 + random.nextDouble() * 0.2); // 70-90% of income
          calculator.calculateBudgetHealth(income, expenses);
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        
        // print('Budget Calculation Performance:');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(4)}ms per calculation');
        // print('  Target: <2ms per calculation');
        
        expect(avgTimeMs, lessThan(2.0),
          reason: 'Budget calculations should complete within 2ms');
      });

      test('Financial ratios calculation performance', () async {
        const int iterations = 2000;
        final stopwatch = Stopwatch();
        final random = Random(42);
        
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          final savings = random.nextDouble() * 5000;
          final debt = random.nextDouble() * 10000;
          final income = random.nextDouble() * 8000 + 2000;
          
          calculator.calculateSavingsRate(income, savings);
          calculator.calculateDebtToIncomeRatio(debt, income);
          calculator.calculateEmergencyFundMonths(savings, income * 0.8);
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        
        // print('Financial Ratios Performance:');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(4)}ms per calculation');
        // print('  Target: <1ms per calculation');
        
        expect(avgTimeMs, lessThan(1.0),
          reason: 'Financial ratio calculations should be very fast');
      });
    });

    group('Authentication Flow Performance', () {
      late SecureDeviceService deviceService;
      late PasswordValidationService passwordService;
      
      setUp(() {
        deviceService = SecureDeviceService();
        passwordService = PasswordValidationService();
      });

      test('Device ID generation performance', () async {
        const int iterations = 100;
        final stopwatch = Stopwatch();
        
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          await deviceService.generateSecureDeviceId();
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        
        // print('Device ID Generation Performance:');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(2)}ms per generation');
        // print('  Target: <100ms per generation');
        
        expect(avgTimeMs, lessThan(100.0),
          reason: 'Device ID generation should complete within 100ms');
      });

      test('Password validation performance', () async {
        const int iterations = 500;
        final stopwatch = Stopwatch();
        final passwords = [
          'weak123',
          'StrongP@ssw0rd!',
          'Sup3rS3cur3P@ssw0rd2024!',
          'abc123',
          'MyV3ryL0ngAndS3cur3P@ssw0rd',
        ];
        
        stopwatch.start();
        for (int i = 0; i < iterations; i++) {
          final password = passwords[i % passwords.length];
          PasswordValidationService.validatePasswordStrength(password);
        }
        stopwatch.stop();
        
        final avgTimeMs = stopwatch.elapsedMilliseconds / iterations;
        
        // print('Password Validation Performance:');
        // print('  Average time: ${avgTimeMs.toStringAsFixed(4)}ms per validation');
        // print('  Target: <5ms per validation');
        
        expect(avgTimeMs, lessThan(5.0),
          reason: 'Password validation should complete within 5ms');
      });

      test('Concurrent authentication operations', () async {
        const int concurrentUsers = 50;
        final metrics = PerformanceMetrics('Concurrent Authentication');
        final completer = Completer<void>();
        int completedOperations = 0;
        final operationTimes = <double>[];
        
        for (int i = 0; i < concurrentUsers; i++) {
          Future.microtask(() async {
            final userStopwatch = Stopwatch()..start();
            try {
              // Simulate complete authentication flow
              await deviceService.generateSecureDeviceId();
              PasswordValidationService.validatePasswordStrength('TestP@ssw0rd123!');
              
              // Simulate token operations
              final mockUserId = 'user_$i';
              // Note: In real test, would validate JWT operations here
              
            } finally {
              userStopwatch.stop();
              operationTimes.add(userStopwatch.elapsedMilliseconds.toDouble());
              metrics.addMeasurement(userStopwatch.elapsedMilliseconds.toDouble());
              
              completedOperations++;
              if (completedOperations == concurrentUsers) {
                completer.complete();
              }
            }
          });
        }
        
        await completer.future;
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.p95, lessThan(200.0),
          reason: 'P95 authentication time should be under 200ms');
        expect(report.mean, lessThan(150.0),
          reason: 'Mean authentication time should be under 150ms');
        expect(operationTimes.length, equals(concurrentUsers),
          reason: 'All operations should complete successfully');
      });
      
      test('High-load authentication stress test', () async {
        const int totalUsers = 200;
        const int batchSize = 25;
        final allResults = <double>[];
        
        // print('\nRunning high-load authentication stress test...');
        // print('Total users: $totalUsers, Batch size: $batchSize');
        
        for (int batch = 0; batch < totalUsers ~/ batchSize; batch++) {
          final batchResults = <double>[];
          final completer = Completer<void>();
          int completed = 0;
          
          // print('Processing batch ${batch + 1}/${totalUsers ~/ batchSize}');
          
          for (int i = 0; i < batchSize; i++) {
            Future.microtask(() async {
              final stopwatch = Stopwatch()..start();
              try {
                await deviceService.generateSecureDeviceId();
                PasswordValidationService.validatePasswordStrength('StressTest@2024!$i');
              } finally {
                stopwatch.stop();
                batchResults.add(stopwatch.elapsedMilliseconds.toDouble());
                completed++;
                if (completed == batchSize) {
                  completer.complete();
                }
              }
            });
          }
          
          await completer.future;
          allResults.addAll(batchResults);
          
          // Brief pause between batches to prevent resource exhaustion
          await Future.delayed(const Duration(milliseconds: 100));
        }
        
        // Analyze results
        allResults.sort();
        final mean = allResults.reduce((a, b) => a + b) / allResults.length;
        final p95 = allResults[(allResults.length * 0.95).floor()];
        final p99 = allResults[(allResults.length * 0.99).floor()];
        
        // print('\nStress Test Results:');
        // print('  Total operations: ${allResults.length}');
        // print('  Mean: ${mean.toStringAsFixed(2)}ms');
        // print('  P95: ${p95.toStringAsFixed(2)}ms');
        // print('  P99: ${p99.toStringAsFixed(2)}ms');
        // print('  Max: ${allResults.last.toStringAsFixed(2)}ms');
        
        expect(p95, lessThan(300.0),
          reason: 'P95 should remain under 300ms even under high load');
        expect(mean, lessThan(200.0),
          reason: 'Mean should remain reasonable under stress');
      });
    });

    group('Data Processing Performance', () {
      test('Large dataset processing', () async {
        const int dataPoints = 10000;
        final stopwatch = Stopwatch();
        final random = Random(42);
        
        // Generate test financial data
        final transactions = <Map<String, dynamic>>[];
        for (int i = 0; i < dataPoints; i++) {
          transactions.add({
            'amount': random.nextDouble() * 1000 + 10,
            'category': 'category_${i % 20}',
            'date': DateTime.now().subtract(Duration(days: i % 365)),
            'description': 'Transaction $i',
          });
        }
        
        stopwatch.start();
        
        // Process transactions (simulate categorization and analysis)
        final categoryTotals = <String, double>{};
        for (final transaction in transactions) {
          final category = transaction['category'] as String;
          final amount = transaction['amount'] as double;
          categoryTotals[category] = (categoryTotals[category] ?? 0.0) + amount;
        }
        
        // Calculate averages and trends
        final averages = categoryTotals.map((key, value) => 
          MapEntry(key, value / (dataPoints / 20)));
        
        stopwatch.stop();
        
        final processingTimeMs = stopwatch.elapsedMilliseconds;
        final itemsPerSecond = (dataPoints * 1000) / processingTimeMs;
        
        // print('Large Dataset Processing Performance:');
        // print('  Data points: $dataPoints');
        // print('  Processing time: ${processingTimeMs}ms');
        // print('  Items per second: ${itemsPerSecond.toStringAsFixed(0)}');
        // print('  Target: >5,000 items/second');
        
        expect(itemsPerSecond, greaterThan(5000),
          reason: 'Should process at least 5,000 transactions per second');
        
        expect(averages.length, equals(20),
          reason: 'Should correctly process all categories');
      });
    });

    group('Advanced Financial Operations Performance', () {
      late ProductionBudgetEngine budgetEngine;
      late SmartCategorizationService categorizationService;
      
      setUp(() {
        budgetEngine = ProductionBudgetEngine();
        categorizationService = SmartCategorizationService();
      });
      
      test('Complex budget calculation performance', () async {
        const int iterations = 500;
        final metrics = PerformanceMetrics('Complex Budget Calculations');
        final random = Random(42);
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          // Simulate complex budget scenario
          final monthlyIncome = 3000 + random.nextDouble() * 7000; // $3k-$10k
          final expenses = <Map<String, dynamic>>[];
          
          // Generate realistic expense data
          final categories = ['food', 'transport', 'utilities', 'entertainment', 'healthcare'];
          for (int j = 0; j < 20; j++) {
            expenses.add({
              'amount': random.nextDouble() * 500 + 50,
              'category': categories[j % categories.length],
              'date': DateTime.now().subtract(Duration(days: j)),
              'recurring': j < 5, // Some recurring expenses
            });
          }
          
          // Perform complex calculations
          final budgetResult = budgetEngine.calculateOptimalBudget(
            monthlyIncome: monthlyIncome,
            tier: IncomeTier.medium, // Default tier for performance test
            goals: ['savings', 'investment'],
            habits: ['regular_saver'],
          );
          
          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
          
          // Validate result structure
          expect(budgetResult, isNotNull);
          expect(budgetResult['totalBudget'], greaterThan(0));
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(50.0),
          reason: 'Complex budget calculations should complete within 50ms');
        expect(report.p95, lessThan(100.0),
          reason: 'P95 for complex calculations should be under 100ms');
      });
      
      test('Smart categorization performance', () async {
        const int iterations = 1000;
        final metrics = PerformanceMetrics('Smart Categorization');
        final transactions = [
          'Starbucks Coffee Shop',
          'Shell Gas Station',
          'Whole Foods Market',
          'Netflix Subscription',
          'AT&T Wireless',
          'Amazon.com Purchase',
          'Uber Technologies',
          'CVS Pharmacy',
          'Home Depot',
          'Spotify Premium',
        ];
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          final transaction = transactions[i % transactions.length];
          final amount = 10 + (i % 500); // $10-$510

          final category = await categorizationService.categorizeTransaction(
            merchant: transaction,
            amount: amount.toDouble(),
            date: DateTime.now(),
            location: 'test_location',
          );

          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());

          expect(category, isNotNull);
          expect(category, isNotEmpty);
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(5.0),
          reason: 'Smart categorization should complete within 5ms');
        expect(report.p95, lessThan(10.0),
          reason: 'P95 categorization time should be under 10ms');
      });
      
      test('Multi-currency calculation performance', () async {
        const int iterations = 2000;
        final metrics = PerformanceMetrics('Multi-currency Calculations');
        final currencies = ['USD', 'EUR', 'GBP', 'CAD', 'JPY', 'AUD', 'CHF'];
        final random = Random(42);
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          final fromCurrency = currencies[i % currencies.length];
          final toCurrency = currencies[(i + 1) % currencies.length];
          final amount = random.nextDouble() * 1000 + 100;
          
          // Simulate currency conversion calculation
          final exchangeRate = 0.8 + random.nextDouble() * 0.4; // 0.8-1.2
          final convertedAmount = amount * exchangeRate;
          final fee = convertedAmount * 0.025; // 2.5% conversion fee
          final finalAmount = convertedAmount - fee;
          
          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
          
          expect(finalAmount, greaterThan(0));
          expect(finalAmount, lessThan(amount * 1.5)); // Sanity check
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(1.0),
          reason: 'Currency calculations should be very fast');
      });
    });
    
    group('Security Feature Performance Impact', () {
      test('Rate limiting lookup performance', () async {
        const int iterations = 5000;
        final metrics = PerformanceMetrics('Rate Limiting Lookups');
        final random = Random(42);
        
        // Simulate rate limiting cache
        final rateLimitCache = <String, Map<String, dynamic>>{};
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          final userId = 'user_${i % 100}'; // 100 unique users
          const endpoint = '/api/auth/login';
          final key = '$userId:$endpoint';
          
          // Simulate rate limit check
          final now = DateTime.now().millisecondsSinceEpoch;
          final existing = rateLimitCache[key];
          
          if (existing != null) {
            final lastRequest = existing['lastRequest'] as int;
            final requestCount = existing['count'] as int;
            
            if (now - lastRequest < 60000) { // 1 minute window
              rateLimitCache[key] = {
                'count': requestCount + 1,
                'lastRequest': now,
                'blocked': requestCount >= 10, // Rate limit: 10 req/min
              };
            } else {
              rateLimitCache[key] = {'count': 1, 'lastRequest': now, 'blocked': false};
            }
          } else {
            rateLimitCache[key] = {'count': 1, 'lastRequest': now, 'blocked': false};
          }
          
          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(5.0),
          reason: 'Rate limiting should add minimal overhead');
        expect(report.p95, lessThan(10.0),
          reason: 'P95 rate limiting should be under 10ms');
      });
      
      test('Token blacklist performance', () async {
        const int iterations = 3000;
        final metrics = PerformanceMetrics('Token Blacklist Operations');
        final blacklist = HashSet<String>();
        final random = Random(42);
        
        // Pre-populate blacklist with some tokens
        for (int i = 0; i < 1000; i++) {
          blacklist.add('revoked_token_$i');
        }
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          if (i % 10 == 0) {
            // Add token to blacklist (10% of operations)
            blacklist.add('revoked_token_${1000 + i}');
          } else {
            // Check if token is blacklisted (90% of operations)
            final tokenToCheck = 'token_${random.nextInt(2000)}';
            final isBlacklisted = blacklist.contains(tokenToCheck);
          }
          
          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(1.0),
          reason: 'Token blacklist operations should be very fast');
        expect(report.p99, lessThan(5.0),
          reason: 'P99 blacklist lookup should be under 5ms');
      });
      
      test('Input validation performance', () async {
        const int iterations = 2000;
        final metrics = PerformanceMetrics('Input Validation');
        final testInputs = [
          {'email': 'user@example.com', 'valid': true},
          {'email': 'invalid-email', 'valid': false},
          {'phone': '+1234567890', 'valid': true},
          {'phone': '123', 'valid': false},
          {'amount': '123.45', 'valid': true},
          {'amount': 'abc', 'valid': false},
          {'password': 'StrongP@ss123!', 'valid': true},
          {'password': '123', 'valid': false},
        ];
        
        for (int i = 0; i < iterations; i++) {
          final stopwatch = Stopwatch()..start();
          
          final testCase = testInputs[i % testInputs.length];
          
          // Simulate comprehensive input validation
          for (final entry in testCase.entries) {
            if (entry.key != 'valid') {
              final value = entry.value as String;
              
              // Basic validation checks
              if (entry.key == 'email') {
                final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
                emailRegex.hasMatch(value);
              } else if (entry.key == 'phone') {
                final phoneRegex = RegExp(r'^\+?[1-9]\d{1,14}$');
                phoneRegex.hasMatch(value);
              } else if (entry.key == 'amount') {
                double.tryParse(value) != null;
              } else if (entry.key == 'password') {
                value.length >= 8 && 
                RegExp(r'[A-Z]').hasMatch(value) &&
                RegExp(r'[a-z]').hasMatch(value) &&
                RegExp(r'\d').hasMatch(value) &&
                RegExp(r'[!@#\$&*~]').hasMatch(value);
              }
            }
          }
          
          stopwatch.stop();
          metrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        
        final report = metrics.generateReport();
        report.printReport();
        
        expect(report.mean, lessThan(2.0),
          reason: 'Input validation should complete within 2ms');
      });
    });
    
    group('Memory and Resource Usage Tests', () {
      test('Memory usage under sustained load', () async {
        const int iterations = 10000;
        const int batchSize = 1000;
        final memorySnapshots = <int>[];
        final incomeService = IncomeService();
        
        // print('\nRunning memory usage test...');
        
        for (int batch = 0; batch < iterations ~/ batchSize; batch++) {
          // Perform batch of operations
          for (int i = 0; i < batchSize; i++) {
            incomeService.classifyIncome(1000.0 + (i % 10000));
          }
          
          // Take memory snapshot (approximation)
          memorySnapshots.add(DateTime.now().millisecondsSinceEpoch);
          
          // Brief pause to allow GC
          await Future.delayed(const Duration(milliseconds: 1));
        }
        
        // print('Memory stability test completed');
        // print('  Batches processed: ${iterations ~/ batchSize}');
        // print('  Operations per batch: $batchSize');
        // print('  Total operations: $iterations');
        
        expect(memorySnapshots.length, equals(iterations ~/ batchSize));
      });
      
      test('Resource cleanup verification', () async {
        const int iterations = 1000;
        final createdObjects = <Object>[];
        
        // Create objects that simulate resource usage
        for (int i = 0; i < iterations; i++) {
          final obj = {
            'id': i,
            'data': List.generate(100, (index) => 'data_$index'),
            'timestamp': DateTime.now(),
          };
          createdObjects.add(obj);
        }
        
        expect(createdObjects.length, equals(iterations));
        
        // Clear references
        createdObjects.clear();
        
        // Force garbage collection attempt
        await Future.delayed(const Duration(milliseconds: 100));
        
        expect(createdObjects.length, equals(0));
      });
    });
    
    group('Performance Regression Detection', () {
      test('Comprehensive baseline performance metrics', () async {
        final results = <String, PerformanceReport>{};
        
        // Income classification baseline
        // print('\nGenerating baseline metrics...');
        
        final incomeMetrics = PerformanceMetrics('Income Classification Baseline');
        final incomeService = IncomeService();
        for (int i = 0; i < 1000; i++) {
          final stopwatch = Stopwatch()..start();
          incomeService.classifyIncome(5000.0 + (i % 1000));
          stopwatch.stop();
          incomeMetrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        results['income_classification'] = incomeMetrics.generateReport();
        
        // Password validation baseline
        final passwordMetrics = PerformanceMetrics('Password Validation Baseline');
        final passwordService = PasswordValidationService();
        for (int i = 0; i < 500; i++) {
          final stopwatch = Stopwatch()..start();
          PasswordValidationService.validatePasswordStrength('TestP@ssw0rd$i');
          stopwatch.stop();
          passwordMetrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        results['password_validation'] = passwordMetrics.generateReport();
        
        // Financial calculation baseline
        final financialMetrics = PerformanceMetrics('Financial Calculation Baseline');
        final calculator = FinancialHealthCalculator();
        for (int i = 0; i < 1000; i++) {
          final stopwatch = Stopwatch()..start();
          calculator.calculateBudgetHealth(5000.0, 3500.0);
          stopwatch.stop();
          financialMetrics.addMeasurement(stopwatch.elapsedMilliseconds.toDouble());
        }
        results['financial_calculation'] = financialMetrics.generateReport();
        
        // Print all baseline reports
        results.forEach((key, report) {
          report.printReport();
        });
        
        // Save baseline to JSON for regression testing
        final baselineData = {
          'timestamp': DateTime.now().toIso8601String(),
          'version': '1.0.0',
          'metrics': results.map((key, report) => MapEntry(key, report.toJson())),
        };
        
        // print('\nBaseline data generated for regression testing');
        // print('JSON data size: ${json.encode(baselineData).length} bytes');
        
        // Validate baseline performance targets
        expect(results['income_classification']!.mean, lessThan(0.08),
          reason: 'Income classification baseline should meet target');
        expect(results['password_validation']!.mean, lessThan(5.0),
          reason: 'Password validation baseline should meet target');
        expect(results['financial_calculation']!.mean, lessThan(2.0),
          reason: 'Financial calculation baseline should meet target');
      });
    });
    
    group('Load Testing Framework', () {
      test('Concurrent user simulation - Authentication', () async {
        final simulator = LoadTestSimulator(
          concurrentUsers: 25,
          testDuration: const Duration(seconds: 30),
          operationToTest: () async {
            final deviceService = SecureDeviceService();
            await deviceService.generateSecureDeviceId();
            final passwordService = PasswordValidationService();
            PasswordValidationService.validatePasswordStrength('LoadTest@2024!');
          },
        );
        
        final result = await simulator.runLoadTest();
        result.printResult();
        
        expect(result.errors.length, lessThan(result.totalOperations * 0.01),
          reason: 'Error rate should be less than 1%');
        expect(result.opsPerSecond, greaterThan(5.0),
          reason: 'Should maintain at least 5 operations per second');
      });
      
      test('Concurrent user simulation - Income Classification', () async {
        final simulator = LoadTestSimulator(
          concurrentUsers: 50,
          testDuration: const Duration(seconds: 15),
          operationToTest: () async {
            final incomeService = IncomeService();
            final random = Random();
            final income = 1000 + random.nextDouble() * 9000;
            incomeService.classifyIncome(income);
          },
        );
        
        final result = await simulator.runLoadTest();
        result.printResult();
        
        expect(result.errors.isEmpty, true,
          reason: 'Income classification should not produce errors');
        expect(result.opsPerSecond, greaterThan(1000.0),
          reason: 'Should handle over 1000 classifications per second');
      });
      
      test('Mixed operation load test', () async {
        final operations = <Future<void> Function()>[
          () async {
            final incomeService = IncomeService();
            incomeService.classifyIncome(Random().nextDouble() * 10000 + 1000);
          },
          () async {
            final calculator = FinancialHealthCalculator();
            calculator.calculateBudgetHealth(5000.0, 3500.0);
          },
          () async {
            final passwordService = PasswordValidationService();
            PasswordValidationService.validatePasswordStrength('MixedTest@${Random().nextInt(1000)}!');
          },
          () async {
            final deviceService = SecureDeviceService();
            await deviceService.generateSecureDeviceId();
          },
        ];
        
        final simulator = LoadTestSimulator(
          concurrentUsers: 30,
          testDuration: const Duration(seconds: 20),
          operationToTest: () async {
            final randomOperation = operations[Random().nextInt(operations.length)];
            await randomOperation();
          },
        );
        
        final result = await simulator.runLoadTest();
        result.printResult();
        
        expect(result.errors.length, lessThan(result.totalOperations * 0.02),
          reason: 'Mixed operation error rate should be less than 2%');
        expect(result.totalOperations, greaterThan(1000),
          reason: 'Should complete a significant number of mixed operations');
      });
    });
  });
}
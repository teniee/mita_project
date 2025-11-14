# Installment Service - Quick Reference

## Import
```dart
import 'package:mita/services/installment_service.dart';
import 'package:mita/models/installment_models.dart';
```

## Get Instance
```dart
final installmentService = InstallmentService();
```

## Core Methods (10 Required)

### 1. Calculate Risk
```dart
final output = await installmentService.calculateInstallmentRisk(input);
// POST /api/installments/calculator
```

### 2. Create Profile
```dart
final profile = await installmentService.createFinancialProfile(profile);
// POST /api/installments/profile
```

### 3. Get Profile
```dart
final profile = await installmentService.getFinancialProfile();
// GET /api/installments/profile
// Returns null if not found
```

### 4. Create Installment
```dart
final installment = await installmentService.createInstallment(installment);
// POST /api/installments
```

### 5. Get Installments
```dart
final summary = await installmentService.getInstallments(status: InstallmentStatus.active);
// GET /api/installments?status=active
```

### 6. Get Single Installment
```dart
final installment = await installmentService.getInstallment(installmentId);
// GET /api/installments/{installment_id}
```

### 7. Update Installment
```dart
final updated = await installmentService.updateInstallment(installmentId, {'notes': 'New note'});
// PATCH /api/installments/{installment_id}
```

### 8. Delete Installment
```dart
await installmentService.deleteInstallment(installmentId);
// DELETE /api/installments/{installment_id}
```

### 9. Get Calendar
```dart
final calendar = await installmentService.getMonthlyCalendar(2025, 11);
// GET /api/installments/calendar/{year}/{month}
```

### 10. Get Achievements
```dart
final achievements = await installmentService.getAchievements();
// GET /api/installments/achievements
```

## Convenience Methods (15 Additional)

### Filters
```dart
// Get only active installments
final active = await installmentService.getActiveInstallments();

// Get only completed installments
final completed = await installmentService.getCompletedInstallments();

// Get only overdue installments
final overdue = await installmentService.getOverdueInstallments();
```

### Profile Helpers
```dart
// Check if profile exists
final exists = await installmentService.hasFinancialProfile();

// Get or create profile
final profile = await installmentService.getOrCreateFinancialProfile(
  monthlyIncome: 5000.0,
  currentBalance: 2000.0,
  ageGroup: AgeGroup.age25_34,
);
```

### Summary Data
```dart
// Get total monthly payment obligation
final total = await installmentService.getTotalMonthlyPayment();

// Get next payment date
final nextDate = await installmentService.getNextPaymentDate();

// Check if payment due soon (within 7 days)
final dueSoon = await installmentService.hasPaymentDueSoon();
```

### Calendar Helpers
```dart
// Get calendar for current month
final calendar = await installmentService.getCurrentMonthCalendar();
```

### Actions
```dart
// Mark payment as made
final updated = await installmentService.markPaymentMade(installmentId);

// Cancel installment
final cancelled = await installmentService.cancelInstallment(installmentId);

// Add notes
final withNotes = await installmentService.addNotes(installmentId, 'My notes');
```

## Error Handling

```dart
try {
  final installment = await installmentService.getInstallment(id);
} on InstallmentServiceException catch (e) {
  if (e.isAuthError) {
    // Handle authentication error (401)
  } else if (e.isNotFound) {
    // Handle not found (404)
  } else if (e.isValidationError) {
    // Handle validation error (400, 422)
  } else if (e.isNetworkError) {
    // Handle network error (0)
  } else if (e.isServerError) {
    // Handle server error (500+)
  } else {
    // Handle other errors
    print(e.message);
  }
}
```

## Complete Example

```dart
import 'package:flutter/material.dart';
import 'package:mita/services/installment_service.dart';
import 'package:mita/models/installment_models.dart';

class InstallmentCalculatorScreen extends StatefulWidget {
  @override
  _InstallmentCalculatorScreenState createState() => _InstallmentCalculatorScreenState();
}

class _InstallmentCalculatorScreenState extends State<InstallmentCalculatorScreen> {
  final _service = InstallmentService();
  bool _loading = false;
  InstallmentCalculatorOutput? _result;

  Future<void> _calculateRisk() async {
    setState(() => _loading = true);

    try {
      final input = InstallmentCalculatorInput(
        purchaseAmount: 1500.0,
        category: InstallmentCategory.electronics,
        numPayments: 12,
        interestRate: 0.15,
        monthlyIncome: 5000.0,
        currentBalance: 2000.0,
        ageGroup: AgeGroup.age25_34,
        activeInstallmentsCount: 0,
        activeInstallmentsMonthly: 0.0,
      );

      final result = await _service.calculateInstallmentRisk(input);

      setState(() {
        _result = result;
        _loading = false;
      });

      if (result.shouldProceed) {
        _showSuccessDialog();
      } else if (result.hasCriticalWarnings) {
        _showWarningDialog();
      }
    } on InstallmentServiceException catch (e) {
      setState(() => _loading = false);

      if (e.isAuthError) {
        Navigator.pushNamed(context, '/login');
      } else if (e.isNetworkError) {
        _showErrorDialog('No internet connection. Please try again.');
      } else {
        _showErrorDialog(e.message);
      }
    }
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Good to Go!'),
        content: Text(_result!.verdict),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('OK'),
          ),
          ElevatedButton(
            onPressed: _createInstallment,
            child: Text('Create Installment'),
          ),
        ],
      ),
    );
  }

  void _showWarningDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Warning'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_result!.verdict),
            SizedBox(height: 16),
            ..._result!.warnings.map((w) => Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Icon(Icons.warning, color: Colors.orange, size: 16),
                  SizedBox(width: 8),
                  Expanded(child: Text(w)),
                ],
              ),
            )),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _createInstallment();
            },
            child: Text('Proceed Anyway'),
          ),
        ],
      ),
    );
  }

  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _createInstallment() async {
    // Implementation for creating installment
    final installment = Installment(
      id: '',
      userId: '',
      itemName: 'MacBook Pro',
      category: InstallmentCategory.electronics,
      totalAmount: _result!.totalCost,
      paymentAmount: _result!.monthlyPayment,
      interestRate: 0.15,
      totalPayments: 12,
      paymentsMade: 0,
      paymentFrequency: 'monthly',
      firstPaymentDate: DateTime.now().add(Duration(days: 30)),
      nextPaymentDate: DateTime.now().add(Duration(days: 30)),
      finalPaymentDate: DateTime.now().add(Duration(days: 365)),
      status: InstallmentStatus.active,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );

    try {
      final created = await _service.createInstallment(installment);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Installment created successfully!')),
      );
      Navigator.pop(context);
    } on InstallmentServiceException catch (e) {
      _showErrorDialog(e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Installment Calculator')),
      body: _loading
          ? Center(child: CircularProgressIndicator())
          : Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                children: [
                  // Form fields here
                  ElevatedButton(
                    onPressed: _calculateRisk,
                    child: Text('Calculate Risk'),
                  ),
                  if (_result != null) _buildResults(),
                ],
              ),
            ),
    );
  }

  Widget _buildResults() {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Risk Level: ${_result!.riskLevel.displayName}'),
            Text('Monthly Payment: \$${_result!.monthlyPayment.toStringAsFixed(2)}'),
            Text('Total Interest: \$${_result!.totalInterest.toStringAsFixed(2)}'),
            Text('Verdict: ${_result!.verdict}'),
          ],
        ),
      ),
    );
  }
}
```

## Key Features

### Automatic Retry
- Retries network failures up to 3 times
- Exponential backoff (2s, 4s, 6s)
- Only retries transient failures

### Authentication
- Automatic token injection
- Token refresh handling
- Auth error detection

### Error Handling
- RFC7807 compliant
- Categorized exceptions
- Detailed error messages

### Logging
- Structured logging
- Operation tracking
- Debug/Info/Warning/Error levels
- Tag: `INSTALLMENT_SERVICE`

### Configuration
- Base URL: From config.dart
- Timeout: 30 seconds
- Max Retries: 3
- Retry Delay: 2 seconds (exponential)

## Model Properties Quick Reference

### InstallmentCalculatorOutput
- `riskLevel`: RiskLevel (green, yellow, orange, red)
- `riskScore`: double
- `verdict`: String
- `monthlyPayment`: double
- `totalInterest`: double
- `totalCost`: double
- `paymentSchedule`: List<Map>
- `riskFactors`: List<RiskFactor>
- `warnings`: List<String>
- `tips`: List<String>
- `shouldProceed`: bool (getter)
- `hasCriticalWarnings`: bool (getter)

### Installment
- `id`: String
- `itemName`: String
- `category`: InstallmentCategory
- `totalAmount`: double
- `paymentAmount`: double
- `totalPayments`: int
- `paymentsMade`: int
- `status`: InstallmentStatus
- `nextPaymentDate`: DateTime
- `progressPercentage`: double (getter)
- `remainingPayments`: int (getter)
- `remainingBalance`: double (getter)
- `isPaymentDueSoon`: bool (getter)
- `isOverdue`: bool (getter)

### InstallmentsSummary
- `totalActive`: int
- `totalCompleted`: int
- `totalMonthlyPayment`: double
- `nextPaymentDate`: DateTime?
- `installments`: List<Installment>
- `activeInstallments`: List<Installment> (getter)
- `completedInstallments`: List<Installment> (getter)
- `overdueInstallments`: List<Installment> (getter)
- `hasPaymentDueSoon`: bool (getter)

### UserFinancialProfile
- `monthlyIncome`: double?
- `currentBalance`: double?
- `ageGroup`: AgeGroup?
- `creditCardDebt`: double?
- `planningMortgage`: bool
- `totalMonthlyObligations`: double (getter)
- `hasCompleteProfile`: bool (getter)

### InstallmentAchievement
- `installmentsCompleted`: int
- `calculationsPerformed`: int
- `calculationsDeclined`: int
- `daysWithoutNewInstallment`: int
- `maxDaysStreak`: int
- `interestSaved`: double
- `achievementLevel`: String
- `declineRate`: double (getter)
- `isOnGoodStreak`: bool (getter)

## Status Codes

- `0`: Network error
- `200`: Success
- `201`: Created
- `400`: Bad request / Validation error
- `401`: Unauthorized (auth error)
- `404`: Not found
- `422`: Unprocessable entity (validation error)
- `429`: Rate limit exceeded
- `500+`: Server error

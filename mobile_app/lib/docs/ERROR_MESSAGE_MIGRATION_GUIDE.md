# Error Message System Migration Guide

## Overview

This guide helps developers migrate from the old generic error handling system to the new Financial Error Message system that provides user-friendly, actionable error messages with financial context.

## What's New

### 🎯 Key Improvements
- **Financial Context**: Error messages include context about financial operations
- **Actionable Guidance**: Every error provides specific steps users can take
- **Material 3 Design**: Updated UI components following Material Design 3
- **Accessibility First**: Full screen reader support and semantic structure
- **Comprehensive Testing**: Automated tests for error message quality

### 🗂️ New Files Added
```
lib/core/financial_error_messages.dart       # Core error categorization and messages
lib/widgets/financial_error_widgets.dart     # Material 3 UI components
lib/services/financial_error_service.dart    # Centralized error management
lib/docs/ERROR_MESSAGE_STYLE_GUIDE.md       # Style guide for error messages
test/error_message_test.dart                 # Comprehensive testing framework
```

## Migration Steps

### Step 1: Update Imports

**Before:**
```dart
import '../core/error_handling.dart';
import '../core/app_error_handler.dart';
```

**After:**
```dart
import '../core/error_handling.dart';
import '../core/app_error_handler.dart';
import '../services/financial_error_service.dart';
import '../core/financial_error_messages.dart';
```

### Step 2: Update Screen Mixins

**Before:**
```dart
class _LoginScreenState extends State<LoginScreen> with TickerProviderStateMixin {
  // Error handling
  void _handleError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message))
    );
  }
}
```

**After:**
```dart
class _LoginScreenState extends State<LoginScreen> 
    with TickerProviderStateMixin, FinancialErrorHandling {
  // Error handling is now built-in through the mixin
  // Use: showError(), showSuccess(), showWarning()
}
```

### Step 3: Update Error Display Calls

**Before:**
```dart
// Generic error display
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(content: Text('Login failed'))
);

// Generic dialog
showDialog(
  context: context,
  builder: (context) => AlertDialog(
    title: Text('Error'),
    content: Text('Something went wrong'),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: Text('OK'),
      ),
    ],
  ),
);
```

**After:**
```dart
// Financial error with context and guidance
await showError(
  AuthenticationException('Invalid credentials'),
  context: {
    'operation': 'login',
    'screen': 'login',
  },
  onRetry: _retryLogin,
);

// Or using context extension
context.showFinancialError(
  error,
  context: {'operation': 'login'},
  onRetry: _retryLogin,
);
```

### Step 4: Update Success Messages

**Before:**
```dart
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(
    content: Text('Transaction saved'),
    backgroundColor: Colors.green,
  ),
);
```

**After:**
```dart
showSuccess(
  'Transaction saved successfully!',
  financialContext: 'Your expense has been recorded and your budget updated.',
);

// Or using context extension
context.showFinancialSuccess(
  'Transaction saved successfully!',
  financialContext: 'Your expense has been recorded and your budget updated.',
);
```

### Step 5: Update Form Validation

**Before:**
```dart
String? _validateAmount(String? value) {
  if (value?.isEmpty ?? true) return 'Amount required';
  if (double.tryParse(value!) == null) return 'Invalid amount';
  return null;
}
```

**After:**
```dart
String? _validateAmount(String? value) {
  return validateAmount(value, required: true);
  // Built-in validation with financial context and helpful messages
}

// Or for custom validation:
String? _validateBudgetAmount(String? value) {
  return errorService.validateFinancialAmount(
    value,
    maxAmount: currentBudget,
    required: true,
  );
}
```

### Step 6: Update Error Handling in Try-Catch Blocks

**Before:**
```dart
try {
  await apiService.saveTransaction(transaction);
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Transaction saved')),
  );
} catch (e) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Failed to save transaction')),
  );
}
```

**After:**
```dart
try {
  await apiService.saveTransaction(transaction);
  showSuccess(
    'Transaction saved successfully!',
    financialContext: 'Your financial records have been updated.',
  );
} catch (e) {
  await showError(
    e,
    context: {
      'operation': 'save_transaction',
      'transaction_amount': transaction.amount,
      'category': transaction.category,
    },
    onRetry: () => _saveTransaction(),
  );
}
```

### Step 7: Update Network Error Handling

**Before:**
```dart
if (error is DioException) {
  String message = 'Network error occurred';
  if (error.response?.statusCode == 401) {
    message = 'Session expired';
  }
  _showError(message);
}
```

**After:**
```dart
// The financial error system automatically categorizes network errors
await showError(error, context: {
  'operation': 'api_request',
  'endpoint': '/api/transactions',
});

// Results in user-friendly messages like:
// "Your session has expired for your protection. Please sign in again."
// with appropriate actions and financial context
```

## Common Patterns Migration

### Pattern 1: Budget Validation

**Before:**
```dart
if (amount > dailyBudget) {
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Budget Exceeded'),
      content: Text('This expense exceeds your budget'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text('OK')),
      ],
    ),
  );
}
```

**After:**
```dart
if (amount > dailyBudget) {
  final exceeded = amount - dailyBudget;
  final proceed = await errorService.showBudgetExceededDialog(
    context,
    exceededAmount: exceeded,
    dailyBudget: dailyBudget,
    category: selectedCategory,
    onProceed: () => _saveTransaction(),
    onAdjust: () => _adjustAmount(),
  );
}
```

### Pattern 2: Loading States with Error Recovery

**Before:**
```dart
setState(() => _loading = true);
try {
  final result = await operation();
  setState(() => _loading = false);
} catch (e) {
  setState(() => _loading = false);
  _showError('Operation failed');
}
```

**After:**
```dart
// Use the built-in loading state management
await executeRobustly(
  () => operation(),
  operationName: 'Load Transactions',
  showLoadingState: true,
  onError: () {
    // Error is automatically displayed with context
    // No need to manually manage loading state
  },
);
```

### Pattern 3: Form Validation

**Before:**
```dart
final _formKey = GlobalKey<FormState>();

TextFormField(
  validator: (value) {
    if (value?.isEmpty ?? true) return 'Email required';
    if (!value!.contains('@')) return 'Invalid email';
    return null;
  },
)
```

**After:**
```dart
final _formKey = GlobalKey<FormState>();

TextFormField(
  validator: validateEmail, // Built-in with financial context
)

// Or for custom validation with inline errors:
Column(
  children: [
    TextFormField(/*...*/),
    if (_hasEmailError)
      errorService.buildInlineError(
        ValidationException('Email format error'),
        onRetry: () => _validateEmail(),
      ),
  ],
)
```

## Testing Migration

### Update Widget Tests

**Before:**
```dart
testWidgets('should show error message', (tester) async {
  // Trigger error
  await tester.tap(find.byKey(Key('login_button')));
  await tester.pumpAndSettle();
  
  // Check for generic error
  expect(find.text('Login failed'), findsOneWidget);
});
```

**After:**
```dart
testWidgets('should show financial error message', (tester) async {
  // Trigger error
  await tester.tap(find.byKey(Key('login_button')));
  await tester.pumpAndSettle();
  
  // Check for specific financial error components
  expect(find.text('Login Failed'), findsOneWidget);
  expect(find.text('Sign In Again'), findsOneWidget);
  expect(find.byIcon(Icons.person_off_outlined), findsOneWidget);
  
  // Check for financial context
  expect(find.textContaining('financial data'), findsOneWidget);
});
```

### Update Unit Tests

**Before:**
```dart
test('should handle login error', () {
  final service = AuthService();
  expect(() => service.login('', ''), throwsException);
});
```

**After:**
```dart
test('should categorize login error correctly', () {
  final error = AuthenticationException('Invalid credentials');
  final errorInfo = FinancialErrorMessages.getErrorInfo(error);
  
  expect(errorInfo.title, equals('Login Failed'));
  expect(errorInfo.category, equals('Authentication'));
  expect(errorInfo.actions.any((a) => a.label == 'Try Again'), isTrue);
  expect(errorInfo.financialContext, isNotNull);
});
```

## Backwards Compatibility

The new system is designed to work alongside existing error handling:

1. **Old error handling still works**: Existing `ScaffoldMessenger` and `AlertDialog` calls continue to function
2. **Gradual migration**: You can migrate screens one at a time
3. **Fallback support**: Generic errors are automatically enhanced with basic financial context

## Validation Checklist

Before completing migration of a screen:

- [ ] All error messages are user-friendly (no technical jargon)
- [ ] Financial context is provided where appropriate
- [ ] Actionable guidance is included (what user can do)
- [ ] Success messages include financial context
- [ ] Form validation uses the new validators
- [ ] Loading states use the new components
- [ ] Error dialogs use the new Material 3 components
- [ ] Accessibility is properly implemented
- [ ] Tests are updated to check for new error components

## Troubleshooting

### Issue: Import errors
**Solution**: Make sure all new files are properly imported and pubspec.yaml is updated

### Issue: Old error messages still showing
**Solution**: Check that you're using the new methods (`showError()`) instead of old ones (`ScaffoldMessenger`)

### Issue: Error messages not localized
**Solution**: Ensure you've updated the localization files (app_en.arb) with new error keys

### Issue: Tests failing
**Solution**: Update tests to check for new error components and messages

## Examples

### Complete Screen Migration

**Before:**
```dart
class LoginScreen extends StatefulWidget {
  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _loading = false;
  
  void _login() async {
    setState(() => _loading = true);
    try {
      await authService.login(email, password);
      Navigator.pushReplacementNamed(context, '/dashboard');
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Login failed')),
      );
    }
    setState(() => _loading = false);
  }
}
```

**After:**
```dart
class LoginScreen extends StatefulWidget {
  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> 
    with FinancialErrorHandling {
  
  void _login() async {
    await executeRobustly(
      () async {
        await authService.login(email, password);
        showSuccess(
          'Welcome back!',
          financialContext: 'Your financial data is secure and up to date.',
        );
        Navigator.pushReplacementNamed(context, '/dashboard');
      },
      operationName: 'Login',
      showLoadingState: true,
      onError: () {
        // Error automatically displayed with financial context
        // User gets actionable guidance and retry options
      },
    );
  }
}
```

## Benefits After Migration

1. **Better User Experience**: Users get helpful, actionable error messages
2. **Consistent Design**: All errors follow Material 3 design principles  
3. **Financial Context**: Users understand how errors affect their financial data
4. **Better Accessibility**: Full screen reader support and semantic structure
5. **Easier Maintenance**: Centralized error handling logic
6. **Better Testing**: Comprehensive test framework for error scenarios
7. **Localization Ready**: All messages support multiple languages

## Need Help?

- Check the [Error Message Style Guide](ERROR_MESSAGE_STYLE_GUIDE.md) for message writing guidelines
- Run the test suite to validate your changes: `flutter test test/error_message_test.dart`
- Review existing migrated screens for examples
- Ensure all error scenarios are covered in your testing
# MITA Flutter Accessibility Guidelines

## Overview

This document provides comprehensive guidelines for implementing accessibility features in MITA's Flutter financial application. These guidelines ensure compliance with WCAG 2.1 AA standards and financial application accessibility requirements (ADA, Section 508).

## Table of Contents

1. [Accessibility Service Usage](#accessibility-service-usage)
2. [Screen Reader Support](#screen-reader-support)
3. [Visual Accessibility](#visual-accessibility)
4. [Navigation Accessibility](#navigation-accessibility)
5. [Financial Data Accessibility](#financial-data-accessibility)
6. [Interactive Element Guidelines](#interactive-element-guidelines)
7. [Form Accessibility](#form-accessibility)
8. [Error Handling](#error-handling)
9. [Testing Guidelines](#testing-guidelines)

## Accessibility Service Usage

### Initialization

Always initialize the accessibility service in your screen's `initState()` method:

```dart
@override
void initState() {
  super.initState();
  _accessibilityService.initialize().then((_) {
    _accessibilityService.announceNavigation(
      'Screen Name',
      description: 'Brief description of screen purpose',
    );
  });
}
```

### Import and Instance

```dart
import '../services/accessibility_service.dart';

class _YourScreenState extends State<YourScreen> {
  final AccessibilityService _accessibilityService = AccessibilityService.instance;
}
```

## Screen Reader Support

### Semantic Labels

Always provide meaningful semantic labels for UI elements:

```dart
Semantics(
  label: _accessibilityService.createFinancialSemanticLabel(
    label: 'Budget Amount',
    amount: 250.00,
    category: 'Daily Budget',
    status: 'Within limits',
  ),
  child: Text('\$250.00'),
)
```

### Live Regions

Use live regions for dynamic content that should be announced:

```dart
Semantics(
  liveRegion: true,
  label: 'Budget updated: ${newAmount}',
  child: dynamicContent,
)
```

### Headers

Mark important titles and headers:

```dart
Semantics(
  header: true,
  label: 'Budget Dashboard',
  child: Text('Budget Dashboard'),
)
```

## Visual Accessibility

### High Contrast Support

Check for high contrast mode and adjust colors:

```dart
final highContrastScheme = _accessibilityService.getHighContrastColorScheme(baseScheme);
if (highContrastScheme != null) {
  // Use high contrast colors
}
```

### Dynamic Text Scaling

Support system text scaling:

```dart
Text(
  'Budget Amount',
  style: TextStyle(
    fontSize: 16 * _accessibilityService.textScaleFactor,
  ),
)
```

### Color Contrast

Ensure sufficient contrast ratios:
- Normal text: 4.5:1 minimum
- Large text: 3:1 minimum
- UI components: 3:1 minimum

## Navigation Accessibility

### Focus Management

Implement proper focus management:

```dart
final FocusNode _focusNode = FocusNode();

// Request focus
_accessibilityService.manageFocus(_focusNode);

// Navigate to previous focus
_accessibilityService.navigateToPreviousFocus();

// Clear focus history when navigating
_accessibilityService.clearFocusHistory();
```

### Minimum Touch Targets

Ensure all interactive elements meet minimum size requirements:

```dart
ElevatedButton(
  onPressed: onPressed,
  child: Text('Button'),
).withMinimumTouchTarget()
```

### Navigation Announcements

Announce navigation changes:

```dart
Navigator.pushNamed(context, '/next-screen');
_accessibilityService.announceNavigation(
  'Next Screen',
  description: 'Description of destination',
);
```

## Financial Data Accessibility

### Currency Formatting

Use the accessibility service's currency formatter:

```dart
final accessibleAmount = _accessibilityService.formatCurrency(125.50);
// Returns: "125 dollars and 50 cents"
```

### Progress Indicators

Create accessible progress descriptions:

```dart
Semantics(
  label: _accessibilityService.createProgressSemanticLabel(
    category: 'Monthly Budget',
    spent: 750.00,
    limit: 1000.00,
    status: 'On track',
  ),
  child: LinearProgressIndicator(value: 0.75),
)
```

### Financial Updates

Announce financial changes:

```dart
await _accessibilityService.announceFinancialUpdate(
  'Expense added',
  45.99,
  category: 'Groceries',
  context: 'to today\'s budget',
);
```

## Interactive Element Guidelines

### Buttons

Create accessible button labels:

```dart
Semantics(
  label: _accessibilityService.createButtonSemanticLabel(
    action: 'Add Expense',
    context: 'Opens expense entry form',
    isDisabled: false,
  ),
  button: true,
  child: ElevatedButton(
    onPressed: onPressed,
    child: Text('Add Expense'),
  ).withMinimumTouchTarget(),
)
```

### Form Fields

Provide comprehensive field descriptions:

```dart
Semantics(
  label: _accessibilityService.createTextFieldSemanticLabel(
    label: 'Amount',
    isRequired: true,
    hasError: hasError,
    errorMessage: errorMessage,
    helperText: 'Enter expense amount in dollars',
  ),
  child: TextFormField(
    decoration: InputDecoration(labelText: 'Amount'),
  ),
).withMinimumTouchTarget()
```

## Form Accessibility

### Validation Errors

Announce form validation errors:

```dart
if (!_formKey.currentState!.validate()) {
  List<String> errors = collectValidationErrors();
  await _accessibilityService.announceFormErrors(errors);
  return;
}
```

### Error Messages

Make error messages accessible:

```dart
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(
    content: Semantics(
      liveRegion: true,
      label: 'Error: ${errorMessage}',
      child: Text(errorMessage),
    ),
  ),
);
```

## Error Handling

### Accessible Error States

Use the MitaWidgets error screen:

```dart
MitaWidgets.buildErrorScreen(
  title: 'Load Failed',
  message: 'Unable to load budget data. Please check your connection.',
  onRetry: () => _retryLoad(),
)
```

### Loading States

Provide accessible loading feedback:

```dart
MitaWidgets.buildLoadingScreen(
  message: 'Loading budget data',
  showLogo: true,
)
```

## Testing Guidelines

### Manual Testing

1. **Screen Reader Testing**:
   - Test with TalkBack (Android) or VoiceOver (iOS)
   - Ensure all elements are readable
   - Verify logical reading order

2. **Focus Testing**:
   - Test keyboard/switch navigation
   - Verify focus indicators are visible
   - Check focus order is logical

3. **Contrast Testing**:
   - Use color contrast analyzers
   - Test in high contrast mode
   - Verify with different system themes

### Automated Testing

Use Flutter's accessibility testing tools:

```dart
testWidgets('Budget screen accessibility test', (WidgetTester tester) async {
  await tester.pumpWidget(MyApp());
  
  // Test semantic labels
  expect(find.bySemanticsLabel('Budget Amount'), findsOneWidget);
  
  // Test minimum touch targets
  final button = find.byType(ElevatedButton);
  final buttonSize = tester.getSize(button);
  expect(buttonSize.width, greaterThanOrEqualTo(48));
  expect(buttonSize.height, greaterThanOrEqualTo(48));
});
```

## Best Practices

### Do's

✅ **Always provide semantic labels for financial data**  
✅ **Use the AccessibilityService for consistent formatting**  
✅ **Test with real assistive technologies**  
✅ **Announce important state changes**  
✅ **Ensure minimum 48dp touch targets**  
✅ **Support dynamic text scaling**  
✅ **Use high contrast colors when needed**  
✅ **Provide alternative text for images**  

### Don'ts

❌ **Don't rely on color alone to convey information**  
❌ **Don't use generic labels like "Button" or "Text"**  
❌ **Don't forget to announce loading states**  
❌ **Don't ignore validation error announcements**  
❌ **Don't hardcode text sizes**  
❌ **Don't create inaccessible custom widgets**  
❌ **Don't skip focus management**  
❌ **Don't use placeholder text as labels**  

## Implementation Checklist

For each new screen or component:

- [ ] Import and initialize AccessibilityService
- [ ] Add semantic labels to all interactive elements
- [ ] Implement proper focus management
- [ ] Ensure minimum touch target sizes
- [ ] Add loading and error state announcements
- [ ] Test with screen readers
- [ ] Verify high contrast support
- [ ] Check dynamic text scaling
- [ ] Validate form error announcements
- [ ] Test keyboard navigation

## Financial App Specific Requirements

### Regulatory Compliance

MITA must meet specific financial accessibility standards:

1. **Currency Announcements**: All financial amounts must be announced in full currency format
2. **Transaction Clarity**: Transaction details must be clearly announced with context
3. **Budget Status**: Budget warnings and limits must be immediately announced
4. **Security**: Sensitive operations must have clear audio confirmation
5. **Error Recovery**: Financial errors must provide clear recovery paths

### Security Considerations

- Ensure sensitive data is not exposed through accessibility APIs
- Provide audio confirmations for financial actions
- Use secure input methods compatible with assistive technologies
- Implement timeout warnings with audio alerts

## Resources

- [Flutter Accessibility Guide](https://flutter.dev/accessibility)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Material Design Accessibility](https://material.io/design/usability/accessibility.html)
- [ADA Compliance for Financial Apps](https://www.ada.gov/resources/web-guidance/)

## Support

For accessibility implementation questions or issues, consult:

1. The AccessibilityService documentation
2. Flutter's accessibility testing tools
3. Platform-specific accessibility guidelines
4. Financial industry accessibility standards

Remember: Accessibility is not just compliance—it's about creating an inclusive experience for all MITA users.
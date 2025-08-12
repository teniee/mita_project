# MITA Flutter App - Internationalization (i18n) Developer Guidelines

## Overview

This guide provides comprehensive guidelines for maintaining and extending internationalization support in the MITA Flutter financial application. Follow these practices to ensure consistent, accessible, and scalable multilingual support.

## Table of Contents

1. [Setup and Configuration](#setup-and-configuration)
2. [Adding New Strings](#adding-new-strings)  
3. [Financial Formatting](#financial-formatting)
4. [RTL/Text Direction Support](#rtltext-direction-support)
5. [Best Practices](#best-practices)
6. [Testing Guidelines](#testing-guidelines)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)

## Setup and Configuration

### Dependencies
Ensure your `pubspec.yaml` includes:
```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  intl: ^0.19.0

flutter:
  generate: true
```

### Configuration Files
- **l10n.yaml**: Main localization configuration
- **lib/l10n/app_en.arb**: English (base) translations
- **lib/l10n/app_es.arb**: Spanish translations

### Main App Configuration
```dart
MaterialApp(
  localizationsDelegates: const [
    AppLocalizations.delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  supportedLocales: AppLocalizations.supportedLocales,
  // ... rest of app configuration
)
```

## Adding New Strings

### Step 1: Add to ARB Files

**Add to `lib/l10n/app_en.arb`:**
```json
{
  "myNewString": "Hello World",
  "@myNewString": {
    "description": "Greeting message for users",
    "context": "Used in welcome dialog"
  }
}
```

**Add to `lib/l10n/app_es.arb`:**
```json
{
  "myNewString": "Hola Mundo"
}
```

### Step 2: Regenerate Localizations
```bash
flutter gen-l10n
```

### Step 3: Use in Code
```dart
// Import generated localizations
import '../l10n/generated/app_localizations.dart';

// In your widget
Widget build(BuildContext context) {
  final l10n = AppLocalizations.of(context);
  return Text(l10n.myNewString);
}
```

### Parameterized Messages
For messages with variables:

**ARB file:**
```json
{
  "welcomeUser": "Welcome back, {userName}!",
  "@welcomeUser": {
    "description": "Personalized welcome message",
    "placeholders": {
      "userName": {
        "type": "String",
        "example": "John"
      }
    }
  }
}
```

**Usage:**
```dart
Text(l10n.welcomeUser(user.name))
```

### Pluralization
For messages that change based on quantity:

**ARB file:**
```json
{
  "transactionCount": "{count, plural, =0{No transactions} =1{1 transaction} other{{count} transactions}}",
  "@transactionCount": {
    "description": "Number of transactions",
    "placeholders": {
      "count": {
        "type": "int"
      }
    }
  }
}
```

**Usage:**
```dart
Text(l10n.transactionCount(transactions.length))
```

## Financial Formatting

### Currency Formatting
Always use the provided financial formatters for consistent locale-aware display:

```dart
import '../utils/financial_formatters.dart';

// Basic currency formatting
Text(FinancialFormatters.formatCurrency(context, 1234.56))
// Output: $1,234.56 (US) or 1.234,56 € (ES)

// Compact formatting for large amounts
Text(FinancialFormatters.formatCurrency(context, 1234567, compact: true))
// Output: $1.2M

// Using extension method
Text(context.formatMoney(amount))
```

### Percentage Formatting
```dart
// Format as percentage
Text(FinancialFormatters.formatPercentage(0.1256))
// Output: 12.6% (US) or 12,6 % (ES)

// Budget progress
Text(FinancialFormatters.formatBudgetProgress(context, spent, budget))
```

### Date Formatting
```dart
// Transaction dates with relative formatting
Text(FinancialFormatters.formatTransactionDate(context, transaction.date))
// Output: "Today", "Yesterday", or formatted date

// Budget periods
Text(FinancialFormatters.formatBudgetPeriod(DateTime.now()))
// Output: "January 2024" or "enero 2024"
```

### Category Names
```dart
// Always localize category names
Text(FinancialFormatters.formatCategory(context, 'food'))
// Output: "Food" (EN) or "Comida" (ES)
```

## RTL/Text Direction Support

### Using Text Direction Service
```dart
import '../services/text_direction_service.dart';

final textDir = TextDirectionService.instance;

// Check if RTL
if (textDir.isRTL) {
  // RTL-specific logic
}

// Appropriate text alignment
Text(
  'My text',
  textAlign: textDir.getTextAlign(),
)

// Directional padding
Container(
  padding: textDir.getDirectionalPadding(start: 16.0, end: 8.0),
  child: child,
)
```

### Directional Icons
```dart
// Navigation icons that flip in RTL
Icon(textDir.backIcon)      // arrow_back (LTR) or arrow_forward (RTL)
Icon(textDir.forwardIcon)   // arrow_forward (LTR) or arrow_back (RTL)
```

### Directional Layouts
```dart
// Row that respects text direction
textDir.createDirectionalRow(
  children: [
    Icon(Icons.person),
    Text('User Name'),
  ],
)

// Positioned elements
Stack(
  children: [
    background,
    textDir.createDirectionalPositioned(
      start: 16.0,
      top: 16.0,
      child: FloatingActionButton(...),
    ),
  ],
)
```

## Best Practices

### String Management
1. **Never hardcode strings** in UI code
2. **Provide context** in ARB descriptions
3. **Use meaningful keys** that describe content, not UI location
4. **Group related strings** with consistent prefixes
5. **Include examples** for parameterized messages

### Financial Content
1. **Always format currency** through LocalizationService
2. **Consider cultural differences** in financial concepts
3. **Use appropriate precision** for monetary values
4. **Handle zero and negative values** appropriately

### Text Direction
1. **Test with RTL languages** even if not currently supported
2. **Use directional properties** instead of absolute positioning
3. **Avoid hardcoded left/right** in layouts
4. **Consider icon directionality** for navigation elements

### Performance
1. **Cache localization instances** when possible
2. **Avoid rebuilding** localized strings unnecessarily
3. **Use const constructors** where appropriate
4. **Minimize ARB file size** by avoiding redundant descriptions

## Testing Guidelines

### Locale Testing
```dart
// Test with different locales
testWidgets('shows localized content', (tester) async {
  await tester.pumpWidget(
    MaterialApp(
      locale: Locale('es'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: MyWidget(),
    ),
  );
  
  expect(find.text('Hola Mundo'), findsOneWidget);
});
```

### Currency Testing
```dart
void testCurrencyFormatting() {
  LocalizationService.instance.setLocale(Locale('es', 'ES'));
  
  final formatted = FinancialFormatters.formatCurrency(context, 1234.56);
  expect(formatted, contains('€'));
}
```

### RTL Testing
Enable RTL testing in your IDE or device:
1. **Android**: Settings > System > Languages > Add Arabic/Hebrew
2. **iOS**: Settings > General > Language & Region > Add Arabic/Hebrew
3. **Flutter Inspector**: Use text direction overrides

## Common Patterns

### Error Messages
```dart
// Always provide user-friendly, localized error messages
void showError(String message) {
  final l10n = AppLocalizations.of(context);
  
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      action: SnackBarAction(
        label: l10n.dismiss,
        onPressed: () => ScaffoldMessenger.of(context).hideCurrentSnackBar(),
      ),
    ),
  );
}
```

### Form Validation
```dart
String? validateAmount(String? value) {
  final l10n = AppLocalizations.of(context);
  
  if (value == null || value.isEmpty) {
    return l10n.fieldRequired;
  }
  
  final amount = FinancialFormatters.parseCurrencyInput(value);
  if (amount == null) {
    return l10n.invalidAmount;
  }
  
  return null;
}
```

### Conditional UI
```dart
Widget buildBudgetStatus(double spent, double budget) {
  final l10n = AppLocalizations.of(context);
  final status = FinancialFormatters.formatBudgetStatus(context, spent, budget);
  final color = FinancialFormatters.getBudgetStatusColor(context, spent, budget);
  
  return Container(
    padding: EdgeInsets.all(8.0),
    decoration: BoxDecoration(
      color: color.withOpacity(0.1),
      borderRadius: BorderRadius.circular(8.0),
    ),
    child: Text(
      status,
      style: TextStyle(color: color, fontWeight: FontWeight.bold),
    ),
  );
}
```

## Troubleshooting

### Common Issues

**1. "AppLocalizations not found" Error**
- Ensure `flutter gen-l10n` has been run
- Check that ARB files are valid JSON
- Verify l10n.yaml configuration

**2. Missing Translations**
- Check untranslated.json for missing keys
- Ensure all ARB files have the same keys
- Regenerate localizations after adding strings

**3. Currency Not Formatting Correctly**
- Verify locale is set correctly in LocalizationService
- Check currency data in localization_service.dart
- Ensure proper currency symbols for target markets

**4. RTL Layout Issues**
- Use EdgeInsetsDirectional instead of EdgeInsets
- Check icon directionality
- Test with actual RTL languages

### Debug Tools
```dart
// Debug current locale
debugPrint('Current locale: ${Localizations.localeOf(context)}');

// Debug text direction
debugPrint('Text direction: ${Directionality.of(context)}');

// Debug currency formatting
debugPrint('Currency: ${LocalizationService.instance.currencyCode}');
```

## Adding New Languages

### Step 1: Update Configuration
Add new locale to l10n.yaml:
```yaml
locales:
  - en
  - es
  - fr  # New French support
```

### Step 2: Create ARB File
Create `lib/l10n/app_fr.arb` with all required translations.

### Step 3: Update Currency Data
Add currency information to LocalizationService:
```dart
static const Map<String, Map<String, String>> _currencyData = {
  // ... existing currencies
  'fr_FR': {'code': 'EUR', 'symbol': '€', 'name': 'Euro'},
};
```

### Step 4: Test and Validate
- Test all screens with new language
- Verify currency formatting
- Check text overflow and layout
- Validate RTL behavior if applicable

## Maintenance

### Regular Tasks
1. **Review ARB files** for consistency
2. **Update translations** when adding features
3. **Test currency formatting** with exchange rate changes
4. **Validate RTL support** with new UI components
5. **Monitor performance** of localization loading

### Version Control
- Always commit ARB files and generated localizations together
- Use meaningful commit messages for translation updates
- Consider translation review process for sensitive content

## Resources

### Internal Files
- `lib/services/localization_service.dart` - Core localization utilities
- `lib/utils/financial_formatters.dart` - Financial formatting helpers
- `lib/services/text_direction_service.dart` - RTL/LTR support utilities

### External Resources
- [Flutter Internationalization Guide](https://flutter.dev/docs/development/accessibility-and-localization/internationalization)
- [ARB File Format](https://github.com/googlei18n/app-resource-bundle)
- [Unicode CLDR](http://cldr.unicode.org/) - Currency and date formatting standards

---

**Remember**: Internationalization is not just about translating text—it's about creating an inclusive user experience that respects cultural differences in financial concepts, number formats, and visual layout preferences.